"""每文件独立原数据文件（files/<rel>.json）测试：index.json 轻量化。"""
import json

import pytest

from naskb.common.desc_store import FILES_DIR_NAME, NaskbStore, FileEntry
from naskb.common.fs.local import LocalAdapter


@pytest.fixture
def store(tmp_path):
    return NaskbStore(LocalAdapter(str(tmp_path)), analyzer_version="test-0.2.0")


def _entry(name, **kw):
    data = dict(path=name, category="测试", summary="摘要",
                ocr_text="完整全文" * 100, content_description="描述" * 50,
                transcription="转写" * 30, tags=["t1"],
                images=[{"path": "artifacts/x.png", "description": "图"}])
    data.update(kw)
    return FileEntry(**data)


class TestSplitStorage:
    def test_index_light_data_file_full(self, store, tmp_path):
        f = tmp_path / "合同.pdf"
        f.write_bytes(b"%PDF fake")
        store.set_entry(str(f), _entry("合同.pdf"))
        repo = tmp_path / ".naskb"
        idx = json.loads((repo / "index.json").read_text(encoding="utf-8"))
        item = idx["files"][0]
        # index.json 轻量：不含大字段，但含摘要/分类/hash 与 data_file 指针
        assert "ocr_text" not in item
        assert "transcription" not in item
        assert "images" not in item
        assert "content_description" not in item["analysis"]
        assert item["analysis"]["summary"] == "摘要"
        assert item["analysis"]["category"] == "测试"
        assert item["file_hash"].startswith("sha256:")
        assert item["data_file"] == "合同.pdf.json"
        # 完整原数据在独立文件
        df = repo / FILES_DIR_NAME / "合同.pdf.json"
        assert df.exists()
        full = json.loads(df.read_text(encoding="utf-8"))
        assert full["ocr_text"] == "完整全文" * 100
        assert full["transcription"] == "转写" * 30
        assert full["images"][0]["description"] == "图"
        assert full["analysis"]["content_description"] == "描述" * 50

    def test_index_stays_small_with_many_files(self, store, tmp_path):
        """大量文件 + 大全文时 index.json 保持小体积。"""
        for i in range(20):
            f = tmp_path / f"f{i}.pdf"
            f.write_bytes(b"%PDF")
            store.set_entry(str(f), _entry(f"f{i}.pdf"))
        idx = json.loads((tmp_path / ".naskb" / "index.json").read_text(encoding="utf-8"))
        assert len(idx["files"]) == 20
        # 每个条目只有轻量字段（全文 200 字符*20 不在 index 里）
        assert (tmp_path / ".naskb" / "index.json").stat().st_size < 20000

    def test_get_entry_returns_full(self, store, tmp_path):
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF")
        store.set_entry(str(f), _entry("a.pdf"))
        back = store.get_entry(str(f))
        assert back.ocr_text == "完整全文" * 100
        assert back.transcription == "转写" * 30
        assert back.images[0]["description"] == "图"
        assert back.summary == "摘要"

    def test_remove_entry_deletes_data_file(self, store, tmp_path):
        f = tmp_path / "b.pdf"
        f.write_bytes(b"%PDF")
        store.set_entry(str(f), _entry("b.pdf"))
        df = tmp_path / ".naskb" / FILES_DIR_NAME / "b.pdf.json"
        assert df.exists()
        store.remove_entry(str(f))
        assert not df.exists()
        assert store.get_entry(str(f)) is None

    def test_move_entry_data_file_follows(self, store, tmp_path):
        """跨目录移动：描述迁入新目录自己的仓库（每目录一个 .naskb）。"""
        src = tmp_path / "c.pdf"
        src.write_bytes(b"%PDF")
        store.set_entry(str(src), _entry("c.pdf"))
        dst = tmp_path / "子目录" / "c.pdf"
        assert store.move_entry(str(src), str(dst))
        # 旧仓库 data_file 删除，新目录仓库建立且完整
        assert not (tmp_path / ".naskb" / FILES_DIR_NAME / "c.pdf.json").exists()
        new_df = tmp_path / "子目录" / ".naskb" / FILES_DIR_NAME / "c.pdf.json"
        assert new_df.exists()
        back = store.get_entry(str(dst))
        assert back is not None
        assert back.ocr_text == "完整全文" * 100
        assert back.summary == "摘要"

    def test_subdir_data_file_mirrors(self, store, tmp_path):
        """源文件在子目录时，仓库随目录（每目录一个 .naskb），data_file 在子目录仓库。"""
        f = tmp_path / "文档" / "笔记.md"
        f.parent.mkdir(parents=True)
        f.write_text("hi", encoding="utf-8")
        store.set_entry(str(f), _entry("笔记.md"))
        df = tmp_path / "文档" / ".naskb" / FILES_DIR_NAME / "笔记.md.json"
        assert df.exists()
        # 根目录仓库没有该条目
        assert not (tmp_path / ".naskb" / FILES_DIR_NAME / "文档").exists()


