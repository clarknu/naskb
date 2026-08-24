"""来源注册表（REQ-R7-03）：系统接入的知识源登记与寻址边界。

一个来源 = 一个知识库根（NAS 视图内目录 / 本地目录 / SMB/NFS/iSCSI 挂载点），
带读写属性 rw/ro（只读知识库：绝不写源端，REQ-R7-05）。

- PG 后端：public.sources 表（[pg] 启用时，权威存储）
- JSON 后端：工作区 sources.json（无 PG 时的轻量实现，接口一致）
- 注册表即安全边界：内容访问层只接受 resource_id/source_id 寻址，
  不接受裸路径；密码字段与 config 同策略明文存储（REQ-R6-02），
  API 输出一律脱敏。
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from .fs.base import FileSystemAdapter
from .pgstore import PgStore, normalize_identity, schema_name_for

PROTOCOLS = ("local", "webdav", "smb")
ACCESS_MODES = ("rw", "ro")

_ALIAS_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


@dataclass
class SourceRecord:
    """一条知识源注册。"""
    alias: str
    protocol: str                      # local | webdav | smb
    host: str = ""                     # webdav: 主机/IP；local/smb 视实现
    port: int = 0
    username: str = ""
    password: str = ""                 # 敏感：API 输出必须脱敏
    root_path: str = ""                # 知识库根（协议内路径或本机绝对路径）
    url: str = ""                      # webdav 完整 URL（含 scheme）
    access_mode: str = "rw"            # rw | ro
    label: str = ""
    scan_auto: bool = False            # 调度器自动周期扫描
    scan_interval_min: int = 60
    deep: bool = False                 # 来源级深度分析（REQ-R5-06：分析时自动建条款级 chunk）
    enabled: bool = True
    verify_ssl: bool = True
    source_id: str = field(
        default_factory=lambda: str(uuid.uuid4()))
    nas_id: str = ""                   # 五要素注册 id（PG 后端维护）
    schema_name: str = ""              # 所属 NAS schema（派生）
    last_scan_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def identity(self) -> tuple[str, str, int, str]:
        """五要素身份（REQ-R4-01）。"""
        return normalize_identity(self.protocol, self.host, self.port,
                                  self.username)

    def validate(self) -> Optional[str]:
        """合法性校验；返回错误消息或 None。"""
        if not _ALIAS_RE.match(self.alias or ""):
            return "alias 只允许字母数字-_（1~64 位）"
        if self.protocol not in PROTOCOLS:
            return f"protocol 必须是 {'/'.join(PROTOCOLS)}"
        if self.access_mode not in ACCESS_MODES:
            return "access_mode 必须是 rw 或 ro"
        if self.protocol in ("local",) and not (self.root_path or "").strip():
            return "local 来源必须提供 root_path"
        if self.protocol == "webdav" and not (self.url or "").strip():
            return "webdav 来源必须提供 url"
        try:
            self.scan_interval_min = max(5, int(self.scan_interval_min))
        except (TypeError, ValueError):
            self.scan_interval_min = 60
        return None

    def open_adapter(self) -> FileSystemAdapter:
        """按注册信息构建内容访问适配器（相对 source 根的 SubRoot 视图）。"""
        if self.protocol == "local":
            inner = FileSystemAdapter.create("local", self.root_path)
            prefix = "."
        elif self.protocol == "webdav":
            inner = FileSystemAdapter.create("webdav", self.url, {
                "username": self.username, "password": self.password,
                "verify_ssl": self.verify_ssl})
            prefix = ""
        else:
            inner = FileSystemAdapter.create(self.protocol, self.root_path, {
                "username": self.username, "password": self.password})
            prefix = "."
        from .fs.base import SubRootAdapter
        # local：SubRootAdapter(inner, ".") 前缀=根自身 → 相对路径视图；
        # webdav：prefix="" 时以 adapter 的 root_path 为前缀
        if self.protocol == "webdav":
            base_prefix = getattr(inner, "_root_path", "/") or "/"
            return SubRootAdapter(inner, unquote_path(base_prefix))
        return SubRootAdapter(inner, prefix)

    def to_api(self, include_secret: bool = False) -> dict:
        """API 输出（默认脱敏密码）。"""
        d = asdict(self)
        if not include_secret:
            d["password"] = "" if not self.password else "******"
        return d


def unquote_path(p: str) -> str:
    from urllib.parse import unquote
    return unquote(p or "/")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SourceRegistry:
    """来源注册表门面：按 config 自动选择 PG / JSON 后端。"""

    def __init__(self, config):
        self._config = config
        self._lock = threading.Lock()
        if getattr(config, "pg_enabled", False):
            self._pg = PgStore(config)
            self._json_path = None
        else:
            self._pg = None
            self._json_path = os.path.join(
                config.work_path, "sources.json")
        self._json_cache: Optional[dict] = None

    @property
    def backend(self) -> str:
        return "pg" if self._pg is not None else "json"

    # ── CRUD ──

    def list(self, include_disabled: bool = True) -> list[SourceRecord]:
        with self._lock:
            rows = self._load_all()
        out = [self._to_record(r) for r in rows]
        if not include_disabled:
            out = [r for r in out if r.enabled]
        return out

    def get(self, source_id_or_alias: str) -> Optional[SourceRecord]:
        """按 source_id 或 alias 取（id 优先）。"""
        key = (source_id_or_alias or "").strip()
        if not key:
            return None
        with self._lock:
            rows = self._load_all()
        for r in rows:
            if str(r.get("source_id")) == key:
                return self._to_record(r)
        for r in rows:
            if r.get("alias") == key:
                return self._to_record(r)
        return None

    def create(self, rec: SourceRecord) -> SourceRecord:
        err = rec.validate()
        if err:
            raise ValueError(err)
        rec.source_id = rec.source_id or str(uuid.uuid4())
        rec.schema_name = schema_name_for(*rec.identity())
        now = _now_iso()
        rec.created_at = now
        rec.updated_at = now
        with self._lock:
            rows = self._load_all()
            if any(x.get("alias") == rec.alias for x in rows):
                raise ValueError(f"alias 已存在: {rec.alias}")
            rows.append(asdict(rec))
            self._save_all(rows)
        return rec

    def update(self, source_id: str, **fields) -> SourceRecord:
        allowed = {"alias", "protocol", "host", "port", "username",
                   "password", "root_path", "url", "access_mode", "label",
                   "scan_auto", "scan_interval_min", "deep", "enabled",
                   "verify_ssl"}
        with self._lock:
            rows = self._load_all()
            target = None
            for i, r in enumerate(rows):
                if str(r.get("source_id")) == source_id:
                    target = i
                    break
            if target is None:
                raise KeyError(f"source 不存在: {source_id}")
            rec = self._to_record(rows[target])
            for k, v in fields.items():
                if k in allowed and v is not None:
                    setattr(rec, k, v)
            err = rec.validate()
            if err:
                raise ValueError(err)
            others = [x for j, x in enumerate(rows) if j != target]
            if any(x.get("alias") == rec.alias for x in others):
                raise ValueError(f"alias 已存在: {rec.alias}")
            rec.schema_name = schema_name_for(*rec.identity())
            rec.updated_at = _now_iso()
            rows[target] = asdict(rec)
            self._save_all(rows)
        return rec

    def delete(self, source_id: str) -> bool:
        with self._lock:
            rows = self._load_all()
            remain = [r for r in rows
                      if str(r.get("source_id")) != source_id]
            if len(remain) == len(rows):
                return False
            self._save_all(remain)
        return True

    def touch_scan(self, source_id: str, when_iso: str = "") -> None:
        """记录最近扫描时间（调度器用）。"""
        with self._lock:
            rows = self._load_all()
            for i, r in enumerate(rows):
                if str(r.get("source_id")) == source_id:
                    r["last_scan_at"] = when_iso or _now_iso()
                    r["updated_at"] = _now_iso()
                    rows[i] = r
                    self._save_all(rows)
                    return

    # ── 后端存取 ──

    def _to_record(self, raw: dict) -> SourceRecord:
        fields = {f for f in SourceRecord.__dataclass_fields__}
        return SourceRecord(**{k: v for k, v in raw.items() if k in fields})

    def _load_all(self) -> list[dict]:
        if self._pg is not None:
            self._ensure_pg_table()
            with self._pg.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT data FROM public.sources ORDER BY created_at")
                    return [row[0] for row in cur.fetchall()]
        if self._json_path and os.path.isfile(self._json_path):
            try:
                with open(self._json_path, encoding="utf-8") as f:
                    return json.load(f).get("sources", [])
            except Exception:
                return []
        return []

    def _save_all(self, rows: list[dict]) -> None:
        if self._pg is not None:
            self._ensure_pg_table()
            # 行级 upsert：以 source_id 为键全量对齐
            want = {str(r["source_id"]): r for r in rows}
            with self._pg.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT source_id FROM public.sources")
                    have = {str(r[0]) for r in cur.fetchall()}
                    for sid in have - set(want):
                        cur.execute(
                            "DELETE FROM public.sources WHERE source_id=%s",
                            (sid,))
                    for sid, r in want.items():
                        cur.execute(
                            "INSERT INTO public.sources (source_id, alias, "
                            "data) VALUES (%s,%s,%s) "
                            "ON CONFLICT (source_id) DO UPDATE SET "
                            "alias=EXCLUDED.alias, data=EXCLUDED.data",
                            (uuid.UUID(sid), r["alias"], json.dumps(
                                r, ensure_ascii=False)))
            return
        tmp = self._json_path + ".tmp"
        os.makedirs(os.path.dirname(self._json_path), exist_ok=True)
        payload = json.dumps({"sources": rows}, ensure_ascii=False, indent=2)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, self._json_path)

    def _ensure_pg_table(self) -> None:
        self._pg.ensure_registry()
        with self._pg.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.sources (
                      source_id uuid PRIMARY KEY,
                      alias     text NOT NULL UNIQUE,
                      data      jsonb NOT NULL,
                      created_at timestamptz NOT NULL DEFAULT now()
                    )
                """)
