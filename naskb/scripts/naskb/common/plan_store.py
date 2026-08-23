"""整理方案持久化 — 工作区 plans/<plan_id>.json。

plan_id 是 plan → apply 之间的唯一凭证：apply 凭 plan_id 取回方案与
快照指纹（P0-3 复检），同时是人工确认 / 审计 / MCP 工具 plan_id 参数
的载体。原子写（tmp + os.replace），中断不留半文件。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from typing import Optional

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().astimezone().isoformat(timespec="seconds")


def plans_dir(work_path: str) -> str:
    d = os.path.join(work_path, "plans")
    os.makedirs(d, exist_ok=True)
    return d


def _plan_path(work_path: str, plan_id: str) -> str:
    if not plan_id or not _SAFE_ID.match(plan_id):
        raise ValueError(f"非法 plan_id: {plan_id!r}")
    return os.path.join(plans_dir(work_path), f"{plan_id}.json")


def save_plan(work_path: str, plan: dict, snapshot: dict, root: str,
              meta: Optional[dict] = None) -> str:
    """持久化方案，返回 plan_id。

    - plan:      重组方案（{plan_name, rationale, new_folders, moves, ...}）
    - snapshot:  复检指纹 {规范化源路径: file_hash}（P0-3 用）
    - root:      整理根目录（apply 越界复校验用）
    """
    plan_id = str(uuid.uuid4())
    record = {
        "plan_id": plan_id,
        "root": root,
        "created_at": _now_iso(),
        "status": "pending",          # pending | applied | expired
        "plan": plan,
        "snapshot": snapshot,
        "applied_at": None,
        "result": None,
        "audit": [],
    }
    if meta:
        record["meta"] = meta
    path = _plan_path(work_path, plan_id)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return plan_id


def load_plan(work_path: str, plan_id: str) -> Optional[dict]:
    """读取方案记录；不存在或损坏返回 None。"""
    try:
        path = _plan_path(work_path, plan_id)
    except ValueError:
        return None
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def list_plans(work_path: str, root: Optional[str] = None,
               status: Optional[str] = None) -> list[dict]:
    """列出方案记录（可按 root 精确匹配 / status 过滤，按创建时间排序）。"""
    out: list[dict] = []
    d = plans_dir(work_path)
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json"):
            continue
        rec = load_plan(work_path, name[:-5])
        if rec is None:
            continue
        if root and os.path.normcase(os.path.normpath(rec.get("root", ""))) != \
                os.path.normcase(os.path.normpath(root)):
            continue
        if status and rec.get("status") != status:
            continue
        out.append(rec)
    return out


def mark_applied(work_path: str, plan_id: str, result: dict,
                 by: str = "") -> Optional[dict]:
    """标记方案已执行（写入 apply 结果与审计），返回更新后的记录。"""
    rec = load_plan(work_path, plan_id)
    if rec is None:
        return None
    rec["status"] = "applied"
    rec["applied_at"] = _now_iso()
    rec["result"] = result
    if by:
        rec["audit"].append({"at": _now_iso(), "action": "apply", "by": by})
    path = _plan_path(work_path, plan_id)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return rec


def _root_hash(root: str) -> str:
    """root 规范化哈希（锁文件名用，长度截 12）。"""
    return hashlib.sha1(
        os.path.normcase(os.path.normpath(root)).encode("utf-8")
    ).hexdigest()[:12]


class RootLock:
    """root 级互斥锁（plans/root-<hash>.lock）。

    O_EXCL 创建、内容记 pid+时间戳；锁 mtime 超 STALE_AFTER 秒视为残留
    （进程崩溃遗留）可接管。防两个调用方同时对同一 root 执行整理。
    work_path 为空时锁不可用（acquire 返回 False，由调用方决定降级）。
    """

    STALE_AFTER = 3600.0

    def __init__(self, work_path: str, root: str):
        self._path = ""
        if work_path and root:
            self._path = os.path.join(plans_dir(work_path),
                                      f"root-{_root_hash(root)}.lock")
        self._held = False

    def acquire(self, timeout: float = 0.0) -> bool:
        """获取锁；timeout 秒内轮询（0 = 不等待）。成功返回 True。"""
        if not self._path:
            return False
        deadline = time.monotonic() + max(timeout, 0.0)
        while True:
            try:
                fd = os.open(self._path,
                             os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w") as f:
                    f.write(f"{os.getpid()} {time.time()}\n")
                self._held = True
                return True
            except FileExistsError:
                if self._is_stale():
                    try:
                        os.unlink(self._path)
                        continue
                    except OSError:
                        pass
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.2)

    def _is_stale(self) -> bool:
        try:
            return time.time() - os.path.getmtime(self._path) > self.STALE_AFTER
        except OSError:
            return False

    def release(self) -> None:
        if self._held and self._path:
            try:
                os.unlink(self._path)
            except OSError:
                pass
            self._held = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
