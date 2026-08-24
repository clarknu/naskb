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
from .chunker import chunk_markdown

REGISTRY_TABLE = "nas_registry"
EMBEDDING_MODEL = "bge-small-zh-v1.5"
EMBEDDING_DIM = 512
# 旧数据（无来源注册表时代）的来源占位 id：保证 (source_id, rel_path) 唯一索引可用
LEGACY_SOURCE = uuid.UUID(int=0)


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
  artifacts    jsonb NOT NULL DEFAULT '{{}}',
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

# v3 来源化迁移（幂等）：resources 增 source_id 列 + (source_id, rel_path) 唯一；
# folders 独立目录描述表（ADR-20260818-1 决策 6）
_MIGRATE_SOURCES = """
ALTER TABLE {schema}.resources ADD COLUMN IF NOT EXISTS source_id uuid;
ALTER TABLE {schema}.resources ADD COLUMN IF NOT EXISTS artifacts jsonb;
UPDATE {schema}.resources SET source_id = {legacy}::uuid WHERE source_id IS NULL;
UPDATE {schema}.resources SET artifacts = '{{}}'::jsonb WHERE artifacts IS NULL;
ALTER TABLE {schema}.resources DROP CONSTRAINT IF EXISTS resources_rel_path_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_resources_source_path
  ON {schema}.resources (source_id, rel_path);
"""

_DDL_FOLDERS = """
CREATE TABLE IF NOT EXISTS {schema}.folders (
  folder_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id   uuid NOT NULL DEFAULT {legacy}::uuid,
  rel_path    text NOT NULL,
  parent_dir  text NOT NULL DEFAULT '',
  name        text NOT NULL,
  summary     text NOT NULL DEFAULT '',
  description text NOT NULL DEFAULT '',
  tags        text[] NOT NULL DEFAULT '{{}}',
  file_count  int NOT NULL DEFAULT 0,
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_folders_source_path
  ON {schema}.folders (source_id, rel_path);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON {schema}.folders (parent_dir);
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


# ═══════════════════════════════════════════════════════════════════
# 条款级 chunk 增强（REQ-R5-06 / ADR-20260823-1）迁移：幂等
#   - vectors 扩列：level('summary'|'chunk')、chunk_seq、title_path、search_vector
#   - 唯一约束放宽：摘要行 (resource_id,model) 唯一；chunk 行按 seq 唯一
#     （原 UNIQUE(resource_id,model) 与「一文件多 chunk」冲突，故拆分）
#   - termbase：每 schema 术语表（jieba 自定义词典，关键词通道二期用）
# ═══════════════════════════════════════════════════════════════════
_MIGRATE_CHUNKS = """
ALTER TABLE {schema}.vectors ADD COLUMN IF NOT EXISTS level text NOT NULL DEFAULT 'summary';
ALTER TABLE {schema}.vectors ADD COLUMN IF NOT EXISTS chunk_seq int;
ALTER TABLE {schema}.vectors ADD COLUMN IF NOT EXISTS title_path text[] NOT NULL DEFAULT '{{}}';
ALTER TABLE {schema}.vectors ADD COLUMN IF NOT EXISTS search_vector tsvector;
ALTER TABLE {schema}.vectors DROP CONSTRAINT IF EXISTS vectors_resource_id_model_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_vectors_summary_unique
  ON {schema}.vectors (resource_id, model) WHERE level = 'summary';
CREATE UNIQUE INDEX IF NOT EXISTS idx_vectors_chunk_unique
  ON {schema}.vectors (resource_id, model, chunk_seq) WHERE level = 'chunk';
CREATE INDEX IF NOT EXISTS idx_vectors_chunk_hnsw
  ON {schema}.vectors USING hnsw (embedding vector_cosine_ops) WHERE level = 'chunk';
CREATE INDEX IF NOT EXISTS idx_vectors_chunk_tsv
  ON {schema}.vectors USING gin (search_vector) WHERE level = 'chunk';
