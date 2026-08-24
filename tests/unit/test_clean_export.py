"""clean_export 单测（REQ-R5-02）：干净 Markdown 构造 + 目录/ZIP 导出。"""
import os
import zipfile

from naskb.common.clean_export import build_clean_markdown, export_clean
from naskb.common.retrieval import Doc


def _doc(path="D:/标准.pdf", summary="压力试验规范", category="标准", tags=None,
         context="第6章 试验方法\n施加 1.5 倍压力。"):
    return Doc(path=path, kind="file", text=summary, summary=summary,
               category=category, tags=tags or [], context=context)


def test_build_clean_markdown_front_matter():
    md = build_clean_markdown(_doc(tags=["标准", "试验"]))
    assert md.startswith("---\n")
    assert 'path: "D:/标准.pdf"' in md
    assert 'category: "标准"' in md
    assert 'tags: ["标准", "试验"]' in md
    assert "## 摘要" in md and "## 内容" in md
    assert "第6章 试验方法" in md          # 内容保留


def test_build_clean_markdown_no_context_falls_back():
    md = build_clean_markdown(_doc(context=""))
    assert "## 摘要" in md
    # 无 context 时用 text 兜底（仍保留）

def test_export_clean_dir(tmp_path):
    docs = [_doc(path="D:/标准.pdf", context="标准正文"), _doc()]  # 一条缺 path? 都有
    res = export_clean(docs, str(tmp_path))
    assert res["files"] == 2
    names = os.listdir(tmp_path)
    assert any(n.endswith(".md") for n in names)


def test_export_clean_zip(tmp_path):
    docs = [_doc(path="D:/标准.pdf", context="标准正文")]
    res = export_clean(docs, str(tmp_path), zip=True)
    assert res["files"] == 1
    assert res["out"].endswith(".zip")
    with zipfile.ZipFile(res["out"]) as zf:
        assert len(zf.namelist()) == 1
        assert zf.namelist()[0].endswith(".md")
