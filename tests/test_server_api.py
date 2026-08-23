"""平台服务 API 测试（无 PG 路径）：旧契约形状、认证、来源 CRUD。"""
import pytest
from fastapi.testclient import TestClient


class _Cfg:
    def __init__(self, work_path, tokens=None, anon=True):
        self.work_path = str(work_path)
        self.pg_enabled = False
        self.llm_text = None
        self.server_tokens = list(tokens or [])
        self.anonymous_read = anon


@pytest.fixture()
def open_client(tmp_path):
    from naskb.server.app import create_app
    app = create_app(_Cfg(tmp_path))
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def locked_client(tmp_path):
    from naskb.server.app import create_app
    app = create_app(_Cfg(tmp_path, tokens=["t0ken"], anon=True))
    with TestClient(app) as c:
        yield c


class TestLegacyContract:
    """ADR-20260816-2 冻结契约：形状与 stdlib serve 一致。"""

    def test_search_missing_q_400_shape(self, open_client):
        r = open_client.get("/api/search")
        assert r.status_code == 400
        assert r.json() == {"error": "缺少查询参数 q"}

    def test_search_success_shape(self, open_client):
        r = open_client.get("/api/search", params={"q": "合同"})
        assert r.status_code == 200
        d = r.json()
        assert set(d.keys()) >= {"query", "engine", "hits",
                                 "total_docs", "nas"}
        assert isinstance(d["hits"], list)

    def test_ask_missing_question_400_shape(self, open_client):
        r = open_client.post("/api/ask", json={})
        assert r.status_code == 400
        assert r.json() == {"error": "缺少 question 字段"}

    def test_stats_shape(self, open_client):
        d = open_client.get("/api/stats").json()
        assert {"engine", "docs", "pg", "nas_options"} <= set(d.keys())

    def test_reload_empty_library(self, open_client):
        d = open_client.post("/api/reload").json()
        assert d["ok"] is False       # 空库提示（不炸）


class TestSourceCrud:
    def _payload(self, **kw):
        p = dict(alias="home", protocol="local",
                 root_path="C:/tmp/x", access_mode="ro")
        p.update(kw)
        return p

    def test_create_list_mask_delete(self, open_client):
        r = open_client.post("/api/sources",
                             json=self._payload(password="pw123"))
        assert r.status_code == 200
        sid = r.json()["source"]["source_id"]
        lst = open_client.get("/api/sources").json()["sources"]
        assert len(lst) == 1
        assert lst[0]["password"] == "******"          # API 输出脱敏
        r2 = open_client.patch(f"/api/sources/{sid}",
                               json={"enabled": False, "label": "x"})
        assert r2.json()["source"]["enabled"] is False
        r3 = open_client.delete(f"/api/sources/{sid}")
        assert r3.json()["deleted"] is True
        assert open_client.get("/api/sources").json()["sources"] == []

    def test_duplicate_alias_422(self, open_client):
        open_client.post("/api/sources", json=self._payload())
        r = open_client.post("/api/sources", json=self._payload())
        assert r.status_code == 422

    def test_bad_protocol_422(self, open_client):
        r = open_client.post(
            "/api/sources", json=self._payload(protocol="ftp"))
        assert r.status_code == 422

    def test_files_require_pg(self, open_client):
        r = open_client.post("/api/sources", json=self._payload())
        sid = r.json()["source"]["source_id"]
        rr = open_client.get(f"/api/files/{sid}", params={"src": sid})
        assert rr.status_code == 400
        assert "[pg]" in rr.json()["detail"]

    def test_kb_search_fallback_bm25(self, open_client):
        d = open_client.get("/api/kb/search",
                            params={"query": "任意"}).json()
        assert d["engine"] == "bm25"
        assert "hint" in d

    def test_openapi_available(self, open_client):
        assert open_client.get("/api/openapi.json").status_code == 200


class TestAuth:
    def test_anonymous_read_allowed(self, locked_client):
        # 匿名只读：stats 开放；sources 列表需要 token
        assert locked_client.get("/api/stats").status_code == 200
        assert locked_client.get("/api/sources").status_code == 401

    def test_bearer_grants_admin(self, locked_client):
        h = {"Authorization": "Bearer t0ken"}
        assert locked_client.get("/api/sources", headers=h).status_code == 200
        assert locked_client.post("/api/reload", headers=h).status_code == 200

    def test_wrong_token_rejected(self, locked_client):
        h = {"Authorization": "Bearer wrong"}
        assert locked_client.get("/api/sources", headers=h).status_code == 401

    def test_anonymous_off_locks_reads(self, tmp_path):
        from naskb.server.app import create_app
        app = create_app(_Cfg(tmp_path, tokens=["t"], anon=False))
        with TestClient(app) as c:
            assert c.get("/api/stats").status_code == 401
            h = {"Authorization": "Bearer t"}
            assert c.get("/api/stats", headers=h).status_code == 200

    def test_public_config(self, locked_client):
        d = locked_client.get("/api/config/public").json()
        assert d["auth_required"] is True and d["anonymous_read"] is True
