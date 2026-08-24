"""目录级分析（folder.json）测试。"""
import pytest

from naskb.common.analyzer.folder import FolderAnalyzer, _fmt_size
from naskb.common.fs.local import LocalAdapter


@pytest.fixture
def sample_dir(tmp_path):
    d = tmp_path / "software"
    (d / "src").mkdir(parents=True)
    (d / "tests").mkdir()
    (d / "docs").mkdir()
    (d / "src" / "main.py").write_text("print('hi')", encoding="utf-8")
    (d / "src" / "utils.py").write_text("", encoding="utf-8")
    (d / "tests" / "test_main.py").write_text("", encoding="utf-8")
    (d / "docs" / "README.md").write_text("docs", encoding="utf-8")
    (d / "setup.py").write_text("", encoding="utf-8")
    (d / "requirements.txt").write_text("", encoding="utf-8")
    return d


class TestFormatSize:
    def test_fmt_size(self):
        assert _fmt_size(0) == "0B"
        assert _fmt_size(1024) == "1.0KB"
        assert _fmt_size(1536) == "1.5KB"
        assert _fmt_size(1024 * 1024) == "1.0MB"


class TestCollect:
    def test_structure_stats(self, sample_dir):
        fs = LocalAdapter(str(sample_dir))
        fa = FolderAnalyzer()
        s = fa.collect_structure(fs, ".")
        assert s["file_count"] == 6
        assert s["ext_distribution"][".py"] == 4
        assert s["ext_distribution"][".md"] == 1
        assert s["total_size_bytes"] > 0
        assert "src" in s["subdirs"]
        assert "docs" in s["subdirs"]
        assert "main.py" in s["sample_files"]
        assert s["max_depth"] == 1

    def test_no_llm_fallback_summary(self, sample_dir):
        fs = LocalAdapter(str(sample_dir))
        fa = FolderAnalyzer(llm_client=None)
        entry = fa.analyze(fs, ".")
        assert entry.file_type_distribution[".py"] == 4
        assert "6 个文件" in entry.summary
        assert entry.description == entry.summary
        assert not entry.tags

    def test_excludes_repo_files(self, sample_dir):
        """目录统计应排除 .naskb/ 描述仓库自身。"""
        fs = LocalAdapter(str(sample_dir))
        # 构造一个描述仓库（内部文件不应计入目录内容）
        (sample_dir / ".naskb").mkdir(exist_ok=True)
        (sample_dir / ".naskb" / "index.json").write_text(
            '{"files": []}', encoding="utf-8")
        fa = FolderAnalyzer()
        s = fa.collect_structure(fs, ".")
        assert s["file_count"] == 6  # 不含 index.json
        assert ".naskb" not in "".join(s["subdirs"])

    def test_excludes_hidden_and_excluded_dirs(self, sample_dir):
        """统计应排除隐藏目录（.git）与 excluded_folders（node_modules）。"""
        fs = LocalAdapter(str(sample_dir))
        (sample_dir / ".git").mkdir()
        (sample_dir / ".git" / "HEAD").write_text("ref", encoding="utf-8")
        (sample_dir / "node_modules").mkdir()
        (sample_dir / "node_modules" / "lib.js").write_text("x", encoding="utf-8")
        (sample_dir / "docs" / "guide.md").write_text("g", encoding="utf-8")
        fa = FolderAnalyzer(excluded_folders=["node_modules"])
        s = fa.collect_structure(fs, ".")
        assert s["file_count"] == 7  # 6 原始 + docs/guide.md；不含 .git/node_modules
        assert ".git" not in s["subdirs"] and "node_modules" not in s["subdirs"]
        assert s["ext_distribution"].get(".js") is None

    def test_build_structure_webdav_root(self):
        """WebDAV 挂载根（base="/"）统计不空。"""
        from naskb.common.fs.base import FileStat
        files = [
            FileStat(path="/a.txt", name="a.txt", size_bytes=3,
                     mtime=0.0, ext=".txt"),
            FileStat(path="/sub/b.txt", name="b.txt", size_bytes=3,
                     mtime=0.0, ext=".txt"),
        ]
        s = FolderAnalyzer.build_structure(files, "/")
        assert s["file_count"] == 2
        assert s["ext_distribution"][".txt"] == 2
        assert s["subdirs"] == ["sub"]


class _FakeLLM:
    """模拟 DeepSeek complete_json。"""

    def complete_json(self, prompt: str) -> dict:
        assert "扩展名分布" in prompt  # 结构统计进了 prompt
        return {
            "description": "Python 软件项目目录",
            "structure": [
                {"name": "src", "type": "dir", "summary": "源码"},
                {"name": "main.py", "type": "file", "summary": "入口"},
            ],
            "tags": ["代码", "Python", "软件"],
            "summary": "一个 Python 项目",
            "language": "zh",
            "confidence": 0.9,
        }


class TestAnalyzeWithLLM:
    def test_llm_generates_entry(self, sample_dir):
        fs = LocalAdapter(str(sample_dir))
        fa = FolderAnalyzer(llm_client=_FakeLLM())
        entry = fa.analyze(fs, ".")
        assert entry.description == "Python 软件项目目录"
        assert entry.summary == "一个 Python 项目"
        assert entry.tags == ["代码", "Python", "软件"]
        assert len(entry.structure) == 2
        assert entry.structure[0]["type"] == "dir"
        assert entry.confidence == 0.9
        assert entry.file_type_distribution[".py"] == 4

    def test_llm_structure_capped(self, sample_dir):
        fs = LocalAdapter(str(sample_dir))
        fa = FolderAnalyzer(llm_client=_FakeLLM())
        entry = fa.analyze(fs, ".")
        assert len(entry.structure) <= 20
