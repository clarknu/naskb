"""WebDAV file system adapter for NASKB.

基于 webdav4 库（~50KB），适配到 FileSystemAdapter 统一接口。
webdav4 是 Python 生态中最成熟的 WebDAV 客户端库。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from .base import FileSystemAdapter, FileStat

# ── webdav4 是轻量库（~50KB），直接顶层引入 ──
try:
    from webdav4.client import Client as _WebDAVClient
except ImportError:
    _WebDAVClient = None  # type: ignore[assignment]


def _to_timestamp(v: Any) -> float:
    """webdav4 的 modified/created 是 datetime 对象（带时区），转 epoch 秒。"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if hasattr(v, "timestamp"):  # datetime
        try:
            return float(v.timestamp())
        except (OverflowError, OSError, ValueError):
            return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _norm_path(p: str) -> str:
    """规范化 WebDAV 路径：统一 / 分隔、去掉重复 // 与尾部斜杠。"""
    p = p.replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    if p == "/":
        return "/"
    return p.rstrip("/")


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
        self._verify: bool = auth.get(
            "verify_ssl", auth.get("verify", True)) if "verify_ssl" in auth else auth.get("verify", True)

        parsed = urlparse(root_url)
        self._base_url: str = f"{parsed.scheme}://{parsed.netloc}"
        self._root_path: str = parsed.path.rstrip("/") or "/"

        if self._username and self._password:
            self._client = _WebDAVClient(
                self._base_url, auth=(self._username, self._password),
                verify=self._verify, timeout=60, retry=False)
        else:
            self._client = _WebDAVClient(self._base_url, verify=self._verify,
                                         timeout=60, retry=False)

    @property
    def root(self) -> str:
        return self._root_url

    # ── list_files ──

    def list_files(self, root: str, recursive: bool = True) -> list[FileStat]:
        results: list[FileStat] = []
        try:
            remote_path = self._to_remote_path(root)
            # detail=True 返回 list[dict]；name 是相对请求路径，href 是服务器绝对路径
            raw: list[dict[str, Any]] = self._client.ls(remote_path, detail=True)  # type: ignore[assignment]
            for entry in raw:
                entry_type: str = str(entry.get("type", ""))
                href: str = str(entry.get("href", ""))
                display: str = str(entry.get("display_name") or "")
                # 完整逻辑路径：href 以 / 开头直接用，否则拼 root；
                # href 是 URL 编码（如 %E4%BA%A4），统一解码成可读路径
                if href.startswith("/"):
                    full = _norm_path(unquote(href))
                else:
                    full = _norm_path(os.path.join(root, unquote(href)))
                if entry_type == "directory":
                    if recursive:
                        results.extend(self.list_files(full, recursive=True))
                    continue
                name = display or Path(full).name
                results.append(FileStat(
                    path=full,
                    name=name,
                    size_bytes=int(entry.get("content_length", 0) or 0),
                    mtime=_to_timestamp(entry.get("modified")),
                    is_dir=False,
                    ext=Path(name).suffix.lower() or "",
                    ctime=_to_timestamp(entry.get("created")),
                ))
        except Exception as e:
            print(f"[naskb] WebDAV list error for {root}: {e}")
        return results

    # ── read ──

    def read_text(self, path: str) -> str:
        return self.read_bytes(path).decode("utf-8", errors="replace")

    def read_bytes(self, path: str, max_bytes: int = 65536) -> bytes:
        remote_path = self._to_remote_path(path)
        # 不用 client.open()：其 isdir() 探测对非 ASCII 路径会 KeyError
        # （webdav4 已知问题：PROPFIND 响应缓存键是 URL 编码后的 href）
        resp = self._client._request("GET", remote_path)  # type: ignore[union-attr]
        try:
            return resp.read()[:max_bytes]
        finally:
            resp.close()

    def read_chunks(self, path: str, chunk_size: int = 1 << 20):
        """Yield file content in chunks from the WebDAV server."""
        remote_path = self._to_remote_path(path)
        # 同上：绕开 client.open() 的 isdir 探测（中文路径 KeyError）
        resp = self._client._request("GET", remote_path)  # type: ignore[union-attr]
        try:
            for chunk in resp.iter_bytes(chunk_size):
                yield chunk
        finally:
            resp.close()

    def read_ranges(self, path: str, ranges: list[tuple[int, int]]) -> bytes:
        """按 HTTP Range 逐段读取并拼接（采样 hash 用，每段一个请求）。

        服务器不支持 Range（返回 200 全量）时也能正确截取对应偏移；
        读取不足说明文件已缩短/变化，抛异常由调用方按"内容已变"处理。
        """
        remote_path = self._to_remote_path(path)
        out = bytearray()
        for start, length in ranges:
            end = start + length - 1
            resp = self._client._request(  # type: ignore[union-attr]
                "GET", remote_path,
                headers={"Range": f"bytes={start}-{end}"})
            try:
                body = resp.read()
            finally:
                resp.close()
            if resp.status_code in (200, 206):
                data = body[start:] if resp.status_code == 200 else body
                if len(data) != length:
                    raise OSError(
                        f"short range read at {start}+{length} (got {len(data)})")
                out.extend(data)
            else:
                raise OSError(f"Range request failed: HTTP {resp.status_code}")
        return bytes(out)

    def write_bytes(self, path: str, data: bytes) -> None:
        """Write raw bytes to the WebDAV server."""
        import io

        remote_path = self._to_remote_path(path)
        self._ensure_parent_dir(remote_path)
        self._client.upload_fileobj(  # type: ignore[union-attr]
            io.BytesIO(data), remote_path, overwrite=True
        )

    def move(self, src: str, dst: str) -> None:
        """Move/rename on the WebDAV server (server-side MOVE)."""
        remote_src = self._to_remote_path(src)
        remote_dst = self._to_remote_path(dst)
        self._ensure_parent_dir(remote_dst)
        self._client.move(remote_src, remote_dst, overwrite=True)  # type: ignore[union-attr]

    def mkdir(self, path: str) -> None:
        """Create directory (recursively)."""
        remote_path = self._to_remote_path(path).rstrip("/")
        if not remote_path:
            return
        # Walk from root down, creating each missing level
        parts = remote_path.split("/")
        acc = ""
        for part in parts:
            if not part:
                continue
            acc = acc + "/" + part
            if not self.exists(acc):
                try:
                    self._client.mkdir(acc)  # type: ignore[union-attr]
                except Exception:
                    # mkdir 幂等：并发/误判下目录已存在不算错误
                    if not self.exists(acc):
                        raise

    def delete(self, path: str) -> None:
        """Delete a file on the WebDAV server."""
        remote_path = self._to_remote_path(path)
        if self._client.exists(remote_path):  # type: ignore[union-attr]
            self._client.remove(remote_path)  # type: ignore[union-attr]

    def _ensure_parent_dir(self, remote_path: str) -> None:
        """Create parent directories of a remote path if missing."""
        parent = remote_path.rstrip("/").rsplit("/", 1)[0] if "/" in remote_path else ""
        if parent:
            self.mkdir(parent)

    # ── stat ──

    def stat(self, path: str) -> Optional[FileStat]:
        try:
            remote_path = self._to_remote_path(path)
            info: dict[str, Any] = self._client.info(remote_path)  # type: ignore[assignment,union-attr]
            href: str = str(info.get("href", ""))
            fname = Path(path).name
            return FileStat(
                path=_norm_path(unquote(href)) if href.startswith("/") else path,
                name=fname,
                size_bytes=int(info.get("content_length", 0) or 0),
                mtime=_to_timestamp(info.get("modified")),
                is_dir=info.get("type", "") == "directory",
                ext=Path(fname).suffix.lower() or "",
                ctime=_to_timestamp(info.get("created")),
            )
        except Exception:
            return None

    def exists(self, path: str) -> bool:
        """HEAD 探测存在性（无响应体，绕开 PROPFIND multistatus 解析挂起）。

        部分 NAS 对目录的 HEAD 返回 404（不支持）——404 或请求失败时
        回退 PROPFIND stat 复核（Client 已带 timeout=60 + retry=False）。
        """
        remote_path = self._to_remote_path(path)
        try:
            resp = self._client._request("HEAD", remote_path)  # type: ignore[union-attr]
            try:
                if resp.status_code < 400:
                    return True
                if resp.status_code == 404:
                    return False
            finally:
                resp.close()
        except Exception:
            pass
        st = self.stat(path)
        return st is not None

    def is_dir(self, path: str) -> bool:
        st = self.stat(path)
        return st.is_dir if st else False

    # ── helpers ──

    def _to_remote_path(self, local_path: str) -> str:
        """把（可能 URL 编码的）路径映射为服务器绝对路径，返回解码后的可读形式。

        前缀匹配前先 unquote：root_url/root_path 可能带编码（%E4%BA%A4），
        调用方传入的路径可能已解码（交易记录），统一按解码后文本比较。
        """
        lp = unquote(local_path)
        root_url_u = unquote(self._root_url)
        root_path_u = unquote(self._root_path or "/")
        candidate = None
        if lp.startswith(root_url_u):
            candidate = root_url_u
        elif lp.startswith(root_path_u):
            candidate = root_path_u

        if candidate is not None:
            rest = lp[len(candidate):]
            # 剩余部分以 '/' 开头（或为空）才算真正命中前缀
            if rest == "" or rest.startswith("/"):
                relative = rest
            else:
                relative = lp
        else:
            relative = lp
        rel = relative.lstrip("/")
        if not rel:
            return unquote(self._root_path or "/")
        root = unquote(self._root_path or "/").rstrip("/") or "/"
        if root == "/":
            return "/" + rel
        return root + "/" + rel

    def resolve_path(self, path: str) -> str:
        """WebDAV 规范路径（服务器绝对路径形式）。"""
        return self._to_remote_path(path)

    def close(self) -> None:
        try:
            self._client.close()  # type: ignore[union-attr]
        except Exception:
            pass
