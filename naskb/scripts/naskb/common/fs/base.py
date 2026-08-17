"""Abstract file system adapter for NASKB.

Provides a factory to create file system adapters for different backends.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileStat:
    """File metadata."""
    path: str
    name: str
    size_bytes: int = 0
    mtime: float = 0.0
    is_dir: bool = False
    ext: str = ""
    ctime: float = 0.0    # 创建时间（epoch 秒）；取不到为 0.0 = 缺失（免检必要条件，ADR-20260816-4）


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

    def read_chunks(self, path: str, chunk_size: int = 1 << 20):
        """Yield file content in chunks (for hashing large files)."""
        raise NotImplementedError

    def read_ranges(self, path: str, ranges: list[tuple[int, int]]) -> bytes:
        """Read specific byte ranges [(start, length), ...] and return them
        concatenated in order (采样 hash 用，ADR-20260816-4)。

        读取总量必须等于 sum(length)；不足说明文件正在变化/已缩短，
        实现应抛异常（调用方按"内容已变"处理，不静默降级）。
        """
        raise NotImplementedError

    def resolve_path(self, path: str) -> str:
        """把（可能相对的）路径解析为适配器内的规范绝对路径。

        默认原样返回；Local 等适配器覆写为相对路径接根路径。
        """
        return path

    def write_bytes(self, path: str, data: bytes) -> None:
        """Write raw bytes (overwrite). Creates parent dirs if needed."""
        raise NotImplementedError

    def write_text(self, path: str, text: str) -> None:
        """Write UTF-8 text (overwrite)."""
        self.write_bytes(path, text.encode("utf-8"))

    def move(self, src: str, dst: str) -> None:
        """Move/rename within the same server (WebDAV MOVE semantics)."""
        raise NotImplementedError

    def mkdir(self, path: str) -> None:
        """Create directory (recursively, no error if exists)."""
        raise NotImplementedError

    def delete(self, path: str) -> None:
        """Delete a file."""
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
        if fs_type == "local":
            from .local import LocalAdapter
            # 本地路径不经过 urlparse（Windows 盘符会被误判为 scheme）
            path = root_url
            if path.startswith("file://"):
                path = path[len("file://"):]
                # file:///D:/Notes -> D:/Notes；file:///home/x -> /home/x
                if path.startswith("/") and len(path) > 2 and path[2] == ":":
                    path = path[1:]
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

    def read_chunks(self, path: str, chunk_size: int = 1 << 20):
        with self._fs.open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def write_bytes(self, path: str, data: bytes) -> None:
        with self._fs.open(path, "wb") as f:
            f.write(data)

    def move(self, src: str, dst: str) -> None:
        self._fs.mv(src, dst)

    def mkdir(self, path: str) -> None:
        self._fs.makedirs(path, exist_ok=True)

    def delete(self, path: str) -> None:
        self._fs.rm(path)

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
