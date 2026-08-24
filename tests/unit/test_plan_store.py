"""整理方案持久化测试（P1-1）。"""
import os

from naskb.common.plan_store import (list_plans, load_plan, mark_applied,
                                     plans_dir, save_plan)


def test_save_load_roundtrip(tmp_path):
    work = str(tmp_path / "work")
    plan = {"plan_name": "按类型归类", "rationale": "r",
            "new_folders": ["财务"], "moves": [{"from": "a", "to": "b"}],
            "root": str(tmp_path / "nas")}
    snap = {"c:/nas/a.pdf": "hash123"}
    plan_id = save_plan(work, plan, snap, root=plan["root"])
    rec = load_plan(work, plan_id)
    assert rec is not None
    assert rec["plan_id"] == plan_id
    assert rec["status"] == "pending"
    assert rec["root"] == plan["root"]
    assert rec["plan"]["plan_name"] == "按类型归类"
    assert rec["snapshot"] == snap
    assert rec["applied_at"] is None and rec["result"] is None
    # 无残留临时文件
    assert not [n for n in os.listdir(plans_dir(work)) if n.endswith(".tmp")]


def test_load_missing_returns_none(tmp_path):
    assert load_plan(str(tmp_path / "work"), "no-such-id") is None
    assert load_plan(str(tmp_path / "work"), "bad id!") is None   # 非法字符


def test_list_plans_filters(tmp_path):
    work = str(tmp_path / "work")
    root_a = str(tmp_path / "nasA")
    root_b = str(tmp_path / "nasB")
    id_a = save_plan(work, {"moves": []}, {}, root=root_a)
    save_plan(work, {"moves": []}, {}, root=root_b)
    mark_applied(work, id_a, {"moved": 1})
    assert len(list_plans(work)) == 2
    assert len(list_plans(work, root=root_a)) == 1
    assert len(list_plans(work, status="pending")) == 1
    assert len(list_plans(work, status="applied")) == 1
    assert len(list_plans(work, root=root_a, status="applied")) == 1


def test_mark_applied(tmp_path):
    work = str(tmp_path / "work")
    plan_id = save_plan(work, {"moves": []}, {}, root=str(tmp_path / "nas"))
    result = {"moved": 2, "failed": []}
    rec = mark_applied(work, plan_id, result, by="tester")
    assert rec["status"] == "applied"
    assert rec["applied_at"]
    assert rec["result"] == result
    assert rec["audit"][0]["action"] == "apply"
    assert rec["audit"][0]["by"] == "tester"
    assert mark_applied(work, "no-such", {}) is None
