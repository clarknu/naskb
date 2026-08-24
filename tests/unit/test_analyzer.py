"""文档分析器测试：文本提取、编码探测、依赖缺失降级。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "naskb" / "scripts"))

import pytest

from naskb.common.analyzer import DocumentAnalyzer, ExtractionResult
from naskb.common.fs.local import LocalAdapter


@pytest.fixture
def analyzer():
    return DocumentAnalyzer(max_chars=1000)


class TestTextFile:
    def test_txt_utf8(self, analyzer, tmp_path):
        f = tmp_path / "笔记.txt"
        f.write_text("这是中文笔记内容。", encoding="utf-8")
        r = analyzer.extract(str(f))
        assert r.text == "这是中文笔记内容。"
        assert r.analyzer == "text"
        assert r.error is None
        assert r.metadata.file_size > 0

    def test_md(self, analyzer, tmp_path):
        f = tmp_path / "README.md"
        f.write_text("# Title\n\nBody text", encoding="utf-8")
        r = analyzer.extract(str(f))
        assert "Title" in r.text

    def test_gbk_encoding_fallback(self, analyzer, tmp_path):
        """GBK 编码文件（无 chardet 时通过回退链解码）。"""
        f = tmp_path / "gbk.txt"
        f.write_bytes("简体中文内容".encode("gbk"))
        r = analyzer.extract(str(f))
        assert r.text == "简体中文内容"

    def test_csv(self, analyzer, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("name,age\nalice,30", encoding="utf-8")
        r = analyzer.extract(str(f))
        assert "alice" in r.text

    def test_truncation(self, tmp_path):
        a = DocumentAnalyzer(max_chars=10)
        f = tmp_path / "long.txt"
        f.write_text("x" * 100, encoding="utf-8")
        r = a.extract(str(f))
        assert r.truncated is True
        assert len(r.text) == 10


class TestUnsupported:
    def test_unknown_ext(self, analyzer, tmp_path):
        f = tmp_path / "archive.xyz"
        f.write_bytes(b"\x00\x01binary")
        r = analyzer.extract(str(f))
        assert r.text is None
        assert "不支持" in r.error

    def test_no_ext(self, analyzer, tmp_path):
        f = tmp_path / "README"
        f.write_text("hello", encoding="utf-8")
        r = analyzer.extract(str(f))
        assert r.text is None
        assert r.error


class TestPdf:
    def test_parse_failure_degrades(self, analyzer, tmp_path):
        """PDF 无法解析时优雅降级，不抛异常（依赖缺失或文件损坏均覆盖）。"""
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 fake pdf bytes")
        r = analyzer.extract(str(f))
        assert r.analyzer == "pdf"
        if r.text is None:
            assert r.error, "PDF 提取失败应返回 error 说明"
        else:
            pytest.skip("PDF 解析成功，跳过降级断言")

    def test_missing_dependency_message(self, analyzer, tmp_path):
        """PyMuPDF 未安装时 error 明确提示安装命令。"""
        f = tmp_path / "doc2.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        r = analyzer.extract(str(f))
        if r.error and "PyMuPDF" in r.error:
            assert "pip install pymupdf" in r.error
        else:
            pytest.skip("PyMuPDF 已安装，跳过依赖缺失提示测试")

    def test_scan_like_detection(self, tmp_path):
        """扫描件特征：图片页 + 文本稀薄 → exif.scan_like=True。"""
        import pymupdf as fitz

        f = tmp_path / "scan.pdf"
        doc = fitz.open()
        page = doc.new_page()
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 200))
        pix.clear_with(200)
        page.insert_image(fitz.Rect(50, 50, 300, 300), pixmap=pix)
        page.insert_text((50, 350), "扫描件内嵌 OCR 层")  # 少量文本
        doc.save(f)
        doc.close()

        r = DocumentAnalyzer().extract(str(f))
        assert r.analyzer == "pdf"
        assert r.text is not None
        assert r.metadata.exif.get("scan_like") is True
        assert r.metadata.exif.get("page_count") == 1

    def test_text_pdf_not_scan_like(self, tmp_path):
        """纯文本 PDF（无图片页）→ scan_like=False。"""
        import pymupdf as fitz

        f = tmp_path / "text.pdf"
        doc = fitz.open()
        page = doc.new_page()
        for i in range(20):  # 足够多的文本
            page.insert_text((72, 72 + i * 30), f"这是第 {i} 行文本内容", fontsize=12)
        doc.save(f)
        doc.close()

        r = DocumentAnalyzer().extract(str(f))
        assert r.metadata.exif.get("scan_like") is False


class TestDocx:
    def test_parse_failure_degrades(self, analyzer, tmp_path):
        """Word 文档无法解析时优雅降级，不抛异常（依赖缺失或文件损坏均覆盖）。"""
        f = tmp_path / "doc.docx"
        f.write_bytes(b"PK\x03\x04 fake docx")
        r = analyzer.extract(str(f))
        assert r.analyzer == "docx"
        if r.text is None:
            assert r.error
        else:
            pytest.skip("python-docx 解析成功，跳过降级断言")


class TestDoc:
    def test_not_doc_degrades(self, analyzer, tmp_path):
        """非 .doc 内容（如随机字节）应优雅降级不抛异常。"""
        f = tmp_path / "old.doc"
        f.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x11\xe1 random bytes")
        r = analyzer.extract(str(f))
        assert r.analyzer == "doc"
        if r.text is None:
            assert r.error

    def test_extract_doc_via_analyzer_dispatches(self, tmp_path):
        """DocumentAnalyzer 对 .doc 分发到 extract_doc。"""
        f = tmp_path / "x.doc"
        f.write_bytes(b"not a real doc")
        r = DocumentAnalyzer().extract(str(f))
        assert r.analyzer == "doc"


try:
    import xlrd
except ImportError:
    xlrd = None


@pytest.mark.skipif(xlrd is None, reason="xlrd not installed (optional: old .xls format)")
class TestXls:
    def test_not_xls_degrades(self, analyzer, tmp_path):
        """非 .xls 内容应优雅降级不抛异常。"""
        f = tmp_path / "old.xls"
        f.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x11\xe1 random bytes")
        r = analyzer.extract(str(f))
        assert r.analyzer == "xls"
        if r.text is None:
            assert r.error

    def test_xls_via_analyzer_dispatches(self, tmp_path):
        f = tmp_path / "x.xls"
        f.write_bytes(b"not a real xls")
        r = DocumentAnalyzer().extract(str(f))
        assert r.analyzer == "xls"


class TestXlsx:
    def test_parse_failure_degrades(self, analyzer, tmp_path):
        """Excel 文件无法解析时优雅降级，不抛异常（依赖缺失或文件损坏均覆盖）。"""
        f = tmp_path / "book.xlsx"
        f.write_bytes(b"PK\x03\x04 fake xlsx")
        r = analyzer.extract(str(f))
        assert r.analyzer == "xlsx"
        if r.text is None:
            assert r.error
        else:
            pytest.skip("openpyxl 解析成功，跳过降级断言")


class TestRemote:
    def test_extract_remote_local_fs(self, analyzer, tmp_path):
        """通过 fs adapter 下载提取，临时文件清理。"""
        from naskb.common.fs.local import LocalAdapter

        f = tmp_path / "remote.txt"
        f.write_text("远端内容", encoding="utf-8")

        fs = LocalAdapter(str(tmp_path))
        tmp_dir = tmp_path / "tmp" / "analyzer"
        r = analyzer.extract_remote(fs, str(f), str(tmp_dir))
        assert r.text == "远端内容"
        # 临时文件已清理
        leftovers = list(tmp_dir.rglob("*.tmp"))
        assert leftovers == []
        fs.close()

    def test_extract_remote_max_file_bytes(self, tmp_path):
        """超过 max_file_bytes 时拒绝下载，不产生临时文件。"""
        from naskb.common.fs.local import LocalAdapter

        a = DocumentAnalyzer(max_chars=1000, max_file_bytes=10)
        f = tmp_path / "big.txt"
        f.write_text("x" * 100, encoding="utf-8")

        fs = LocalAdapter(str(tmp_path))
        tmp_dir = tmp_path / "tmp"
        r = a.extract_remote(fs, str(f), str(tmp_dir))
        assert r.text is None
        assert "过大" in (r.error or "")
        assert not list(tmp_dir.rglob("*"))  # 未下载任何文件
        fs.close()


class TestFsFactory:
    def test_local_windows_bare_path(self, tmp_path):
        """Windows 裸盘符路径不被 urlparse 截断（回归修复）。"""
        from naskb.common.fs.base import FileSystemAdapter

        fs = FileSystemAdapter.create("local", str(tmp_path))
        assert isinstance(fs, LocalAdapter)
        assert fs.root == str(tmp_path.resolve())
        fs.close()

    def test_local_file_url(self, tmp_path):
        """file:// 前缀仍被支持。"""
        from naskb.common.fs.base import FileSystemAdapter

        fs = FileSystemAdapter.create("local", f"file://{tmp_path}")
        assert fs.root == str(tmp_path.resolve())
        fs.close()


class TestWebDAVPathMapping:
    def test_prefix_boundary(self):
        """_to_remote_path 前缀匹配要求 '/' 边界，避免 /home 误匹配 /home2。"""
        from naskb.common.fs.webdav import WebDAVAdapter

        adapter = WebDAVAdapter.__new__(WebDAVAdapter)
        adapter._root_url = "webdav://nas/home"
        adapter._root_path = "/home"

        assert adapter._to_remote_path("webdav://nas/home/a.txt") == "/home/a.txt"
        assert adapter._to_remote_path("webdav://nas/home2/a.txt") == "/home/webdav://nas/home2/a.txt"
        assert adapter._to_remote_path("/home/a.txt") == "/home/a.txt"
        assert adapter._to_remote_path("a.txt") == "/home/a.txt"
