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


def test_aggregate_expect_keyword_terms():
    """expect 支持 | 分隔的关键词片段：任一片段命中（答案或来源）即 hit——
    长句答案场景避免整句逐字匹配失效（A1 真实文档验证发现）。"""
    results = [
        {"question": "违约金怎么约定", "deep_answer":
            "第五条约定提前一个月通知对方，并偿付一个月租金的违约金。",
         "deep_sources": ["房租合同.pdf"],
         "base_answer": "条款见第五条规定。", "base_sources": [],
         "expect": "提前一个月通知|一个月租金的违约金"},
        {"question": "无关键词", "deep_answer": "不详", "deep_sources": [],
         "base_answer": "知识库中没有找到相关内容。", "base_sources": ["X.pdf"],
         "expect": "不存在的关键词|也不存在"},
    ]
    agg = aggregate(results)
    assert agg["scored"] == 2
    assert agg["deep_expect_hit"] == 1    # 第一题答案含关键词；第二题两路均未命中
    assert agg["base_expect_hit"] == 0


def test_aggregate_expect_hit_via_source_path():
    """期望词命中来源路径（文件级期望，如 '标准.pdf'）。"""
    results = [
        {"question": "q", "deep_answer": "A", "deep_sources": ["标准.pdf"],
         "base_answer": "B", "base_sources": ["其它.pdf"], "expect": "标准.pdf"},
    ]
    agg = aggregate(results)
    assert agg["deep_expect_hit"] == 1
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
