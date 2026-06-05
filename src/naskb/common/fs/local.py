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

    def list_files(self, root: str, recursive: bool = True) -> list[FileStat]:
        """List all files under root."""
        results: list[FileStat] = []
        root_p = Path(root)

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
            ))

        return results

    def read_text(self, path: str) -> str:
        """Read a text file as UTF-8."""
        return Path(path).read_text(encoding="utf-8", errors="replace")

    def stat(self, path: str) -> Optional[FileStat]:
        """Get file metadata."""
        p = Path(path)
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
            )
        except OSError:
            return None

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def is_dir(self, path: str) -> bool:
        return Path(path).is_dir()

    def read_bytes(self, path: str, max_bytes: int = 65536) -> bytes:
        """Read raw bytes."""
        with open(path, "rb") as f:
            return f.read(max_bytes)

    @staticmethod
    def _is_accessible(p: Path) -> bool:
        """Check if file is readable."""
        try:
            return os.access(str(p), os.R_OK)
        except OSError:
            return False