class TestLazyMigration:
    def test_old_index_with_large_fields_splits_on_read(self, store, tmp_path):
        """旧数据（大字段仍在 index.json）读取时自动懒迁移拆分。"""
        f = tmp_path / "old.pdf"
        f.write_bytes(b"%PDF")
        repo = tmp_path / ".naskb"
        repo.mkdir()
        (repo / FILES_DIR_NAME).mkdir()
        old = {
            "schema": 2,
            "files": [{
                "path": "old.pdf",
                "file_hash": "sha256:abc",
                "analysis": {"summary": "旧摘要", "content_description": "旧全文" * 20},
                "ocr_text": "旧OCR" * 10,
            }],
        }
        (repo / "index.json").write_text(
            json.dumps(old, ensure_ascii=False), encoding="utf-8")

        back = store.get_entry(str(f))
        assert back.ocr_text == "旧OCR" * 10
        assert back.content_description == "旧全文" * 20
        # 读取后：独立文件已建立，index 已轻量化
        assert (repo / FILES_DIR_NAME / "old.pdf.json").exists()
        idx = json.loads((repo / "index.json").read_text(encoding="utf-8"))
        item = idx["files"][0]
        assert "ocr_text" not in item
        assert item["data_file"] == "old.pdf.json"


class TestBatchSplit:
    def test_split_index_migrates_all(self, store, tmp_path):
        """批量拆分：所有带大字段的旧条目一次性迁到独立原数据文件。"""
        repo = tmp_path / ".naskb"
        repo.mkdir()
        (repo / FILES_DIR_NAME).mkdir()
        old = {
            "schema": 2,
            "files": [
                {"path": "a.pdf", "file_hash": "sha256:a",
                 "analysis": {"summary": "A", "content_description": "A全文" * 30},
                 "ocr_text": "A的OCR" * 20},
                {"path": "b.xlsx", "file_hash": "sha256:b",
                 "analysis": {"summary": "B"},
                 "transcription": "B的转写" * 10},
                {"path": "c.txt", "file_hash": "sha256:c",
                 "analysis": {"summary": "C"}},  # 无大字段，不动
            ],
        }
        (repo / "index.json").write_text(
            json.dumps(old, ensure_ascii=False), encoding="utf-8")

        n = store.split_index(str(tmp_path))
        assert n == 2  # a.pdf 和 b.xlsx 被拆，c.txt 不动
        # 独立文件全部建立
        assert (repo / FILES_DIR_NAME / "a.pdf.json").exists()
        assert (repo / FILES_DIR_NAME / "b.xlsx.json").exists()
        assert not (repo / FILES_DIR_NAME / "c.txt.json").exists()
        # index 轻量化且带 data_file 指针
        idx = json.loads((repo / "index.json").read_text(encoding="utf-8"))
        by_path = {i["path"]: i for i in idx["files"]}
        assert "ocr_text" not in by_path["a.pdf"]
        assert "transcription" not in by_path["b.xlsx"]
        assert by_path["a.pdf"]["data_file"] == "a.pdf.json"
        assert "data_file" not in by_path["c.txt"]
        # 拆分后 get_entry 仍能读到完整全文
        fa = tmp_path / "a.pdf"
        fa.write_bytes(b"%PDF")
        back = store.get_entry(str(fa))
        assert back.ocr_text == "A的OCR" * 20
        assert back.content_description == "A全文" * 30

    def test_split_index_idempotent(self, store, tmp_path):
        """重复执行批量拆分：第二次无新拆分。"""
        repo = tmp_path / ".naskb"
        repo.mkdir()
        (repo / FILES_DIR_NAME).mkdir()
        old = {"schema": 2, "files": [
            {"path": "a.pdf", "file_hash": "sha256:a",
             "analysis": {"summary": "A"}, "ocr_text": "x" * 100}]}
        (repo / "index.json").write_text(
            json.dumps(old, ensure_ascii=False), encoding="utf-8")
        assert store.split_index(str(tmp_path)) == 1
        assert store.split_index(str(tmp_path)) == 0
