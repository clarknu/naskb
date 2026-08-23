"""MCP Server 服务对象测试（阶段 A）：直接调用 NasKbService 工具方法。

不经过 stdio 传输（协议层由 mcp SDK 保证）；验证工具语义与复用链。
"""
import base64
import os
import time

import pytest

from naskb.common.desc_store import FileEntry, NaskbStore
from naskb.common.fs.local import LocalAdapter
from naskb.mcp.server import NasKbService, build_mcp


@pytest.fixture
def kb_env(tmp_path):
    """迷你知识库：work 工作区 + nas 库目录（3 个已分析条目）。"""
    work = tmp_path / "work"
    nas = tmp_path / "nas"
    nas.mkdir(parents=True)
    (nas / "发票1.pdf").write_bytes(b"%PDF fake invoice")
    (nas / "照片1.jpg").write_bytes(b"fake jpg")
    (nas / "项目计划.txt").write_text("项目计划：预算与排期", encoding="utf-8")
    store = NaskbStore(LocalAdapter(str(nas)))
    for name, cat, summ in (("发票1.pdf", "财务", "房租发票"),
                            ("照片1.jpg", "图片", "桂林山水照片"),
                            ("项目计划.txt", "文档", "年度项目计划")):
        store.set_entry(str(nas / name),
                        FileEntry(original_path=name, summary=summ,
                                  category=cat))
    return work, nas


def _wait_job(svc, job_id, timeout=30.0):
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        last = svc.kb_job_status(job_id)
        if last["status"] in ("completed", "failed"):
            return last
        time.sleep(0.1)
    raise TimeoutError(f"job {job_id} 未在 {timeout}s 内完成: {last}")


class TestServiceInit:
    def test_build_and_stats(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)], pg=False)
        try:
            stats = svc.kb_stats()
            assert stats["docs"] == 3
            assert str(nas) in stats["roots"]
        finally:
            svc.shutdown()

    def test_all_capabilities_registered(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            mcp = build_mcp(svc)
            names = set(mcp._tool_manager._tools.keys())
            assert {"kb_search", "kb_ask", "kb_get_doc", "kb_fetch_file",
                    "kb_ingest", "kb_sync_vectors", "kb_index_vectors",
                    "kb_job_status", "kb_list_jobs", "kb_plan_reorganize",
                    "kb_preview_reorganize", "kb_apply_reorganize",
                    "kb_status", "kb_stats"} <= names
        finally:
            svc.shutdown()


class TestReadTools:
    def test_search_bm25_fallback(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            out = svc.kb_search("房租发票")
            assert out["engine"] in ("bm25", "vector")
            assert out["hits"]
            assert out["hits"][0]["path"].endswith("发票1.pdf")
        finally:
            svc.shutdown()

    def test_ask_returns_result_or_error(self, kb_env):
        """LLM 未配置时返回 error 不抛异常（引擎仍可用）。"""
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            # 确定性：显式置空 LLM（真实环境可能已配 key）
            svc._core.set_llm(None)
            out = svc.kb_ask("发票金额多少")
            assert "answer" in out and "error" in out
        finally:
            svc.shutdown()

    def test_get_doc(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            d = svc.kb_get_doc(str(nas / "发票1.pdf"))
            assert d["analysis"]["category"] == "财务"
            assert d["analysis"]["summary"] == "房租发票"
            # 默认不带全文
            assert "ocr_text" not in d
        finally:
            svc.shutdown()

    def test_get_doc_path_outside_root_rejected(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            with pytest.raises(ValueError):
                svc.kb_get_doc(str(nas.parent / "other" / "x.pdf"))
        finally:
            svc.shutdown()

    def test_fetch_file(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            out = svc.kb_fetch_file(str(nas / "发票1.pdf"))
            assert out["content_base64"] == base64.b64encode(
                b"%PDF fake invoice").decode()
            # 目录拒绝
            assert "error" in svc.kb_fetch_file(str(nas))
        finally:
            svc.shutdown()

    def test_status(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            out = svc.kb_status()
            scan = out["roots"][0]["scan"]
            assert scan["valid"] == 3
        finally:
            svc.shutdown()


class _FakeLLM:
    """plan/apply 测试用伪 LLM：返回固定方案。"""

    def __init__(self, plan):
        self._plan = plan

    def complete_json(self, prompt):
        return self._plan

    def close(self):
        pass


class TestReorganizeFlow:
    def test_plan_preview_apply_flow(self, kb_env, tmp_path):
        work, nas = kb_env
        # 方案：把发票1.pdf 移入新建财务目录
        plan_moves = [{"from": str(nas / "发票1.pdf"),
                       "to": str(nas / "财务" / "发票1.pdf"), "reason": "归财务"}]
        svc = NasKbService(str(work), [str(nas)])
        svc._new_llm = lambda: _FakeLLM({
            "plan_name": "按类归档", "rationale": "平铺文件归类",
            "new_folders": ["财务"], "moves": plan_moves})
        try:
            # 1) plan（长任务）
            j = _wait_job(svc, svc.kb_plan_reorganize(str(nas))["job_id"])
            assert j["status"] == "completed", j
            plan_id = j["result"]["plan_id"]
            assert j["result"]["moves"] == 1
            # 文件未移动（只规划）
            assert (nas / "发票1.pdf").exists()
            assert not (nas / "财务" / "发票1.pdf").exists()
            # 2) preview：dry-run 判定为 move
            pv = svc.kb_preview_reorganize(plan_id)
            assert pv["summary"].get("move") == 1
            assert pv["moves"][0]["action"] == "move"
            # 3) apply（长任务）
            j2 = _wait_job(svc, svc.kb_apply_reorganize(plan_id)["job_id"])
            assert j2["status"] == "completed", j2
            result = j2["result"]
            assert len(result["moved"]) == 1
            assert (nas / "财务" / "发票1.pdf").exists()
            assert not (nas / "发票1.pdf").exists()
            # 4) 重复 apply 被拒（方案已执行）
            assert "error" in svc.kb_apply_reorganize(plan_id)
        finally:
            svc.shutdown()

    def test_preview_unknown_plan(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            assert "error" in svc.kb_preview_reorganize("no-such-id")
        finally:
            svc.shutdown()


class TestIngest:
    def test_ingest_new_file(self, kb_env):
        work, nas = kb_env
        # 入库前：新增一个未分析文件
        (nas / "新合同.txt").write_text("新合同内容：甲乙双方", encoding="utf-8")
        svc = NasKbService(str(work), [str(nas)])
        try:
            j = _wait_job(svc, svc.kb_ingest(str(nas), llm=False)["job_id"])
            assert j["status"] == "completed", j
            # 新文件有了条目（scan valid 数增加）
            out = svc.kb_status(str(nas))
            assert out["roots"][0]["scan"]["valid"] == 4
        finally:
            svc.shutdown()

    def test_ingest_root_not_registered(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            with pytest.raises(ValueError):
                svc.kb_ingest(str(nas.parent / "other"))
        finally:
            svc.shutdown()


class TestJobs:
    def test_job_status_and_list(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            assert "error" in svc.kb_job_status("no-such")
            out = svc.kb_list_jobs()
            assert "jobs" in out
        finally:
            svc.shutdown()
