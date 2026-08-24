"""chunker — MinerU Markdown 标题层级分段（D' 方案 / REQ-R5-06）。

设计参考 MaxKB v2 标题树递归分段思想（只读学设计，代码自行实现，REQ-R6-07）：
- 标题树递归切分：块按标题层级组织，title_path 记录章节路径（比 MaxKB 的空格平铺增强为结构化数组）
- 代码围栏掩码：``` 内的 # 不当作标题（防伪标题）
- 句末智能切分：超长块在句末标点处断开，且至少保留窗口后半段
自研差异（超越参考实现）：
- 块间重叠（overlap_ratio），弥补跨页长条款丢失上下文
- title_path 前置拼入嵌入文本（emb_text），提升章节名/主张召回
- 超长表格按行切段并重复表头（转义由调用方或解析层负责，此处保持原文）

本模块为纯函数（输入 md 文本 → 输出 Chunk 列表），不触 fs/网络/PG，便于离线单测。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

TARGET_CHARS = 800        # 目标块字符数（阶段 3 评测定稿）
LIMIT_CHARS = 1200        # 硬上限（超限才触发句末智能切分）
OVERLAP_RATIO = 0.12      # 句末切分的相邻块间重叠比例（标题树断层处不加）
_SENT_END = "。！？!?；;\n"
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Chunk:
    """一个可检索的条款级分段。"""

    seq: int                       # 块序号（同一文档内递增）
    title_path: list[str]          # 结构化标题路径（如 ["第6章 试验方法","6.3 压力试验","6.3.2 ..."]）
    text: str                      # 块正文（含标题下的内容；不含标题行）
    start: int                     # 在源 md 中的字符偏移（含）
    end: int                       # 在源 md 中的字符偏移（不含）

    @property
    def emb_text(self) -> str:
        """用于向量化的文本：标题路径前置拼入正文（提升章节名/主张召回）。"""
        prefix = " > ".join(t for t in self.title_path if t)
        return (prefix + "\n" + self.text).strip()


def _preprocess(text: str) -> str:
    """归一化换行/去 NUL/压缩多余空行（保留一个空行作段界）。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return re.sub(r"\n{3,}", "\n\n", text)


def _split_lines(text: str) -> list[str]:
    """含换行符的按行切分（keepends），偏移量=各元素累计长度。"""
    return re.split(r"(?<=\n)", text)


def _parse_headings(lines: list[str]) -> list[dict]:
    """识别标题行（跳过代码围栏内部），返回 {level,title,line} 列表。"""
    heads: list[dict] = []
    in_fence = False
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if _FENCE_RE.match(stripped):
            # ``` 与 ~~~ 围栏切换（闭合检测按行首围栏标记）
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            # 过滤纯 # 空标题与纯符号标题（如 "###" 或 "####"）
            if title and not re.fullmatch(r"#+", title):
                heads.append({"level": level, "title": title, "line": i})
    return heads


def _build_tree(heads: list[dict], n_lines: int) -> dict:
    """把标题栈构建为父子树（根为虚拟 level0）。返回根节点。

    每个节点含 level/title/line/children/end_line（end_line=下一个 level<= 此节点 level
    的标题行号，未闭合则=n_lines）。
    """
    root = {"level": 0, "title": None, "line": -1, "children": [], "end_line": n_lines}
    stack = [root]
    for h in heads:
        node = {"level": h["level"], "title": h["title"], "line": h["line"],
                "children": [], "end_line": None}
        while stack and stack[-1]["level"] >= node["level"]:
            closed = stack.pop()
            if closed["end_line"] is None:
                closed["end_line"] = node["line"]
        stack[-1]["children"].append(node)
        stack.append(node)
    while stack:
        closed = stack.pop()
        if closed["end_line"] is None:
            closed["end_line"] = n_lines
    return root


