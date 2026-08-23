"""扫描入库（inventory）测试：walk / 指纹 / 对账（PG 集成部分自动跳过）。"""
import hashlib
import os

import pytest

from naskb.common.fs.base import SubRootAdapter
from naskb.common.fs.local import LocalAdapter
from naskb.common.hashing import sample_ranges
from naskb.common.inventory import (compute_missing_hashes, guess_category,
                                    walk_source)


@pytest.fixture
def source_dir(tmp_path):
    root = tmp_path / "home"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "a.txt").write_text("hello naskb", encoding="utf-8")
    (root / "pics").mkdir()
    (root / "pics" / "b.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpg")
    big = root / "big.dat"
    big.write_bytes(bytes(range(256)) * 2400)      # 614,400 B > 512KB
    (root / ".hidden").mkdir()
    (root / ".hidden" / "x.txt").write_text("skip", encoding="utf-8")
    return str(root)


def test_walk_source_relative_and_filters(source_dir):
    fs = SubRootAdapter(LocalAdapter(source_dir), ".")
    items, skipped = walk_source(fs)
    rels = {it["rel_path"] for it in items}
    assert rels == {"docs/a.txt", "pics/b.jpg", "big.dat"}
    assert skipped == 0
    by = {it["rel_path"]: it for it in items}
    assert by["docs/a.txt"]["parent_dir"] == "docs"
    assert by["docs/a.txt"]["file_type"] == "txt"


def test_fingerprint_full_for_small_file(source_dir):
    fs = SubRootAdapter(LocalAdapter(source_dir), ".")
    items, _ = walk_source(fs)
    compute_missing_hashes(fs, items)
    by = {it["rel_path"]: it for it in items}
    expect = hashlib.sha256(b"hello naskb").hexdigest()
    assert by["docs/a.txt"]["file_hash"] == expect
    assert by["docs/a.txt"]["hash_algorithm"] == "sha256:full"


def test_fingerprint_sampled_for_big_file(source_dir):
    """>512KB 文件按 8×64KB 采样，与手工规则复算一致（ADR-20260816-4）。"""
    fs = SubRootAdapter(LocalAdapter(source_dir), ".")
    items, _ = walk_source(fs)
    compute_missing_hashes(fs, items)
    it = next(x for x in items if x["rel_path"] == "big.dat")
    data = open(os.path.join(source_dir, "big.dat"), "rb").read()
    spans = sample_ranges(len(data))
    h = hashlib.sha256()
    for s, l in spans:
        h.update(data[s:s + l])
    assert it["hash_algorithm"] == "sha256:sample8x64k"
    assert it["file_hash"] == h.hexdigest()


def test_guess_category():
    assert guess_category("pdf") == "文档"
    assert guess_category(".PNG") == "图片"
    assert guess_category("mp4") == "视频"
    assert guess_category("xyz123") == "其他"


# ── PG 集成：reconcile 状态机（无 PG 自动跳过）──
try:
    import psycopg  # noqa: F401
    import pgvector  # noqa: F401
    _PG_DEPS = True
except ImportError:
    _PG_DEPS = False


