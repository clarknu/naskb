"""异步任务队列（长任务 job 模式，MCP/HTTP 共用）。

analyze-tree / sync-vectors / 向量索引构建 / 整理执行等分钟级操作走
job 模式：调用方立即拿到 job_id，轮询 status（或 MCP 进度通知）获取
进度与结果。线程池默认 1 并发执行写类任务（避免并发写同一 .naskb）。
"""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().astimezone().isoformat(timespec="seconds")


class JobManager:
    """内存 job 队列：submit → 线程池执行 → get/list 查询。

    线程安全说明：job 记录由单个 worker 线程写入、任意线程读取
    （简单赋值 + GIL 保证原子性；不做细粒度锁，避免过度设计）。
    """

    def __init__(self, max_workers: int = 1):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="naskb-job")

    def submit(self, kind: str, fn: Callable, *args, **kwargs) -> str:
        """提交任务；fn(job, *args, **kwargs) 在 worker 线程执行。

        fn 的第一个参数是 job 记录（dict），worker 内通过
        `job["progress"] = ...` / `job["message"] = ...` 上报进度。
        返回 job_id。
        """
        job_id = uuid.uuid4().hex[:12]
        job: dict[str, Any] = {
            "id": job_id,
            "kind": kind,
            "status": "pending",          # pending | running | completed | failed
            "created_at": _now_iso(),
            "started_at": None,
            "completed_at": None,
            "progress": 0.0,              # 0.0 ~ 1.0
            "message": "",
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        self._pool.submit(self._run, job, fn, args, kwargs)
        return job_id

    def _run(self, job: dict, fn: Callable, args, kwargs) -> None:
        job["status"] = "running"
        job["started_at"] = _now_iso()
        try:
            result = fn(job, *args, **kwargs)
            job["result"] = result
            job["status"] = "completed"
            job["progress"] = 1.0
        except Exception as e:  # noqa: BLE001 - job 失败不炸线程池
            job["status"] = "failed"
            job["error"] = f"{type(e).__name__}: {e}"
        finally:
            job["completed_at"] = _now_iso()

    def get(self, job_id: str) -> Optional[dict]:
        """查询任务状态；不存在返回 None。"""
        with self._lock:
            j = self._jobs.get(job_id)
            return dict(j) if j else None

    def list(self, status: Optional[str] = None) -> list[dict]:
        """任务列表（按创建时间升序；可按 status 过滤）。"""
        with self._lock:
            jobs = [dict(j) for j in self._jobs.values()]
        jobs.sort(key=lambda j: j["created_at"])
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        return jobs

    def shutdown(self, wait: bool = True) -> None:
        """停止接收新任务并等待进行中的任务（可选）。"""
        self._pool.shutdown(wait=wait)
