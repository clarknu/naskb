"""deep_bench 集成测试（REQ-R5-06 Stage 3）：合成基准 + 参数扫描。缺 bge 模型则 skip。

不需要真实标准/人工标注；只做检索召回，不调 LLM。
"""
import pytest

try:
    from naskb.common.deep_bench import SYNTH_MD, build_questions, benchmark
    from naskb.common.embeddings import model_ready
except Exception:  # pragma: no cover
    pytest.skip("deep_bench 依赖不可用", allow_module_level=True)


def _model(config):
    if not model_ready(config.work_path):
        pytest.skip("bge 模型未下载（先 desc index-vectors）")
    return True


def test_synth_doc_has_clause_anchors():
    # 保证合成标准里，每个期望关键词确实存在（前置正确性）
    for q in build_questions():
        assert q["expect"] in SYNTH_MD, q


def test_benchmark_runs_and_selects(tmp_path, ):
    from naskb.common.config import Config
    cfg = Config.from_work_path("NASKB_data")
    if not _model(cfg):
        return
    res = benchmark(cfg.work_path, write_report_to=str(tmp_path))
    assert "sweep" in res
    assert res["sweep"], "应有参数扫描结果"
    assert res["recommended"] is not None
    assert res["n_questions"] >= 5
    # 至少一组参数 recall@5 > 0（条款级能定位到条款）
    assert any(s["recall@5"] > 0 for s in res["sweep"])
    assert (tmp_path / "deep-bench-report.json").exists()
