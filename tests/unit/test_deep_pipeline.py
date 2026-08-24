"""深度分析（REQ-R5-06）纯逻辑单测：深析根匹配、[deep] 配置归一化、chunk 参数联动。
与 PG 无关（PG 相关走 test_pgstore 的集成路径，缺 PG 则 skip）。
"""
import pytest

from naskb.common.config import Config
from naskb.common.pgstore import PgStore
from naskb.common.chunker import chunk_markdown


def test_is_deep_prefix_match():
    is_deep = PgStore._is_deep
    assert is_deep("D:/docs/standards/a.pdf", ["D:/docs/standards"]) is True
    assert is_deep("D:/docs/standards/sub/b.md", ["D:/docs/standards"]) is True
    # 前级相同但不是子路径（伪前缀）
    assert is_deep("D:/docs/standards_old/a.pdf", ["D:/docs/standards"]) is False
    assert is_deep("D:/docs/other/a.pdf", ["D:/docs/standards"]) is False
    # 反斜杠规范化
    assert is_deep(r"D:\docs\standards\a.pdf", ["D:/docs/standards"]) is True
    # 空 roots → False
    assert is_deep("D:/anything", []) is False


def test_deep_doc_cfg_defaults():
    cfg = Config("x", {})
    d = cfg.deep_doc_cfg()
    assert d["enabled"] is False
    assert d["roots"] == []
    assert d["target_chars"] == 800 and d["limit_chars"] == 1200
    assert abs(d["overlap_ratio"] - 0.12) < 1e-9
    assert d["direct_return"] is False
    assert abs(d["direct_return_similarity"] - 0.9) < 1e-9
    assert d["max_context_chars"] == 5000
    assert d["top_n"] == 5
    assert d["no_hit_mode"] == "designated"


def test_deep_doc_cfg_overrides():
    cfg = Config("x", {"deep": {
        "enabled": True,
        "roots": ["/v1/specs"],
        "target_chars": 500,
        "limit_chars": 900,
        "overlap_ratio": 0.2,
        "direct_return": True,
        "top_n": 3,
        "no_hit_mode": "llm_fallback",
    }})
    d = cfg.deep_doc_cfg()
    assert d["enabled"] is True
    assert d["roots"] == ["/v1/specs"]
    assert d["target_chars"] == 500 and d["limit_chars"] == 900
    assert abs(d["overlap_ratio"] - 0.2) < 1e-9
    assert d["direct_return"] is True
    assert d["top_n"] == 3
    assert d["no_hit_mode"] == "llm_fallback"


def test_chunk_params_take_effect():
    # 更小的 target/limit → 更多块；更大 limit → 更少块（合并到一段）
    body = "。".join(f"测试条款内容填充示例。{i}" for i in range(600))
    small = chunk_markdown("## 章\n" + body, target_chars=300, limit_chars=400)
    big = chunk_markdown("## 章\n" + body, target_chars=800, limit_chars=2000)
    assert len(small) > len(big)
    for c in small:
        assert len(c.text) <= 400 + 1


def test_enrich_deep_gate_off_skips():
    """来源级 deep 开关关闭 → _enrich_deep 直接跳过（不触 pg）。"""
    from types import SimpleNamespace
    from naskb.common import enrich

    # deep=False → 早返回，未触 pg/embedder
    out = enrich._enrich_deep(SimpleNamespace(deep=False), "s", [],
                              SimpleNamespace(), SimpleNamespace(), None)
    assert out == {"skipped": "deep 未开启"}
