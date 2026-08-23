"""HTTP Range 头解析（下载代理 REQ-R7-07）。纯函数，便于单测。"""
from __future__ import annotations

from typing import Optional


def parse_range(header: Optional[str], size: int
                ) -> tuple[Optional[tuple[int, int]], bool]:
    """解析单个 Range 请求头。

    返回 (range, valid)：
    - (None, True)   无 Range 头或格式不支持 → 按 200 全量处理
    - ((start,end), True)  命中闭区间 [start, end]（含端点）
    - (None, False)  Range 头存在但越界不可满足 → 应返回 416
    仅支持单区间 "bytes=a-b / a- / -suffix"（多区间场景回退全量）。
    """
    if not header:
        return None, True
    header = header.strip()
    if not header.lower().startswith("bytes="):
        return None, True
    spec = header[len("bytes="):].strip()
    if "," in spec:          # 多区间：不支持，回退全量
        return None, True
    if size <= 0:
        return None, False
    if "-" not in spec:
        return None, True
    first, last = (x.strip() for x in spec.split("-", 1))
    try:
        if first == "" and last != "":          # 尾部 N 字节
            n = int(last)
            if n <= 0:
                return None, False
            start = max(0, size - n)
            return (start, size - 1), True
        if first != "":
            start = int(first)
            end = int(last) if last != "" else size - 1
            if start >= size or start > end:
                return None, False
            return (start, min(end, size - 1)), True
    except ValueError:
        return None, True
    return None, True


def content_range(start: int, end: int, size: int) -> str:
    """Content-Range 响应头值。"""
    return f"bytes {start}-{end}/{size}"