CREATE TABLE IF NOT EXISTS {schema}.termbase (
  term       text PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
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
        """确保 NAS schema 与 resources/vectors/folders 表存在（幂等）。"""
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}")
                            .format(ident))
                cur.execute(sql.SQL(_DDL_RESOURCES).format(schema=ident))
                cur.execute(sql.SQL(_DDL_VECTORS).format(schema=ident))
                cur.execute(sql.SQL(_MIGRATE_SOURCES).format(
                    schema=ident, legacy=str(LEGACY_SOURCE)))
                cur.execute(sql.SQL(_DDL_FOLDERS).format(
                    schema=ident, legacy=str(LEGACY_SOURCE)))
                cur.execute(sql.SQL(_MIGRATE_CHUNKS).format(schema=ident))

    # ── sync（四操作）──

    def sync_vectors(self, schema_name: str, docs: list[Doc],
                     embedder=None, batch: int = 200,
                     source_id: uuid.UUID | str | None = None) -> dict:
        """增量同步：增/改/删/移 四操作（ADR-20260816-3 §5.4）。

        embedder: Embedder 实例（encode_batch）；None 时调用方必须保证
                  docs 无新增/更新条目（纯校验模式）。
        source_id: 来源作用域（v3 来源注册表）；None → LEGACY_SOURCE。
                  差异比对/移动识别/删除检测都只在该来源的行集合内进行，
                  INSERT 的行打上该 source_id 标记。
        返回 {added, updated, moved, deleted, unchanged, embedded, enriched}。
        """
        if embedder is None:
            from .embeddings import Embedder
            embedder = Embedder(self._cfg.work_path)
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        self.ensure_nas_schema(schema_name)
        stats = {"added": 0, "updated": 0, "moved": 0, "deleted": 0,
                 "unchanged": 0, "embedded": 0, "enriched": 0, "errors": []}

        new_docs = [d for d in docs if d.kind == "file"]
        by_path: dict[str, Doc] = {}
        for d in new_docs:
            rel = self._rel_of(d.path)
            by_path.setdefault(rel, d)

        with self.connect() as conn:
            # 现库状态（本来源作用域；带向量存在性——富化回填判定用）
            existing: dict[str, dict] = {}
            ident = sql.Identifier(schema_name)
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT r.resource_id, r.rel_path, r.file_hash, "
                    "r.hash_algorithm, (v.resource_id IS NOT NULL) AS has_vec "
                    "FROM {r}.resources r LEFT JOIN {v}.vectors v "
                    "ON v.resource_id = r.resource_id AND v.model = %s "
                    "AND v.level = 'summary' "
                    "WHERE r.source_id = %s").format(r=ident, v=ident),
                    (EMBEDDING_MODEL, sid))
                for row in cur.fetchall():
                    existing[row[1]] = {
                        "resource_id": row[0], "file_hash": row[2],
                        "hash_algorithm": row[3], "has_vector": row[4]}

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
                        and cur_row["file_hash"] == doc.file_hash \
                        and cur_row["has_vector"]:
                    stats["unchanged"] += 1
                elif cur_row["hash_algorithm"] == doc.hash_algorithm \
                        and cur_row["file_hash"] == doc.file_hash:
                    # 内容未变但向量缺失：富化回填（更新描述列 + 补向量）
                    self._enrich_existing(conn, schema_name,
                                          cur_row["resource_id"], doc,
                                          embedder, stats)
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
                        "analyzer_version, analyzed_at, status, source_id, "
                        "artifacts) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                        "%s,%s,%s,'ok',%s,%s) RETURNING resource_id")
                        .format(sql.Identifier(schema_name)),
                        (rel, self._parent_of(rel),
                         rel.split("/")[-1], doc.kind, doc.category,
                         doc.tags, doc.summary,
                         doc.content_description or "", doc.file_type or "",
                         doc.file_hash, doc.hash_algorithm,
                         doc.mtime, doc.ctime or None, doc.size_bytes,
                         "", self._ts(doc.analyzed_at), sid,
                         Jsonb(doc.artifacts or {})))
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
                        "content_description=%s, file_type=%s, "
                        "artifacts=%s, "
                        "prev_hashes = prev_hashes || %s::jsonb, "
                        "status='ok', synced_at=now() "
                        "WHERE resource_id=%s")
                        .format(sql.Identifier(schema_name)),
                        (doc.file_hash, doc.hash_algorithm, doc.mtime,
                         doc.ctime or None, doc.size_bytes, doc.summary,
                         doc.category, doc.tags,
                         doc.content_description or "", doc.file_type or "",
                         Jsonb(doc.artifacts or {}),
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

    def _enrich_existing(self, conn, schema_name: str, resource_id, doc: Doc,
                         embedder, stats: dict) -> None:
        """内容未变但向量缺失：回填描述列 + 补建向量（富化路径，v3）。"""
        vec = embedder.encode_one(doc.text) if hasattr(embedder, "encode_one") \
            else embedder.encode([doc.text])[0]
        ident = sql.Identifier(schema_name)
        with conn.cursor() as cur:
            cur.execute(sql.SQL(
                "UPDATE {}.resources SET summary=%s, category=%s, tags=%s, "
                "content_description=%s, file_type=%s, artifacts=%s, "
                "status='ok', synced_at=now() WHERE resource_id=%s")
                .format(ident),
                (doc.summary, doc.category, doc.tags,
                 doc.content_description or "", doc.file_type or "",
                 Jsonb(doc.artifacts or {}),
                 resource_id))
            cur.execute(sql.SQL(
                "INSERT INTO {}.vectors (resource_id, model, dim, embedding, "
                "summary_text, full_text, source_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (resource_id, model) WHERE level='summary' "
                "DO UPDATE SET embedding=EXCLUDED.embedding, "
                "summary_text=EXCLUDED.summary_text, "
                "full_text=EXCLUDED.full_text, "
                "source_hash=EXCLUDED.source_hash, updated_at=now()")
                .format(ident),
                (resource_id, EMBEDDING_MODEL, EMBEDDING_DIM, vec,
                 doc.text, doc.context, doc.file_hash))
        stats["embedded"] += 1
        stats["enriched"] += 1

    # ── 检索 ──

    def search(self, schema_name: str, query_vector,
               top_k: int = 10, model: str = EMBEDDING_MODEL,
               source_ids: list | None = None,
               level: str = "summary") -> list[dict]:
        """余弦 top-k。query_vector: np.ndarray/list（已归一化）。

        source_ids: 来源过滤（v3）；None/空 = 全部来源。
        level: 检索层级——'summary'（文档级，默认）/ 'chunk'（条款级，REQ-R5-06）。
        输出含 resource_id/source_id（str），供内容访问层凭 id 寻址。
        """
        ident = sql.Identifier(schema_name)
        sids = None
        if source_ids:
            sids = [uuid.UUID(str(s)) for s in source_ids]
        where_extra = " AND r.source_id = ANY(%s)" if sids else ""
        params: list = [query_vector, model, level]
        if sids:
            params.append(sids)
        params.extend([query_vector, top_k])
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT r.rel_path, r.parent_dir, r.name, r.kind, "
                    "r.category, r.tags, r.summary, r.status, "
                    "r.file_hash, r.hash_algorithm, r.size_bytes, "
                    "r.mtime, r.ctime, v.summary_text, v.full_text, "
                    "v.source_hash, v.title_path, v.chunk_seq, v.level, "
                    "r.resource_id, r.source_id, "
                    "1 - (v.embedding <=> %s::vector) AS score "
                    "FROM {v}.vectors v "
                    "JOIN {r}.resources r ON r.resource_id = v.resource_id "
                    "WHERE v.model = %s AND v.level = %s" + where_extra + " "
                    "ORDER BY v.embedding <=> %s::vector LIMIT %s"
                    ).format(v=ident, r=ident),
                    tuple(params))
                rows = cur.fetchall()
        cols = ("path", "parent_dir", "name", "kind", "category", "tags",
                "summary", "status", "file_hash", "hash_algorithm",
                "size_bytes", "mtime", "ctime", "text", "context",
                "source_hash", "title_path", "chunk_seq", "level",
                "resource_id", "source_id", "score")
        out = []
        for row in rows:
            item = dict(zip(cols, row))
            item["stale"] = item["status"] != "ok"
            if item.get("resource_id") is not None:
                item["resource_id"] = str(item["resource_id"])
            if item.get("source_id") is not None:
                item["source_id"] = str(item["source_id"])
            out.append(item)
        return out

    # ── 条款级 chunk 同步 + 术语表（REQ-R5-06）──

    @staticmethod
    def _is_deep(path: str, roots: list[str]) -> bool:
        """path（绝对或 rel）是否命中某个深析根目录（前缀匹配，规范化）。"""
        if not roots:
            return False
        p = (path or "").replace("\\", "/").rstrip("/")
        for r in roots:
            rn = r.replace("\\", "/").rstrip("/")
            if not rn:
                continue
            if p == rn or p.startswith(rn + "/"):
                return True
        return False

    def sync_chunks(self, schema_name: str, docs: list[Doc], *,
                    deep_cfg: dict, embedder=None,
                    source_id: uuid.UUID | str | None = None,
                    read_md=None, batch: int = 100,
                    match_all: bool = False) -> dict:
        """为深析圈定目录/来源的文档写条款级 chunk 向量行（REQ-R5-06）。

        deep_cfg: config `[deep]` 归一化 dict：enabled/roots/target_chars/
                  limit_chars/overlap_ratio。
        match_all: True 时忽略 roots 目录判定（来源级 deep 开关——整源都算深析）。
        read_md:  callable(doc) -> str|None，返回该文档的 MinerU Markdown；
                  缺省则尝试 doc.artifacts（仅路径，本层不读盘），取不到即计
                  skipped_no_md。实际调用方需注入「读 .naskb/artifacts md」的
                  fs 实现（本地/WebDAV）。
        前提：sync_vectors 已先跑（resources 行存在）；本方法对每个深析文档
              先删后建 chunk 行（幂等），不触碰摘要行。
        """
        stats = {"documents": 0, "chunks": 0,
                 "skipped_not_deep": 0, "skipped_no_resource": 0,
                 "skipped_no_md": 0, "empty_doc": 0, "errors": []}
        if not deep_cfg.get("enabled"):
            return stats
        if embedder is None:
            from .embeddings import Embedder
            embedder = Embedder(self._cfg.work_path)
        roots = list(deep_cfg.get("roots") or [])
        target = int(deep_cfg.get("target_chars", 800))
        limit = int(deep_cfg.get("limit_chars", 1200))
        overlap = float(deep_cfg.get("overlap_ratio", 0.12))
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE

        with self.connect() as conn:
            with conn.cursor() as cur:
                for doc in docs:
                    if doc.kind and doc.kind != "file":
                        continue
                    rel = self._rel_of(doc.path)
                    if not match_all and not self._is_deep(doc.path, roots) \
                            and not self._is_deep(rel, roots):
                        stats["skipped_not_deep"] += 1
                        continue
                    cur.execute(sql.SQL(
                        "SELECT resource_id, file_hash FROM {}.resources "
                        "WHERE source_id=%s AND rel_path=%s").format(
                        sql.Identifier(schema_name)),
                        (sid, rel))
                    row = cur.fetchone()
                    if row is None:
                        stats["skipped_no_resource"] += 1
                        continue
                    resource_id, file_hash = row
                    md = read_md(doc) if read_md else None
                    if not md and (doc.artifacts or {}).get("md_path"):
                        # 仅已知路径，无内容：交给调用方（read_md）补齐
                        md = None
                    if not md:
                        stats["skipped_no_md"] += 1
                        continue
                    chunks = chunk_markdown(
                        md, target_chars=target, limit_chars=limit,
                        overlap_ratio=overlap)
                    if not chunks:
                        stats["empty_doc"] += 1
                        continue
                    vecs = embedder.encode([c.emb_text for c in chunks])
                    cur.execute(sql.SQL(
                        "DELETE FROM {}.vectors WHERE resource_id=%s "
                        "AND level='chunk'").format(sql.Identifier(schema_name)),
                        (resource_id,))
                    for c, vec in zip(chunks, vecs):
                        cur.execute(sql.SQL(
                            "INSERT INTO {}.vectors (resource_id, model, dim, "
                            "embedding, summary_text, full_text, source_hash, "
                            "level, chunk_seq, title_path) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,'chunk',%s,%s) "
                            "ON CONFLICT (resource_id, model, chunk_seq) "
                            "WHERE level='chunk' "
                            "DO UPDATE SET embedding=EXCLUDED.embedding, "
                            "summary_text=EXCLUDED.summary_text, "
                            "full_text=EXCLUDED.full_text, "
                            "source_hash=EXCLUDED.source_hash, "
                            "title_path=EXCLUDED.title_path, "
                            "updated_at=now()").format(
                            sql.Identifier(schema_name)),
                            (resource_id, EMBEDDING_MODEL, EMBEDDING_DIM,
                             vec, c.emb_text, c.text, file_hash,
                             c.seq, c.title_path))
                    stats["documents"] += 1
                    stats["chunks"] += len(chunks)
        return stats

    def add_termbase(self, schema_name: str, terms) -> int:
        """写入术语表（jieba 自定义词典，关键词通道二期用）。返回新增数。"""
        terms = [t for t in (terms or []) if t and str(t).strip()]
        if not terms:
            return 0
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    sql.SQL(
                        "INSERT INTO {}.termbase (term) VALUES (%s) "
                        "ON CONFLICT (term) DO NOTHING").format(ident),
                    [(str(t).strip(),) for t in terms])
                return cur.rowcount or 0

    def list_termbase(self, schema_name: str) -> list[str]:
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT term FROM {}.termbase ORDER BY term"
                    ).format(ident))
                return [r[0] for r in cur.fetchall()]

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

    # ── v3 来源化：库存对账 / 目录浏览 / 资源访问（REQ-R7-03/05/06）──

    def reconcile_resources(self, schema_name: str, source_id,
                            items: list[dict]) -> dict:
        """只读源扫描对账（REQ-R7-06）：把源端现状对齐到 resources 行。

        items: [{rel_path, name, parent_dir, size_bytes, mtime, ctime,
                 file_hash, hash_algorithm, file_type}]（file_hash 可为 ""，
                 表示本轮未算指纹——仅登记，不算变化）。
        状态机：新文件→ok；stat 变且无相同指纹→stale_source；
        源端消失→missing_source；恢复一致→回 ok。
        目录清单同步 upsert 到 folders（file_count 统计）。
        """
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        self.ensure_nas_schema(schema_name)
        ident = sql.Identifier(schema_name)
        stats = {"added": 0, "updated": 0, "unchanged": 0,
                 "stale_source": 0, "restored": 0, "missing": 0}
        now = datetime.now(timezone.utc)

        def _close(a: float, b) -> bool:
            if not a and not b:
                return True
            try:
                return abs(float(a) - float(b or 0)) < 1e-6
            except (TypeError, ValueError):
                return False

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT rel_path, file_hash, hash_algorithm, mtime, "
                    "size_bytes, ctime, status FROM {}.resources "
                    "WHERE source_id = %s").format(ident), (sid,))
                existing = {r[0]: {"file_hash": r[1], "hash_algorithm": r[2],
                                   "mtime": r[3], "size_bytes": r[4],
                                   "ctime": r[5], "status": r[6]}
                            for r in cur.fetchall()}

            with conn.cursor() as cur:
                for it in items:
                    row = existing.get(it["rel_path"])
                    if row is None:
                        cur.execute(sql.SQL(
                            "INSERT INTO {}.resources (rel_path, parent_dir, "
                            "name, kind, category, file_type, file_hash, "
                            "hash_algorithm, mtime, ctime, size_bytes, "
                            "status, source_id) "
                            "VALUES (%s,%s,%s,'file',%s,%s,%s,%s,%s,%s,%s,"
                            "'ok',%s) ON CONFLICT (source_id, rel_path) "
                            "DO NOTHING")
                            .format(ident),
                            (it["rel_path"], it["rel_path"].rsplit("/", 1)[0]
                             if "/" in it["rel_path"] else "",
                             it["name"], it.get("category") or "",
                             it.get("file_type") or "",
                             it.get("file_hash") or "",
                             it.get("hash_algorithm") or "",
                             it.get("mtime") or 0,
                             it.get("ctime") or None,
                             it.get("size_bytes") or 0, sid))
                        if cur.rowcount:
                            stats["added"] += 1
                        continue
                    same_stat = (
                        _close(row["mtime"], it.get("mtime"))
                        and _close(row["ctime"], it.get("ctime"))
                        and int(row["size_bytes"] or 0) ==
                        int(it.get("size_bytes") or 0))
                    same_hash = (
                        bool(it.get("file_hash")) and bool(row["file_hash"])
                        and row["file_hash"] == it["file_hash"]
                        and row["hash_algorithm"] == it["hash_algorithm"])
                    if same_stat and row["status"] != "missing_source":
                        # 免检命中；顺手回填缺失指纹
                        if it.get("file_hash") and not row["file_hash"]:
                            cur.execute(sql.SQL(
                                "UPDATE {}.resources SET file_hash=%s, "
                                "hash_algorithm=%s WHERE resource_id="
                                "(SELECT resource_id FROM {}.resources "
                                "WHERE source_id=%s AND rel_path=%s)")
                                .format(ident, ident),
                                (it["file_hash"], it["hash_algorithm"],
                                 sid, it["rel_path"]))
                        stats["unchanged"] += 1
                    elif same_hash and row["status"] != "missing_source":
                        stats["unchanged"] += 1
                    elif same_stat and row["status"] == "missing_source":
                        cur.execute(sql.SQL(
                            "UPDATE {}.resources SET status='ok', "
                            "synced_at=now() WHERE source_id=%s "
                            "AND rel_path=%s").format(ident),
                            (sid, it["rel_path"]))
                        stats["restored"] += 1
                    else:
                        # 源已变：更新 stat、保留旧指纹、标 stale_source
                        cur.execute(sql.SQL(
                            "UPDATE {}.resources SET mtime=%s, ctime=%s, "
                            "size_bytes=%s, status='stale_source', "
                            "synced_at=now() WHERE source_id=%s "
                            "AND rel_path=%s").format(ident),
                            (it.get("mtime") or 0, it.get("ctime") or None,
                             it.get("size_bytes") or 0, sid, it["rel_path"]))
                        stats["stale_source"] += 1

                # 源端消失 → missing_source（知识保留可搜）
                walked = {it["rel_path"] for it in items}
                for rel in existing.keys() - walked:
                    cur.execute(sql.SQL(
                        "UPDATE {}.resources SET status='missing_source', "
                        "synced_at=now() WHERE source_id=%s AND rel_path=%s")
                        .format(ident), (sid, rel))
                    stats["missing"] += 1

                # 目录清单登记（含中间目录）
                dirs: set[str] = set()
                for it in items:
                    parts = it["rel_path"].split("/")
                    for i in range(len(parts) - 1):
                        dirs.add("/".join(parts[:i + 1]))
                for d in sorted(dirs):
                    parent = d.rsplit("/", 1)[0] if "/" in d else ""
                    name = d.rsplit("/", 1)[-1]
                    cur.execute(sql.SQL(
                        "INSERT INTO {f}.folders (source_id, rel_path, "
                        "parent_dir, name) VALUES (%s,%s,%s,%s) "
                        "ON CONFLICT (source_id, rel_path) DO UPDATE SET "
                        "parent_dir=EXCLUDED.parent_dir, "
                        "name=EXCLUDED.name, updated_at=now()")
                        .format(f=ident), (sid, d, parent, name))
                # file_count 重算：先清零，再按 resources 聚合回填
                cur.execute(sql.SQL(
                    "UPDATE {f}.folders SET file_count=0 WHERE source_id=%s")
                    .format(f=ident), (sid,))
                cur.execute(sql.SQL(
                    "UPDATE {f}.folders f SET file_count = c.n, "
                    "updated_at=now() FROM "
                    "(SELECT parent_dir, count(*) AS n FROM {r}.resources "
                    "WHERE source_id=%s GROUP BY parent_dir) c "
                    "WHERE f.source_id=%s AND f.rel_path = c.parent_dir")
                    .format(f=ident, r=ident), (sid, sid))
        return stats

    def list_dir(self, schema_name: str, source_id, parent_dir: str = "") -> tuple[list[dict], list[dict]]:
        """列目录（罗列检索）：返回 (子目录, 文件) 两张清单。"""
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT rel_path, name, summary, description, tags, "
                    "file_count FROM {}.folders WHERE source_id=%s "
                    "AND parent_dir=%s ORDER BY name").format(ident),
                    (sid, parent_dir))
                dirs = [{"rel_path": r[0], "name": r[1], "summary": r[2],
                         "description": r[3], "tags": list(r[4] or []),
                         "file_count": r[5]} for r in cur.fetchall()]
                cur.execute(sql.SQL(
                    "SELECT resource_id, rel_path, name, size_bytes, mtime, "
                    "status, summary, file_type, category, tags "
                    "FROM {}.resources WHERE source_id=%s AND parent_dir=%s "
                    "AND kind='file' ORDER BY name").format(ident),
                    (sid, parent_dir))
                files = []
                for r in cur.fetchall():
                    files.append({
                        "resource_id": str(r[0]), "rel_path": r[1],
                        "name": r[2], "size_bytes": r[3], "mtime": r[4],
                        "status": r[5], "summary": r[6], "file_type": r[7],
                        "category": r[8], "tags": list(r[9] or []),
                        "ext": ("." + r[1].rsplit(".", 1)[-1].lower())
                        if "." in r[1] else ""})
        return dirs, files

    def get_folder(self, schema_name: str, source_id, rel_path: str) -> Optional[dict]:
        """按来源与目录路径取 folders 目录条目（一致性 report /api/folder 端点用）。

        返回 {rel_path, name, summary, description, tags, file_count}；
        该 (source_id, rel_path) 未被登记或已不存在时返回 None。
        """
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT rel_path, name, summary, description, tags, "
                    "file_count FROM {}.folders WHERE source_id=%s "
                    "AND rel_path=%s").format(ident), (sid, rel_path))
                row = cur.fetchone()
        if row is None:
            return None
        return {"rel_path": row[0], "name": row[1], "summary": row[2],
                "description": row[3], "tags": list(row[4] or []),
                "file_count": row[5]}

    def get_resource(self, schema_name: str, resource_id) -> Optional[dict]:
        """按 resource_id 取资源行（内容访问层凭 id 寻址，REQ-R7-03）。"""
        ident = sql.Identifier(schema_name)
        rid = uuid.UUID(str(resource_id))
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT resource_id, source_id, rel_path, parent_dir, "
                    "name, kind, category, tags, summary, "
                    "content_description, file_type, file_hash, "
                    "hash_algorithm, mtime, ctime, size_bytes, status, "
                    "analyzed_at, artifacts FROM {}.resources "
                    "WHERE resource_id = %s").format(ident), (rid,))
                row = cur.fetchone()
        if row is None:
            return None
        cols = ("resource_id", "source_id", "rel_path", "parent_dir",
                "name", "kind", "category", "tags", "summary",
                "content_description", "file_type", "file_hash",
                "hash_algorithm", "mtime", "ctime", "size_bytes", "status",
                "analyzed_at", "artifacts")
        d = dict(zip(cols, row))
        d["tags"] = list(d["tags"] or [])
        d["artifacts"] = d["artifacts"] or {}
        d["resource_id"] = str(d["resource_id"])
        d["source_id"] = str(d["source_id"]) if d["source_id"] else ""
        return d

    def all_rows(self, schema_name: str, source_id=None) -> list[dict]:
        """来源全部资源行（export-repo 用，含 artifacts/全文主体字段）。"""
        sid = None
        if source_id is not None:
            sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                if sid is not None:
                    cur.execute(sql.SQL(
                        "SELECT resource_id, source_id, rel_path, parent_dir, "
                        "name, kind, category, tags, summary, "
                        "content_description, file_type, file_hash, "
                        "hash_algorithm, mtime, ctime, size_bytes, status, "
                        "analyzed_at, artifacts FROM {}.resources "
                        "WHERE source_id=%s ORDER BY rel_path").format(ident),
                        (sid,))
                else:
                    cur.execute(sql.SQL(
                        "SELECT resource_id, source_id, rel_path, parent_dir, "
                        "name, kind, category, tags, summary, "
                        "content_description, file_type, file_hash, "
                        "hash_algorithm, mtime, ctime, size_bytes, status, "
                        "analyzed_at, artifacts FROM {}.resources "
                        "ORDER BY rel_path").format(ident))
                rows = cur.fetchall()
        cols = ("resource_id", "source_id", "rel_path", "parent_dir",
                "name", "kind", "category", "tags", "summary",
                "content_description", "file_type", "file_hash",
                "hash_algorithm", "mtime", "ctime", "size_bytes", "status",
                "analyzed_at", "artifacts")
        out = []
        for row in rows:
            d = dict(zip(cols, row))
            d["tags"] = list(d["tags"] or [])
            d["artifacts"] = d["artifacts"] or {}
            d["resource_id"] = str(d["resource_id"])
            d["source_id"] = str(d["source_id"]) if d["source_id"] else ""
            out.append(d)
        return out

    def upsert_artifacts(self, schema_name: str, resource_id,
                         artifacts: dict) -> None:
        """更新单个资源行的解析产物登记（解析视图用）。"""
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "UPDATE {}.resources SET artifacts=%s, synced_at=now() "
                    "WHERE resource_id=%s").format(ident),
                    (Jsonb(artifacts or {}), uuid.UUID(str(resource_id))))

    def rebind_nas(self, old: dict, new: dict) -> dict:
        """pg-rebind（REQ-R4-14）：NAS 主机/账号变更时重绑五要素不丢库。

        old/new: {protocol?,host,port,username?,label?}。流程：
        归一化新五要素 → 计算新 schema 名 → 若与旧名不同则改 schema 名
        → 更新 registry 行。返回 {changed, old_schema, new_schema}。
        """
        old_proto, old_host, old_port, old_user = normalize_identity(
            old.get("protocol", "webdav"), old.get("host", ""),
            old.get("port", 0), old.get("username", ""))
        old_schema = schema_name_for(old_proto, old_host, old_port, old_user)
        new_proto, new_host, new_port, new_user = normalize_identity(
            new.get("protocol", old_proto), new.get("host", old_host),
            new.get("port", old_port), new.get("username", old_user))
        new_schema = schema_name_for(new_proto, new_host, new_port, new_user)
        self.ensure_registry()
        changed = False
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT nas_id FROM public.nas_registry
                    WHERE protocol=%s AND host=%s AND port=%s AND username=%s
                """, (old_proto, old_host, old_port, old_user))
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("未找到该 NAS 注册记录（先 sync-vectors 注册）")
                nas_id = row[0]
                if old_schema != new_schema:
                    cur.execute(sql.SQL("ALTER SCHEMA {} RENAME TO {}")
                                .format(sql.Identifier(old_schema),
                                        sql.Identifier(new_schema)))
                    changed = True
                cur.execute("""
                    UPDATE public.nas_registry SET host=%s, port=%s,
                    username=%s, schema_name=%s
                    WHERE nas_id=%s
                """, (new_host, new_port, new_user, new_schema, nas_id))
        return {"changed": changed, "old_schema": old_schema,
                "new_schema": new_schema, "nas_id": str(nas_id)}

    def delete_source_rows(self, schema_name: str, source_id) -> int:
        """删除来源的全部行（vectors 级联；注销来源时用）。"""
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "DELETE FROM {}.resources WHERE source_id=%s")
                    .format(ident), (sid,))
                n = cur.rowcount
                cur.execute(sql.SQL(
                    "DELETE FROM {}.folders WHERE source_id=%s")
                    .format(ident), (sid,))
        return n

    def delete_chunk_rows(self, schema_name: str, source_id) -> int:
        """删除来源所有 level='chunk' 的向量行（deep 关闭语义）。

        vectors 表无 source_id 列，须经 resources JOIN 定位该来源的 chunk 行；
        仅删条款级，保留文档级 summary 行与其他来源数据。返回删除行数。
        """
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "DELETE FROM {v}.vectors USING {r}.resources "
                    "WHERE vectors.resource_id = resources.resource_id "
                    "AND resources.source_id = %s AND vectors.level = 'chunk'")
                    .format(v=ident, r=ident), (sid,))
                return cur.rowcount or 0

    def source_stats(self, schema_name: str, source_id) -> dict:
        """单来源状态分布（一致性报告用）。"""
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT count(*), "
                    "count(*) FILTER (WHERE status='ok'), "
                    "count(*) FILTER (WHERE status='stale_source'), "
                    "count(*) FILTER (WHERE status='missing_source'), "
                    "count(*) FILTER (WHERE summary <> '') "
                    "FROM {}.resources WHERE source_id=%s").format(ident),
                    (sid,))
                r = cur.fetchone()
                cur.execute(sql.SQL(
                    "SELECT count(*) FROM {}.vectors v "
                    "JOIN {}.resources r ON r.resource_id=v.resource_id "
                    "WHERE r.source_id=%s AND v.level='chunk'")
                    .format(ident, ident),
                    (sid,))
                chunks = cur.fetchone()[0]
        return {"files": r[0], "ok": r[1], "stale_source": r[2],
                "missing_source": r[3], "analyzed": r[4], "chunks": chunks}

    def source_changes(self, schema_name: str, source_id, items) -> dict:
        """dry-run 差异报告（确认清单用，只读不应用，REQ-R5-06/系统流程）。

        items: [{rel_path, file_hash, hash_algorithm, mtime, size_bytes, ...}]。
        返回 {added, changed, missing, unchanged} —— 均为 rel_path 列表。
        changed 判定：指纹（hash 双方皆提供且不同）或 stat（mtime/size 不同）
        之一变化；其余为 unchanged。missing = 来源已无但 resources 仍在。
        """
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT rel_path, file_hash, hash_algorithm, mtime, "
                    "size_bytes, ctime, status FROM {}.resources "
                    "WHERE source_id = %s").format(ident), (sid,))
                existing = {r[0]: {"file_hash": r[1], "hash_algorithm": r[2],
                                   "mtime": r[3], "size_bytes": r[4],
                                   "ctime": r[5], "status": r[6]}
                            for r in cur.fetchall()}

        def _close(a, b) -> bool:
            if not a and not b:
                return True
            try:
                return abs(float(a) - float(b or 0)) < 1e-6
            except (TypeError, ValueError):
                return False

        added, changed, unchanged = [], [], []
        seen = set()
        for it in items:
            rp = it["rel_path"]
            seen.add(rp)
            row = existing.get(rp)
            if row is None:
                added.append(rp)
                continue
            h1, h2 = row.get("file_hash") or "", it.get("file_hash") or ""
            hash_diff = bool(h1 and h2 and h1 != h2)
            stat_diff = (not _close(row.get("mtime"), it.get("mtime"))
                         or not _close(row.get("size_bytes"),
                                       it.get("size_bytes")))
            if hash_diff or stat_diff or row.get("status") == "stale_source":
                changed.append(rp)
            else:
                unchanged.append(rp)
        missing = [rp for rp in existing if rp not in seen]
        return {"added": added, "changed": changed,
                "missing": missing, "unchanged": unchanged}

    def upsert_folder_meta(self, schema_name: str, source_id, rel_path: str,
                           summary: str = "", description: str = "",
                           tags: list | None = None) -> None:
        """写入目录级智能描述（folder.json 富化回填用）。"""
        sid = uuid.UUID(str(source_id)) if source_id else LEGACY_SOURCE
        parent = rel_path.rsplit("/", 1)[0] if "/" in rel_path else ""
        name = rel_path.rsplit("/", 1)[-1]
        ident = sql.Identifier(schema_name)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "INSERT INTO {}.folders (source_id, rel_path, "
                    "parent_dir, name, summary, description, tags) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (source_id, rel_path) DO UPDATE SET "
                    "summary=EXCLUDED.summary, description=EXCLUDED.description, "
                    "tags=EXCLUDED.tags, updated_at=now()")
                    .format(ident),
                    (sid, rel_path, parent, name, summary, description,
                     tags or []))

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
