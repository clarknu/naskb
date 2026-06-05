"""文件系统监控器。

基于 watchdog 库实时监控知识库来源目录的文件变更，
将变更事件转化为索引任务推送到 JobQueue。

watchdog 是可选依赖。如果未安装，FileWatcher 将优雅降级。
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Optional

from .job_queue import JobQueue, JobType

# ── 可选依赖 watchdog ──
_watchdog_available = False
_Observer = None
_T_EventHandler = None

try:
    from watchdog.observers import Observer as _Observer
    from watchdog.events import FileSystemEventHandler as _T_EventHandler
    _watchdog_available = True
except ImportError:
    pass


if _watchdog_available:

    class _DebouncedHandler(_T_EventHandler):
        """带去重的文件事件处理器。

        同一文件在 debounce_window 内的多次事件合并为一次。
        .kbdes/ 目录内的事件被忽略（避免索引循环）。
        """

        def __init__(self, callback, debounce_window: float = 0.5,
                     exclude_patterns: list[str] | None = None):
            super().__init__()
            self._callback = callback
            self._debounce_window = debounce_window
            self._pending: dict[str, float] = {}
            self._last_emit: dict[str, float] = {}
            self._exclude_patterns = exclude_patterns or [
                ".kbdes", ".git", "__pycache__"
            ]

        def _should_ignore(self, path: str) -> bool:
            """检查路径是否应被忽略。"""
            normalized = path.replace("\\", "/")
            for pattern in self._exclude_patterns:
                seg = f"/{pattern}/"
                if seg in normalized:
                    return True
                if normalized.endswith(f"/{pattern}"):
                    return True
                if f"/{pattern}" in normalized:
                    return True
            return False

        def on_created(self, event):
            self._handle(event, "created")

        def on_modified(self, event):
            self._handle(event, "modified")

        def on_deleted(self, event):
            self._handle(event, "deleted")

        def on_moved(self, event):
            self._handle(event, "moved")

        def _handle(self, event, event_type: str):
            if event.is_directory:
                return
            path = event.src_path
            if self._should_ignore(path):
                return

            now = time.time()
            if path in self._pending:
                self._pending[path] = now
                return

            self._pending[path] = now
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                return

            loop.call_later(
                self._debounce_window,
                lambda p=path, et=event_type: self._emit(p, et)
            )

        def _emit(self, path: str, event_type: str):
            now = time.time()
            self._pending.pop(path, None)
            last_emit = self._last_emit.get(path, 0)
            if now - last_emit < self._debounce_window:
                return
            self._last_emit[path] = now
            try:
                self._callback(path, event_type)
            except Exception as e:
                print(f"[naskb] Watcher callback error for {path}: {e}")

else:
    # Stub class when watchdog is not installed
    class _DebouncedHandler:
        pass


class FileWatcher:
    """文件系统监控管理器。

    为每个知识来源目录创建独立的 Observer，
    将变更事件推送到 JobQueue 进行异步索引。

    如果 watchdog 未安装，所有操作将优雅地无操作。
    """

    def __init__(self, job_queue: JobQueue, debounce_window: float = 1.0):
        self._job_queue = job_queue
        self._debounce_window = debounce_window
        self._observer = None
        self._handler = None
        self._watched_sources: dict[str, dict] = {}
        self._running = False

    @property
    def is_available(self) -> bool:
        """检查 watchdog 是否可用。"""
        return _watchdog_available

    @property
    def is_running(self) -> bool:
        return self._running

    def get_watched_sources(self) -> list[dict]:
        """返回当前监控的来源列表。"""
        return [
            {"source_id": sid, "root": info["root"],
             "watching_since": info.get("since", 0)}
            for sid, info in self._watched_sources.items()
        ]

    async def start(self, sources: list[dict]) -> None:
        """启动文件监控。

        Args:
            sources: [{"id": "...", "root_url": "..."}, ...]
        """
        if not _watchdog_available:
            print("[naskb] watchdog not installed. File watching disabled.")
            print("[naskb] Install with: pip install watchdog")
            return

        if self._running:
            return

        self._observer = _Observer()
        self._handler = _DebouncedHandler(
            callback=self._on_file_event,
            debounce_window=self._debounce_window,
        )

        for src in sources:
            root = src.get("root_url", "")
            if not root or not os.path.isdir(root):
                continue
            self._observer.schedule(self._handler, root, recursive=True)
            self._watched_sources[src["id"]] = {
                "root": root, "since": time.time()
            }
            print(f"[naskb] Watching: [{src['id']}] {root}")

        if self._watched_sources:
            self._observer.start()
            self._running = True
            print(f"[naskb] File watcher started for "
                  f"{len(self._watched_sources)} source(s).")
        else:
            print("[naskb] No valid directories to watch.")

    async def stop(self) -> None:
        """停止文件监控。"""
        if not self._running:
            return
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._handler = None
        self._watched_sources.clear()
        self._running = False
        print("[naskb] File watcher stopped.")

    async def restart(self, sources: list[dict]) -> None:
        """重启文件监控（先停后启）。"""
        await self.stop()
        await self.start(sources)

    def _on_file_event(self, path: str, event_type: str):
        """文件变更回调。"""
        source_id = self._find_source_for_path(path)
        if not source_id:
            return

        if event_type in ("created", "modified"):
            ext = Path(path).suffix.lower()
            from ..common.scanner import Scanner
            if Scanner.is_text_file(ext):
                job_type = JobType.INDEX_FILE
            else:
                from .desc_manager import DescManager
                desc_path = DescManager.get_desc_path(path)
                if os.path.exists(desc_path):
                    kbdesc = DescManager.read(desc_path)
                    if kbdesc and kbdesc.is_stale:
                        job_type = JobType.UPDATE_DESC
                    else:
                        job_type = JobType.INDEX_FILE
                else:
                    job_type = JobType.GENERATE_DESC
        elif event_type in ("deleted",):
            job_type = JobType.REMOVE_INDEX
        elif event_type in ("moved",):
            job_type = JobType.INDEX_FILE
        else:
            return

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    self._job_queue.submit(
                        job_type=job_type, source_id=source_id,
                        target_path=path,
                    )
                )
        except Exception:
            pass

    def _find_source_for_path(self, path: str) -> Optional[str]:
        """根据文件路径找到对应的来源 ID。"""
        path_norm = os.path.normpath(path)
        for source_id, info in self._watched_sources.items():
            root_norm = os.path.normpath(info["root"])
            if path_norm.startswith(root_norm):
                return source_id
        return None
