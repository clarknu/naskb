"""语义向量索引 — bge-small-zh 嵌入 + numpy 余弦检索。

与 BM25Index 输出同构（{score, path, kind, summary, category, tags, text}），
desc search / desc ask 可在两者间无缝切换（有索引用向量，无则 BM25）。
索引持久化于工作区 db/vectors.npz + vectors.json。
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import numpy as np

from .embeddings import Embedder
from .retrieval import Doc

_BATCH = 64


def index_paths(work_path: str) -> tuple[str, str]:
    db = os.path.join(work_path, "db")
    return (os.path.join(db, "vectors.npz"),
            os.path.join(db, "vectors.json"))


class VectorIndex:
    """构建/加载/检索语义向量索引（余弦相似度，纯 numpy）。"""

    def __init__(self, embedder: Embedder, work_path: str):
        self._embed = embedder
        self._npz, self._json = index_paths(work_path)
        self._mat: Optional[np.ndarray] = None
        self._meta: dict[str, Any] = {}

    # ── 构建 / 持久化 ──

    def build(self, docs: list[Doc]) -> int:
        """编码全部文档并持久化，返回文档数。"""
        texts = [d.text for d in docs]
        chunks = [texts[i:i + _BATCH] for i in range(0, len(texts), _BATCH)]
        mats = [self._embed.encode(c) for c in chunks]
        self._mat = np.vstack(mats) if mats else np.zeros((0, 512))
        self._meta = {
            "paths": [d.path for d in docs],
            "kinds": [d.kind for d in docs],
            "summaries": [d.summary for d in docs],
            "categories": [d.category for d in docs],
            "tags": [d.tags for d in docs],
            "texts": [d.text for d in docs],
            "contexts": [d.context for d in docs],
        }
        os.makedirs(os.path.dirname(self._npz), exist_ok=True)
        np.savez_compressed(self._npz, mat=self._mat)
        with open(self._json, "w", encoding="utf-8") as f:
            json.dump(self._meta, f, ensure_ascii=False)
        return len(docs)

    # ── 加载 ──

    def exists(self) -> bool:
        return os.path.isfile(self._npz) and os.path.isfile(self._json)

    def load(self) -> bool:
        """加载已有索引；不存在或损坏返回 False。"""
        try:
            if not self.exists():
                return False
            data = np.load(self._npz, allow_pickle=False)
            self._mat = data["mat"]
            with open(self._json, encoding="utf-8") as f:
                self._meta = json.load(f)
            # 兼容旧索引（无 contexts 字段）
            self._meta.setdefault("contexts", [""] * len(self._meta.get("paths", [])))
            return len(self._meta.get("paths", [])) == len(self._mat)
        except Exception:
            return False

    # ── 检索 ──

    def search(self, query: str, top_k: int = 10,
               kind: Optional[str] = None) -> list[dict]:
        """余弦相似度 top-k，返回与 BM25Index.search 同构的结果列表。"""
        if self._mat is None:
            return []
        q = self._embed.encode_one(query)
        sims = self._mat @ q
        order = np.argsort(-sims)
        out: list[dict] = []
        for i in order:
            if kind and self._meta["kinds"][i] != kind:
                continue
            out.append({
                "score": float(sims[i]),
                "path": self._meta["paths"][i],
                "kind": self._meta["kinds"][i],
                "summary": self._meta["summaries"][i],
                "category": self._meta["categories"][i],
                "tags": self._meta["tags"][i],
                "text": self._meta["texts"][i],
                "context": self._meta["contexts"][i],
            })
            if len(out) >= top_k:
                break
        return out

    def count(self) -> int:
        return len(self._meta.get("paths", []))

    def paths(self) -> list[str]:
        """索引覆盖的文档路径列表（用于与当前文档集合比对，判断陈旧）。"""
        return list(self._meta.get("paths", []))

    def remap_paths(self, mapping: dict[str, str]) -> int:
        """按映射 {旧路径: 新路径} 重写索引中的 paths 字段，返回受影响条数。

        仅重写 vectors.json（向量矩阵不变：移动不改 summary 文本 → 向量
        不变，无需重新嵌入）。映射键按 normcase+normpath 规范化匹配
        （Windows 大小写不敏感）。索引未加载时返回 0。
        """
        if self._mat is None:
            return 0
        paths = self._meta.get("paths", [])
        norm = {os.path.normcase(os.path.normpath(k)): v
                for k, v in (mapping or {}).items()}
        changed = 0
        for i, p in enumerate(paths):
            key = os.path.normcase(os.path.normpath(p))
            if key in norm and norm[key] != p:
                paths[i] = norm[key]
                changed += 1
        if changed:
            with open(self._json, "w", encoding="utf-8") as f:
                json.dump(self._meta, f, ensure_ascii=False)
        return changed
