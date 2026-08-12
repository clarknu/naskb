"""NaskbStore（.naskb/ 目录隐藏仓库）测试。

覆盖：index.json/folder.json 读写、原子写无残留、hash 校验、
目录内/跨目录移动、删除清理、孤儿、扫描、重建、meta。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from naskb.common.desc_store import FileEntry, FolderEntry, NaskbStore
from naskb.common.fs.local import LocalAdapter


@pytest.fixture
def store(tmp_path):
    return NaskbStore(LocalAdapter(str(tmp_path)), analyzer_version="test-0.2.0")


def _entry(path, summary="", category="", tags=None):
    return FileEntry(
        path=path,
        summary=summary or "摘要",
        category=category or "测试",
        tags=tags or ["测试"],
        original_path=path,
    )


class TestRepoStructure:
    def test_ensure_repo_creates_hidden_dir(self, store, tmp_path):
        repo = store.ensure_repo(str(tmp_path))
        assert repo.endswith(".naskb")
        assert Path(repo).is_dir()
        assert Path(store.artifacts_dir(str(tmp_path))).is_dir()

    def test_index_paths(self, store, tmp_path):
        assert store.index_path(str(tmp_path)).endswith(".naskb/index.json")
        assert store.folder_path(str(tmp_path)).endswith(".naskb/folder.json")
        assert store.meta_path(str(tmp_path)).endswith(".naskb/meta.json")

    def test_dir_of(self, store):
        assert store.dir_of("/a/b/c.txt") == "/a/b"
        assert store.dir_of("a.txt") == "/"  # 无目录 → 根


class TestEntryCRUD:
    def test_set_get_entry(self, store, tmp_path):
        f = tmp_path / "照片.jpg"
        f.write_bytes(b"fake jpeg")
        ok = store.set_entry(str(f), _entry("照片.jpg", summary="海边日落"))
        assert ok

        repo = tmp_path / ".naskb"
        assert repo.is_dir()
        idx = json.loads((repo / "index.json").read_text(encoding="utf-8"))
        assert idx["schema"] == 2
        assert idx["files"][0]["path"] == "照片.jpg"
        assert idx["files"][0]["file_hash"].startswith("sha256:")
        assert idx["files"][0]["analysis"]["summary"] == "海边日落"

        entry = store.get_entry(str(f))
        assert entry is not None
        assert entry.summary == "海边日落"
        assert entry.category == "测试"
        assert entry.analyzer_version == "test-0.2.0"

    def test_get_entry_missing(self, store, tmp_path):
        assert store.get_entry(str(tmp_path / "nope.txt")) is None

    def test_set_entry_update_replaces(self, store, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        store.set_entry(str(f), _entry("a.txt", summary="v1"))
        store.set_entry(str(f), _entry("a.txt", summary="v2", tags=["新"]))
        idx = json.loads((tmp_path / ".naskb" / "index.json").read_text(encoding="utf-8"))
        assert len(idx["files"]) == 1
        assert idx["files"][0]["analysis"]["summary"] == "v2"
        assert idx["files"][0]["analysis"]["tags"] == ["新"]

    def test_remove_entry(self, store, tmp_path):
        f = tmp_path / "gone.txt"
        f.write_text("bye", encoding="utf-8")
        store.set_entry(str(f), _entry("gone.txt"))
        assert store.remove_entry(str(f))
        assert store.get_entry(str(f)) is None
        # 再次删除不报错
        assert store.remove_entry(str(f))

    def test_atomic_write_no_tmp_leftover(self, store, tmp_path):
        """多次写入后目录无 .tmp- 残留。"""
        f = tmp_path / "doc.md"
        f.write_text("# t", encoding="utf-8")
        for i in range(3):
            store.set_entry(str(f), _entry("doc.md", summary=f"v{i}"))
        repo = tmp_path / ".naskb"
        leftovers = [p for p in repo.iterdir() if ".tmp-" in p.name]
        assert leftovers == []


class TestCheck:
    def test_missing(self, store, tmp_path):
        f = tmp_path / "new.txt"
        f.write_text("新", encoding="utf-8")
        assert store.check(str(f)) == "missing"

    def test_valid(self, store, tmp_path):
        f = tmp_path / "ok.txt"
        f.write_text("内容 A", encoding="utf-8")
        store.set_entry(str(f), _entry("ok.txt"))
        assert store.check(str(f)) == "valid"

    def test_stale_after_change(self, store, tmp_path):
        f = tmp_path / "changed.txt"
        f.write_text("内容 A", encoding="utf-8")
        store.set_entry(str(f), _entry("changed.txt"))
        f.write_text("内容 B 变了", encoding="utf-8")
        assert store.check(str(f)) == "stale"


class TestMove:
    def test_move_within_dir(self, store, tmp_path):
        """目录内重命名：path 更新，provenance 记录。"""
        f = tmp_path / "old.txt"
        f.write_text("x", encoding="utf-8")
        store.set_entry(str(f), _entry("old.txt", summary="文档"))

        dst = tmp_path / "new.txt"
        assert store.move_entry(str(f), str(dst))

        assert Path(dst).exists()
        assert store.get_entry(str(dst)) is not None
        assert store.get_entry(str(f)) is None
        e = store.get_entry(str(dst))
        assert e.original_path == str(f)
        assert str(f) in e.moved_from

    def test_move_cross_dir(self, store, tmp_path):
        """跨目录移动：旧目录删条目、新目录加条目。"""
        src_dir = tmp_path / "inbox"
        dst_dir = tmp_path / "归档" / "2023"
        src_dir.mkdir()
        f = src_dir / "报告.pdf"
        f.write_bytes(b"%PDF fake")
        store.set_entry(str(f), _entry("报告.pdf", summary="合同"))

        dst = str(dst_dir / "报告.pdf")
        assert store.move_entry(str(f), dst)

        assert Path(dst).exists()
        assert store.get_entry(dst) is not None
        assert store.get_entry(str(f)) is None
        # 旧目录 index.json 中无残留
        idx_old = json.loads((src_dir / ".naskb" / "index.json").read_text(encoding="utf-8"))
        assert idx_old["files"] == []

    def test_move_without_entry(self, store, tmp_path):
        f = tmp_path / "plain.txt"
        f.write_text("no desc", encoding="utf-8")
        dst = tmp_path / "sub" / "plain.txt"
        assert store.move_entry(str(f), str(dst))
        assert Path(dst).exists()

    def test_delete_with_file(self, store, tmp_path):
        f = tmp_path / "gone.txt"
        f.write_text("bye", encoding="utf-8")
        store.set_entry(str(f), _entry("gone.txt"))
        store.delete_with_file(str(f))
        assert not Path(f).exists()
        assert store.get_entry(str(f)) is None


class TestScanOrphansRebuild:
    def test_find_orphans(self, store, tmp_path):
        (tmp_path / "ok.txt").write_text("ok", encoding="utf-8")
        ghost = tmp_path / "ghost.txt"
        ghost.write_text("ghost", encoding="utf-8")
        store.set_entry(str(tmp_path / "ok.txt"), _entry("ok.txt"))
        store.set_entry(str(ghost), _entry("ghost.txt"))
        ghost.unlink()

        orphans = store.find_orphans(str(tmp_path))
        assert orphans == ["ghost.txt"]

    def test_scan_report(self, store, tmp_path):
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        (tmp_path / "c.txt").write_text("c", encoding="utf-8")
        store.set_entry(str(tmp_path / "a.txt"), _entry("a.txt"))
        store.set_entry(str(tmp_path / "b.txt"), _entry("b.txt"))
        (tmp_path / "b.txt").write_text("b-changed", encoding="utf-8")

        report = store.scan(str(tmp_path))
        assert report["total"] == 3
        assert report["valid"] == 1
        assert report["stale"] == 1
        assert report["missing"] == 1
        assert report["ignored"] == 0
        assert report["orphans"] == 0

    def test_scan_ignored_category(self, store, tmp_path):
        """不支持类型计入 ignored（不进入 missing）；垃圾/锁文件跳过。"""
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "脚本.py").write_text("x", encoding="utf-8")
        (tmp_path / "Dockerfile").write_text("FROM x", encoding="utf-8")
        (tmp_path / "Thumbs.db").write_bytes(b"\x00")
        (tmp_path / "~$a.docx").write_bytes(b"\x00")
        report = store.scan(str(tmp_path))
        assert report["total"] == 3      # 垃圾/锁文件不计入
        assert report["ignored"] == 2      # 脚本.py + Dockerfile
        assert report["missing"] == 1      # 仅 a.txt
        statuses = {d["path"]: d["status"] for d in report["details"]}
        assert "ignored" in statuses.values()

    def test_rebuild(self, store, tmp_path):
        for i in range(3):
            f = tmp_path / f"file{i}.txt"
            f.write_text(f"c{i}", encoding="utf-8")
            store.set_entry(str(f), _entry(f"file{i}.txt", summary=f"摘要{i}"))

        entries = store.rebuild(str(tmp_path))
        assert len(entries) == 3
        assert sorted(e.summary for e in entries) == ["摘要0", "摘要1", "摘要2"]

    def test_rebuild_nested_repos(self, store, tmp_path):
        """嵌套目录各有 .naskb，重建能全部收集。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        f1 = tmp_path / "a.txt"
        f2 = sub / "b.txt"
        f1.write_text("a", encoding="utf-8")
        f2.write_text("b", encoding="utf-8")
        store.set_entry(str(f1), _entry("a.txt", summary="A"))
        store.set_entry(str(f2), _entry("b.txt", summary="B"))

        entries = store.rebuild(str(tmp_path))
        assert len(entries) == 2


