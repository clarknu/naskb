"""deep_bench — 合成基准：条款级检索召回 + 参数扫描（REQ-R5-06 Stage 3 收口）。

不需要真实标准/人工标注——构造一份结构逼真的「合成标准 Markdown」，
问题集与期望条款由代码生成（ground truth by construction）。评测核心是
**条款级检索召回**：对每题，看其期望条款 chunk 是否进入 top-k（比摘要级
整文件召回更细粒度、可量化）。用本地 bge-small-zh（[pg] 工作区模型）离线跑，
对 target/limit/overlap 做网格扫描，按 recall@5 选优锁定初始参数。

用法：`naskb desc deep-bench`；或 `python -c "from naskb.common.deep_bench
import SYNTH_MD, build_questions, benchmark; print(benchmark('<work>'))"`。
"""
from __future__ import annotations

import json
import os
from typing import Optional

from .chunker import chunk_markdown

# ── 合成标准：结构逼真（章/节/条/参数表/跨页长条），数值均为虚构 ──
SYNTH_MD = """# 第1章 范围
本标准规定了某设备的试验方法与检验规则。适用于额定电压不超过 1000V 的电气设备。

# 第2章 术语和定义
下列术语和定义适用于本文件。

## 2.1 额定工作电压
指设备上标注的、按制造商设计规定的正常工作电压。

## 2.2 耐压强度
指设备绝缘在规定条件下能承受而不击穿的最高试验电压。

# 第3章 一般要求
设备应结构完整、标志清晰，并在出厂前完成出厂检验。

# 第4章 试验方法

## 4.1 外观检查
目视检查设备外表，不得有明显的划痕、裂纹、变形或锈蚀；标志应清晰可辨。

## 4.2 尺寸检查
用游标卡尺测量外形尺寸，偏差不得超过标称值的 ±2%。

## 4.3 耐压试验

### 4.3.1 试验装置
试验电源应能输出可调的交流电压，容量不低于 2kVA，频率 50Hz。

### 4.3.2 保压时间
施加 1.5 倍额定工作电压，保压持续时间不少于 30 分钟，不得发生击穿或闪络。

### 4.3.3 泄漏电流
试验期间泄漏电流不超过 0.5mA，试验后绝缘电阻不小于 100MΩ。

## 4.4 温升试验
额定负载下连续运行 2 小时，各部件温升不超过下表的规定值。

| 部件 | 温升限值(℃) | 测量方法 |
| --- | --- | --- |
| 绕组 | 75 | 电阻法 |
| 铁芯 | 60 | 热电偶 |
| 外壳 | 45 | 热电偶 |

## 4.5 长期运行试验
设备在额定条件下连续运行期间，应能保持稳定并满足下列各项要求：运行过程中各部位的温度
不得超过按第 4.4 章测得的温升限值，且不得出现任何可能影响安全或正常使用的异常振动、异常
噪声或异味。在连续运行 24 小时后，测量其绝缘电阻仍应不低于第 4.3.3 章规定的下限值，同时
复核泄漏电流不得超过第 4.3.3 章给出的最大值。试验期间还应定时记录环境温度与设备表面温度，
并按制造方推荐的周期进行维护保养以验证长期运行的可靠性。试验结束后应检查各紧固件是否松脱、
密封处是否渗漏，必要时对关键连接部位进行人工复检并留存记录，作为型式检验的组成部分之一。

# 第5章 检验规则

## 5.1 出厂检验
每台设备应经出厂检验，项目包括外观、尺寸、耐压、绝缘电阻。

## 5.2 型式检验
遇下列情况之一应进行型式检验：新产品定型、结构或工艺重大变更、停产一年以上恢复生产。

# 第6章 标志、包装、运输和贮存
标志应包含型号、额定电压、制造商名称。产品应包装牢固，贮存在干燥通风处。
"""

