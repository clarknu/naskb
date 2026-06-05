"""Abstract file system adapter for NASKB.

Provides a factory to create file system adapters for different backends.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


@dataclass
class FileStat:
    """File metadata."""
    path: str
    name: str
    size_bytes: int = 0
    mtime: float = 0.0
    is_dir: bool = False
    ext: str = ""


class FileSystemAdapter(ABC):
    """Abstract base for file system adapters."""

    @abstractmethod
    def list_files(self, root: str, recursive: bool = True) -> list[FileStat]:
        """List all files under root. Returns flat list."""

    @abstractmethod
    def read_text(self, path: str) -> str:
        """Read a text file. Returns content as string."""

    @abstractmethod
    def stat(self, path: str) -> Optional[FileStat]:
        """Get file metadata. Returns None if file doesn't exist."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if path exists."""

    @abstractmethod
    def is_dir(self, path: str) -> bool:
        """Check if path is a directory."""

    def read_bytes(self, path: str, max_bytes: int = 65536) -> bytes:
        """Read raw bytes (first max_bytes)."""
        raise NotImplementedError

    def close(self) -> None:
        """Clean up resources."""
        pass

    @staticmethod
    def create(fs_type: str, root_url: str,
               auth: Optional[dict] = None) -> "FileSystemAdapter":
        """
        Factory method to create the appropriate adapter.

        Args:
            fs_type: "local", "webdav", "sftp", "smb"
            root_url: e.g. "file://D:/Notes", "webdav://192.168.1.1/doc"
            auth: optional dict with username/password/token
        """
        parsed = urlparse(root_url)

        if fs_type == "local":
            from .local import LocalAdapter
            # Extract path from URL or use as-is
            path = parsed.path or root_url
            if path.startswith("/") and not path.startswith("//"):
                # Windows: file:///D:/Notes -> D:/Notes
                if len(path) > 2 and path[2] == ":":
                    path = path[1:]  # Remove leading /
            return LocalAdapter(path)

        elif fs_type in ("webdav", "http", "https"):
            try:
                from .webdav import WebDAVAdapter
                return WebDAVAdapter(root_url, auth or {})
            except ImportError as e:
                raise ImportError(
                    "WebDAV support requires 'webdav4'. Install: pip install webdav4"
                ) from e

        elif fs_type in ("smb", "cifs"):
            # SMB support via fsspec
            try:
                import fsspec
                fs = fsspec.filesystem("smb", **auth or {})
                # Wrap fsspec in adapter interface
                return _FsspecAdapter(fs, root_url)
            except ImportError:
                raise ImportError("SMB support requires 'fsspec[smb]'.")

        else:
            # Generic fsspec fallback
            try:
                import fsspec
                fs = fsspec.filesystem(fs_type, **auth or {})
                return _FsspecAdapter(fs, root_url)
            except ImportError:
                raise ImportError(f"fsspec not available for fs_type={fs_type}")


class _FsspecAdapter(FileSystemAdapter):
    """Generic fsspec-based adapter."""

    def __init__(self, fs, root_url: str):
        self._fs = fs
        self._root = root_url

    def list_files(self, root: str, recursive: bool = True) -> list[FileStat]:
        maxdepth = None if recursive else 1
        results = []
        try:
            for entry in self._fs.find(root, maxdepth=maxdepth, detail=True).values():
                if entry["type"] == "directory":
                    continue
                results.append(FileStat(
                    path=entry["name"],
                    name=entry["name"].split("/")[-1],
                    size_bytes=entry.get("size", 0),
                    mtime=entry.get("mtime", 0),
                    is_dir=False,
                    ext=_get_ext(entry["name"]),
                ))
        except Exception:
            pass
        return results

    def read_text(self, path: str) -> str:
        with self._fs.open(path, "r", encoding="utf-8") as f:
            return f.read()

    def stat(self, path: str) -> Optional[FileStat]:
        try:
            info = self._fs.info(path)
            return FileStat(
                path=path,
                name=path.split("/")[-1],
                size_bytes=info.get("size", 0),
                mtime=info.get("mtime", 0),
                is_dir=info.get("type") == "directory",
                ext=_get_ext(path),
            )
        except Exception:
            return None

    def exists(self, path: str) -> bool:
        return self._fs.exists(path)

    def is_dir(self, path: str) -> bool:
        return self._fs.isdir(path) if hasattr(self._fs, 'isdir') else False

    def close(self) -> None:
        if hasattr(self._fs, 'close'):
            self._fs.close()


def _get_ext(path: str) -> str:
    """Extract lowercase extension from path."""
    name = path.replace("\\", "/").split("/")[-1]
    if "." in name:
        return "." + name.rsplit(".", 1)[-1].lower()
    return ""
