"""ask_deep 单测（REQ-R5-06）：两级引用/保真直返/无命中兜底。纯离线（假 searcher/假 llm）。"""
from naskb.common.retrieval import ask_deep


class _FakeSearcher:
    def __init__(self, hits):
        self._hits = hits
        self.calls = []

    def search_chunks(self, q, top_k=None):
        self.calls.append((q, top_k))
        return self._hits


class _FakeLLM:
    def __init__(self, answer="生成答案"):
        self._answer = answer
        self.calls = []

    def complete(self, prompt):
        self.calls.append(prompt)
        return self._answer


def _hit(path="D:/标准.pdf", title=None, score=0.7, text="条款正文",
         context="条款正文完整内容"):
    return {"path": path, "kind": "file", "level": "chunk",
            "chunk_seq": 2, "title_path": title or ["第6章", "6.3.2"],
            "text": text, "context": context, "score": score,
            "status": "ok", "stale": False, "engine": "pg", "schema": "s"}


def test_rag_mode_two_level_citation():
    searcher = _FakeSearcher([_hit(), _hit(path="D:/规范.pdf",
                                           title=["第3章", "3.1"],
                                           score=0.6)])
    llm = _FakeLLM("按条款 6.3.2 执行。")
    r = ask_deep(llm, searcher, "保压多久？", top_k=2)
    assert r["mode"] == "rag"
    assert r["answer"] == "按条款 6.3.2 执行。"
    assert llm.calls                       # 调了 LLM
    assert set(r["sources"]) == {"D:/标准.pdf", "D:/规范.pdf"}
    assert r["citations"][0]["title_path"] == ["第6章", "6.3.2"]
    assert r["citations"][0]["chunk_seq"] == 2
    assert "6.3.2" in llm.calls[0]          # 提示词带条款路径
    assert r["engine"] == "pg-chunk"


def test_direct_return_skips_llm():
    searcher = _FakeSearcher([_hit(score=0.95)])
    llm = _FakeLLM("不应被调用")
    r = ask_deep(llm, searcher, "6.3.2 保压时间", direct_return=True,
                 direct_return_similarity=0.9)
    assert r["mode"] == "direct"
    assert r["answer"] == "条款正文完整内容"      # 直接返回原文
    assert not llm.calls                         # 未调 LLM
    assert r["sources"] == ["D:/标准.pdf"]
    assert r["score"] == 0.95


def test_no_hit_designated_default():
    searcher = _FakeSearcher([])
    llm = _FakeLLM()
    r = ask_deep(llm, searcher, "不存在的问题")
    assert r["mode"] == "no_hit_designated"
    assert "未找到" in r["answer"]
    assert r["sources"] == [] and r["citations"] == []
    assert not llm.calls


def test_no_hit_llm_fallback():
    searcher = _FakeSearcher([])
    llm = _FakeLLM("基于常识作答。")
    r = ask_deep(llm, searcher, "问题", no_hit_mode="llm_fallback")
    assert r["mode"] == "no_hit_fallback"
    assert r["answer"] == "基于常识作答。"
    assert llm.calls


def test_low_score_no_direct_return():
    # 低于阈值 → 走 rag（即使 direct_return=True）
    searcher = _FakeSearcher([_hit(score=0.6)])
    llm = _FakeLLM("生成")
    r = ask_deep(llm, searcher, "x", direct_return=True,
                 direct_return_similarity=0.9)
    assert r["mode"] == "rag"
    assert llm.calls
