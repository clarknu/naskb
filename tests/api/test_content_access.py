"""内容访问端到端（PG 门控）：扫描入库 → 浏览/元数据/预览/下载代理。

覆盖 V1 验收主链路（REQ-R7-06/07/08）：Range 206、ETag 304、
stale 提示头、文本/图片预览分流、missing/stale 徽章数据源。
"""
import hashlib
import os
import uuid

import pytest

try:
    import psycopg  # noqa: F401
    import pgvector  # noqa: F401
    from fastapi.testclient import TestClient
    _DEPS = True
except ImportError:
    _DEPS = False

pytestmark = pytest.mark.skipif(
    not _DEPS, reason="psycopg/pgvector/httpx 未安装")


class _RealCfg:
    """真实工作区配置（PG 可达时运行；否则 skip）。"""

    def __init__(self):
        from naskb.common.config import Config
        self._c = Config.from_work_path("NASKB_data")
        for k in ("pg_host", "pg_port", "pg_user", "pg_password",
                  "pg_database", "work_path", "server_tokens",
                  "anonymous_read"):
            setattr(self, k, getattr(self._c, k))

    @property
    def pg_enabled(self):
        return bool(self.pg_host)


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    try:
        cfg = _RealCfg()
    except Exception:
        pytest.skip("config.toml 不可用")
    from naskb.common.pgstore import PgStore
    pg = PgStore(cfg)
    try:
        with pg.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception:
        pytest.skip("[pg] 不可达")

    # 本地只读源 fixture：txt + jpg(伪) + 大二进制
    root = tmp_path_factory.mktemp("src")
    (root / "docs").mkdir()
    (root / "docs" / "note.txt").write_text("hello naskb 内容", encoding="utf-8")
    (root / "pics").mkdir()
    (root / "pics" / "p.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"x" * 64)
    big = root / "data.bin"
    payload = os.urandom(300 * 1024)
    big.write_bytes(payload)

    from naskb.server.app import create_app
    app = create_app(cfg)
    uniq = uuid.uuid4().hex[:6]
    with TestClient(app) as client:
        r = client.post("/api/sources", json={
            "alias": f"t-src-{uniq}", "protocol": "local",
            "root_path": str(root), "access_mode": "ro"})
        assert r.status_code == 200, r.text
        sid = r.json()["source"]["source_id"]
        rec = client.app.state.registry.get(sid)
        stats = client.app.state.scan_source_fn(rec)     # 同步执行扫描
        yield client, sid, str(big), payload
        # 清理：来源行 + 知识行
        try:
            client.app.state.pg.delete_source_rows(rec.schema_name,
                                                   rec.source_id)
        except Exception:
            pass
        try:
            client.app.state.registry.delete(sid)
        except Exception:
            pass


class TestTreeAndMeta:
    def test_tree_lists_dirs_files(self, env):
        client, sid, *_ = env
        d = client.get("/api/tree", params={"src": sid, "dir": ""}).json()
        assert {x["name"] for x in d["dirs"]} >= {"docs", "pics"}
        names = {f["name"] for f in d["files"]}
        assert names == {"data.bin"}

    def test_subdir_files(self, env):
        client, sid, *_ = env
        d = client.get("/api/tree", params={"src": sid, "dir": "docs"}).json()
        assert [f["name"] for f in d["files"]] == ["note.txt"]
        rid = d["files"][0]["resource_id"]
        m = client.get(f"/api/files/{rid}",
                       params={"src": sid}).json()
        assert m["resource"]["rel_path"] == "docs/note.txt"
        assert m["viewable"] == "text"


class TestPreview:
    def test_text_preview(self, env):
        client, sid, *_ = env
        _, files = client.app.state.pg.list_dir(
            client.app.state.registry.get(sid).schema_name,
            client.app.state.registry.get(sid).source_id, "docs")
        rid = files[0]["resource_id"]
        p = client.get(f"/api/files/{rid}/preview",
                       params={"src": sid}).json()
        assert p["viewable"] == "text"
        assert "hello naskb" in p["content"]

    def test_image_preview_inline_url(self, env):
        client, sid, *_ = env
        _, files = client.app.state.pg.list_dir(
            client.app.state.registry.get(sid).schema_name,
            client.app.state.registry.get(sid).source_id, "pics")
        rid = files[0]["resource_id"]
        p = client.get(f"/api/files/{rid}/preview",
                       params={"src": sid}).json()
        assert p["viewable"] == "image"
        assert "disposition=inline" in p["url"]

    def test_unsupported_binary(self, env):
        client, sid, *_ = env
        _, files = client.app.state.pg.list_dir(
            client.app.state.registry.get(sid).schema_name,
            client.app.state.registry.get(sid).source_id, "")
        rid = next(f["resource_id"] for f in files if f["name"] == "data.bin")
        p = client.get(f"/api/files/{rid}/preview",
                       params={"src": sid}).json()
        assert p["viewable"] is False
        assert p["reason"] == "unsupported_type"
        assert "download_url" in p


class TestDownloadProxy:
    def test_full_download_200(self, env):
        client, sid, path, payload = env
        rid = _rid(client, sid, "data.bin")
        r = client.get(f"/api/files/{rid}/download",
                       params={"src": sid})
        assert r.status_code == 200
        assert r.headers["Accept-Ranges"] == "bytes"
        assert r.content == payload
        expect = hashlib.sha256(payload).hexdigest()
        assert r.headers["ETag"] == f'"{expect}"'

    def test_range_206_slice(self, env):
        client, sid, path, payload = env
        rid = _rid(client, sid, "data.bin")
        r = client.get(f"/api/files/{rid}/download",
                       params={"src": sid},
                       headers={"Range": "bytes=100-199"})
        assert r.status_code == 206
        assert r.headers["Content-Range"].startswith("bytes 100-199/")
        assert r.content == payload[100:200]

    def test_suffix_range(self, env):
        client, sid, path, payload = env
        rid = _rid(client, sid, "data.bin")
        r = client.get(f"/api/files/{rid}/download",
                       params={"src": sid},
                       headers={"Range": "bytes=-16"})
        assert r.status_code == 206
        assert r.content == payload[-16:]

    def test_etag_304(self, env):
        client, sid, path, payload = env
        rid = _rid(client, sid, "data.bin")
        etag = hashlib.sha256(payload).hexdigest()
        r = client.get(f"/api/files/{rid}/download",
                       params={"src": sid},
                       headers={"If-None-Match": f'"{etag}"'})
        assert r.status_code == 304

    def test_unsatisfiable_416(self, env):
        client, sid, path, payload = env
        rid = _rid(client, sid, "data.bin")
        r = client.get(f"/api/files/{rid}/download",
                       params={"src": sid},
                       headers={"Range": f"bytes={len(payload)+10}-"})
        assert r.status_code == 416
        assert r.headers["Content-Range"].endswith(f"/{len(payload)}")

    def test_stale_header_after_touch(self, env):
        client, sid, path, payload = env
        rid = _rid(client, sid, "data.bin")
        t = os.path.getmtime(path) + 500
        os.utime(path, (t, t))
        r = client.get(f"/api/files/{rid}/download",
                       params={"src": sid})
        assert r.status_code == 206 or r.status_code == 200
        assert r.headers.get("X-NASKB-Stale") == "1"

    def test_rid_cross_source_guard(self, env):
        """资源不属于该来源时拒绝（防串库寻址）。"""
        import uuid as _uuid
        client, sid, path, _payload = env
        rid = _rid(client, sid, "data.bin")
        other = client.post("/api/sources", json={
            "alias": "t-src2-" + _uuid.uuid4().hex[:6], "protocol": "local",
            "root_path": os.path.dirname(path), "access_mode": "ro"})
        sid2 = other.json()["source"]["source_id"]
        try:
            r = client.get(f"/api/files/{rid}",
                           params={"src": sid2})
            assert r.status_code in (404,)      # 不属于该来源 → 拒绝
        finally:
            client.delete(f"/api/sources/{sid2}")


def _rid(client, sid, name, dir=""):
    rec = client.app.state.registry.get(sid)
    _, files = client.app.state.pg.list_dir(rec.schema_name,
                                            rec.source_id, dir)
    for f in files:
        if f["name"] == name:
            return f["resource_id"]
    raise AssertionError(f"{name} not found")
