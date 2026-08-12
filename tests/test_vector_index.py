"""语义向量索引测试（mock embedding，不依赖真实模型）。"""
import numpy as np
import pytest

from naskb.common.retrieval import Doc
from naskb.common.vector_index import VectorIndex


class _FakeEmbedder:
    """确定性伪嵌入：按共享关键词（身份/护照/装修/雅思…）构造稀疏向量，
    语义相近（共享词）的文本向量余弦相似度高。"""

    _WORDS = ["身份", "护照", "证件", "装修", "预算", "雅思", "笔记", "学习", "财务"]

    def __init__(self):
        self.calls = 0

    def _vec(self, text: str) -> np.ndarray:
        v = np.array([1.0 if w in text else 0.0 for w in self._WORDS])
        n = np.linalg.norm(v)
        return v / n if n else v

    def encode(self, texts):
        self.calls += 1
        return np.vstack([self._vec(t) for t in texts])

    def encode_one(self, text):
        return self._vec(text)

    def close(self):
        pass


def _docs():
    return [
        Doc(path="/a/身份证.pdf", kind="file", text="居民身份证正反面扫描件",
            summary="身份证", category="证件"),
        Doc(path="/b/护照.pdf", kind="file", text="因私护照信息页",
            summary="护照", category="证件"),
        Doc(path="/c/装修预算.xlsx", kind="file", text="装修预算与材料清单",
            summary="装修预算", category="财务"),
        Doc(path="/d/雅思笔记.md", kind="file", text="雅思口语学习笔记",
            summary="雅思笔记", category="学习"),
    ]


class TestVectorIndex:
    def test_build_and_load(self, tmp_path):
        emb = _FakeEmbedder()
        idx = VectorIndex(emb, str(tmp_path))
        n = idx.build(_docs())
        assert n == 4
        # 持久化后可重新加载
        idx2 = VectorIndex(_FakeEmbedder(), str(tmp_path))
        assert idx2.load()
        assert idx2.count() == 4

    def test_search_semantic_ranking(self, tmp_path):
        emb = _FakeEmbedder()
        idx = VectorIndex(emb, str(tmp_path))
        idx.build(_docs())
        hits = idx.search("身份证", top_k=4)
        # 语义召回：查询与"身份证.pdf"共享"身份"词 → 排第一
        assert hits[0]["path"].endswith("身份证.pdf")
        assert hits[0]["score"] > hits[1]["score"]

    def test_search_kind_filter(self, tmp_path):
        emb = _FakeEmbedder()
        idx = VectorIndex(emb, str(tmp_path))
        idx.build(_docs())
        hits = idx.search("笔记", top_k=10, kind="file")
        assert all(h["kind"] == "file" for h in hits)
        assert any(h["path"].endswith("雅思笔记.md") for h in hits)

    def test_output_shape_matches_bm25(self, tmp_path):
        """输出字段与 BM25Index.search 同构（供 RAG 无缝切换）。"""
        emb = _FakeEmbedder()
        idx = VectorIndex(emb, str(tmp_path))
        idx.build(_docs())
        hits = idx.search("护照", top_k=1)
        assert set(hits[0].keys()) == {
            "score", "path", "kind", "summary", "category", "tags", "text",
            "context"}

    def test_missing_index_falls_back(self, tmp_path):
        idx = VectorIndex(_FakeEmbedder(), str(tmp_path))
        assert not idx.exists()
        assert idx.search("x") == []
