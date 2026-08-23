"""认证（REQ-R7-11）：单管理员 Bearer token + 匿名只读开关。

- config [server] tokens = ["..."]：配置了 token 即进入认证模式；
  未配置 → 局域网信任开放模式（与旧 desc serve 行为一致，启动时打印提示）。
- anonymous_read = true 时，只读 GET 端点免 token；写操作与管理端点
  永远需要 token。
"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Request

# 匿名可访问的只读路径前缀（精确匹配或前缀）
_READ_PREFIXES = (
    "/api/search", "/api/ask", "/api/stats", "/api/reload",
    "/api/kb/search", "/api/tree", "/api/folder",
    "/api/files/", "/api/config/public", "/api/jobs/",
)
_ADMIN_EXACT = {"/api/reload"}     # 虽是 GET/POST 混合，但属于管理动作


class AuthPolicy:
    """认证判定器。app.state.auth 持有。"""

    def __init__(self, tokens: list[str], anonymous_read: bool):
        self.tokens = [t for t in (tokens or []) if t]
        self.anonymous_read = bool(anonymous_read)

    @property
    def enabled(self) -> bool:
        return bool(self.tokens)

    @classmethod
    def from_config(cls, config) -> "AuthPolicy":
        tokens = list(getattr(config, "server_tokens", []) or [])
        anon = bool(getattr(config, "anonymous_read", True))
        return cls(tokens, anon)

    def check(self, request: Request) -> bool:
        """是否放行该请求。"""
        if not self.enabled:
            return True
        supplied = self._bearer(request)
        if supplied and secrets.compare_digest(supplied, self.tokens[0]):
            return True
        # 匿名只读通道
        if self.anonymous_read and request.method in ("GET", "HEAD"):
            path = request.url.path
            if path not in _ADMIN_EXACT and any(
                    path == p or path.startswith(p) for p in _READ_PREFIXES):
                return True
            if path.startswith("/") and not path.startswith("/api"):
                return True      # 静态页面资源放行
        return False

    @staticmethod
    def _bearer(request: Request) -> Optional[str]:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None
