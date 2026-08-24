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


class TestKbAsk:
    """深度条款问答端点（REQ-R5-06）；无 PG/LLM 时降级或明确报错。"""

    def test_missing_question_400(self, open_client):
        r = open_client.post("/api/kb/ask", json={})
        assert r.status_code == 400

    def test_no_llm_503(self, open_client):
        # 无 [llm.text] → 明确返回 503（不静默）
        r = open_client.post("/api/kb/ask", json={"question": "保压多久"})
        assert r.status_code == 503


class TestSourceChangesGuard:
    """确认清单差分端点：无 [pg] 时明确 400（不静默）。"""

    def test_changes_requires_pg(self, open_client):
        r = open_client.get("/api/sources/nonexist/changes")
        assert r.status_code == 400
        assert "pg" in r.json()["detail"]

    def test_confirm_requires_pg(self, open_client):
        r = open_client.post("/api/sources/nonexist/confirm", json={"rel_paths": []})
        assert r.status_code == 400

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
    def test_anon_exceptions_only(self, locked_client):
        # DD-009 匿名移除：仅引导端点/直链匿名；业务端点一律 401
        assert locked_client.get("/api/stats").status_code == 401
        assert locked_client.get("/api/sources").status_code == 401
        assert locked_client.get("/api/kb/search",
                                 params={"query": "x"}).status_code == 401
        assert locked_client.get("/api/config/public").status_code == 200
        assert locked_client.get("/api/openapi.json").status_code == 200

    def test_bearer_grants_admin(self, locked_client):
        h = {"Authorization": "Bearer t0ken"}
        assert locked_client.get("/api/sources", headers=h).status_code == 200
        assert locked_client.post("/api/reload", headers=h).status_code == 200

    def test_wrong_token_rejected(self, locked_client):
        h = {"Authorization": "Bearer wrong"}
        assert locked_client.get("/api/sources", headers=h).status_code == 401

    def test_no_tokens_open_mode(self, tmp_path):
        # 未配置 tokens = 本机开放模式（enabled=False 全放行）
        from naskb.server.app import create_app
        app = create_app(_Cfg(tmp_path, tokens=[], anon=False))
        with TestClient(app) as c:
            assert c.get("/api/stats").status_code == 200

    def test_public_config(self, locked_client):
        d = locked_client.get("/api/config/public").json()
        assert d["auth_required"] is True and d["anonymous_read"] is False


class TestDd009Endpoints:
    """DD-009 拍板批次回归：report 接回 / folder 端点 / deep 关闭钩子（无 PG 路径）。"""

    def _src(self, client, tmp_path):
        root = tmp_path / "src"
        root.mkdir()
        (root / "a.txt").write_text("hello", encoding="utf-8")
        r = client.post("/api/sources?test=true", json={
            "alias": "dd009-src", "protocol": "local", "access_mode": "ro",
            "root_path": str(root)})
        assert r.status_code == 200, r.text
        return r.json()["source"]["source_id"]

    def test_report_endpoint_restored(self, open_client, tmp_path):
        sid = self._src(open_client, tmp_path)
        r = open_client.get(f"/api/sources/{sid}/report")
        assert r.status_code == 200
        d = r.json()
        assert set(d.keys()) >= {"source", "backend"}
        assert d["source"]["alias"] == "dd009-src"
        assert d["backend"] in ("pg", "json")

    def test_report_404(self, open_client):
        assert open_client.get(
            "/api/sources/00000000-0000-0000-0000-000000000000/report"
        ).status_code == 404

    def test_folder_endpoint_requires_pg(self, open_client, tmp_path):
        sid = self._src(open_client, tmp_path)
        r = open_client.get("/api/folder", params={"src": sid, "dir": ""})
        assert r.status_code == 400
        assert "pg" in r.json()["detail"]

    def test_deep_toggle_no_pg_cleanup_skipped(self, open_client, tmp_path):
        sid = self._src(open_client, tmp_path)
        r = open_client.patch(f"/api/sources/{sid}", json={"deep": True})
        assert r.status_code == 200 and r.json()["source"]["deep"] is True
        r2 = open_client.patch(f"/api/sources/{sid}", json={"deep": False})
        assert r2.status_code == 200
        d = r2.json()
        assert d["source"]["deep"] is False
        assert d.get("note") is None  # 无 PG → 清理钩子跳过，note 为 None
