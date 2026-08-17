"""naskb desc serve — 内置知识库服务测试（检索/问答内核 + HTTP 接口）。"""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from naskb.common.desc_store import FileEntry, NaskbStore
from naskb.common.fs.local import LocalAdapter
from naskb.common.retrieval import collect_docs
from naskb.common.serve import KnowledgeCore, _Handler


# ── fixtures ──

@pytest.fixture
def repo_dir(tmp_path):
    """构造 .naskb 描述仓库：两个文件各一条描述。"""
    root = tmp_path / "kb"
    d1 = root / "影视"
    d2 = root / "学习"
    d1.mkdir(parents=True)
    d2.mkdir(parents=True)
    (d1 / "星际穿越.mkv").write_bytes(b"fake video")
    (d2 / "机器学习笔记.pdf").write_bytes(b"%PDF fake")
    fs = LocalAdapter(str(root))
    store = NaskbStore(fs)
    store.set_entry(str(d1 / "星际穿越.mkv"), FileEntry(
        original_path="星际穿越.mkv",
        summary="诺兰科幻电影，时间旅行",
        category="影视", tags=["电影", "科幻"]))
    store.set_entry(str(d2 / "机器学习笔记.pdf"), FileEntry(
        original_path="机器学习笔记.pdf",
        summary="深度神经网络基础课程笔记",
        category="学习", tags=["AI", "课程"]))
    return root


class _FakeChat:
    def __init__(self):
        self.closed = False

    def complete(self, prompt: str) -> str:
        return "根据描述，星际穿越是诺兰的科幻电影。"

    def close(self):
        self.closed = True


class _FakePgEngine:
    """最小 PgSearchEngine 替身：search 返回同构 hits（可配置抛异常）。"""

    def __init__(self, hits=None, fail=False):
        self._hits = hits or [{
            "score": 0.95, "path": "/pg/远程文件.pdf", "kind": "file",
            "summary": "PG 库中的摘要", "category": "PG分类",
            "tags": ["pg"], "text": "PG 索引文本", "context": "PG 全文",
            "status": "ok", "stale": False, "engine": "pg",
        }]
        self.fail = fail
        self.closed = False

    def search(self, query, top_k=10, kind=None, schema=None):
        if self.fail:
            raise RuntimeError("pg down")
        return self._hits

    def nas_options(self):
        return [{"schema": "nas_test", "label": "test NAS"}]

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _no_vector(monkeypatch):
    """禁用真实 Embedder（避免测试触发模型下载），强制 BM25 路径。"""
    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("disabled in tests")
    monkeypatch.setattr("naskb.common.embeddings.Embedder", _Boom)


def _make_core(tmp_path, repo_dir, llm=None):
    fs = LocalAdapter(str(repo_dir))
    core = KnowledgeCore(str(tmp_path / "work"),
                         lambda: collect_docs(fs, "."))
    core.load(collect_docs(fs, "."))
    if llm is not None:
        core.set_llm(llm)
    return core, fs


# ── 内核单元测试 ──

