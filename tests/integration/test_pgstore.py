"""pgstore 集成测试（真实 PG + pgvector，REQ-R4）。

需要 config.toml [pg] 可用且 NASKB_data/models 已下载嵌入模型；
两者任一缺失 → 整个模块 skip（PG 为可选增强）。
"""
import secrets
import uuid

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

    def test_source_changes_dryrun(self, pg_env):
        """dry-run 差异（确认清单）：只读，不应用。"""
        pg: PgStore = pg_env["pg"]
        nas = pg.get_or_create_nas("local", "local", 0, pg_env["username"])
        schema = nas["schema_name"]
        docs = [_doc("a.txt", "内容A", "完整A", "hash-h1"),
                _doc("b.txt", "内容B", "完整B", "hash-h2")]
        pg.sync_vectors(schema, docs)

        items = [
            {"rel_path": "a.txt", "file_hash": "hash-h1",
             "hash_algorithm": "sha256:full", "mtime": 1.0, "size_bytes": 100},
            {"rel_path": "b.txt", "file_hash": "hash-h2-mod",
             "hash_algorithm": "sha256:full", "mtime": 1.0, "size_bytes": 100},
            {"rel_path": "c.txt", "file_hash": "hash-h3",
             "hash_algorithm": "sha256:full", "mtime": 1.0, "size_bytes": 50},
        ]
        diff = pg.source_changes(schema, None, items)
        assert "a.txt" in diff["unchanged"]      # 指纹/stat 一致
        assert "b.txt" in diff["changed"]        # hash 变化
        assert "c.txt" in diff["added"]
        assert diff["missing"] == []             # 都还在


