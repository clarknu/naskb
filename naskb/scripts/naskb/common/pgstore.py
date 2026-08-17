"""pgstore — PostgreSQL + pgvector 多 NAS 向量库（REQ-R4，ADR-20260816-3）。

设计依据：design/pg-vector-multi-nas.md（v2）

- NAS 身份五要素（protocol/host/port/username）→ 独立 schema（向量库）
- public.nas_registry：全局注册表（nas_id → 五要素 + schema 名）
- 每 NAS schema：resources（资源/目录结构/指纹/状态）+ vectors（vector(512) + 摘要 + 全文 + 源哈希）
- 同步四操作：增/改/删/移（rel_path 为键 + hash 匹配识别移动，移动保留 resource_id）
- 状态机：ok / stale_vector / stale_source
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from .hashing import KNOWN_ALGORITHMS
from .retrieval import Doc

REGISTRY_TABLE = "nas_registry"
EMBEDDING_MODEL = "bge-small-zh-v1.5"
EMBEDDING_DIM = 512


# ═══════════════════════════════════════════════════════════════════
# NAS 身份与 schema 命名（REQ-R4-01/02）
# ═══════════════════════════════════════════════════════════════════

def normalize_identity(protocol: str, host: str, port: int,
                       username: str) -> tuple[str, str, int, str]:
    """五要素归一化（ADR-20260816-3 §3.1）。"""
    protocol = (protocol or "").lower()
    host = (host or "").lower().rstrip(".")
    if protocol == "local":
        host = "local"
        port = 0
    try:
        port = int(port or 0)
    except (TypeError, ValueError):
        port = 0
    return protocol, host, port, username or ""


def schema_name_for(protocol: str, host: str, port: int,
                    username: str) -> str:
    """确定性 schema 名：nas_<protocol>_<host>_<port>_u<sha1(user)[:12]>。

    host 中非 [a-z0-9] 全部替换为下划线；超 63 字符整体降级为
    nas_<sha1(五要素)[:24]>（PG 标识符上限）。
    """
    protocol, host, port, username = normalize_identity(
        protocol, host, port, username)
    h = host if re.fullmatch(r"[a-z0-9]+", host) \
        else re.sub(r"[^a-z0-9]", "_", host)
    user_hash = hashlib.sha1(username.encode("utf-8")).hexdigest()[:12] \
        if username else "anon"
    name = f"nas_{protocol}_{h}_{port}_u{user_hash}"
    if len(name) > 63:
        digest = hashlib.sha1(
            f"{protocol}|{host}|{port}|{username}".encode("utf-8")
        ).hexdigest()[:24]
        name = f"nas_{digest}"
    return name


# ═══════════════════════════════════════════════════════════════════
# PgStore
# ═══════════════════════════════════════════════════════════════════

_DDL_RESOURCES = """
CREATE TABLE IF NOT EXISTS {schema}.resources (
  resource_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rel_path     text NOT NULL,
  parent_dir   text NOT NULL,
  name         text NOT NULL,
  kind         text NOT NULL DEFAULT 'file',
  category     text NOT NULL DEFAULT '',
  tags         text[] NOT NULL DEFAULT '{{}}',
  summary      text NOT NULL DEFAULT '',
  content_description text NOT NULL DEFAULT '',
  file_type    text NOT NULL DEFAULT '',
  file_hash    text NOT NULL DEFAULT '',
  hash_algorithm text NOT NULL DEFAULT '',
  mtime        double precision NOT NULL DEFAULT 0,
  ctime        double precision,
  size_bytes   bigint NOT NULL DEFAULT 0,
  analyzer_version text NOT NULL DEFAULT '',
  analyzed_at  timestamptz,
  status       text NOT NULL DEFAULT 'ok',
  prev_hashes  jsonb NOT NULL DEFAULT '[]',
  synced_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (rel_path)
);
CREATE INDEX IF NOT EXISTS idx_resources_parent ON {schema}.resources (parent_dir);
CREATE INDEX IF NOT EXISTS idx_resources_status ON {schema}.resources (status);
CREATE INDEX IF NOT EXISTS idx_resources_dedup
  ON {schema}.resources (hash_algorithm, size_bytes, file_hash);