class TestCore:
    def test_load_falls_back_to_bm25(self, tmp_path, repo_dir):
        core, fs = _make_core(tmp_path, repo_dir)
        s = core.stats()
        assert s["engine"] == "bm25"
        assert s["docs"] == 2
        assert not s["vector_stale"]

    def test_search(self, tmp_path, repo_dir):
        core, fs = _make_core(tmp_path, repo_dir)
        engine, hits = core.search("科幻", top_k=5)
        assert engine == "bm25"
        assert hits and "星际穿越" in hits[0]["path"]

    def test_ask_returns_answer_and_sources(self, tmp_path, repo_dir):
        core, fs = _make_core(tmp_path, repo_dir, llm=_FakeChat())
        result = core.ask("星际穿越是谁拍的？")
        assert "诺兰" in result["answer"]
        assert any("星际穿越" in s for s in result["sources"])
        assert result["engine"] == "bm25"

    def test_ask_without_llm_returns_error(self, tmp_path, repo_dir):
        core, fs = _make_core(tmp_path, repo_dir, llm=None)
        result = core.ask("任意问题")
        assert result["error"]
        assert "LLM" in result["error"]

    def test_reload_refreshes_docs(self, tmp_path, repo_dir):
        core, fs = _make_core(tmp_path, repo_dir)
        # 新增一个文件及其描述
        d3 = repo_dir / "生活"
        d3.mkdir()
        (d3 / "装修预算.xlsx").write_bytes(b"x")
        store = NaskbStore(fs)
        store.set_entry(str(d3 / "装修预算.xlsx"), FileEntry(
            original_path="装修预算.xlsx",
            summary="装修预算明细表",
            category="生活", tags=["装修"]))
        result = core.reload()
        assert result["ok"] is True
        assert result["docs"] == 3
        engine, hits = core.search("装修", top_k=5)
        assert hits and "装修预算" in hits[0]["path"]

    def test_vector_stale_falls_back_to_bm25(self, tmp_path, repo_dir, monkeypatch):
        """向量索引与当前文档集合不一致 → 标记陈旧并降级 BM25。"""
        class _FakeEmb:
            def __init__(self, *a, **k):
                pass

            def close(self):
                pass

        class _StaleVector:
            def __init__(self, emb, work_path):
                pass

            def load(self):
                return True

            def paths(self):
                return ["/其它root/旧文件.md"]  # 与当前 docs 不一致

            def count(self):
                return 1

        monkeypatch.setattr("naskb.common.embeddings.Embedder", _FakeEmb)
        monkeypatch.setattr("naskb.common.vector_index.VectorIndex", _StaleVector)
        core, fs = _make_core(tmp_path, repo_dir)
        s = core.stats()
        assert s["engine"] == "bm25"
        assert s["vector_stale"] is True

    def test_vector_fresh_used(self, tmp_path, repo_dir, monkeypatch):
        """向量索引与当前文档集合一致 → 使用向量引擎。"""
        class _FakeEmb:
            def __init__(self, *a, **k):
                pass

            def close(self):
                pass

        class _FreshVector:
            def __init__(self, emb, work_path):
                pass

            def load(self):
                return True

            def paths(self):
                fs = LocalAdapter(str(repo_dir))
                return [d.path for d in collect_docs(fs, ".")]

            def count(self):
                return 2

            def search(self, query, top_k=10, kind=None):
                return []

        monkeypatch.setattr("naskb.common.embeddings.Embedder", _FakeEmb)
        monkeypatch.setattr("naskb.common.vector_index.VectorIndex", _FreshVector)
        core, fs = _make_core(tmp_path, repo_dir)
        s = core.stats()
        assert s["engine"] == "vector"
        assert s["vector_count"] == 2
        assert not s["vector_stale"]


class TestCorePg:
    """PG 后端：nas 选择、失败回退、stats 带 nas_options（REQ-R4-12/13）。"""

    def _core_with_pg(self, tmp_path, repo_dir, pg_engine):
        fs = LocalAdapter(str(repo_dir))
        core = KnowledgeCore(str(tmp_path / "work"),
                             lambda: collect_docs(fs, "."),
                             pg_engine=pg_engine)
        core.load(collect_docs(fs, "."))
        core.set_llm(_FakeChat())
        return core

    def test_search_pg_when_nas_given(self, tmp_path, repo_dir):
        core = self._core_with_pg(tmp_path, repo_dir, _FakePgEngine())
        engine, hits = core.search("任意", nas_schema="nas_test")
        assert engine == "pg"
        assert hits and hits[0]["path"] == "/pg/远程文件.pdf"

    def test_search_local_when_no_nas(self, tmp_path, repo_dir):
        core = self._core_with_pg(tmp_path, repo_dir, _FakePgEngine())
        engine, hits = core.search("科幻")
        assert engine == "bm25"   # 无 nas → 本地引擎
        assert any("星际穿越" in h["path"] for h in hits)

    def test_search_fallback_when_pg_fails(self, tmp_path, repo_dir):
        core = self._core_with_pg(tmp_path, repo_dir,
                                  _FakePgEngine(fail=True))
        engine, hits = core.search("科幻", nas_schema="nas_test")
        assert engine == "bm25"   # PG 失败 → 自动回退本地
        assert hits

    def test_ask_pg_uses_pg_context(self, tmp_path, repo_dir):
        core = self._core_with_pg(tmp_path, repo_dir, _FakePgEngine())
        result = core.ask("问题", nas_schema="nas_test")
        assert result["engine"] == "pg"
        assert result["sources"] == ["/pg/远程文件.pdf"]

    def test_ask_fallback_when_pg_fails(self, tmp_path, repo_dir):
        core = self._core_with_pg(tmp_path, repo_dir,
                                  _FakePgEngine(fail=True))
        result = core.ask("星际穿越是谁拍的？", nas_schema="nas_test")
        assert result["engine"] == "bm25"
        assert "诺兰" in result["answer"]

    def test_stats_lists_nas_options(self, tmp_path, repo_dir):
        core = self._core_with_pg(tmp_path, repo_dir, _FakePgEngine())
        s = core.stats()
        assert s["pg"] is True
        assert s["nas_options"] == [{"schema": "nas_test",
                                     "label": "test NAS"}]


