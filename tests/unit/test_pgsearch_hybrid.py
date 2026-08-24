"""R5-05 混合检索单测：RRF 融合纯函数 / jieba 预分词 / hybrid 透传。

覆盖（unit 层，不触真 PG）：
  - rrf_fuse：两路命中融合排序（重叠提升/单路/top-N 截断/k 值）；
  - _tokenize_for_ts / _tsquery_from_text：中文/英文/空/标点/max_terms；
  - PgStore.search hybrid 分支：关键词通道空 → 退化为纯向量；
    融合结果按 RRF 分值排序（mock _search_vector/keyword_search）；
  - PgSearchEngine：hybrid 透传 PgStore.search + engine 标注 'pg-hybrid'；
  - retrieval.ask hybrid：仅 PgSearchEngine 生效，其它索引忽略开关。
真 PG 的 keyword_search/索引存在性见 tests/integration/test_pgstore.py。
"""
import pytest

from naskb.common.pgstore import (
    PgStore, _tokenize_for_ts, _tsquery_from_text, rrf_fuse,
)
from naskb.common.pgsearch import PgSearchEngine
from naskb.common.retrieval import ask


# ── rrf_fuse ──

def _hit(rid, level="summary", **kw):
    h = {"resource_id": rid, "level": level, "path": f"p/{rid}",
         "kind": "file", "summary": f"摘要{rid}", "category": "类",
         "tags": [], "status": "ok", "text": "t", "context": "c",
         "stale": False, "score": 0.5, "chunk_seq": None,
         "title_path": [], "schema": "nas_x", "engine": "pg"}
    h.update(kw)
    return h


def test_rrf_fuse_overlap_ranks_higher():
    v = [_hit("A"), _hit("B"), _hit("C")]
    k = [_hit("B"), _hit("D")]
    merged = rrf_fuse(v, k, k=10)
    ids = [h["resource_id"] for h in merged]
    # B 两路命中 → 第一；A(rank0)=1/11 > D(rank1)=1/12 > C(rank2)=1/13
    assert ids == ["B", "A", "D", "C"]
    assert merged[0]["score"] > merged[1]["score"]
    assert merged[1]["score"] == pytest.approx(1 / 11)
    assert merged[2]["score"] == pytest.approx(1 / 12)
    assert merged[3]["score"] == pytest.approx(1 / 13)


def test_rrf_fuse_single_route_and_limit():
    merged = rrf_fuse([_hit("A", level="summary"), _hit("B")], [], limit=1)
    assert [h["resource_id"] for h in merged] == ["A"]
    merged2 = rrf_fuse([], [_hit("X"), _hit("Y")], limit=2)
    assert [h["resource_id"] for h in merged2] == ["X", "Y"]
    # 无 limit → 全量
    assert len(rrf_fuse([_hit("A"), _hit("B")], [], limit=None)) == 2


def test_rrf_fuse_distinguishes_level():
    """同 resource_id 不同 level（summary/chunk）独立融合，互不覆盖。"""
    merged = rrf_fuse([_hit("A", "summary")], [_hit("A", "chunk")])
    assert len(merged) == 2
    assert {h["level"] for h in merged} == {"summary", "chunk"}


# ── jieba 预分词 / tsquery ──

def test_tokenize_for_ts():
    assert _tokenize_for_ts("") == ""
    toks = _tokenize_for_ts("月租金为3200元 合同 租赁").split()
    assert len(toks) >= 3
    joined = "".join(toks)
    # 核心词保留（不依赖 jieba 具体切词粒度：月/租金/3200/合同/租赁 都应在）
    assert "租金" in joined and "3200" in joined
    assert "合同" in joined and "租赁" in joined
    # 英文/数字 token 保留（jieba 可能整词保留）
    assert any(t.startswith("ILCE") for t in _tokenize_for_ts("ILCE-6000 说明书").split())


def test_tsquery_from_text():
    assert _tsquery_from_text("") == ""
    assert _tsquery_from_text("   ") == ""
    q = _tsquery_from_text("月租金 多少")
    assert "|" in q and len(q) > 4
    # max_terms 截断
    many = _tsquery_from_text(" ".join(f"词{i}" for i in range(100)), max_terms=8)
    assert len(many.split("|")) == 8


# ── PgStore.search hybrid 分支（mock 内部两路通道）──