"""

_DDL_VECTORS = """
CREATE TABLE IF NOT EXISTS {schema}.vectors (
  vector_id    bigserial PRIMARY KEY,
  resource_id  uuid NOT NULL REFERENCES {schema}.resources(resource_id) ON DELETE CASCADE,
  model        text NOT NULL,
  dim          int  NOT NULL,
  embedding    vector(512) NOT NULL,
  summary_text text NOT NULL,
  full_text    text NOT NULL DEFAULT '',
  source_hash  text NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (resource_id, model)
);
CREATE INDEX IF NOT EXISTS idx_vectors_embedding ON {schema}.vectors
  USING hnsw (embedding vector_cosine_ops);
"""

_DDL_REGISTRY = """
CREATE TABLE IF NOT EXISTS public.nas_registry (
  nas_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  protocol    text NOT NULL,
  host        text NOT NULL,
  port        int  NOT NULL,
  username    text NOT NULL,
  schema_name text NOT NULL UNIQUE,
  label       text NOT NULL DEFAULT '',
  root_hint   text NOT NULL DEFAULT '',
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (protocol, host, port, username)
);
"""


class PgStore:
    """PG 多 NAS 向量库存储层。连接参数来自 Config 的 [pg] 段。"""

    def __init__(self, config):
        self._cfg = config  # Config 对象（pg_host/pg_port/pg_user/...）
        from pgvector.psycopg import register_vector
        self._register_vector = register_vector

    @property
    def enabled(self) -> bool:
        return bool(getattr(self._cfg, "pg_enabled", False))

    def connect(self) -> psycopg.Connection:
        conn = psycopg.connect(
            host=self._cfg.pg_host, port=self._cfg.pg_port,
            user=self._cfg.pg_user, password=self._cfg.pg_password,
            dbname=self._cfg.pg_database, connect_timeout=10,
        )
        self._register_vector(conn)
        return conn

    # ── registry / schema ──

    def ensure_registry(self) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(_DDL_REGISTRY)

    def get_or_create_nas(self, protocol: str, host: str, port: int,
                          username: str, label: str = "",
                          root_hint: str = "") -> dict:
        """按五要素取/建 NAS 注册（幂等），返回 registry 行 dict。"""
        protocol, host, port, username = normalize_identity(
            protocol, host, port, username)
        schema_name = schema_name_for(protocol, host, port, username)
        self.ensure_registry()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT nas_id, protocol, host, port, username, "
                    "schema_name, label, root_hint, created_at "
                    "FROM public.nas_registry "
                    "WHERE protocol=%s AND host=%s AND port=%s AND username=%s",
                    (protocol, host, port, username))
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        "INSERT INTO public.nas_registry "
                        "(protocol, host, port, username, schema_name, "
                        "label, root_hint) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (protocol, host, port, username) "
                        "DO UPDATE SET label=EXCLUDED.label, "
                        "root_hint=EXCLUDED.root_hint "
                        "RETURNING nas_id, protocol, host, port, username, "
                        "schema_name, label, root_hint, created_at",
                        (protocol, host, port, username, schema_name,
                         label, root_hint))
                    row = cur.fetchone()
        cols = ("nas_id", "protocol", "host", "port", "username",
                "schema_name", "label", "root_hint", "created_at")
        return dict(zip(cols, row))

    def ensure_nas_schema(self, schema_name: str) -> None:
        """确保 NAS schema 与 resources/vectors 表存在（幂等）。"""
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}")
                            .format(ident))
                cur.execute(sql.SQL(_DDL_RESOURCES).format(schema=ident))
                cur.execute(sql.SQL(_DDL_VECTORS).format(schema=ident))

    # ── sync（四操作）──

    def sync_vectors(self, schema_name: str, docs: list[Doc],
                     embedder=None, batch: int = 200) -> dict:
        """增量同步：增/改/删/移 四操作（ADR-20260816-3 §5.4）。

        embedder: Embedder 实例（encode_batch）；None 时调用方必须保证
                  docs 无新增/更新条目（纯校验模式）。
        返回 {added, updated, moved, deleted, unchanged, embedded}。
        """
        if embedder is None:
            from .embeddings import Embedder
            embedder = Embedder(self._cfg.work_path)
        self.ensure_nas_schema(schema_name)
        stats = {"added": 0, "updated": 0, "moved": 0, "deleted": 0,
                 "unchanged": 0, "embedded": 0, "errors": []}

        new_docs = [d for d in docs if d.kind == "file"]
        by_path: dict[str, Doc] = {}
        for d in new_docs:
            rel = self._rel_of(d.path)
            by_path.setdefault(rel, d)

        with self.connect() as conn:
            # 现库状态
            existing: dict[str, dict] = {}
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT resource_id, rel_path, file_hash, hash_algorithm "
                    "FROM {}.resources").format(sql.Identifier(schema_name)))
                for row in cur.fetchall():
                    existing[row[1]] = {
                        "resource_id": row[0], "file_hash": row[2],
                        "hash_algorithm": row[3]}

            # 待嵌入条目（新增/更新）
            to_embed: list[Doc] = []
            to_insert: list[Doc] = []
            to_update: list[tuple[Doc, dict]] = []

            for rel, doc in by_path.items():
                cur_row = existing.get(rel)
                if cur_row is None:
                    to_insert.append(doc)
                    to_embed.append(doc)
                elif cur_row["hash_algorithm"] == doc.hash_algorithm \
                        and cur_row["file_hash"] == doc.file_hash:
                    stats["unchanged"] += 1
                else:
                    to_update.append((doc, cur_row))
                    to_embed.append(doc)

            # 删除 vs 移动：PG 有、.naskb 无
            doc_hashes = {(d.hash_algorithm, d.file_hash): d
                          for d in by_path.values()}
            for rel, row in existing.items():
                if rel in by_path:
                    continue
                key = (row["hash_algorithm"], row["file_hash"])
                if key in doc_hashes and key != ("", ""):
                    # 移动：hash 匹配 → 保留 resource_id，更新路径
                    doc = doc_hashes[key]
                    with conn.cursor() as cur:
                        cur.execute(sql.SQL(
                            "UPDATE {}.resources SET rel_path=%s, "
                            "parent_dir=%s, name=%s, synced_at=now() "
                            "WHERE resource_id=%s")
                            .format(sql.Identifier(schema_name)),
                            (self._rel_of(doc.path),
                             self._parent_of(self._rel_of(doc.path)),
                             doc.path.replace("\\", "/").split("/")[-1],
                             row["resource_id"]))
                    stats["moved"] += 1
                    # 该 doc 不再作为新增处理
                    to_insert = [d for d in to_insert
                                 if self._rel_of(d.path) != self._rel_of(doc.path)]
                    to_embed = [d for d in to_embed
                                if self._rel_of(d.path) != self._rel_of(doc.path)]
                    by_path.pop(rel, None)
                else:
                    with conn.cursor() as cur:
                        cur.execute(sql.SQL(
                            "DELETE FROM {}.resources WHERE resource_id=%s")
                            .format(sql.Identifier(schema_name)),
                            (row["resource_id"],))
                    stats["deleted"] += 1

            # 编码（批量）
            if to_embed:
                vectors = embedder.encode([d.text for d in to_embed])
                emb_by_path = {self._rel_of(d.path): vec
                               for d, vec in zip(to_embed, vectors)}
                stats["embedded"] = len(to_embed)

            now = datetime.now(timezone.utc)
            with conn.cursor() as cur:
                for doc in to_insert:
                    rel = self._rel_of(doc.path)
                    vec = emb_by_path.get(rel)
                    if vec is None:
                        stats["errors"].append(f"嵌入缺失: {rel}")
                        continue
                    cur.execute(sql.SQL(
                        "INSERT INTO {}.resources (rel_path, parent_dir, "
                        "name, kind, category, tags, summary, "
                        "content_description, file_type, file_hash, "
                        "hash_algorithm, mtime, ctime, size_bytes, "
                        "analyzer_version, analyzed_at, status) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                        "%s,%s,%s,'ok') RETURNING resource_id")
                        .format(sql.Identifier(schema_name)),
                        (rel, self._parent_of(rel),
                         rel.split("/")[-1], doc.kind, doc.category,
                         doc.tags, doc.summary,
                         "", "", doc.file_hash, doc.hash_algorithm,
                         doc.mtime, doc.ctime or None, doc.size_bytes,
                         "", self._ts(doc.analyzed_at)))
                    rid = cur.fetchone()[0]
                    cur.execute(sql.SQL(
                        "INSERT INTO {}.vectors (resource_id, model, dim, "
                        "embedding, summary_text, full_text, source_hash) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)")
                        .format(sql.Identifier(schema_name)),
                        (rid, EMBEDDING_MODEL, EMBEDDING_DIM, vec,
                         doc.text, doc.context, doc.file_hash))
                    stats["added"] += 1

                for doc, row in to_update:
                    rel = self._rel_of(doc.path)
                    vec = emb_by_path.get(rel)
                    if vec is None:
                        stats["errors"].append(f"嵌入缺失: {rel}")
                        continue
                    cur.execute(sql.SQL(
                        "UPDATE {}.resources SET file_hash=%s, "
                        "hash_algorithm=%s, mtime=%s, ctime=%s, "
                        "size_bytes=%s, summary=%s, category=%s, tags=%s, "
                        "prev_hashes = prev_hashes || %s::jsonb, "
                        "status='ok', synced_at=now() "
                        "WHERE resource_id=%s")
                        .format(sql.Identifier(schema_name)),
                        (doc.file_hash, doc.hash_algorithm, doc.mtime,
                         doc.ctime or None, doc.size_bytes, doc.summary,
                         doc.category, doc.tags,
                         Jsonb([{"hash": row["file_hash"],
                                 "algorithm": row["hash_algorithm"],
                                 "replaced_at": now.isoformat()}]),
                         row["resource_id"]))
                    cur.execute(sql.SQL(
                        "UPDATE {}.vectors SET embedding=%s, "
                        "summary_text=%s, full_text=%s, source_hash=%s, "
                        "updated_at=now() WHERE resource_id=%s AND model=%s")
                        .format(sql.Identifier(schema_name)),
                        (vec, doc.text, doc.context, doc.file_hash,
                         row["resource_id"], EMBEDDING_MODEL))
                    stats["updated"] += 1
        return stats

    # ── 检索 ──

    def search(self, schema_name: str, query_vector,
               top_k: int = 10, model: str = EMBEDDING_MODEL) -> list[dict]:
        """余弦 top-k。query_vector: np.ndarray/list（已归一化）。"""
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT r.rel_path, r.parent_dir, r.name, r.kind, "
                    "r.category, r.tags, r.summary, r.status, "
                    "r.file_hash, r.hash_algorithm, r.size_bytes, "
                    "r.mtime, r.ctime, v.summary_text, v.full_text, "
                    "v.source_hash, 1 - (v.embedding <=> %s::vector) AS score "
                    "FROM {}.vectors v "
                    "JOIN {}.resources r ON r.resource_id = v.resource_id "
                    "WHERE v.model = %s "
                    "ORDER BY v.embedding <=> %s::vector LIMIT %s")
                    .format(ident, ident),
                    (query_vector, model, query_vector, top_k))
                rows = cur.fetchall()
        cols = ("path", "parent_dir", "name", "kind", "category", "tags",
                "summary", "status", "file_hash", "hash_algorithm",
                "size_bytes", "mtime", "ctime", "text", "context",
                "source_hash", "score")
        out = []
        for row in rows:
            item = dict(zip(cols, row))
            item["stale"] = item["status"] != "ok"
            out.append(item)
        return out

    def resource_rows(self, schema_name: str) -> dict[str, dict]:
        """schema 内 resources 的 rel_path → 指纹映射（只读，sync-status 用）。"""
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT rel_path, file_hash, hash_algorithm, status "
                    "FROM {}.resources").format(ident))
                return {row[0]: {"file_hash": row[1],
                                 "hash_algorithm": row[2],
                                 "status": row[3]}
                        for row in cur.fetchall()}

    def nas_stats(self, schema_name: str) -> dict:
        """schema 内统计（resources/vectors 数量、状态分布）。"""
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT count(*), count(*) FILTER (WHERE status='ok'), "
                    "count(*) FILTER (WHERE status='stale_vector'), "
                    "count(*) FILTER (WHERE status='stale_source') "
                    "FROM {}.resources").format(ident))
                res = cur.fetchone()
                cur.execute(sql.SQL(
                    "SELECT count(*) FROM {}.vectors").format(ident))
                vec = cur.fetchone()[0]
        return {"resources": res[0], "ok": res[1], "stale_vector": res[2],
                "stale_source": res[3], "vectors": vec}

    def list_nas(self) -> list[dict]:
        """注册表全量（含统计）。"""
        self.ensure_registry()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT nas_id, protocol, host, port, username, "
                    "schema_name, label, root_hint, created_at "
                    "FROM public.nas_registry ORDER BY created_at")
                rows = cur.fetchall()
        cols = ("nas_id", "protocol", "host", "port", "username",
                "schema_name", "label", "root_hint", "created_at")
        return [dict(zip(cols, r)) for r in rows]

    # ── helpers ──

    @staticmethod
    def _rel_of(path: str) -> str:
        return path.replace("\\", "/").lstrip("/")

    @staticmethod
    def _parent_of(rel: str) -> str:
        return rel.rsplit("/", 1)[0] if "/" in rel else ""

    @staticmethod
    def _ts(iso: str) -> Optional[datetime]:
        if not iso:
            return None
        try:
            return datetime.fromisoformat(iso)
        except ValueError:
            return None
