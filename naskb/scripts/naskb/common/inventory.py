"""只读源/通用源扫描入库（REQ-R7-05/06）：inventory 对账与内容指纹。

职责：
- walk_source：经来源适配器遍历文件清单（相对路径），套用隐藏/排除规则；
- fingerprint：按 ADR-20260816-4 采样规则计算内容 hash
  （≤512KB 全量 / >512KB 8×64KB；超过 max_hash_mb 的大文件跳过指纹，
   仅登记 stat——指纹留给后续 analyze/verify 补）；
- reconcile：pgstore.reconcile_resources 的前置组装（分类、目录统计）。

设计要点（platform-v3-design §3.3）：
扫描只做 stat 级登记，不做 AI 分析；分析是显式 enrich 动作。
"""
from __future__ import annotations

import hashlib
from typing import Optional

from .fs.base import FileSystemAdapter, FileStat
from .hashing import HASH_ALG_FULL, HASH_ALG_SAMPLE, sample_ranges

# 与 batch.py 相同口径的系统垃圾排除（保持行为一致）
_SYSTEM_FILE_NAMES = {"desktop.ini", "thumbs.db", ".ds_store", ".localized"}
_EXCLUDE_DIRS_DEFAULT = {"$recycle.bin", "system volume information",
                         "#recycle", "@eaDir"}


def is_system_file(name: str) -> bool:
    low = name.lower()
    return low in _SYSTEM_FILE_NAMES or (
        low.startswith("~$") or low.startswith("."))


def walk_source(adapter: FileSystemAdapter, root: str = "",
                max_file_mb: int = 0) -> tuple[list[dict], int]:
    """遍历来源根，产出登记条目清单。

    返回 (items, skipped_big)。item 字段对齐 pgstore.reconcile_resources：
    {rel_path, name, parent_dir, size_bytes, mtime, ctime,
     file_hash, hash_algorithm, file_type}
    file_hash 本轮为空串——指纹由 compute_missing_hashes 按需补算
    （WebDAV 场景逐文件 Range 请求成本高，扫描阶段默认不算）。
    """
    items: list[dict] = []
    skipped_big = 0
    max_bytes = max_file_mb * 1024 * 1024 if max_file_mb else 0
    for f in adapter.list_files(root, recursive=True):
        parts = f.path.replace("\\", "/").split("/")
        # 隐藏/系统目录与垃圾文件：与 analyze-tree 同口径跳过
        hidden = any(p.startswith(".") for p in parts[:-1])
        excluded = any(p.lower() in _EXCLUDE_DIRS_DEFAULT
                       for p in parts[:-1])
        if hidden or excluded:
            continue
        if f.name.lower() in _SYSTEM_FILE_NAMES or f.name.startswith("~$"):
            continue
        if max_bytes and f.size_bytes > max_bytes:
            skipped_big += 1
            continue
        parent = f.path.rsplit("/", 1)[0] if "/" in f.path else ""
        items.append({
            "rel_path": f.path.replace("\\", "/"),
            "name": f.name,
            "parent_dir": parent,
            "size_bytes": f.size_bytes,
            "mtime": f.mtime,
            "ctime": f.ctime,
            "file_hash": "",
            "hash_algorithm": "",
            "file_type": f.ext.lstrip("."),
        })
    return items, skipped_big


def content_fingerprint(adapter: FileSystemAdapter, st: FileStat,
                        path: str) -> tuple[str, str]:
    """按采样规则计算内容指纹（ADR-20260816-4）。失败返回 ("","")。"""
    try:
        spans = sample_ranges(st.size_bytes)
        h = hashlib.sha256()
        if spans is None:
            for chunk in adapter.read_chunks(path, 1 << 20):
                h.update(chunk)
                if st.size_bytes and chunk == b"":
                    break
            return h.hexdigest(), HASH_ALG_FULL
        data = adapter.read_ranges(path, [(s, l) for s, l in spans])
        got = sum(l for _, l in spans)
        if len(data) != got:
            return "", ""
        h.update(data)
        return h.hexdigest(), HASH_ALG_SAMPLE
    except Exception:
        return "", ""


def compute_missing_hashes(adapter: FileSystemAdapter, items: list[dict],
                           max_hash_mb: int = 512,
                           on_progress=None) -> int:
    """为缺指纹的条目补算采样 hash（本地源扫描后调用；WebDAV 可选）。

    返回成功计算的条数。单条失败不中断（保留空指纹）。
    """
    limit = max_hash_mb * 1024 * 1024
    done = 0
    total = len(items)
    for i, it in enumerate(items):
        if it.get("file_hash"):
            continue
        size = int(it.get("size_bytes") or 0)
        if limit and size > limit:
            continue
        fp, alg = content_fingerprint(adapter, _stat_like(it), it["rel_path"])
        if fp:
            it["file_hash"], it["hash_algorithm"] = fp, alg
            done += 1
        if on_progress and i % 20 == 0:
            on_progress(i / max(total, 1),
                        f"指纹 {i}/{total}")
    return done


class _stat_like:
    """轻量 FileStat 替身（content_fingerprint 只用 size_bytes）。"""

    def __init__(self, it: dict):
        self.size_bytes = int(it.get("size_bytes") or 0)


def guess_category(ext: str) -> str:
    """扩展名粗分类（浏览页 AI 富化前的兜底标签）。"""
    e = (ext or "").lower().lstrip(".")
    if e in ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt",
             "md", "rtf", "csv"):
        return "文档"
    if e in ("jpg", "jpeg", "png", "gif", "webp", "bmp", "heic", "tif",
             "tiff", "svg"):
        return "图片"
    if e in ("mp3", "wav", "m4a", "flac", "aac", "ogg"):
        return "音频"
    if e in ("mp4", "mkv", "mov", "avi", "wmv", "webm", "flv", "ts"):
        return "视频"
    if e in ("zip", "rar", "7z", "tar", "gz", "bz2"):
        return "压缩包"
    if e in ("py", "js", "ts", "java", "c", "cpp", "go", "rs", "sh", "bat",
             "ps1", "json", "yaml", "yml", "toml", "xml", "html", "css"):
        return "代码"
    if e in ("iso", "exe", "msi", "apk", "dmg"):
        return "软件"
    return "其他"


def reconcile(pg, schema_name: str, source_id, items: list[dict]) -> dict:
    """登记入库：补齐 category 后调 pgstore.reconcile_resources。"""
    for it in items:
        if not it.get("category"):
            it.setdefault("category", "")
    res = pg.reconcile_resources(schema_name, source_id, items)
    # 目录级粗描述兜底：AI 富化前浏览页也有内容可看
    return res


__all__ = [
    "walk_source", "content_fingerprint", "compute_missing_hashes",
    "guess_category", "reconcile", "is_system_file",
]
