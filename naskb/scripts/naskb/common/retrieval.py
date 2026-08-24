"""基于 .naskb 描述数据的检索与问答。

- BM25 关键词模糊搜索（零第三方依赖：中文按单字+bigram，英文按单词分词）
- RAG 问答：检索 top-k 描述 → DeepSeek 生成带来源的回答

只消费 .naskb/ 描述数据（index.json / folder.json），不读文件原文。
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from .desc_store import REPO_DIR_NAME, FileEntry, FolderEntry, _fs_read_json


@dataclass
class Doc:
    """可检索的描述文档。"""
    path: str            # 原文件/目录路径
    kind: str            # "file" | "folder"
    text: str            # 检索索引文本（仅摘要+描述，不含全文——用户拍板）
    summary: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    context: str = ""    # RAG 生成上下文（含全文，供 ask 回答细节问题）
    content_description: str = ""   # 内容描述（v3：入库 PG 独立列）
    file_type: str = ""             # 类型标记（扩展名/类别名，v3）
    artifacts: dict = field(default_factory=dict)   # 解析产物登记（解析视图用）
    md_abs: str = ""            # 绝对 MinerU Markdown 路径（chunk 分段源，REQ-R5-06）
    # 指纹（REQ-R4-05 / ADR-20260816-4）：sync-vectors 与去重使用
    file_hash: str = ""
    hash_algorithm: str = ""
    size_bytes: int = 0
    mtime: float = 0.0
    ctime: float = 0.0
    analyzed_at: str = ""


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """中文按单字+bigram，英文/数字按单词。零依赖分词。"""
    tokens: list[str] = []
    for w in _TOKEN_RE.findall(text.lower()):
        tokens.append(w)
    for chunk in _CJK_RE.findall(text):
        for i in range(len(chunk)):
            tokens.append(chunk[i])
            if i + 1 < len(chunk):
                tokens.append(chunk[i:i + 2])
    return tokens


class BM25Index:
    """BM25 关键词检索（k1=1.5, b=0.75 标准参数）。"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self._k1 = k1
        self._b = b
        self._docs: list[Doc] = []
        self._doc_tokens: list[list[str]] = []
        self._doc_lens: list[int] = []
        self._avgdl = 0.0
        self._idf: dict[str, float] = {}

    def build(self, docs: list[Doc]) -> None:
        self._docs = list(docs)
        self._doc_tokens = [tokenize(d.text) for d in self._docs]
        self._doc_lens = [len(t) for t in self._doc_tokens]
        n = len(self._docs)
        self._avgdl = sum(self._doc_lens) / n if n else 0.0
        df: Counter = Counter()
        for toks in self._doc_tokens:
            df.update(set(toks))
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, top_k: int = 10,
               kind: Optional[str] = None) -> list[dict]:
        """返回 [{score, path, kind, summary, category, tags}]，按得分降序。"""
        q = set(tokenize(query))
        scored: list[tuple[float, int]] = []
        for i, toks in enumerate(self._doc_tokens):
            if kind and self._docs[i].kind != kind:
                continue
            tf = Counter(toks)
            s = 0.0
            dl = self._doc_lens[i]
            for t in q:
                f = tf.get(t, 0)
                if not f or t not in self._idf:
                    continue
                denom = (f + self._k1 * (1 - self._b + self._b * dl / self._avgdl)
                         if self._avgdl else f)
                s += self._idf[t] * f * (self._k1 + 1) / denom
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: -x[0])
        return [
            {
                "score": s,
                "path": self._docs[i].path,
                "kind": self._docs[i].kind,
                "summary": self._docs[i].summary,
                "category": self._docs[i].category,
                "tags": self._docs[i].tags,
                "text": self._docs[i].text,      # 索引文本（摘要+描述）
                "context": self._docs[i].context,  # RAG 上下文（含全文）
            }
            for s, i in scored[:top_k]
        ]


def _to_rel(path: str, root: str) -> str:
    """统一路径语义（B-06）：归一到源内相对路径（posix）；跨盘符保留原值。"""
    p = path.replace("\\", "/")
    try:
        r = os.path.relpath(p, root).replace("\\", "/")
    except ValueError:
        return p
    if r in (".", ""):
        return p.split("/")[-1] if "/" in p else p
    return r.lstrip("./")