class TestFolderEntry:
    def test_write_read_folder(self, store, tmp_path):
        fe = FolderEntry(
            description="公司软件发布目录",
            structure=[{"name": "src", "type": "dir", "summary": "源码"}],
            file_type_distribution={"py": 10},
            tags=["软件"],
            summary="软件发布目录",
            confidence=0.9,
        )
        assert store.write_folder(str(tmp_path), fe)

        back = store.read_folder(str(tmp_path))
        assert back is not None
        assert back.description == "公司软件发布目录"
        assert back.structure[0]["name"] == "src"
        assert back.file_type_distribution == {"py": 10}
        assert back.confidence == 0.9

    def test_read_folder_missing(self, store, tmp_path):
        assert store.read_folder(str(tmp_path)) is None

    def test_meta(self, store, tmp_path):
        assert store.write_meta(str(tmp_path), {"model_snapshot": {"llm_text": "deepseek"}})
        meta = store.read_meta(str(tmp_path))
        assert meta["schema"] == 2
        assert meta["model_snapshot"]["llm_text"] == "deepseek"
        assert meta["updated_at"]


class TestSchema:
    def test_entry_roundtrip(self):
        e = FileEntry(
            path="a.jpg", file_hash="sha256:x", summary="图",
            images=[{"path": "artifacts/x.png", "description": "架构图"}],
            transcription="转写文本", ocr_text="OCR",
            exif={"camera": "iPhone"}, duration_seconds=12.5,
            width=100, height=50, processing_policy="full",
        )
        d = e.to_dict()
        back = FileEntry.from_dict(d)
        assert back.path == "a.jpg"
        assert back.images[0]["description"] == "架构图"
        assert back.transcription == "转写文本"
        assert back.ocr_text == "OCR"
        assert back.exif == {"camera": "iPhone"}
        assert back.duration_seconds == 12.5
        assert back.width == 100
        assert back.processing_policy == "full"

    def test_entry_tolerant(self):
        e = FileEntry.from_dict({"path": "x", "analysis": {"tags": [1, "a"]}})
        assert e.tags == ["1", "a"]
        assert e.summary == ""

    def test_entry_rejects_non_object(self):
        with pytest.raises(ValueError):
            FileEntry.from_dict([1])
