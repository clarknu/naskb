"""MinerU 解析后端测试：可用性降级、双路径判定、产物定位。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "naskb" / "scripts"))

import pytest

from naskb.common.analyzer.mineru import MinerUAnalyzer, _module_available


class TestAvailability:
    def test_disabled(self):
        m = MinerUAnalyzer(enabled=False)
        assert m.available() is False

    def test_available_or_degrade(self, tmp_path):
        """未安装 mineru 时返回 False 且 parse 报错提示安装（不抛异常）。"""
        m = MinerUAnalyzer(enabled=True)
        # 无论装没装，available() 返回 bool 不抛异常
        assert isinstance(m.available(), bool)
        if not m.available():
            src = tmp_path / "doc.pdf"
            src.write_bytes(b"%PDF-1.4 fake")
            r = m.parse(str(src), str(tmp_path / "out"))
            assert r["ok"] is False
            assert "MinerU" in r["error"]


class TestDualPath:
    def test_rich_text_uses_fast_path(self):
        m = MinerUAnalyzer()
        assert m.needs_mineru(0.9) is False
        assert m.needs_mineru(0.5) is False

    def test_scanned_pdf_needs_mineru(self):
        m = MinerUAnalyzer()
        assert m.needs_mineru(0.1, fast_text_ratio=0.3) is True
        assert m.needs_mineru(0.0, fast_text_ratio=0.3) is True

    def test_unknown_ratio_needs_mineru(self):
        m = MinerUAnalyzer()
        assert m.needs_mineru(None) is True

    def test_text_len_sufficient_uses_fast_path(self):
        """文本量充足时直接走快速路径，避免 PDF 结构开销导致比值偏低误送。"""
        m = MinerUAnalyzer()
        # 比值低但文本量充足 → 快速路径
        assert m.needs_mineru(0.09, text_len=112, min_text_chars=80) is False
        assert m.needs_mineru(0.01, text_len=500, min_text_chars=80) is False
        # 无文本 / 极少文本 → MinerU
        assert m.needs_mineru(0.0, text_len=0) is True
        assert m.needs_mineru(0.0, text_len=20, min_text_chars=80) is True
        # 默认阈值 500：少量文本层（扫描件常见）也走 MinerU OCR
        assert m.needs_mineru(0.01, text_len=200) is True
        assert m.needs_mineru(0.01, text_len=600) is False


class TestOutputLocation:
    def test_locate_v3_auto_subdir(self, tmp_path):
        """MinerU 3.x 布局：<out>/<stem>/auto/ 下产物。"""
        out = tmp_path / "out"
        d = out / "doc" / "auto"
        d.mkdir(parents=True)
        (d / "doc.md").write_text("# 标题", encoding="utf-8")
        (d / "doc_middle.json").write_text("{}", encoding="utf-8")
        (d / "images").mkdir()
        (d / "images" / "img_1.png").write_bytes(b"png")

        m = MinerUAnalyzer()
        r = m._locate_outputs(tmp_path / "doc.pdf", str(out))
        assert r["ok"] is True
        assert r["md_path"] and r["md_path"].endswith("doc.md")
        assert r["middle_json"] and r["middle_json"].endswith("doc_middle.json")
        assert r["images_dir"] and r["images_dir"].endswith("images")

    def test_locate_subdir_layout(self, tmp_path):
        """新版输出：out/<stem>/ 子目录。"""
        out = tmp_path / "out"
        d = out / "doc"
        d.mkdir(parents=True)
        (d / "doc.md").write_text("# 标题", encoding="utf-8")
        (d / "doc.html").write_text("<h1>标题</h1>", encoding="utf-8")
        (d / "doc.middle.json").write_text("{}", encoding="utf-8")
        (d / "images").mkdir()
        (d / "images" / "img_1.png").write_bytes(b"png")

        m = MinerUAnalyzer()
        r = m._locate_outputs(tmp_path / "doc.pdf", str(out))
        assert r["ok"] is True
        assert r["md_path"].endswith("doc.md")
        assert r["html_path"].endswith("doc.html")
        assert r["middle_json"].endswith("doc.middle.json")
        assert r["images_dir"].endswith("images")

    def test_locate_flat_layout(self, tmp_path):
        """旧版输出：产物平铺在 out/ 下。"""
        out = tmp_path / "out"
        out.mkdir(parents=True)
        (out / "doc.md").write_text("# 标题", encoding="utf-8")
        m = MinerUAnalyzer()
        r = m._locate_outputs(tmp_path / "doc.pdf", str(out))
        assert r["ok"] is True
        assert r["md_path"].endswith("doc.md")

    def test_locate_nothing_found(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir(parents=True)
        m = MinerUAnalyzer()
        r = m._locate_outputs(tmp_path / "doc.pdf", str(out))
        assert r["ok"] is False
        assert "未找到产物" in r["error"]

    def test_parse_missing_source(self, tmp_path):
        m = MinerUAnalyzer()
        r = m.parse(str(tmp_path / "nope.pdf"), str(tmp_path / "out"))
        assert r["ok"] is False
        assert "源文件不存在" in r["error"]
