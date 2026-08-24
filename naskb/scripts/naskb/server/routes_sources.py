"""来源管理路由（REQ-R7-03）：CRUD / 连通性测试 / 扫描 / 分析 / 报告 / 任务。"""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import Body, HTTPException, Query, Request
from pydantic import BaseModel

from ..common.source_registry import ACCESS_MODES


class SourceIn(BaseModel):
    alias: str
    protocol: str
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    root_path: str = ""
    url: str = ""
    access_mode: str = ACCESS_MODES[0]  # K-001 清理：引用唯一权威定义（source_registry.ACCESS_MODES）
    label: str = ""
    scan_auto: bool = False
    scan_interval_min: int = 60
    deep: bool = False                 # 来源级深度分析（REQ-R5-06）
    enabled: bool = True
    verify_ssl: bool = True


class RebindIn(BaseModel):
    protocol: str = "webdav"
    old_host: str
    old_port: int = 0
    old_user: str = ""
    new_host: str
    new_port: int = 0
    new_user: str = ""


def register_sources_routes(app) -> None:

    def st(request: Request):
        return request.app.state

    # ── CRUD ──

    @app.get("/api/sources")
    async def list_sources(request: Request):
        s = st(request)
        out = []
        for r in s.registry.list():
            d = r.to_api()
            if s.pg is not None and r.schema_name:
                try:
                    d["stats"] = s.pg.source_stats(r.schema_name, r.source_id)
                except Exception:
                    d["stats"] = None
            out.append(d)
        return {"sources": out}

    @app.post("/api/sources")
    async def create_source(request: Request, body: SourceIn,
                            test: bool = Query(False)):
        s = st(request)
        from ..common.source_registry import SourceRecord
        rec = SourceRecord(**body.model_dump())
        probe = None
        if test:
            probe = _probe(rec)
            if not probe.get("ok"):
                raise HTTPException(422, detail={
                    "message": "连通性测试失败", "detail": probe})
        try:
            rec = s.registry.create(rec)
        except ValueError as e:
            raise HTTPException(422, detail=str(e))
        return {"source": rec.to_api(), "probe": probe}

    @app.patch("/api/sources/{sid}")
    async def patch_source(request: Request, sid: str,
                           body: dict = Body(...)):
        s = st(request)
        fields = {k: v for k, v in (body or {}).items()
                  if k != "source_id" and v != "******"}
        before = s.registry.get(sid)
        try:
            rec = s.registry.update(sid, **fields)
        except KeyError:
            raise HTTPException(404, detail=f"来源不存在: {sid}")
        except ValueError as e:
            raise HTTPException(422, detail=str(e))
        # deep 关闭语义（DD-009）：清理该来源存量条款级 chunk 向量行（失败不阻断）
        note = None
        if (before is not None and before.deep and fields.get("deep") is False
                and s.pg is not None and rec.schema_name):
            try:
                removed = s.pg.delete_chunk_rows(rec.schema_name, rec.source_id)
                note = f"deep 关闭：已清理条款级 chunk 行 {removed} 条"
            except Exception as e:
                note = f"deep 关闭：条款级 chunk 清理失败（{e}）"
        return {"source": rec.to_api(), "note": note}

    @app.delete("/api/sources/{sid}")
    async def delete_source(request: Request, sid: str,
                            purge: bool = Query(True)):
        s = st(request)
        rec = s.registry.get(sid)
        if rec is None:
            raise HTTPException(404, detail=f"来源不存在: {sid}")
        removed_rows = 0
        if purge and s.pg is not None and rec.schema_name:
            try:
                removed_rows = s.pg.delete_source_rows(
                    rec.schema_name, rec.source_id)
            except Exception as e:
                raise HTTPException(502, detail=f"清理知识库行失败: {e}")
        ok = s.registry.delete(rec.source_id)
        return {"deleted": ok, "purged_rows": removed_rows}

    # ── 连通性测试 ──

    @app.post("/api/sources/{sid}/test")
    async def test_source(request: Request, sid: str):
        s = st(request)
        rec = s.registry.get(sid)
        if rec is None:
            raise HTTPException(404, detail=f"来源不存在: {sid}")
        return _probe(rec)

    # ── 扫描（stat 级登记入库）──

    @app.post("/api/sources/{sid}/scan")
    async def scan_source(request: Request, sid: str,
                          hash: bool = Query(False, alias="hash")):
        s = st(request)
        rec = s.registry.get(sid)
        if rec is None:
            raise HTTPException(404, detail=f"来源不存在: {sid}")
        compute_hash = hash

        def run(job):
            job["progress"] = 0.05

            def prog(p: float, m: str) -> None:
                job["progress"] = min(0.05 + float(p) * 0.9, 0.95)
                job["message"] = m

            result = s.scan_source_fn(rec, do_hash=compute_hash,
                                      on_progress=prog)
            job["progress"] = 1.0
            return result

        job_id = s.jobs.submit("scan", run)
        return {"job_id": job_id, "hint": "GET /api/jobs/{job_id} 查询进度"}

    # ── 确认清单（REQ-R5-06/系统流程）：dry-run 差异 + 确认后分析 ──

    @app.get("/api/sources/{sid}/changes")
    async def source_changes(request: Request, sid: str,
                             hash: bool = Query(False, alias="hash")):
        s = st(request)
        if s.pg is None:
            raise HTTPException(400, detail="差异报告需要配置 [pg] 知识主库")
        rec = s.registry.get(sid)
        if rec is None:
            raise HTTPException(404, detail=f"来源不存在: {sid}")
        from ..common.inventory import walk_source, compute_missing_hashes
        fs = rec.open_adapter()
        try:
            items, skipped_big = walk_source(fs)
            hashed_now = 0
            if hash or rec.protocol == "local":
                hashed_now = compute_missing_hashes(fs, items)
        finally:
            try:
                fs.close()
            except Exception:
                pass
        diff = s.pg.source_changes(rec.schema_name, rec.source_id, items)
        return {"alias": rec.alias, "diff": diff,
                "skipped_big": skipped_big, "hashed_now": hashed_now}

    @app.post("/api/sources/{sid}/confirm")
    async def confirm_changes(request: Request, sid: str,
                              body: dict = Body(...)):
        """确认清单选中后触发：先对账（幂等），再调度 AI 分析入库。

        body: {"rel_paths": [...]}（可选，记录为本次确认子集）。
        rel_paths 提供时供前端展示/审计；分析仍按来源幂等执行（analyze
        只重析 hash 变化的文件，与子集天然一致）。返回 job_id（分析任务）。
        """
        s = st(request)
        if s.pg is None:
            raise HTTPException(400, detail="确认同步需要配置 [pg] 知识主库")
        rec = s.registry.get(sid)
        if rec is None:
            raise HTTPException(404, detail=f"来源不存在: {sid}")
        rel_paths = body.get("rel_paths")
        from ..common.enrich import enrich_source
        config = s.config

        def run(job):
            job["progress"] = 0.02
            job["message"] = "确认对账…"

            def prog(p: float, m: str) -> None:
                job["progress"] = min(0.05 + float(p) * 0.9, 0.95)
                job["message"] = m

            reconcile = s.scan_source_fn(rec, do_hash=True, on_progress=prog)
            job["reconcile"] = reconcile
            result = enrich_source(
                rec, s.pg, config, on_progress=lambda p, m: (
                    job.__setitem__("progress", min(float(p), 1.0)),
                    job.__setitem__("message", m)))
            return {"reconcile": reconcile, "analyze": result,
                    "confirmed": rel_paths or "all"}

        job_id = s.jobs.submit("confirm", run)
        return {"job_id": job_id, "confirmed": rel_paths or "all",
                "hint": "长任务：GET /api/jobs/{job_id} 查询"}

    # ── AI 富化（分析入库）──

    @app.post("/api/sources/{sid}/analyze")
    async def analyze_source(request: Request, sid: str,
                             llm: bool = Query(True),
                             limit: Optional[int] = Query(None),
                             force: bool = Query(False)):
        s = st(request)
        if s.pg is None:
            raise HTTPException(400, detail="AI 富化需要配置 [pg] 知识主库")
        rec = s.registry.get(sid)
        if rec is None:
            raise HTTPException(404, detail=f"来源不存在: {sid}")
        config = s.config

        def run(job):
            from ..common.enrich import enrich_source
            return enrich_source(
                rec, s.pg, config, llm=llm, limit=limit, force=force,
                on_progress=lambda p, m: (
                    job.__setitem__("progress", min(float(p), 1.0)),
                    job.__setitem__("message", m)))

        job_id = s.jobs.submit("analyze", run)
        return {"job_id": job_id, "hint": "长任务：GET /api/jobs/{job_id} 查询"}

    # ── adopt 收编存量 .naskb（REQ-R7-13）──

    @app.post("/api/sources/{sid}/adopt")
    async def adopt_source(request: Request, sid: str):
        s = st(request)
        if s.pg is None:
            raise HTTPException(400, detail="收编需要配置 [pg] 知识主库")
        rec = s.registry.get(sid)
        if rec is None:
            raise HTTPException(404, detail=f"来源不存在: {sid}")

        def run(job):
            from ..common.adopt import adopt_repo
            return adopt_repo(s.pg, s.config, rec,
                              on_progress=lambda p, m: (
                                  job.__setitem__("progress",
                                                  min(float(p), 1.0)),
                                  job.__setitem__("message", m)))
        job_id = s.jobs.submit("adopt", run)
        return {"job_id": job_id,
                "hint": "收编来源端已有的 .naskb 描述仓库；GET /api/jobs/{job_id}"}

    # ── 一致性报告（DD-009 拍板接回：2026-08-24 恢复装饰器）──
    @app.get("/api/sources/{sid}/report")
    async def source_report(request: Request, sid: str):
        s = st(request)
        rec = s.registry.get(sid)
        if rec is None:
            raise HTTPException(404, detail=f"来源不存在: {sid}")
        out = {"source": rec.to_api(), "backend": s.registry.backend}
        if s.pg is not None and rec.schema_name:
            try:
                out["knowledge"] = s.pg.source_stats(
                    rec.schema_name, rec.source_id)
            except Exception as e:
                out["knowledge"] = {"error": str(e)}
        return out

    # ── PG 重绑（REQ-R4-14：NAS 主机/账号迁移）──

    @app.post("/api/pg/rebind")
    async def pg_rebind(request: Request, body: RebindIn):
        s = st(request)
        if s.pg is None:
            raise HTTPException(400, detail="重绑需要配置 [pg]")
        try:
            res = s.pg.rebind_nas(
                {"protocol": body.protocol, "host": body.old_host,
                 "port": body.old_port, "username": body.old_user},
                {"protocol": body.protocol, "host": body.new_host,
                 "port": body.new_port, "username": body.new_user or ""})
        except RuntimeError as e:
            raise HTTPException(404, detail=str(e))
        # 同步更新引用该 schema 的来源记录（schema_name 由五要素重算）
        updated = 0
        if res["changed"]:
            for rec in s.registry.list():
                if rec.schema_name == res["old_schema"]:
                    s.registry.update(
                        rec.source_id, host=body.new_host,
                        port=body.new_port,
                        username=body.new_user or "", protocol=body.protocol)
                    updated += 1
        return {**res, "sources_updated": updated}

    # ── 任务中心 ──

    @app.get("/api/jobs")
    async def list_jobs(request: Request, status: str = Query("")):
        s = st(request)
        return {"jobs": s.jobs.list(status=status.strip() or None)}

    @app.get("/api/jobs/{job_id}")
    async def get_job(request: Request, job_id: str):
        s = st(request)
        j = s.jobs.get(job_id)
        if j is None:
            raise HTTPException(404, detail="任务不存在")
        return j


def _probe(rec) -> dict:
    """连通性探测：建适配器 → stat 根 → 列一层目录取样。"""
    t0 = time.time()
    fs = None
    try:
        fs = rec.open_adapter()
        root_st = fs.stat("")
        if root_st is None and not fs.exists(""):
            raise OSError(f"根不可访问: {rec.root_path or rec.url}")
        sample = fs.list_files("", recursive=False)[:5]
        return {"ok": True, "ms": int((time.time() - t0) * 1000),
                "root": {"path": root_st.path if root_st else "",
                         "is_dir": True},
                "sample": [{"name": f.name, "size": f.size_bytes}
                           for f in sample]}
    except Exception as e:
        return {"ok": False, "ms": int((time.time() - t0) * 1000),
                "error": f"{type(e).__name__}: {e}"}
    finally:
        pass        # 常驻进程复用连接策略：不主动 close（SubRoot 包装无独立资源）
