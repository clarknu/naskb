"""内容指纹采样规则（ADR-20260816-4，用户 2026-08-16 拍板）。

大文件不整读：>512KB 时取 8 段 × 64KB 均匀分布（含文件头与文件尾），
防止"文件头相同、后续内容不同"的伪装文件漏检；位置仅由 size 决定，
同大小文件永远取相同位置（确定性、可复现）。
"""
from __future__ import annotations

SAMPLE_TOTAL = 512 * 1024      # 512KB：hash 数据来源上限
SAMPLE_SEGMENTS = 8            # 段数
SAMPLE_SEG_SIZE = 64 * 1024    # 每段 64KB

HASH_ALG_FULL = "sha256:full"             # ≤512KB 全量
HASH_ALG_SAMPLE = "sha256:sample8x64k"    # >512KB 8 段均匀采样
HASH_ALG_LEGACY = ""                      # 旧条目（升级前）无算法标记

# 已注册的算法（sync 预检一致性校验用）
KNOWN_ALGORITHMS = (HASH_ALG_FULL, HASH_ALG_SAMPLE)


def sample_ranges(size: int) -> list[tuple[int, int]] | None:
    """计算采样区间。

    返回 [(start, length), ...]（按文件偏移升序，i=0..7）；
    size ≤ 512KB 时返回 None 表示全量读取。
    规则保证：i=0 段起点 0（含文件头），i=7 段终点 size（含文件尾）。
    """
    if size <= SAMPLE_TOTAL:
        return None
    seg = SAMPLE_SEG_SIZE
    last = size - seg          # 末段起点（末段终点 = size）
    spans = []
    for i in range(SAMPLE_SEGMENTS):
        start = i * last // (SAMPLE_SEGMENTS - 1)
        length = min(seg, size - start)
        if length <= 0:
            break
        spans.append((start, length))
    return spans