def collect_docs(fs, root: str, repo_name: str = ".naskb") -> list[Doc]:
    """遍历目录树，读取所有 .naskb/index.json + folder.json 构建 Doc 列表。"""
    docs: list[Doc] = []
    for f in fs.list_files(root, recursive=True):
        if f.name not in ("index.json", "folder.json"):
            continue
        rel = f.path.replace("\\", "/")
        if f"/{repo_name}/" not in rel:
            continue
        try:
            # index.json 可能很大（数百 KB），用 2MB 缓冲区读取
            raw_bytes = fs.read_bytes(f.path, max_bytes=2_000_000)
            data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        repo_dir = os.path.dirname(os.path.dirname(f.path))
        if f.name == "index.json":
            for raw in data.get("files") or []:
                entry = FileEntry.from_dict(raw)
                # 完整原数据在独立文件（.naskb/files/<rel>.json）时读取它拿全文
                df = raw.get("data_file")
                if df:
                    df_path = os.path.join(repo_dir, REPO_DIR_NAME, "files",
                                           df).replace("\\", "/")
                    if fs.exists(df_path):
                        full = _fs_read_json(fs, df_path)
                        if full is not None:
                            entry = FileEntry.from_dict(full)
                # 当前位置：检索/展示必须用文件当前所在路径（original_path
                # 只是 provenance，可能是历史本地路径或迁移前路径）
                cur_path = os.path.join(repo_dir, raw.get("path", "")) \
                    .replace("\\", "/")
                # B-06 统一语义（2026-08-24）：Doc.path = 源内相对路径（posix），
                # 与 collect_staging_docs 及数据库 rel_path 列一致；跨盘符（Windows
                # 分区）时退化为绝对路径。
                cur_path = _to_rel(cur_path, root)
                # 检索索引文本：只用摘要+描述（用户拍板——全文不参与向量/关键词检索，
                # 避免全文高频词稀释主题）；全文保留在 context 供 RAG 生成阶段使用
                text = "\n".join(x for x in (
                    cur_path,
                    entry.summary, entry.category, " ".join(entry.tags),
                    entry.content_description) if x)
                context = "\n".join(x for x in (
                    cur_path,
                    entry.summary, entry.category, " ".join(entry.tags),
                    entry.content_description, entry.transcription,
                    entry.ocr_text) if x)
                if not text.strip():
                    continue
                _artifacts = entry.exif.get("mineru_artifacts") or {}
                _md_abs = ""
                if _artifacts.get("md_path"):
                    _md_abs = os.path.join(
                        repo_dir, REPO_DIR_NAME,
                        str(_artifacts["md_path"]).lstrip("/\\"),
                    ).replace("\\", "/")
                docs.append(Doc(
                    path=cur_path,
                    kind="file",
                    text=text,
                    summary=entry.summary,
                    category=entry.category,
                    tags=entry.tags,
                    context=context,
                    content_description=entry.content_description,
                    file_type=entry.file_type,
                    artifacts=_artifacts,
                    md_abs=_md_abs,
                    file_hash=entry.file_hash,
                    hash_algorithm=entry.hash_algorithm,
                    size_bytes=entry.size_bytes,
                    mtime=entry.mtime,
                    ctime=entry.ctime,
                    analyzed_at=entry.analyzed_at,
                ))
        else:  # folder.json
            entry = FolderEntry.from_dict(data)
            text = "\n".join(x for x in (
                entry.summary, entry.description, " ".join(entry.tags)) if x)
            if not text.strip():
                continue
            docs.append(Doc(
                path=_to_rel(repo_dir, root), kind="folder", text=text,
                summary=entry.summary, category="目录", tags=entry.tags,
                context=text))
    return docs


def ask(client, index: BM25Index, question: str, top_k: int = 5,
        context_chars: int = 6000,
        hybrid: bool = False) -> dict:
    """RAG 问答：检索 top-k 描述 → LLM 生成带来源的回答。

    上下文包含检索到的**完整描述文本**（摘要+全文，预算内裁剪），
    而不是只有摘要——否则"月租金多少/和谁签的"这类细节问题
    会因上下文缺失而答不出来。
    hybrid: 混合检索（R5-05，仅 PG 引擎生效）：向量+关键词 RRF 融合后
            交给 LLM；其它引擎（BM25 索引/向量索引）忽略该开关。
    """
    if hybrid:
        from .pgsearch import PgSearchEngine
        if isinstance(index, PgSearchEngine):
            hits = index.search(question, top_k=top_k, hybrid=True)
        else:
            hits = index.search(question, top_k=top_k)
    else:
        hits = index.search(question, top_k=top_k)
    if not hits:
        return {"answer": "知识库中没有找到与问题相关的描述。", "sources": []}
    budget = context_chars
    blocks: list[str] = []
    for i, h in enumerate(hits):
        head = f"[{i + 1}] {h['path']}（{h['category'] or '未分类'}）"
        # 生成上下文用 context（含全文）；无 context 时退回索引文本
        body = (h.get("context") or h.get("text") or "").strip()
        if not body:
            continue
        if len(head) + len(body) > budget:
            body = body[:max(0, budget - len(head))]
        blocks.append(f"{head}:\n{body}")
        budget -= len(head) + len(body) + 2
        if budget <= 0:
            break
    ctx = "\n\n".join(blocks)
    prompt = (
        "你是一个个人知识库问答助手。以下是按相关性检索到的文件内容"
        "（包含摘要与提取的完整文本）。\n"
        "请只依据这些内容回答用户的问题；若内容不足以回答，请明确说"
        "\"知识库中没有找到相关内容\"。回答用中文，结尾列出引用的来源路径。\n\n"
        f"检索到的内容:\n{ctx}\n\n用户问题: {question}"
    )
    answer = client.complete(prompt)
    return {"answer": answer, "sources": [h["path"] for h in hits]}


