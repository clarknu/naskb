"""WebDAV file system adapter for NASKB.

基于 webdav4 库（~50KB），适配到 FileSystemAdapter 统一接口。
webdav4 是 Python 生态中最成熟的 WebDAV 客户端库。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from .base import FileSystemAdapter, FileStat

# ── webdav4 是轻量库（~50KB），直接顶层引入 ──
try:
    from webdav4.client import Client as _WebDAVClient
except ImportError:
    _WebDAVClient = None  # type: ignore[assignment]


class WebDAVAdapter(FileSystemAdapter):
    """WebDAV 文件系统适配器，薄封装 webdav4.Client。"""

    def __init__(self, root_url: str, auth: dict[str, str] | None = None):
        if _WebDAVClient is None:
            raise ImportError(
                "WebDAV support requires 'webdav4'. Install: pip install webdav4"
            )
        auth = auth or {}
        self._root_url: str = root_url
        self._username: str = auth.get("username", "") or auth.get("user", "")
        self._password: str = auth.get("password", "") or auth.get("pass", "")

        parsed = urlparse(root_url)
        self._base_url: str = f"{parsed.scheme}://{parsed.netloc}"
        self._root_path: str = parsed.path.rstrip("/") or "/"

        if self._username and self._password:
            self._client = _WebDAVClient(
                self._base_url, auth=(self._username, self._password)
            )
        else:
            self._client = _WebDAVClient(self._base_url)

    @property
    def root(self) -> str:
        return self._root_url

    # ── list_files ──

    def list_files(self, root: str, recursive: bool = True) -> list[FileStat]:
        results: list[FileStat] = []
        try:
            remote_path = self._to_remote_path(root)
            # detail=True 返回 list[dict]
            raw: list[dict[str, Any]] = self._client.ls(remote_path, detail=True)  # type: ignore[assignment]
            for entry in raw:
                name: str = str(entry.get("name", ""))
                entry_type: str = str(entry.get("type", ""))
                if entry_type == "directory":
                    if recursive:
                        sub_path = os.path.join(root, name).replace("\\", "/")
                        results.extend(self.list_files(sub_path, recursive=True))
                    continue
                results.append(FileStat(
                    path=os.path.join(root, name).replace("\\", "/"),
                    name=name,
                    size_bytes=int(entry.get("size", 0)),
                    mtime=float(entry.get("modified", 0)),
                    is_dir=False,
                    ext=Path(name).suffix.lower() or "",
                ))
        except Exception as e:
            print(f"[naskb] WebDAV list error for {root}: {e}")
        return results

    # ── read ──

    def read_text(self, path: str) -> str:
        remote_path = self._to_remote_path(path)
        with self._client.open(remote_path, "rb") as f:  # type: ignore[union-attr]
            return f.read().decode("utf-8", errors="replace")

    def read_bytes(self, path: str, max_bytes: int = 65536) -> bytes:
        remote_path = self._to_remote_path(path)
        with self._client.open(remote_path, "rb") as f:  # type: ignore[union-attr]
            return f.read(max_bytes)  # type: ignore[return-value]

    # ── stat ──

    def stat(self, path: str) -> Optional[FileStat]:
        try:
            remote_path = self._to_remote_path(path)
            info: dict[str, Any] = self._client.info(remote_path)  # type: ignore[assignment,union-attr]
            fname = Path(path).name
            return FileStat(
                path=path,
                name=fname,
                size_bytes=int(info.get("size", 0)),
                mtime=float(info.get("modified", 0)),
                is_dir=info.get("type", "") == "directory",
                ext=Path(fname).suffix.lower() or "",
            )
        except Exception:
            return None

    def exists(self, path: str) -> bool:
        return self.stat(path) is not None

    def is_dir(self, path: str) -> bool:
        st = self.stat(path)
        return st.is_dir if st else False

    # ── helpers ──

    def _to_remote_path(self, local_path: str) -> str:
        if local_path.startswith(self._root_url):
            relative = local_path[len(self._root_url):]
        elif local_path.startswith(self._root_path):
            relative = local_path[len(self._root_path):]
        else:
            relative = local_path
        return (self._root_path + "/" + relative.lstrip("/")).rstrip("/") or "/"

    def close(self) -> None:
        try:
            self._client.close()  # type: ignore[union-attr]
        except Exception:
            pass