@pytest.mark.skipif(not _PG_DEPS, reason="psycopg/pgvector 未安装")
class TestReconcilePg:
    @pytest.fixture()
    def pg_env(self, source_dir):
        from naskb.common.config import Config
        from naskb.common.pgstore import PgStore, schema_name_for
        try:
            config = Config.from_work_path("NASKB_data")
            pg = PgStore(config)
            with pg.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        except Exception:
            pytest.skip("config.toml [pg] 不可用")
        import secrets
        schema = "nas_test_" + secrets.token_hex(4)
        sid = __import__("uuid").uuid4()
        pg.ensure_nas_schema(schema)
        return pg, schema, sid, source_dir

    def test_reconcile_lifecycle(self, pg_env):
        import os as _os
        from naskb.common.fs.base import SubRootAdapter
        from naskb.common.fs.local import LocalAdapter
        from naskb.common.inventory import compute_missing_hashes, walk_source
        pg, schema, sid, sdir = pg_env
        fs = SubRootAdapter(LocalAdapter(sdir), ".")
        items, _ = walk_source(fs)
        compute_missing_hashes(fs, items)
        stats = pg.reconcile_resources(schema, sid, items)
        assert stats["added"] == 3 and stats["missing"] == 0

        # 二次扫描：全部 unchanged
        again = pg.reconcile_resources(schema, sid, items)
        assert again["added"] == 0
        assert again["unchanged"] + again["restored"] >= 3

        # 删除一个文件 → missing_source；知识保留可查
        _os.remove(_os.path.join(sdir, "docs", "a.txt"))
        items2 = [it for it in items if it["rel_path"] != "docs/a.txt"]
        gone = pg.reconcile_resources(schema, sid, items2)
        assert gone["missing"] == 1
        row = pg.get_resource(
            schema, _rid_of(pg, schema, sid, "docs/a.txt"))
        assert row is not None and row["status"] == "missing_source"

        # 恢复文件 → 回 ok（restored）
        open(_os.path.join(sdir, "docs", "a.txt"), "w",
             encoding="utf-8").write("hello naskb")
        restored = pg.reconcile_resources(schema, sid, items)
        assert restored.get("restored") >= 1 or restored.get("unchanged") >= 3

        # 目录清单已登记
        dirs, files = pg.list_dir(schema, sid, "")
        names = {d["name"] for d in dirs}
        assert {"docs", "pics"} <= names
        # 清理测试 schema 数据
        pg.delete_source_rows(schema, sid)

    def test_sync_vectors_enrich_backfill(self, pg_env):
        """富化路径：库存行存在但无向量 → sync_vectors 补描述+向量。"""
        from naskb.common.pgstore import EMBEDDING_DIM
        from naskb.common.retrieval import Doc
        pg, schema, sid, sdir = pg_env
        from naskb.common.fs.base import SubRootAdapter
        from naskb.common.fs.local import LocalAdapter
        from naskb.common.inventory import compute_missing_hashes, walk_source
        fs = SubRootAdapter(LocalAdapter(sdir), ".")
        items, _ = walk_source(fs)
        compute_missing_hashes(fs, items)
        pg.reconcile_resources(schema, sid, items)

        class _FakeEmbedder:
            def encode(self, texts):
                import numpy as np
                return np.zeros((len(texts), EMBEDDING_DIM), dtype="float32")

            def encode_one(self, text):
                import numpy as np
                return np.zeros((EMBEDDING_DIM,), dtype="float32")

        doc = Doc(path="docs/a.txt", kind="file",
                  text="docs/a.txt\nhello 的摘要",
                  summary="hello 的摘要", category="文档", tags=["t1"],
                  context="docs/a.txt\nhello 的摘要\n全文内容",
                  content_description="一段描述",
                  file_type="txt",
                  file_hash=next(it["file_hash"] for it in items
                                 if it["rel_path"] == "docs/a.txt"),
                  hash_algorithm="sha256:full",
                  size_bytes=11, mtime=0.0, ctime=0.0)
        stats = pg.sync_vectors(schema, [doc], _FakeEmbedder(),
                                source_id=sid)
        assert stats["enriched"] == 1 and stats["added"] == 0
        row = pg.get_resource(
            schema, _rid_of(pg, schema, sid, "docs/a.txt"))
        assert row["summary"] == "hello 的摘要"
        assert row["content_description"] == "一段描述"
        hits = pg.search(schema,
                         __import__("numpy").zeros((EMBEDDING_DIM,)),
                         top_k=5, source_ids=[sid])
        assert any(h["resource_id"] for h in hits)
        pg.delete_source_rows(schema, sid)


def _rid_of(pg, schema, sid, rel_path):
    parent = rel_path.rsplit("/", 1)[0] if "/" in rel_path else ""
    _, files = pg.list_dir(schema, sid, parent)
    for f in files:
        if f["rel_path"] == rel_path:
            return f["resource_id"]
    raise AssertionError(f"row not found: {rel_path}")
