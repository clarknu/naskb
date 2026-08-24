"""认证策略：单管理员 Bearer —— 全部端点需身份（DD-009 匿名移除）。

2026-08-24 拍板（DD-009）：移除匿名只读白名单。例外（匿名放行）仅：
  /、静态资源（非 /api 前缀）、/api/config/public、/api/docs、/api/openapi.json、
  /api/files/{rid}/download（MCP 直链契约——安全边界=外围网关 IP 约束，见 release/policy.md §四b）。
未配置 tokens = 本机开放模式（enabled=False 时全部放行，仅适合 local）。
"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Request

_ANON_EXACT = {"/api/config/public", "/api/docs", "/api/openapi.json"}


class AuthPolicy:
    """认证判定器。app.state.auth 持有。"""

    def __init__(self, tokens: list[str], anonymous_read: bool = False):
        self.tokens = [t for t in (tokens or []) if t]
        # ⚠️ 保留参数仅为兼容旧 fixture（getattr(cfg, "anonymous_read")），
        # 认证逻辑不再使用匿名通道（DD-009）——恒为 False。
        self.anonymous_read = False

    @property
    def enabled(self) -> bool:
        return bool(self.tokens)

    @classmethod
    def from_config(cls, config) -> "AuthPolicy":
        tokens = list(getattr(config, "server_tokens", []) or [])
        # anonymous_read 配置键已废弃（config.py 保留兼容属性，默认 False），不再读取
        return cls(tokens, False)

    def check(self, request: Request) -> bool:
        """是否放行该请求（全部端点需身份，仅引导/直链例外）。"""
        if not self.enabled:
            return True
        supplied = self._bearer(request)
        if supplied and secrets.compare_digest(supplied, self.tokens[0]):
            return True
        path = request.url.path
        if path in _ANON_EXACT:
            return True                      # 启动引导 / OpenAPI 文档
        if not path.startswith("/api"):
            return True                      # 静态资源（前端 UI/脚本/样式）
        if path.startswith("/api/files/") and path.endswith("/download"):
            return True                      # 直链契约（网关 IP 约束为边界，DD-009）
        return False

    @staticmethod
    def _bearer(request: Request) -> Optional[str]:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None