# 题目 = (问句, 期望条款关键词——用「唯一锚点」，只在目标条款出现，避免错位映射)
QUESTIONS = [
    ("耐压试验的试验电源容量应不低于多少？", "2kVA"),
    ("4.3.2 保压时间规定是多长？", "30 分钟"),
    ("试验后的绝缘电阻要求不小于多少？", "100MΩ"),
    ("额定工作电压是如何定义的？", "制造商设计规定"),
    ("外观检查不允许出现哪些缺陷？", "划痕"),
    ("绕组温升限值是多少？", "电阻法"),
    ("出厂检验包含哪几项？", "每台设备应经出厂检验"),
    ("标志应包含哪些内容？", "包装牢固"),
    ("长期运行试验后应复检哪些部位？", "紧固件"),
]


def build_questions() -> list[dict]:
    """返回 [{question, expect}]，expect 为期望条款中的锚定关键词。"""
    return [{"question": q, "expect": e} for q, e in QUESTIONS]


def _recall_at_k(qvec, chunk_vecs, k: int) -> Optional[int]:
    import numpy as np
    sims = chunk_vecs @ qvec
    return np.argpartition(-sims, k - 1)[:k].tolist()


def benchmark(work_path: str, *, params_grid: list[dict] | None = None,
              write_report_to: str | None = None) -> dict:
    """跑合成基准：对每组参数算条款级 recall@3/@5，选优锁定初始参数。

    返回 {sweep, recommended, baseline_note}。需要 bge 模型已下载。
    """
    from .embeddings import Embedder, model_ready

    if not model_ready(work_path):
        return {"error": "bge 模型未下载（先 desc index-vectors）"}
    grid = params_grid or [
        {"target_chars": 800, "limit_chars": 1200, "overlap_ratio": 0.12},
        {"target_chars": 500, "limit_chars": 800, "overlap_ratio": 0.12},
        {"target_chars": 500, "limit_chars": 800, "overlap_ratio": 0.25},
        {"target_chars": 1000, "limit_chars": 1600, "overlap_ratio": 0.12},
        {"target_chars": 800, "limit_chars": 1200, "overlap_ratio": 0.0},
    ]
    emb = Embedder(work_path)
    try:
        qs = build_questions()
        sweep = []
        for cfg in grid:
            chunks = chunk_markdown(SYNTH_MD, target_chars=cfg["target_chars"],
                                    limit_chars=cfg["limit_chars"],
                                    overlap_ratio=cfg["overlap_ratio"])
            if not chunks:
                continue
            vecs = emb.encode([c.emb_text for c in chunks])
            # 每条期望条款的 chunk 下标（首次命中关键词）
            expect_idx = {}
            for q in qs:
                for i, c in enumerate(chunks):
                    if q["expect"] in c.text:
                        expect_idx.setdefault(q["question"], i)
                        break
            hit3 = hit5 = total = 0
            for q in qs:
                idx = expect_idx.get(q["question"])
                if idx is None:
                    continue
                total += 1
                qvec = emb.encode_one(q["question"])
                top3 = _recall_at_k(qvec, vecs, 3)
                top5 = _recall_at_k(qvec, vecs, 5)
                if idx in top3:
                    hit3 += 1
                if idx in top5:
                    hit5 += 1
            sweep.append({
                "target_chars": cfg["target_chars"],
                "limit_chars": cfg["limit_chars"],
                "overlap_ratio": cfg["overlap_ratio"],
                "n_chunks": len(chunks),
                "scored": total,
                "recall@3": round(hit3 / total, 4) if total else 0,
                "recall@5": round(hit5 / total, 4) if total else 0,
            })
        # 选优：recall@5 高者，其次 recall@3，其次块数少（省检索成本）
        best = max(sweep, key=lambda s: (s["recall@5"], s["recall@3"],
                                         -s["n_chunks"])) if sweep else None
        rec = {
            "recommended": best,
            "note": ("合成基准锁定的初始参数；真实标准文档后续验证可再微调。"
                     "摘要级检索只能整文件召回、无法到条款，故不与其并列比 recall，"
                     "仅作为『条款级能定位到条款』的结构性对照。"),
        }
        out = {"synthetic": "self-built structure (fictional values)",
               "n_questions": len(qs), "sweep": sweep, **rec}
        if write_report_to:
            os.makedirs(write_report_to, exist_ok=True)
            p = os.path.join(write_report_to, "deep-bench-report.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(out, fh, ensure_ascii=False, indent=2)
            print(f"[naskb] 基准报告已写入 {p}")
        return out
    finally:
        emb.close()
