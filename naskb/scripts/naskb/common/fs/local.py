"""Local file system adapter for NASKB."""
import os
from pathlib import Path
from typing import Optional

from .base import FileSystemAdapter, FileStat


class LocalAdapter(FileSystemAdapter):
    """Local file system adapter (file://)."""

    def __init__(self, root_path: str):
        self._root = str(Path(root_path).resolve())

    @property
    def root(self) -> str:
        return self._root

    def _resolve(self, path: str) -> Path:
        """绝对路径直接用；相对路径以 self._root 为基准。"""
        p = Path(path)
        if p.is_absolute():
            return p
        return Path(self._root).joinpath(path)

    def list_files(self, root: str, recursive: bool = True) -> list[FileStat]:
        """List all files under root (root 相对路径时以适配器根为基准)."""
        results: list[FileStat] = []
        root_p = self._resolve(root)

        if not root_p.exists():
            return results

        iterator = root_p.rglob("*") if recursive else root_p.glob("*")

        for entry in iterator:
            try:
                if entry.is_symlink():
                    continue  # Skip symlinks to avoid loops
            except OSError:
                continue

            try:
                is_dir = entry.is_dir()
            except OSError:
                continue

            if is_dir:
                continue  # Skip directories, only return files

            try:
                st = entry.stat()
            except OSError:
                continue

            if not self._is_accessible(entry):
                continue

            results.append(FileStat(
                path=str(entry.resolve()),
                name=entry.name,
                size_bytes=st.st_size,
                mtime=st.st_mtime,
                is_dir=False,
                ext=entry.suffix.lower() or "",
                ctime=_ctime_of(st),
            ))

        return results

    def read_text(self, path: str) -> str:
        """Read a text file as UTF-8."""
        return self._resolve(path).read_text(encoding="utf-8", errors="replace")

    def stat(self, path: str) -> Optional[FileStat]:
        """Get file metadata."""
        p = self._resolve(path)
        if not p.exists():
            return None
        try:
            st = p.stat()
            return FileStat(
                path=str(p.resolve()),
                name=p.name,
                size_bytes=st.st_size,
                mtime=st.st_mtime,
                is_dir=p.is_dir(),
                ext=p.suffix.lower() or "",
                ctime=_ctime_of(st),
            )
        except OSError:
            return None

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def is_dir(self, path: str) -> bool:
        return self._resolve(path).is_dir()

    def read_bytes(self, path: str, max_bytes: int = 65536) -> bytes:
        """Read raw bytes."""
        with open(self._resolve(path), "rb") as f:
            return f.read(max_bytes)

    def read_chunks(self, path: str, chunk_size: int = 1 << 20):
        """Yield raw bytes in chunks."""
        with open(self._resolve(path), "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def read_ranges(self, path: str, ranges: list[tuple[int, int]]) -> bytes:
        """按偏移读取多段并拼接（采样 hash 用）。"""
        out = bytearray()
        with open(self._resolve(path), "rb") as f:
            for start, length in ranges:
                f.seek(start)
                data = f.read(length)
                if len(data) != length:
                    raise OSError(
                        f"short read at {start}+{length} (got {len(data)})")
                out.extend(data)
        return bytes(out)

    def open_stream(self, path: str, start: int | None = None,
                    end: int | None = None, chunk_size: int = 1 << 20):
        """seek + 分块流式读取（下载代理 Range 用，REQ-R7-07）。"""
        f = open(self._resolve(path), "rb")
        try:
            size = os.fstat(f.fileno()).st_size
            if start is None:
                start = 0
            if end is None or end >= size:
                end = size - 1
            if start > end or start >= size:
                raise OSError("range not satisfiable")
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            f.close()

    def write_bytes(self, path: str, data: bytes) -> None:
        """Write raw bytes, creating parent dirs if needed."""
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def move(self, src: str, dst: str) -> None:
        """Move/rename a file (same filesystem)."""
        dst_p = self._resolve(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        self._resolve(src).replace(dst_p)

    def mkdir(self, path: str) -> None:
        """Create directory recursively."""
        self._resolve(path).mkdir(parents=True, exist_ok=True)

    def delete(self, path: str) -> None:
        """Delete a file."""
        self._resolve(path).unlink(missing_ok=True)

    def resolve_path(self, path: str) -> str:
        """相对路径以根为基准解析为绝对路径。"""
        return str(self._resolve(path))

    @staticmethod
    def _is_accessible(p: Path) -> bool:
        """Check if file is readable."""
        try:
            return os.access(str(p), os.R_OK)
        except OSError:
            return False


def _ctime_of(st) -> float:
    """创建时间：优先 st_birthtime（Python 3.12+ 跨平台），退回 st_ctime。

    注意：POSIX 上 st_ctime 是 inode 变更时间（非创建时间）——LocalAdapter
    主要服务 Windows 本机（NTFS 上 st_ctime 即创建时间）；Linux 本地场景
    由 st_birthtime 覆盖，两者都不可用时返回 0.0（=缺失，走 hash 复核）。
    """
    birth = getattr(st, "st_birthtime", None)
    if birth:
        return float(birth)
    return float(getattr(st, "st_ctime", 0.0))
