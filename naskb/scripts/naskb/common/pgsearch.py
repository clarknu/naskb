"""pgsearch — PG 向量检索引擎（REQ-R4-12/13）。

实现与 BM25Index / VectorIndex 同构的 search(query, top_k) 接口，
返回结构含 path/summary/category/tags/text/context/score ——
`retrieval.ask` 零改动复用；serve 后端选择链：pg → numpy 向量 → BM25。
"""
from __future__ import annotations

from typing import Optional

from .embeddings import Embedder
from .pgstore import EMBEDDING_MODEL, PgStore


class PgSearchEngine:
    """PG + pgvector 检索：查询嵌入 → 余弦 top-k（HNSW 索引）。"""

    def __init__(self, pg: PgStore, work_path: str,
                 default_schema: Optional[str] = None):
        self._pg = pg
        self._emb = Embedder(work_path)
        self._default_schema = default_schema

    def close(self) -> None:
        self._emb.close()

    def search(self, query: str, top_k: int = 10,
               kind: Optional[str] = None,
               schema: Optional[str] = None) -> list[dict]:
        """语义检索指定 NAS schema；返回与 BM25Index.search 同构的结果。

        schema 缺省依次用：默认 schema（构造时绑定）→ 注册表第一条。
        """
        schema = schema or self._default_schema
        if schema is None:
            nas_list = self._pg.list_nas()
            if not nas_list:
                return []
            schema = nas_list[0]["schema_name"]
        vec = self._emb.encode_one(query)
        rows = self._pg.search(schema, vec, top_k=top_k, model=EMBEDDING_MODEL)
        hits = []
        for r in rows:
            if kind and r["kind"] != kind:
                continue
            hits.append({
                "score": float(r["score"]),
                "path": r["path"],
                "kind": r["kind"],
                "summary": r["summary"],
                "category": r["category"],
                "tags": list(r["tags"] or []),
                "text": r["text"],        # summary_text（检索索引文本）
                "context": r["context"],  # full_text（RAG 上下文）
                "status": r["status"],
                "stale": r["stale"],
                "engine": "pg",
                "schema": schema,
            })
        return hits

    def nas_options(self) -> list[dict]:
        """供 serve 前端下拉：已注册 NAS 清单（含 alias 提示与统计）。"""
        out = []
        for nas in self._pg.list_nas():
            try:
                stats = self._pg.nas_stats(nas["schema_name"])
            except Exception:
                stats = None
            out.append({
                "schema": nas["schema_name"],
                "label": nas["label"] or (
                    f"{nas['protocol']}://{nas['host']}:{nas['port']}"
                    + (f" ({nas['username']})" if nas["username"] else "")),
                "resources": (stats or {}).get("resources"),
                "vectors": (stats or {}).get("vectors"),
            })
        return out