def ask_deep(client, searcher, question: str, *,
             top_k: int = 5, context_chars: int = 6000,
             direct_return: bool = False,
             direct_return_similarity: float = 0.9,
             no_hit_mode: str = "designated") -> dict:
    """条款级 RAG 问答（REQ-R5-06）：两级引用 + 保真直返 + 无命中兜底。

    searcher: 具有 search_chunks(query, top_k=None) -> list[dict] 的对象，
              每个 hit 含 path/level/chunk_seq/title_path/text/context/score。
    direct_return: 最高分命中相似度 ≥ direct_return_similarity 时，直接返回
                   该条款原文+两级出处，不调 LLM（标准条款保真，防改写）。
    no_hit_mode: 'designated'（默认，明确"未找到依据"）/ 'llm_fallback'
                 （裸问模型，回答前缀声明未依据库内文档）。
    返回 answer/sources（路径列表）/citations（两级引用对象）/engine/mode。
    """
    method = getattr(searcher, "search_chunks", None)
    hits = (method(question, top_k=top_k) if callable(method)
            else searcher.search(question, top_k=top_k))
    if not hits:
        return _no_hit(client, question, no_hit_mode)

    best = hits[0]
    if direct_return and float(best.get("score") or 0) >= direct_return_similarity:
        return {
            "answer": (best.get("context") or best.get("text") or "").strip(),
            "sources": [best.get("path") or ""],
            "citations": [_cite(best)],
            "engine": "pg-chunk", "mode": "direct",
            "score": float(best.get("score") or 0),
        }

    blocks: list[str] = []
    budget = context_chars
    for i, h in enumerate(hits):
        path = h.get("path") or ""
        cats = " ▸ ".join(t for t in (h.get("title_path") or []) if t)
        head = f"[{i + 1}] {path}（{cats or '未分节'}）"
        body = (h.get("context") or h.get("text") or "").strip()
        if not body:
            continue
        if len(head) + len(body) > budget:
            body = body[:max(0, budget - len(head))]
        blocks.append(f"{head}:\n{body}")
        budget -= len(head) + len(body) + 2
        if budget <= 0:
            break
    ctx = "\n\n".join(blocks) if blocks else ""
    if not ctx:
        return _no_hit(client, question, no_hit_mode)

    prompt = (
        "你是一个知识库条款问答助手。以下是按相关性检索到的**条款片段**"
        "（每条含文件路径与章节路径）。\n"
        "请只依据这些片段回答用户的问题；引用时注明条款编号或章节路径；"
        "若片段不足以回答，直接说\"知识库中未找到可依据的条款\"。"
        "回答用中文。\n\n"
        f"检索到的条款片段:\n{ctx}\n\n用户问题: {question}"
    )
    answer = client.complete(prompt)
    citations = [_cite(h) for h in hits]
    return {"answer": answer, "sources": [h.get("path", "") for h in hits],
            "citations": citations, "engine": "pg-chunk", "mode": "rag"}


def _cite(h: dict) -> dict:
    """两级引用对象：文件路径 + 条款路径 + 块序 + 分数。"""
    return {"path": h.get("path", ""), "chunk_seq": h.get("chunk_seq"),
            "title_path": list(h.get("title_path") or []),
            "score": round(float(h.get("score") or 0), 6)}


def _no_hit(client, question: str, mode: str) -> dict:
    if mode == "llm_fallback":
        try:
            answer = client.complete(
                f"用户问题: {question}\n请回答；若依据不足请明确说明。")
        except Exception:
            answer = "（模型未就绪）"
        return {"answer": answer, "sources": [], "citations": [],
                "engine": "pg-chunk", "mode": "no_hit_fallback"}
    return {"answer": "知识库中未找到可依据的条款内容。", "sources": [],
            "citations": [], "engine": "pg-chunk", "mode": "no_hit_designated"}
