"""来源周期扫描调度器（REQ-R7-12）：进程内轻量循环，无新中间件。

每 tick 检查启用了 scan_auto 的来源：距 last_scan_at 超过 interval
即提交一次 scan job（JobManager 单并发执行，天然串行化）。
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Callable, Optional


class ScanScheduler:
    """daemon 线程 + 停止事件；start() 后台运行，stop() 收敛。"""

    def __init__(self, registry, jobs, scan_fn: Callable,
                 tick_seconds: int = 30):
        self._registry = registry
        self._jobs = jobs          # JobManager
        self._scan_fn = scan_fn    # scan_fn(source) -> dict
        self._tick = tick_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="naskb-scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop.wait(self._tick):
            try:
                self._tick_once()
            except Exception:
                pass        # 调度循环永不因单次异常退出

    def _tick_once(self) -> None:
        now = datetime.now(timezone.utc)
        # JobManager 并发为 1：任一扫描任务尚在队/执行中则本轮不再入队
        busy = any(j.get("kind") == "scan" and j.get("status") in
                   ("pending", "running") for j in self._jobs.list())
        if busy:
            return
        for src in self._registry.list(include_disabled=False):
            if not src.scan_auto:
                continue
            interval = max(5, int(src.scan_interval_min or 60)) * 60
            last = _parse_iso(src.last_scan_at)
            if last is not None and (now - last).total_seconds() < interval:
                continue
            self._jobs.submit("scan", _wrap_scan(self._scan_fn), src)
            break       # 单并发：每 tick 至多排一个


def _wrap_scan(scan_fn: Callable):
    def run(job, source) -> dict:
        job["message"] = f"scan:{source.alias}"
        job["progress"] = 0.1
        result = scan_fn(source)
        job["progress"] = 1.0
        return result
    return run


def _parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None