class TestChunks:
    """条款级 chunk（REQ-R5-06）：迁移/termbase/sync_chunks/分级检索。"""

    _MD = (
        "# 第6章 试验方法\n"
        "引言。\n\n"
        "## 6.3 压力试验\n"
        "施加 1.5 倍工作压力，保压 30 分钟。\n\n"
        "## 6.4 气密试验\n"
        "泄漏率不大于 0.5%。\n"
    )

    def test_termbase_and_sync_chunks(self, pg_env):
        pg: PgStore = pg_env["pg"]
        config = pg_env["config"]
        nas = pg.get_or_create_nas("local", "local", 0, pg_env["username"])
        schema = nas["schema_name"]

        docs = [_doc("deep/标准.pdf", "压力试验规范",
                     "施加 1.5 倍工作压力，保压 30 分钟", "hash-q1")]
        pg.sync_vectors(schema, docs)   # 先建 resources + summary 行

        n = pg.add_termbase(schema, ["耐压强度", "保压时间"])
        assert n == 2
        assert sorted(pg.list_termbase(schema)) == ["保压时间", "耐压强度"]

        from naskb.common.embeddings import Embedder
        emb = Embedder(config.work_path)
        try:
            deep_cfg = config.deep_doc_cfg()
            deep_cfg["enabled"] = True
            deep_cfg["roots"] = ["deep"]
            stats = pg.sync_chunks(
                schema, docs, deep_cfg=deep_cfg, embedder=emb,
                read_md=lambda d: self._MD)
            assert stats["documents"] == 1
            assert stats["chunks"] >= 3
            assert stats["errors"] == []

            # 分级检索：chunk 级能命中 sub 章节；summary 级只返回文档级 1 条
            q = emb.encode_one("气密试验 泄漏率")
            chunk_hits = pg.search(schema, q, top_k=5, level="chunk")
            assert chunk_hits, "chunk 级应有命中"
            assert any(h["kind"] == "file" for h in chunk_hits)
            assert all(h["chunk_seq"] is not None for h in chunk_hits)
            summar_hits = pg.search(schema, q, top_k=5, level="summary")
            assert summar_hits and summar_hits[0]["chunk_seq"] is None

            # 幂等：二次 sync_chunks 仍只保留该资源 C(删后建) 不翻倍
            stats2 = pg.sync_chunks(
                schema, docs, deep_cfg=deep_cfg, embedder=emb,
                read_md=lambda d: self._MD)
            assert stats2["documents"] == 1 and stats2["chunks"] >= 3

            def _count_chunks():
                from psycopg import sql
                with pg.connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql.SQL(
                            "SELECT count(*) FROM {}.vectors "
                            "WHERE level='chunk'").format(
                            sql.Identifier(schema)))
                        return cur.fetchone()[0]
            n1 = _count_chunks()
            pg.sync_chunks(schema, docs, deep_cfg=deep_cfg, embedder=emb,
                           read_md=lambda d: self._MD)
            assert _count_chunks() == n1   # 不变（先删后建）

            # 来源级统计应带 chunk 数（schedule/来源页展示用）
            assert pg.source_stats(schema, None)["chunks"] >= 3
        finally:
            emb.close()

    def test_sync_chunks_skip_when_disabled(self, pg_env):
        pg: PgStore = pg_env["pg"]
        config = pg_env["config"]
        nas = pg.get_or_create_nas("local", "local", 0, pg_env["username"])
        schema = nas["schema_name"]
        docs = [_doc("deep/标准.pdf", "压力试验规范", "全文本", "hash-q2")]
        pg.sync_vectors(schema, docs)
        stats = pg.sync_chunks(schema, docs, deep_cfg=config.deep_doc_cfg(),
                               read_md=lambda d: self._MD)
        # [deep].enabled 默认 False → no-op
        assert stats["documents"] == 0 and stats["chunks"] == 0

    def test_pgsearch_engine_search_chunks(self, pg_env):
        from naskb.common.pgsearch import PgSearchEngine
        pg: PgStore = pg_env["pg"]
        config = pg_env["config"]
        nas = pg.get_or_create_nas("local", "local", 0, pg_env["username"])
        schema = nas["schema_name"]

        docs = [_doc("deep/标准.pdf", "压力试验规范", "施加 1.5 倍压力",
                     "hash-q3")]
        pg.sync_vectors(schema, docs)
        deep_cfg = config.deep_doc_cfg()
        deep_cfg["enabled"] = True
        deep_cfg["roots"] = ["deep"]

        from naskb.common.embeddings import Embedder
        emb = Embedder(config.work_path)
        try:
            pg.sync_chunks(schema, docs, deep_cfg=deep_cfg, embedder=emb,
                           read_md=lambda d: self._MD)
        finally:
            emb.close()

        eng = PgSearchEngine(pg, config.work_path, default_schema=schema)
        try:
            hits = eng.search_chunks("气密 泄漏率", top_k=5)
            assert hits and hits[0]["level"] == "chunk"
            assert hits[0]["title_path"]
            assert hits[0]["chunk_seq"] is not None
            # 摘要级 search（level='summary'）不返回 chunk 字段
            summ = eng.search("气密 泄漏率", top_k=5)
            assert summ and all(h["level"] == "summary"
                                for h in summ)
            assert all(h["chunk_seq"] is None for h in summ)
        finally:
            eng.close()

    def test_deep_eval_run_pipeline(self, pg_env):
        """阶段3：真实 PG chunk 数据 + 桩 LLM，把 deep-eval 管线跑通。"""
        from naskb.common.pgsearch import PgSearchEngine
        from naskb.common.deep_eval import run_eval, aggregate
        pg: PgStore = pg_env["pg"]
        config = pg_env["config"]
        nas = pg.get_or_create_nas("local", "local", 0, pg_env["username"])
        schema = nas["schema_name"]

        docs = [_doc("deep/标准.pdf", "压力试验规范", "气密 泄漏率 0.5%",
                     "hash-q4")]
        pg.sync_vectors(schema, docs)
        deep_cfg = config.deep_doc_cfg()
        deep_cfg["enabled"] = True
        deep_cfg["roots"] = ["deep"]
        deep_cfg["direct_return"] = False     # 走 rag 路径，测 citations

        from naskb.common.embeddings import Embedder
        emb = Embedder(config.work_path)
        try:
            pg.sync_chunks(schema, docs, deep_cfg=deep_cfg, embedder=emb,
                           read_md=lambda d: self._MD)
        finally:
            emb.close()

        class _StubLLM:
            def complete(self, prompt):        # noqa: D401
                return "依照 6.3.2 执行。"
            def get_llm(self):
                return self

        eng = PgSearchEngine(pg, config.work_path, default_schema=schema)
        try:
            results = run_eval(eng, _StubLLM(), deep_cfg, schema,
                               [{"q": "气密试验允许多大泄漏率", "expect": "标准.pdf"}],
                               top_k=3)
            assert results and results[0]["deep_sources"], \
                "chunk 路径应命中并给出两级来源"
            assert results[0]["base_sources"]
            assert results[0]["deep_answer"] == "依照 6.3.2 执行。"
            agg = aggregate(results)
            assert agg["deep_expect_hit"] == 1
            assert agg["base_expect_hit"] == 1
        finally:
            eng.close()


