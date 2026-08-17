"""pgstore 集成测试（真实 PG + pgvector，REQ-R4）。

需要 config.toml [pg] 可用且 NASKB_data/models 已下载嵌入模型；
两者任一缺失 → 整个模块 skip（PG 为可选增强）。
"""
import secrets

import pytest

from naskb.common.config import Config
from naskb.common.pgstore import PgStore, normalize_identity, schema_name_for

try:
    import psycopg  # noqa: F401
    import pgvector  # noqa: F401
except ImportError:
    pytest.skip("psycopg/pgvector 未安装", allow_module_level=True)


def _config():
    try:
        return Config.from_work_path("NASKB_data")
    except Exception:
        return None


def _pg_available(config) -> bool:
    if config is None or not config.pg_enabled:
        return False
    try:
        pg = PgStore(config)
        with pg.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def pg_env():
    config = _config()
    if not _pg_available(config):
        pytest.skip("config.toml [pg] 不可用，跳过 PG 集成测试")
    suffix = secrets.token_hex(6)
    username = f"__test__{suffix}"
    pg = PgStore(config)
    # 嵌入模型可用性
    try:
        from naskb.common.embeddings import Embedder
        emb = Embedder(config.work_path)
        emb.close()
    except Exception:
        pytest.skip("嵌入模型不可用，跳过 PG 集成测试")
    yield {"pg": pg, "username": username, "config": config}
    # 清理：删除测试 schema 与 registry 行
    protocol, host, port, user = normalize_identity(
        "local", "local", 0, username)
    schema = schema_name_for(protocol, host, port, user)
    try:
        from psycopg import sql
        with pg.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE")
                            .format(sql.Identifier(schema)))
                cur.execute(
                    "DELETE FROM public.nas_registry WHERE username=%s",
                    (username,))
    except Exception:
        pass


def _doc(rel_path: str, text: str, context: str = "",
         file_hash: str = "h1", category: str = "测试") :
    from naskb.common.retrieval import Doc
    return Doc(path=rel_path, kind="file", text=text, context=context,
               summary=text, category=category, tags=["t"],
               file_hash=file_hash, hash_algorithm="sha256:full",
               size_bytes=100, mtime=1.0, ctime=2.0)


class TestIdentity:
    def test_normalize(self):
        assert normalize_identity("WEBDAV", "192.168.5.2", 5006, "Alice") \
            == ("webdav", "192.168.5.2", 5006, "Alice")

    def test_local_normalized(self):
        assert normalize_identity("local", "anything", 9999, "") \
            == ("local", "local", 0, "")

    def test_schema_name_deterministic(self):
        a = schema_name_for("webdav", "192.168.5.2", 5006, "alice")
        b = schema_name_for("webdav", "192.168.5.2", 5006, "alice")
        c = schema_name_for("webdav", "192.168.5.2", 5006, "bob")
        assert a == b
        assert a != c                       # 账号不同 → 不同向量库
        assert a.startswith("nas_webdav_192_168_5_2_5006_u")
        assert "alice" not in a             # 账号明文不进 schema 名


class TestSync:
    def test_full_sync_and_idempotent(self, pg_env):
        pg: PgStore = pg_env["pg"]
        nas = pg.get_or_create_nas("local", "local", 0,
                                   pg_env["username"], label="test")
        assert nas["schema_name"].startswith("nas_local_local_0_u")

        docs = [_doc("影视/星际穿越.mkv", "诺兰科幻电影，时间旅行",
                     "星际穿越 诺兰 时间旅行 五维空间", "hash-a"),
                _doc("学习/机器学习笔记.pdf", "深度神经网络课程笔记",
                     "神经网络 反向传播 梯度", "hash-b")]
        stats = pg.sync_vectors(nas["schema_name"], docs)
        assert stats["added"] == 2 and stats["embedded"] == 2
        assert stats["updated"] == stats["moved"] == stats["deleted"] == 0

        s = pg.nas_stats(nas["schema_name"])
        assert s["resources"] == 2 and s["vectors"] == 2 and s["ok"] == 2

        # 幂等：二次同步零变化
        stats2 = pg.sync_vectors(nas["schema_name"], docs)
        assert stats2["added"] == stats2["updated"] == 0
        assert stats2["unchanged"] == 2

    def test_update_delete_move(self, pg_env):
        pg: PgStore = pg_env["pg"]
        nas = pg.get_or_create_nas("local", "local", 0, pg_env["username"])
        schema = nas["schema_name"]

        docs = [_doc("a.txt", "内容A", "完整A", "hash-1"),
                _doc("b.txt", "内容B", "完整B", "hash-2"),
                _doc("old/移动.txt", "内容C", "完整C", "hash-3")]
        pg.sync_vectors(schema, docs)

        # 改：a.txt hash 变化 → updated
        docs2 = [_doc("a.txt", "内容A改", "完整A改", "hash-1b"),
                 _doc("b.txt", "内容B", "完整B", "hash-2"),
                 _doc("new/移动.txt", "内容C", "完整C", "hash-3")]  # 移
        stats = pg.sync_vectors(schema, docs2)
        assert stats["updated"] == 1
        assert stats["moved"] == 1   # hash-3 从 old/ 到 new/ 判为移动

        # 删：b.txt 消失
        docs3 = [_doc("a.txt", "内容A改", "完整A改", "hash-1b"),
                 _doc("new/移动.txt", "内容C", "完整C", "hash-3")]
        stats3 = pg.sync_vectors(schema, docs3)
        assert stats3["deleted"] == 1

        s = pg.nas_stats(schema)
        assert s["resources"] == 2

    def test_search(self, pg_env):
        pg: PgStore = pg_env["pg"]
        config = pg_env["config"]
        nas = pg.get_or_create_nas("local", "local", 0, pg_env["username"])
        docs = [_doc("电影/星际穿越.mkv", "诺兰科幻电影，时间旅行黑洞",
                     "星际穿越 诺兰", "hash-a"),
                _doc("学习/笔记.pdf", "深度神经网络课程笔记",
                     "神经网络", "hash-b")]
        pg.sync_vectors(nas["schema_name"], docs)

        from naskb.common.embeddings import Embedder
        emb = Embedder(config.work_path)
        try:
            q = emb.encode_one("科幻电影 黑洞")
        finally:
            emb.close()
        hits = pg.search(nas["schema_name"], q, top_k=2)
        assert hits and hits[0]["path"].endswith("星际穿越.mkv")
        assert hits[0]["status"] == "ok"
        assert hits[0]["stale"] is False
        assert hits[0]["context"]   # 完整文本（RAG 上下文）
