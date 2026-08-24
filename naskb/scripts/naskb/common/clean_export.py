"""clean_export — 干净文本导出（REQ-R5-02，公共资产，解耦引擎语义）。

把 `.naskb` 分析产物导出为干净的 Markdown/ZIP，供外部深度引擎消费或人工取用。
来源是 collect_docs 产出的 Doc（其 context 对 MinerU 文档即结构化 Markdown）。
"""
from __future__ import annotations

import os
import re
import zipfile
from typing import Iterable

from .retrieval import Doc


def _safe_name(path: str) -> str:
    """把路径/文件名映射为安全文件名（保留扩展名）。"""
    path = path.replace("\\", "/").strip("/")
    return re.sub(r"[^A-Za-z0-9.#()\u4e00-\u9fff_-]+", "_", path)


def build_clean_markdown(doc: Doc) -> str:
    """单个 Doc → 干净 Markdown（front matter + 摘要 + 全文/内容）。

    front matter 用 YAML 风格（UTF-8，无 BOM——REQ-R6-01）。
    """
    parts = ["---"]
    parts.append(f"path: \"{doc.path}\"")
    parts.append(f"kind: {doc.kind or 'file'}")
    if doc.category:
        parts.append(f"category: \"{doc.category}\"")
    if doc.tags:
        parts.append("tags: [" + ", ".join(f"\"{t}\"" for t in doc.tags) + "]")
    if doc.summary:
        parts.append(f"summary: \"{doc.summary}\"")
    parts.append("---")
    parts.append("")
    if doc.summary:
        parts.append(f"## 摘要\n\n{doc.summary}")
        parts.append("")
    body = (doc.context or doc.text or "").strip()
    if body:
        parts.append("## 内容\n")
        parts.append(body)
    return "\n".join(parts).strip() + "\n"


def export_clean(docs: Iterable[Doc], out_dir: str, *, zip: bool = False) -> dict:
    """把 Doc 列表导出为 Markdown 目录或单个 ZIP。

    返回 {files, chars, out}。
    """
    os.makedirs(out_dir, exist_ok=True)
    files = 0
    chars = 0
    if zip:
        zip_path = os.path.join(out_dir, "naskb-clean.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc in docs:
                if not doc.path or doc.kind != "file":
                    continue
                text = build_clean_markdown(doc)
                chars += len(text)
                name = _safe_name(doc.path) + ".md"
                zf.writestr(name, text.encode("utf-8"))
                files += 1
        return {"files": files, "chars": chars, "out": zip_path}
    for doc in docs:
        if not doc.path or doc.kind != "file":
            continue
        text = build_clean_markdown(doc)
        chars += len(text)
        name = _safe_name(doc.path) + ".md"
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(text)
        files += 1
    return {"files": files, "chars": chars, "out": out_dir}