class _FakeStore:
    """轻量复用 PgStore.search 的 hybrid 编排（不构造真实 PgStore）。"""

    def __init__(self):
        self.store = object.__new__(PgStore)
        self.store._search_vector = self.search_vector
        self.store.keyword_search = self.keyword_search
        self.calls = []

    def search_vector(self, schema, vec, top_k=10, model=None,
                      source_ids=None, level="summary"):
        self.calls.append(("vec", top_k))
        return [_hit("A"), _hit("B"), _hit("C")][:top_k]

    def keyword_search(self, schema, text, top_k=50, model=None,
                       source_ids=None, level="summary"):
        self.calls.append(("kw", text, top_k))
        return [_hit("B"), _hit("D")] if text else []


def test_pgstore_search_hybrid_fuses_and_truncates():
    fs = _FakeStore()
    hits = fs.store.search("s", [0.1], top_k=2, hybrid=True,
                           keyword_query="月租金")
    assert len(hits) == 2
    assert hits[0]["resource_id"] == "B"   # 两路命中 → 第一
    assert fs.calls[0][0] == "vec" and fs.calls[1][0] == "kw"


def test_pgstore_search_hybrid_empty_keyword_falls_back_to_vector():
    fs = _FakeStore()
    hits = fs.store.search("s", [0.1], top_k=3, hybrid=True, keyword_query="")
    # 关键词空 → 该路无命中 → 退化为纯向量（全部返回，顺序=向量路）
    assert [h["resource_id"] for h in hits] == ["A", "B", "C"]


def test_pgstore_search_non_hybrid_skips_keyword_channel():
    fs = _FakeStore()
    hits = fs.store.search("s", [0.1], top_k=2, hybrid=False)
    assert len(hits) == 2
    assert all(c[0] == "vec" for c in fs.calls)  # 不含 kw 通道


# ── PgSearchEngine 透传 + engine 标记 ──

class _FakeEmb:
    def encode_one(self, q):
        return [0.1, 0.2]

    def close(self):
        pass


class _FakePg:
    def __init__(self, rows):
        self.rows = rows
        self.kw = None

    def list_nas(self):
        return [{"schema_name": "nas_x"}]

    def search(self, schema, vec, top_k=10, model=None, level="summary",
               hybrid=False, keyword_query=None,
               keyword_top_k=50, rrf_k=60):
        self.kw = keyword_query
        self.hybrid = hybrid
        return self.rows


def _engine(rows):
    e = PgSearchEngine.__new__(PgSearchEngine)
    e._emb = _FakeEmb()
    e._pg = _FakePg(rows)
    e._default_schema = None
    return e


def test_pgsearch_hybrid_passthrough_and_engine_tag():
    rows = [_hit("A", score=0.9), _hit("B", score=0.7)]
    e = _engine(rows)
    hits = e.search("月租金是多少", top_k=2, hybrid=True)
    assert e._pg.hybrid is True
    assert e._pg.kw == "月租金是多少"
    assert hits[0]["engine"] == "pg-hybrid"
    # 非 hybrid：不开启
    e2 = _engine(rows)
    hits2 = e2.search("月租金是多少", top_k=2)
    assert hits2[0]["engine"] == "pg"


# ── retrieval.ask hybrid 分支 ──

class _FakeLlm:
    def __init__(self):
        self.calls = []

    def complete(self, prompt):
        self.calls.append(prompt)
        return "ANSWER"


def test_ask_hybrid_only_for_pg_engine():
    llm = _FakeLlm()
    rows = [_hit("A"), _hit("B")]
    e = _engine(rows)
    res = ask(llm, e, "月租金是多少", top_k=2, hybrid=True)
    assert res["answer"] == "ANSWER"
    assert e._pg.hybrid is True
    assert res["sources"] == ["p/A", "p/B"]


def test_ask_hybrid_ignored_for_bm25_index():
    class _Idx:
        def search(self, q, top_k=5, **kw):
            raise AssertionError("BM25 索引不应收到 hybrid 参数")

    llm = _FakeLlm()
    # ask 对非 PgSearchEngine 走 index.search(question, top_k=top_k)（无 hybrid）
    idx = _Idx()
    with pytest.raises(AssertionError):
        ask(llm, idx, "q", hybrid=True)