# ── HTTP 集成测试 ──

@pytest.fixture
def http_url(tmp_path, repo_dir):
    """起真实 HTTP 服务（随机端口），返回 base URL。"""
    core, fs = _make_core(tmp_path, repo_dir, llm=_FakeChat())
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.naskb_core = core
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", core
    httpd.shutdown()
    httpd.server_close()


def _get(url):
    from urllib.error import HTTPError
    try:
        with urlopen(url, timeout=10) as r:
            return r.status, r.read(), r.headers
    except HTTPError as e:
        return e.code, e.read(), e.headers


def _post(url, payload):
    from urllib.error import HTTPError
    req = Request(url, data=json.dumps(payload).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except HTTPError as e:
        return e.code, e.read()


class TestHttp:
    def test_index_page(self, http_url):
        base, core = http_url
        status, body, headers = _get(base + "/")
        assert status == 200
        assert "text/html" in headers["Content-Type"]
        assert "NASKB" in body.decode("utf-8")

    def test_stats(self, http_url):
        base, core = http_url
        status, body, _headers = _get(base + "/api/stats")
        data = json.loads(body)
        assert status == 200
        assert data["engine"] == "bm25"
        assert data["docs"] == 2

    def test_search(self, http_url):
        base, core = http_url
        status, body, _h = _get(base + "/api/search?q=%E7%A7%91%E5%B9%BB")
        data = json.loads(body)
        assert status == 200
        assert data["engine"] == "bm25"
        assert data["hits"] and "星际穿越" in data["hits"][0]["path"]

    def test_search_missing_query(self, http_url):
        base, core = http_url
        status, body, _h = _get(base + "/api/search")
        assert status == 400

    def test_ask(self, http_url):
        base, core = http_url
        status, body = _post(base + "/api/ask",
                             {"question": "星际穿越是谁拍的？"})
        data = json.loads(body)
        assert status == 200
        assert "诺兰" in data["answer"]
        assert any("星际穿越" in s for s in data["sources"])

    def test_ask_without_llm(self, tmp_path, repo_dir):
        core, fs = _make_core(tmp_path, repo_dir, llm=None)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        httpd.naskb_core = core
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            base = f"http://127.0.0.1:{httpd.server_address[1]}"
            status, body = _post(base + "/api/ask", {"question": "测试"})
            data = json.loads(body)
            assert status == 200
            assert data["error"]
            assert "LLM" in data["error"]
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_reload(self, http_url):
        base, core = http_url
        status, body = _post(base + "/api/reload", {})
        data = json.loads(body)
        assert status == 200
        assert data["ok"] is True
        assert data["docs"] == 2

    def test_unknown_route_404(self, http_url):
        base, core = http_url
        status, body, _h = _get(base + "/api/nope")
        assert status == 404