class TestFolderAndChunkDelete:
    """目录条目读取（get_folder）与 deep 关闭语义（delete_chunk_rows）。"""

    _MD = (
        "# 第6章 试验方法\n"
        "引言。\n\n"
        "## 6.3 压力试验\n"
        "施加 1.5 倍工作压力，保压 30 分钟。\n\n"
        "## 6.4 气密试验\n"
        "泄漏率不大于 0.5%。\n"
    )

    @staticmethod
    def _count_rows(pg, schema: str, level: str, sid) -> int:
        """统计某来源某 level 的向量行数（直接 SQL，辅助断言）。"""
        from psycopg import sql
        with pg.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "SELECT count(*) FROM {}.vectors v "
                    "JOIN {}.resources r ON r.resource_id=v.resource_id "
                    "WHERE r.source_id=%s AND v.level=%s").format(
                    sql.Identifier(schema), sql.Identifier(schema)),
                    (sid, level))
                return cur.fetchone()[0]

    def test_get_folder(self, pg_env):
        pg: PgStore = pg_env["pg"]
        nas = pg.get_or_create_nas("local", "local", 0, pg_env["username"])
        schema = nas["schema_name"]
        pg.ensure_nas_schema(schema)          # 确保 folders 表存在
        sid = uuid.uuid4()
        from psycopg import sql

        with pg.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL(
                    "INSERT INTO {}.folders (source_id, rel_path, "
                    "parent_dir, name, summary, description, tags, "
                    "file_count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)")
                    .format(sql.Identifier(schema)),
                    (sid, "资料/项目", "资料", "项目", "项目目录摘要",
                     "这是一个项目目录", ["内部", "重要"], 5))

        folder = pg.get_folder(schema, sid, "资料/项目")
        assert folder == {
            "rel_path": "资料/项目", "name": "项目", "summary": "项目目录摘要",
            "description": "这是一个项目目录", "tags": ["内部", "重要"],
            "file_count": 5,
        }
        # 目录未登记/路径不匹配 → None
        assert pg.get_folder(schema, sid, "不存在/目录") is None

    def test_delete_chunk_rows(self, pg_env):
        pg: PgStore = pg_env["pg"]
        config = pg_env["config"]
        nas = pg.get_or_create_nas("local", "local", 0, pg_env["username"])
        schema = nas["schema_name"]

        # 两个来源各一 deep 文档（resources + summary 向量行 + chunk 向量行）
        sid_a = uuid.uuid4()
        sid_b = uuid.uuid4()
        docs_a = [_doc("deep/a.md", "压力试验规范",
                       "施加 1.5 倍工作压力，保压 30 分钟", "hash-da")]
        docs_b = [_doc("deep/b.md", "气密试验规范",
                       "泄漏率不大于 0.5%", "hash-db")]
        pg.sync_vectors(schema, docs_a, source_id=sid_a)
        pg.sync_vectors(schema, docs_b, source_id=sid_b)

        deep_cfg = config.deep_doc_cfg()
        deep_cfg["enabled"] = True
        deep_cfg["roots"] = ["deep"]

        from naskb.common.embeddings import Embedder
        emb = Embedder(config.work_path)
        try:
            stats_a = pg.sync_chunks(schema, docs_a, deep_cfg=deep_cfg,
                                     embedder=emb, source_id=sid_a,
                                     read_md=lambda d: self._MD)
            stats_b = pg.sync_chunks(schema, docs_b, deep_cfg=deep_cfg,
                                     embedder=emb, source_id=sid_b,
                                     read_md=lambda d: self._MD)
        finally:
            emb.close()

        # 预置校验：两来源各有 1 条 summary 与若干 chunk
        assert self._count_rows(pg, schema, "summary", sid_a) == 1
        assert self._count_rows(pg, schema, "chunk", sid_a) == stats_a["chunks"]
        assert self._count_rows(pg, schema, "chunk", sid_b) == stats_b["chunks"]

        deleted = pg.delete_chunk_rows(schema, sid_a)
        assert deleted == stats_a["chunks"]   # 删除行数正确

        # 来源 A：chunk 清空、summary 保留；来源 B：完全不受影响
        assert self._count_rows(pg, schema, "chunk", sid_a) == 0
        assert self._count_rows(pg, schema, "summary", sid_a) == 1
        assert self._count_rows(pg, schema, "chunk", sid_b) == stats_b["chunks"]
        assert self._count_rows(pg, schema, "summary", sid_b) == 1
