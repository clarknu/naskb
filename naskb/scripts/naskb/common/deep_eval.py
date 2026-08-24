"""deep_eval — 深度分析评测（REQ-R5-06 Stage 3）：条款级 vs 摘要级 固定问题集对比。

用法：`naskb desc deep-eval <root> --questions <file.json> [--nas <alias>] [--out <dir>]`
questions 文件：JSON {"questions": [{"q": "...", "expect": "..."}, ...]} 或纯文本一行一题。
输出：<out>/report.json + 控制台摘要。对比「条款级（chunk）」与「摘要级（summary）」两条
检索+问答路径，用于评测 chunk 增强是否带来命中/引用质量提升。
"""
from __future__ import annotations

import json
import os
from typing import Optional


def aggregate(results: list[dict]) -> dict:
    """结构化聚合：统计两级各自的有答案率、来源命中、期望命中。

    result 字段：question / deep_answer / deep_sources / base_answer /
                 base_sources / expect（可选，子串匹配来源路径或答案）。
    """
    total = len(results)
    if total == 0:
        return {"total": 0}
    deep_ans = sum(1 for r in results if (r.get("deep_answer") or "").strip())
    base_ans = sum(1 for r in results if (r.get("base_answer") or "").strip())
    deep_present = sum(1 for r in results if (r.get("deep_sources") or []))
    base_present = sum(1 for r in results if (r.get("base_sources") or []))
    deep_hit = 0
    base_hit = 0
    scored = 0
    for r in results:
        exp = (r.get("expect") or "").strip()
        if not exp:
            continue
        scored += 1
        if _contains(r.get("deep_sources"), exp) or exp in (r.get("deep_answer") or ""):
            deep_hit += 1
        if _contains(r.get("base_sources"), exp) or exp in (r.get("base_answer") or ""):
            base_hit += 1
    return {
        "total": total,
        "deep_answer_rate": round(deep_ans / total, 4),
        "base_answer_rate": round(base_ans / total, 4),
        "deep_source_rate": round(deep_present / total, 4),
        "base_source_rate": round(base_present / total, 4),
        "scored": scored,
        "deep_expect_hit": deep_hit,
        "base_expect_hit": base_hit,
        "deep_expect_rate": round(deep_hit / scored, 4) if scored else 0,
        "base_expect_rate": round(base_hit / scored, 4) if scored else 0,
    }


def _contains(paths, needle: str) -> bool:
    return any(needle in (p or "") for p in (paths or []))


def load_questions(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return [{"q": str(x), "expect": ""} for x in data]
    return [{"q": str(x["q"]), "expect": str(x.get("expect", ""))}
            for x in data.get("questions", [])]


def run_eval(engine, llm, deep_cfg: dict, schema: str,
             questions: list[dict], top_k: int = 5,
             context_chars: int = 6000) -> list[dict]:
    """两条路径各跑一遍，返回逐题结果列表。

    engine: PgSearchEngine（含 search / search_chunks）。
    """
    from .serve import _SchemaBound
    from .retrieval import ask_deep, ask as rag_ask

    base_bound = _SchemaBound(engine, schema)

    class _ChunkBound:
        def __init__(self, e, sch):
            self._e, self._sch = e, sch
        def search_chunks(self, q, top_k=None):
            return self._e.search_chunks(q, top_k=top_k, schema=self._sch)

    chunk_bound = _ChunkBound(engine, schema)

    out = []
    for item in questions:
        q = item["q"]
        try:
            d = ask_deep(
                llm, chunk_bound, q, top_k=top_k, context_chars=context_chars,
                direct_return=deep_cfg.get("direct_return", False),
                direct_return_similarity=float(
                    deep_cfg.get("direct_return_similarity", 0.9)),
                no_hit_mode=str(deep_cfg.get("no_hit_mode", "designated")))
        except Exception as e:
            d = {"answer": "", "sources": [], "error": str(e)}
        try:
            b = rag_ask(llm, base_bound, q, top_k=top_k,
                        context_chars=context_chars)
        except Exception as e:
            b = {"answer": "", "sources": [], "error": str(e)}
        out.append({
            "question": q,
            "expect": item["expect"],
            "deep_mode": d.get("mode"),
            "deep_answer": d.get("answer") or "",
            "deep_sources": d.get("sources") or [],
            "base_answer": b.get("answer") or "",
            "base_sources": b.get("sources") or [],
        })
    return out


def write_report(results: list[dict], out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    agg = aggregate(results)
    report = {"aggregate": agg, "results": results}
    path = os.path.join(out_dir, "report.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    # 控制台摘要
    print(f"[naskb] 评测 {agg['total']} 题")
    print(f"  有答案率  条款级 {agg['deep_answer_rate']:.2%} / "
          f"摘要级 {agg['base_answer_rate']:.2%}")
    print(f"  有来源率  条款级 {agg['deep_source_rate']:.2%} / "
          f"摘要级 {agg['base_source_rate']:.2%}")
    if agg["scored"]:
        print(f"  期望命中  条款级 {agg['deep_hit']}/{agg['scored']} "
              f"({agg['deep_expect_rate']:.2%}) / "
              f"摘要级 {agg['base_hit']}/{agg['scored']} "
              f"({agg['base_expect_rate']:.2%})")
    print(f"[naskb] 报告已写入 {path}")
    return agg
