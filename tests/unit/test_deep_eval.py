"""deep_eval 单测（REQ-R5-06 Stage 3）：聚合指标与问题集解析。纯离线。"""
import json

from naskb.common.deep_eval import aggregate, load_questions


def test_aggregate_empty():
    assert aggregate([]) == {"total": 0}


def test_aggregate_rates():
    results = [
        {"question": "q1", "deep_answer": "A", "deep_sources": ["D:/标准.pdf"],
         "base_answer": "B", "base_sources": ["D:/标准.pdf"], "expect": "标准.pdf"},
        {"question": "q2", "deep_answer": "", "deep_sources": [],
         "base_answer": "", "base_sources": [], "expect": ""},
    ]
    agg = aggregate(results)
    assert agg["total"] == 2
    assert agg["deep_answer_rate"] == 0.5
    assert agg["base_answer_rate"] == 0.5
    assert agg["deep_source_rate"] == 0.5
    assert agg["scored"] == 1
    assert agg["deep_expect_hit"] == 1
    assert agg["base_expect_hit"] == 1


def test_aggregate_expect_miss_when_not_present():
    results = [
        {"question": "q", "deep_answer": "A", "deep_sources": ["D:/a.pdf"],
         "base_answer": "B", "base_sources": [], "expect": "规范.pdf"},
    ]
    agg = aggregate(results)
    assert agg["deep_expect_hit"] == 0
    assert agg["base_expect_hit"] == 0


def test_load_questions_list_and_object(tmp_path):
    p1 = tmp_path / "q.json"
    p1.write_text(json.dumps(["q1", "q2"]), encoding="utf-8")
    assert load_questions(str(p1)) == [{"q": "q1", "expect": ""},
                                       {"q": "q2", "expect": ""}]
    p2 = tmp_path / "q2.json"
    p2.write_text(json.dumps({"questions": [
        {"q": "保压多久", "expect": "6.3.2"}]}), encoding="utf-8")
    assert load_questions(str(p2)) == [{"q": "保压多久", "expect": "6.3.2"}]