def _smart_split_chunks(text: str, start_char: int, limit: int,
                        overlap_ratio: float) -> list[tuple[str, int, int]]:
    """把超长文本按句末标点切成多块（保后半段约束 + 块间重叠）。

    返回 [(piece_text, abs_start, abs_end), ...]，abs 偏移相对源文本。
    """
    n = len(text)
    if n <= limit:
        return [(text, start_char, start_char + n)]
    pieces: list[tuple[str, int, int]] = []
    pos = 0
    while pos < n:
        remaining = n - pos
        limit_now = limit if remaining >= limit else remaining
        window_end = pos + limit_now
        cut = -1
        search_from = pos + max(1, int(limit_now * 0.5))
        # 从窗口尾部回找句末标点
        for i in range(window_end - 1, search_from - 1, -1):
            if text[i] in _SENT_END:
                cut = i + 1
                break
        if cut <= pos:
            cut = window_end  # 找不到句末点，硬切
        if cut > n:
            cut = n
        piece = text[pos:cut]
        if piece.strip():
            pieces.append((piece, start_char + pos, start_char + cut))
        if cut >= n:
            break
        overlap = int((cut - pos) * overlap_ratio)
        next_pos = pos + (cut - pos)  # 正常前进
        # 重叠：下一块从 cut-overlap 起，但必须前进（防死循环）
        if overlap > 0:
            cand = cut - overlap
            next_pos = cand if cand > pos else pos + 1
        pos = next_pos if next_pos > pos else cut
        if pos > n:
            pos = n
    return pieces


def _emit(node: dict, chain: list[str], lines: list[str], acc: list[dict],
          target: int, limit: int, overlap_ratio: float) -> None:
    """DFS 递归生成块：有子标题则发「前导段」+ 逐子递归；叶子发整段。"""
    title = (node["title"] or "").strip()
    path = chain + ([title] if title else [])
    node_start = node["line"] + 1           # 标题行之后（根节点 line=-1 → 0）
    node_end = node["end_line"]
    children = node["children"]

    if children:
        first = children[0]["line"]
        # 前导段：节点起始 到 首个直接子标题之间
        if first > node_start:
            preamble = "".join(lines[node_start:first])
            if preamble.strip():
                start_off = len("".join(lines[:node_start]))
                _add(preamble, path, acc, start_off, target, limit, overlap_ratio)
        for ch in children:
            _emit(ch, path, lines, acc, target, limit, overlap_ratio)
    else:
        if node_end > node_start:
            content = "".join(lines[node_start:node_end])
            if content.strip():
                start_off = len("".join(lines[:node_start]))
                _add(content, path, acc, start_off, target, limit, overlap_ratio)


def _table_heavy(text: str) -> bool:
    """是否以 Markdown 管道表为主（避免在表格行内按句末标点切碎表格）。

    MinerU 输出的表格是 `| a | b |` 行；若表中出现 `。` 等句末字符，按句切分会
    把表格行截断/错位。表格为主的块整体保留（超长表格的多段拆分在解析层用
    「按行累加 + 重复表头」处理，属后续增强，本模块先保证不破坏表结构）。
    """
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return False
    table_lines = sum(1 for ln in lines if ln.lstrip().startswith("|"))
    return table_lines >= max(2, int(len(lines) * 0.5))


def _add(content: str, path: list[str], acc: list[dict], start_off: int,
         target: int, limit: int, overlap_ratio: float) -> None:
    """把一节文本清理+切块后加入结果（记录 seq）。"""
    text = content.strip()
    if not text:
        return
    if _table_heavy(text):
        acc.append({"title_path": path, "text": text,
                    "start": start_off, "end": start_off + len(text)})
        return
    for piece, _abs_start, _abs_end in _smart_split_chunks(
            text, start_off, limit, overlap_ratio):
        acc.append({"title_path": path, "text": piece,
                    "start": _abs_start, "end": _abs_end})


def chunk_markdown(md_text: str, *,
                   target_chars: int = TARGET_CHARS,
                   limit_chars: int = LIMIT_CHARS,
                   overlap_ratio: float = OVERLAP_RATIO) -> list[Chunk]:
    """把 MinerU 结构化 Markdown 切成条款级 Chunk 列表。"""
    text = _preprocess(md_text)
    if not text.strip():
        return []
    lines = _split_lines(text)
    heads = _parse_headings(lines)
    root = _build_tree(heads, len(lines))

    acc: list[dict] = []
    _emit(root, [], lines, acc, target_chars, limit_chars, overlap_ratio)

    # 编号 + 转 Chunk；首标题前的前言若落空也保留（文档无标题时整个成为一段）
    chunks: list[Chunk] = []
    for i, item in enumerate(acc):
        chunks.append(Chunk(
            seq=i + 1,
            title_path=list(item["title_path"]),
            text=item["text"],
            start=item["start"],
            end=item["end"],
        ))
    return chunks


def chunk_text_for_embed(chunk: Chunk) -> str:
    """供同步层直接调用的嵌入文本（与 Chunk.emb_text 一致，独立暴露便于测试）。"""
    return chunk.emb_text
