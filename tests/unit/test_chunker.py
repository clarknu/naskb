"""chunker 分段器单测（D' / REQ-R5-06）。

覆盖：标题树递归分段、title_path 结构化、代码围栏掩码、句末智能切分 + 重叠、
表格保护、无标题文档整段、空文档、纯 # 标题过滤。
"""
import pytest

from naskb.common.chunker import (
    chunk_markdown, Chunk, LIMIT_CHARS, OVERLAP_RATIO,
)


def _titles(paths):
    return [c.title_path for c in paths]


def _single(chunks):
    assert len(chunks) == 1, f"expected 1 chunk, got {len(chunks)}"
    return chunks[0]


# ── 标题树递归 + title_path ────────────────────────────────────────────
def test_nested_headings_produce_structured_path():
    md = (
        "# 第6章 试验方法\n"
        "引言段。\n\n"
        "## 6.3 压力试验\n"
        "压力试验内容甲。\n\n"
        "### 6.3.2 保压时间\n"
        "保压不少于 30 分钟。\n\n"
        "## 6.4 气密试验\n"
        "气密内容乙。\n"
    )
    cs = chunk_markdown(md)
    # 顶层引言 + 6.3（含前导段与 6.3.2）+ 6.4
    paths = [tuple(c.title_path) for c in cs]
    assert ("第6章 试验方法",) in paths           # 引言段（第6章 直接内容前导）
    assert ("第6章 试验方法", "6.3 压力试验", "6.3.2 保压时间") in paths
    assert ("第6章 试验方法", "6.4 气密试验") in paths
    # 6.3 的子块应带完整面包屑（不丢父级）
    for c in cs:
        if "保压" in c.text:
            assert c.title_path == ["第6章 试验方法", "6.3 压力试验", "6.3.2 保压时间"]


def test_preamble_before_first_heading_is_captured():
    md = "这是没有标题的前言，描述标准适用范围。\n\n# 第一章\n正文。\n"
    cs = chunk_markdown(md)
    # 前言应成一块（无标题路径）
    assert _single([c for c in cs if "前言" in c.text]).title_path == []
    assert len(cs) >= 2


def test_leaf_title_path_flat_into_emb_text():
    c = chunk_markdown("## 6.3.2 保压时间\n保压不少于 30 分钟。")[0]
    assert c.title_path == ["6.3.2 保压时间"]
    assert "6.3.2 保压时间" in c.emb_text and "保压不少于" in c.emb_text


# ── 代码围栏掩码 ───────────────────────────────────────────────────────
def test_code_fence_hash_not_heading():
    md = (
        "# 章节\n正文。\n\n"
        "```python\n"
        "# 这是注释，不是标题\n"
        "def f():\n    pass\n"
        "```\n"
    )
    cs = chunk_markdown(md)
    # 只应有一个章节标题；注释行不产生标题块
    assert all(c.title_path != ["这是注释，不是标题"] for c in cs)
    assert len(cs) == 1  # 仅 "# 章节" 一节，其内容含代码块


# ── 句末智能切分 + 重叠 ───────────────────────────────────────────────
def test_long_paragraph_smart_split_with_overlap():
    # 构造>LIMIT 的长文本，句号为断点
    body = "。".join(f"第{i}句内容语句填充以接近长度阈值确保超出限制" for i in range(400))
    cs = chunk_markdown("## 条款\n" + body)
    assert len(cs) >= 3
    for c in cs:
        assert len(c.text) <= LIMIT_CHARS or _is_table(c.text)
    # 块间重叠：相邻块应共享文本尾部
    overlaps = 0
    for a, b in zip(cs, cs[1:]):
        if a.text[-20:] in b.text or a.text[:20] in b.text:
            overlaps += 1
    assert overlaps >= 1, "相邻块应存在重叠（overlap_ratio>0）"


def _is_table(t):
    lines = [ln for ln in t.split("\n") if ln.strip()]
    return lines and any(l.lstrip().startswith("|") for l in lines)


def test_no_heading_doc_is_single_smart_block():
    body = "。".join(f"普通段落内容{ i }" for i in range(80))
    cs = chunk_markdown(body)
    assert len(cs) >= 1
    assert all(c.title_path == [] for c in cs)


# ── 表格保护 ───────────────────────────────────────────────────────────
def test_table_heavy_block_not_split():
    rows = "\n".join(f"| 参数{i} | 值{i} | 单位 |" for i in range(30))
    md = f"## 表格\n| 参数 | 值 | 单位 |\n| --- | --- | --- |\n{rows}\n"
    cs = chunk_markdown(md)
    # 表格为主 → 整体一块（不被句末标点切碎），保留全部行
    assert len(cs) == 1
    assert cs[0].text.count("| 参数0 |") == 1
    assert "参数29" in cs[0].text


# ── 空/边界 ────────────────────────────────────────────────────────────
def test_empty_and_blank_doc():
    assert chunk_markdown("") == []
    assert chunk_markdown("\n\n\n") == []


def test_pure_hash_heading_filtered():
    md = "#\n正文。\n####\n更多。\n"
    cs = chunk_markdown(md)
    # 纯 # 标题被过滤，正文归入无标题块
    assert all(c.title_path == [] for c in cs)
    assert any("正文" in c.text for c in cs)


def test_blank_line_preserved_as_boundary():
    md = "# 甲\n近段结束。\n\n\n\n新段落开始。\n"
    cs = chunk_markdown(md)
    assert len(cs) == 1
    # 预处理把 3+ 连续换行压缩到 ≤2 个（保留一个空行作段界，不吞内容）
    assert "\n\n\n" not in cs[0].text
    assert "近段结束" in cs[0].text and "新段落开始" in cs[0].text
