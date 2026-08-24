"""MCP Server 服务对象测试（阶段 A）：直接调用 NasKbService 工具方法。

不经过 stdio 传输（协议层由 mcp SDK 保证）；验证工具语义与复用链。
"""
import base64
import os
import time

import pytest

from naskb.common.desc_store import FileEntry, NaskbStore
from naskb.common.fs.local import LocalAdapter
from naskb.common.source_registry import SourceRecord
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


class _FakePg:
    """内容层 PG 替身：list_dir / get_resource 返回受控行（不建真实连接）。

    模拟 pgstore.PgStore.list_dir 的原始行形状（含多余字段），
    用于验证 kb_list_tree 的规范投影确实收敛到目标字段。
    """

    def list_dir(self, schema_name, source_id, parent_dir=""):
        dirs = [{"rel_path": "财务", "name": "财务", "summary": "财会单据",
                 "description": "发票/报销", "tags": [], "file_count": 1}]
        files = [{"resource_id": "r-0001", "rel_path": "财务/发票1.pdf",
                  "name": "发票1.pdf", "size_bytes": 123, "mtime": 0.0,
                  "status": "ok", "summary": "房租发票", "file_type": "pdf",
                  "category": "财务", "tags": [], "ext": ".pdf"}]
        return dirs, files

    def get_resource(self, schema_name, resource_id):
        return {"resource_id": resource_id, "rel_path": "财务/发票1.pdf"}


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
                    "kb_status", "kb_stats",
                    "kb_list_sources", "kb_list_tree",
                    "kb_get_file_url"} <= names
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


class TestDeepParams:
    """kb_search level / kb_ask deep 参数面（无 PG 时的回退路径）。"""

    def test_kb_search_level_default_and_chunk_fallback(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)], pg=False)
        try:
            raw = svc.kb_search("发票", top_k=3)
            assert raw["level"] == "summary"
            chunk = svc.kb_search("发票", top_k=3, level="chunk")
            assert chunk["level"] == "chunk"
            assert isinstance(chunk["hits"], list)
        finally:
            svc.shutdown()

    def test_kb_ask_deep_fallback_when_no_pg(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)], pg=False)
        try:
            svc._core.set_llm(None)      # 确定性：无 LLM → 走 error 回退，不联网
            r = svc.kb_ask("发票租金多少", deep=True)
            assert r.get("error") or "sources" in r
        finally:
            svc.shutdown()


class TestSourceTools:
    """阶段 C 预留的 3 个来源化工具：注册 + 调用返回结构 sanity。

    复用现有替身模式：PG 依赖用 _FakePg 注入（参考 _new_llm 的注入风格），
    来源用 registry.create 注册（JSON 后端，无 PG 也可跑）。
    """

    @staticmethod
    def _register(svc, nas, **kw):
        """注册一条本地来源并返回注册记录。"""
        fields = {"alias": "nas-local", "protocol": "local",
                  "root_path": str(nas), "access_mode": "ro"}
        fields.update(kw)
        return svc.registry.create(SourceRecord(**fields))

    def test_list_sources_structure(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            self._register(svc, nas, password="supersecret", deep=True)
            out = svc.kb_list_sources()
            assert "sources" in out
            s = out["sources"][0]
            for k in ("source_id", "alias", "protocol", "access_mode",
                      "enabled", "deep"):
                assert k in s
            assert s["alias"] == "nas-local"
            assert s["protocol"] == "local"
            assert s["access_mode"] == "ro"
            assert s["enabled"] is True
            assert s["deep"] is True
            # 脱敏：密码不得明文暴露
            assert s["password"] == "******"
        finally:
            svc.shutdown()

    def test_list_tree_structure(self, kb_env, monkeypatch):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            rec = self._register(svc, nas)
            fake = _FakePg()
            # 让 [pg] 视为已配置（启用 kernel 路径），再注入 _pg 替身
            monkeypatch.setattr(svc.config, "pg_host", "fake-host")
            monkeypatch.setattr(svc, "_pg", lambda: fake)
            out = svc.kb_list_tree(rec.alias)
            assert out["source"] == "nas-local"
            assert out["dir"] == ""
            d = out["dirs"][0]
            assert d["rel_path"] == "财务" and d["file_count"] == 1
            assert "description" not in d and "tags" not in d   # 已投影收敛
            f = out["files"][0]
            assert f["resource_id"] == "r-0001"
            assert f["name"] == "发票1.pdf"
            assert f["size_bytes"] == 123
            assert f["summary"] == "房租发票"
            assert f["category"] == "财务"
            assert f["status"] == "ok"
            assert "rel_path" not in f and "ext" not in f        # 资源以 id 定位
        finally:
            svc.shutdown()

    def test_get_file_url_structure(self, kb_env):
        work, nas = kb_env
        svc = NasKbService(str(work), [str(nas)])
        try:
            rec = self._register(svc, nas)
            # 未配 server_base_url → 相对路径（getattr 兜底）
            out = svc.kb_get_file_url("r-0001", rec.alias)
            assert out["url"] == "/api/files/r-0001/download?src=nas-local"
            # 无 [pg] → canonical 为空且不抛异常（读操作防御）
            assert out["canonical"] == ""
            # 配 server_base_url → 拼绝对前缀
            svc.config.server_base_url = "http://127.0.0.1:9000"
            out2 = svc.kb_get_file_url("r-0001", rec.alias)
            assert out2["url"] == (
                "http://127.0.0.1:9000"
                "/api/files/r-0001/download?src=nas-local")
            # 来源不存在 → 抛 ValueError（安全边界）
            with pytest.raises(ValueError):
                svc.kb_get_file_url("r-0001", "no-such-source")
        finally:
            svc.shutdown()
