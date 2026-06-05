"""异步任务队列与状态追踪。

支持后台索引任务的排队执行、进度查询和状态管理。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    INDEX_FILE = "index_file"
    INDEX_FOLDER = "index_folder"
    INDEX_FULL = "index_full"
    INDEX_INCREMENTAL = "index_incremental"
    GENERATE_DESC = "generate_desc"
    UPDATE_DESC = "update_desc"
    REMOVE_INDEX = "remove_index"
    WATCHER_SCAN = "watcher_scan"


@dataclass
class Job:
    """单个后台任务。"""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_type: JobType = JobType.INDEX_FILE
    status: JobStatus = JobStatus.PENDING
    source_id: str = ""
    target_path: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    # 时间戳
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0

    # 结果
    result: Any = None
    error: str = ""
    progress: float = 0.0        # 0.0 ~ 1.0
    progress_message: str = ""

    # 回调
    _future: Optional[asyncio.Future] = field(default=None, repr=False)

    @property
    def elapsed(self) -> float:
        """已用时间（秒）。"""
        if self.started_at:
            end = self.completed_at or time.time()
            return end - self.started_at
        return 0.0

    @property
    def eta_seconds(self) -> float:
        """预估剩余时间（秒）。"""
        if self.progress > 0 and self.elapsed > 0:
            return (self.elapsed / self.progress) * (1.0 - self.progress)
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "source_id": self.source_id,
            "target_path": self.target_path,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed": round(self.elapsed, 2),
            "eta_seconds": round(self.eta_seconds, 2),
            "progress": round(self.progress, 4),
            "progress_message": self.progress_message,
            "error": self.error,
        }


class JobQueue:
    """异步任务队列管理器。

    特性：
    - 并发 Worker 控制
    - 任务去重（同类型 + 同路径的重复提交合并）
    - 进度追踪
    - 任务历史缓存（最近 N 条）
    """

    def __init__(self, max_workers: int = 4, history_size: int = 200):
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._max_workers = max_workers
        self._history_size = history_size
        self._jobs: dict[str, Job] = {}          # 所有任务
        self._history: list[Job] = []            # 已完成任务历史
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._handler: Optional[Callable] = None

    # ── 生命周期 ──

    async def start(self, handler: Callable[[Job], Any]) -> None:
        """启动 Worker 协程。

        Args:
            handler: async callable(job) -> result，处理任务的实际函数
        """
        if self._running:
            return
        self._running = True
        self._handler = handler

        for i in range(self._max_workers):
            worker = asyncio.create_task(self._worker(i), name=f"naskb-worker-{i}")
            self._workers.append(worker)

    async def stop(self, graceful: bool = True) -> None:
        """停止所有 Worker。

        Args:
            graceful: True 时等待当前任务完成；False 时立即取消。
        """
        self._running = False

        # 标记所有 pending 任务为 cancelled
        while not self._queue.empty():
            try:
                job = self._queue.get_nowait()
                if job.status == JobStatus.PENDING:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = time.time()
                    self._queue.task_done()
            except asyncio.QueueEmpty:
                break

        if not graceful:
            for w in self._workers:
                w.cancel()
        else:
            # 等待队列清空
            await self._queue.join()
            for w in self._workers:
                w.cancel()
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()

    # ── 任务提交 ──

    async def submit(self, job_type: JobType, source_id: str = "",
                     target_path: str = "", params: dict | None = None,
                     deduplicate: bool = True) -> Job:
        """提交一个任务。

        Args:
            job_type: 任务类型
            source_id: 知识来源 ID
            target_path: 目标文件/文件夹路径
            params: 额外参数
            deduplicate: 是否对同类型+同来源+同路径的任务去重

        Returns:
            Job 对象
        """
        # 去重检查
        if deduplicate:
            for existing in self._jobs.values():
                if (existing.status in (JobStatus.PENDING, JobStatus.RUNNING) and
                        existing.job_type == job_type and
                        existing.source_id == source_id and
                        existing.target_path == target_path):
                    return existing  # 返回已有任务

        job = Job(
            job_type=job_type,
            source_id=source_id,
            target_path=target_path,
            params=params or {},
        )
        self._jobs[job.job_id] = job

        await self._queue.put(job)
        return job

    async def submit_many(self, jobs_spec: list[tuple[JobType, str, str, dict | None]]) -> list[Job]:
        """批量提交任务。"""
        results = []
        for jt, sid, tp, params in jobs_spec:
            job = await self.submit(jt, sid, tp, params)
            results.append(job)
        return results

    # ── 状态查询 ──

    def get_job(self, job_id: str) -> Optional[Job]:
        """获取任务详情。"""
        return self._jobs.get(job_id)

    def list_jobs(self, status_filter: str = "all",
                  job_type: Optional[JobType] = None) -> list[Job]:
        """列出任务。

        Args:
            status_filter: "all" | "active" | "completed" | "failed" | "pending"
            job_type: 按类型过滤
        """
        result = list(self._jobs.values())

        if status_filter == "active":
            result = [j for j in result
                      if j.status in (JobStatus.PENDING, JobStatus.RUNNING)]
        elif status_filter == "completed":
            result = [j for j in result
                      if j.status == JobStatus.COMPLETED]
        elif status_filter == "failed":
            result = [j for j in result
                      if j.status == JobStatus.FAILED]
        elif status_filter == "pending":
            result = [j for j in result
                      if j.status == JobStatus.PENDING]

        if job_type:
            result = [j for j in result if j.job_type == job_type]

        # 按创建时间倒序
        result.sort(key=lambda j: j.created_at, reverse=True)
        return result

    def get_stats(self) -> dict[str, int]:
        """获取队列统计。"""
        stats = {"pending": 0, "running": 0, "completed": 0,
                 "failed": 0, "cancelled": 0}
        for job in self._jobs.values():
            key = job.status.value
            if key in stats:
                stats[key] += 1
        stats["total"] = len(self._jobs)
        stats["queue_size"] = self._queue.qsize()
        return stats

    # ── 内部控制 ──

    def pause(self) -> None:
        """暂停新任务调度（已在运行的任务继续）。"""
        self._running = False

    def resume(self) -> None:
        """恢复任务调度。"""
        self._running = True

    # ── Worker ──

    async def _worker(self, worker_id: int) -> None:
        """Worker 协程，循环从队列取出任务并执行。"""
        while self._running:
            try:
                # 使用超时避免永久阻塞
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if job.status == JobStatus.CANCELLED:
                self._queue.task_done()
                continue

            # 标记为运行中
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            job.progress = 0.0
            job.progress_message = "Starting..."

            try:
                if self._handler:
                    result = await self._handler(job)
                    job.result = result
                    job.status = JobStatus.COMPLETED
                    job.progress = 1.0
                    job.progress_message = "Completed."
                else:
                    job.status = JobStatus.FAILED
                    job.error = "No handler registered"
            except asyncio.CancelledError:
                job.status = JobStatus.CANCELLED
                job.error = "Cancelled by system"
                self._queue.task_done()
                raise
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = f"{type(e).__name__}: {e}"
                job.progress_message = f"Failed: {e}"

            job.completed_at = time.time()
            self._queue.task_done()

            # 记录到历史
            self._history.append(job)
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]
