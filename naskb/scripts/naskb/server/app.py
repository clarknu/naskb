"""平台服务装配（REQ-R7-01/09/10）：FastAPI 应用工厂。

出口：
- 旧契约原样平移：GET /api/search、POST /api/ask、GET /api/stats、
  POST /api/reload（ADR-20260816-2 冻结，响应形状与 stdlib serve 完全一致）；
- 平台新增：/api/kb/search（凭 resource_id 寻址的检索）、来源管理、浏览、
  内容访问（下载代理/预览）、任务中心；
- Web UI：静态包托管（naskb/web/dist，Vue3，构建产物随包分发）。

认证：AuthPolicy 中间件（单管理员 token + 匿名只读开关，REQ-R7-11）。
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..common.embeddings import Embedder, model_ready
from ..common.jobs import JobManager
from ..common.pgstore import PgStore
from ..common.retrieval import collect_docs
from ..common.serve import KnowledgeCore
from ..common.source_registry import SourceRegistry
from .auth import AuthPolicy
from .scheduler import ScanScheduler

VERSION = "0.1.0"


# ═══════════════════════════════════════════════════════════════
# 装配
# ═══════════════════════════════════════════════════════════════

def create_app(config) -> FastAPI:
    registry = SourceRegistry(config)
    pg = PgStore(config) if getattr(config, "pg_enabled", False) else None
    jobs = JobManager(max_workers=1)
    auth = AuthPolicy.from_config(config)

    # ── 检索内核（旧契约兼容面）：描述数据来自全部启用来源 ──
    def _legacy_loader():
        docs = []
        for src in registry.list(include_disabled=False):
            try:
                fs = src.open_adapter()
                try:
                    docs.extend(collect_docs(fs, ""))
                finally:
                    pass            # SubRootAdapter.close 会关底层；进程常驻不关
            except Exception:
                continue
        return docs

    core = KnowledgeCore(config.work_path, _legacy_loader, pg_engine=None)
    core.load(_legacy_loader())
    try:
        from ..common.llm import LLMConfig, create_llm_client
        if getattr(config, "llm_text", None):
            core.set_llm(create_llm_client(LLMConfig.from_dict(config.llm_text)))
    except Exception:
        pass

    # ── 扫描服务函数（路由与调度器共用）──
    def _scan_source(source, do_hash: bool = False,
                     on_progress=None) -> dict:
        if pg is None:
            raise RuntimeError("扫描入库需要配置 [pg]（知识主库），见 config.toml")
        from ..common.inventory import walk_source, compute_missing_hashes
        if on_progress:
            on_progress(0.15, f"遍历 {source.alias} …")
        fs = source.open_adapter()
        items, skipped_big = walk_source(fs)
        hashed = 0
        if do_hash or source.protocol == "local":
            if on_progress:
                on_progress(0.45, "计算内容指纹…")
            hashed = compute_missing_hashes(fs, items)
        if on_progress:
            on_progress(0.8, "对账入库…")
        stats = pg.reconcile_resources(
            source.schema_name, source.source_id, items)
        registry.touch_scan(source.source_id)
        return {"source": source.alias, **stats,
                "skipped_big": skipped_big, "hashed_now": hashed}

    scheduler = ScanScheduler(registry, jobs, _scan_source)

    # 共享嵌入器（懒加载 + 锁；kb/search 用）
    _emb_lock = threading.Lock()
    _embedder_box: dict = {"emb": None}

    def get_embedder() -> Embedder:
        with _emb_lock:
            if _embedder_box["emb"] is None:
                if not model_ready(config.work_path):
                    raise HTTPException(
                        503, detail="向量模型未下载：请先运行 "
                                    "`naskb desc index-vectors` 或触发一次来源分析")
                _embedder_box["emb"] = Embedder(config.work_path)
            return _embedder_box["emb"]

    # ── 启动/停止（lifespan）──
    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        scheduler.start()
        yield
        scheduler.stop()
        emb = _embedder_box.get("emb")
        if emb:
            try:
                emb.close()
            except Exception:
                pass

    app = FastAPI(
        title="NASKB 知识库系统",
        version=VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )

    app.state.config = config
    app.state.registry = registry
    app.state.pg = pg
    app.state.core = core
    app.state.jobs = jobs
    app.state.auth = auth
    app.state.scheduler = scheduler
    app.state.get_embedder = get_embedder
    app.state.scan_source_fn = _scan_source
    app.state.legacy_loader = _legacy_loader

    # ── 认证中间件 ──
    @app.middleware("http")
    async def _auth_middleware(request: Request, call_next):
        if not auth.check(request):
            return JSONResponse(
                {"error": "unauthorized",
                 "hint": "Authorization: Bearer <token>"},
                status_code=401)
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    # ═══════════════════════════════════════════════════════════
    # 旧契约（冻结，ADR-20260816-2）
    # ═══════════════════════════════════════════════════════════

    @app.get("/api/stats")
    async def legacy_stats():
        return core.stats()

    @app.get("/api/search")
    async def legacy_search(
        q: str = Query(""),
        top_k: int = Query(10),
        nas: str = Query(""),
    ):
        query = q.strip()
        if not query:
            # 契约冻结：错误形状与 stdlib serve 一致（{"error": …}）
            return JSONResponse({"error": "缺少查询参数 q"}, status_code=400)
        top_k = max(1, min(int(top_k), 100))
        nas_schema = nas.strip() or None
        engine, hits = core.search(query, top_k=top_k, nas_schema=nas_schema)
        return {"query": query, "engine": engine, "hits": hits,
                "total_docs": core.stats()["docs"], "nas": nas_schema}

    @app.post("/api/ask")
    async def legacy_ask(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        question = str(body.get("question") or "").strip()
        if not question:
            return JSONResponse({"error": "缺少 question 字段"},
                                status_code=400)
        try:
            top_k = max(1, min(int(body.get("top_k") or 5), 20))
        except (TypeError, ValueError):
            top_k = 5
        nas = str(body.get("nas") or "").strip() or None
        result = core.ask(question, top_k=top_k, nas_schema=nas)
        result["nas"] = nas
        return result

    @app.post("/api/reload")
    async def legacy_reload():
        return core.reload()

    # ═══════════════════════════════════════════════════════════
    # 平台检索（凭 id 寻址，REQ-R7-10）
    # ═══════════════════════════════════════════════════════════

    @app.get("/api/config/public")
    async def public_config():
        return {"version": VERSION,
                "auth_required": auth.enabled,
                "anonymous_read": auth.anonymous_read}

    @app.get("/api/kb/search")
    async def kb_search(
        request: Request,
        query: str = Query("", alias="query"),
        top_k: int = Query(10),
        sources: str = Query(""),       # 逗号分隔 alias/id；空 = 全部
        dir: str = Query(""),           # 目录范围过滤（前缀）
    ):
        query = query.strip()
        if not query:
            raise HTTPException(400, detail="缺少查询参数 query")
        top_k = max(1, min(int(top_k), 100))
        wanted = [x.strip() for x in sources.split(",") if x.strip()]
        records = []
        for key in wanted or [None]:
            rec = registry.get(key) if key else None
            if key and rec is None:
                raise HTTPException(404, detail=f"来源不存在: {key}")
            if rec is not None:
                records.append(rec)
        if wanted and not records:
            records = []

        # PG 向量检索（主路径）
        if pg is not None:
            try:
                emb = get_embedder()
                vec = emb.encode_one(query)
                schemas: dict[str, dict] = {}
                if records:
                    for r in records:
                        schemas.setdefault(r.schema_name, {
                            "sids": [], "aliases": []})
                        schemas[r.schema_name]["sids"].append(r.source_id)
                        schemas[r.schema_name]["aliases"].append(r.alias)
                else:
                    for r in registry.list(include_disabled=False):
                        schemas.setdefault(r.schema_name, {
                            "sids": [], "aliases": []})
                        schemas[r.schema_name]["sids"].append(r.source_id)
                        schemas[r.schema_name]["aliases"].append(r.alias)
                merged: list[dict] = []
                for schema, info in schemas.items():
                    try:
                        hits = pg.search(schema, vec, top_k=top_k,
                                         source_ids=info["sids"])
                    except Exception:
                        continue
                    for h in hits:
                        h["nas"] = info["aliases"][0]
                        merged.append(h)
                merged.sort(key=lambda x: -float(x.get("score") or 0))
                merged = merged[:top_k]
                out = [_trim_hit(h, dir_prefix=dir.strip("/")) for h in merged]
                return {"query": query, "engine": "pg", "hits": out,
                        "total": len(out)}
            except HTTPException:
                raise
            except Exception:
                pass        # PG 失败 → 回退本地引擎链（REQ-R4-13）

        # 回退：本地 KnowledgeCore（无 rid，内容访问不可用）
        engine, hits = core.search(query, top_k=top_k)
        out = [{"resource_id": None, "source_id": None, "path": h.get("path"),
                "name": (h.get("path") or "").rsplit("/", 1)[-1],
                "kind": h.get("kind"), "category": h.get("category"),
                "tags": h.get("tags") or [], "summary": h.get("summary"),
                "score": h.get("score"), "status": "", "stale": False,
                "engine": engine} for h in hits]
        out = [h for h in out
               if not dir or (h["path"] or "").strip("/")
               .startswith(dir.strip("/"))]
        return {"query": query, "engine": engine, "hits": out,
                "total": len(out), "hint": "PG 未启用：结果无资源定位，"
                                           "仅支持元数据查看"}

    def _trim_hit(h: dict, dir_prefix: str = "") -> dict:
        rel = h.get("path") or ""
        if dir_prefix and not rel.lstrip("/").startswith(dir_prefix):
            return {}
        return {
            "resource_id": h.get("resource_id"),
            "source_id": h.get("source_id"),
            "nas": h.get("nas"),
            "path": rel,
            "name": h.get("name") or rel.rsplit("/", 1)[-1],
            "kind": h.get("kind"),
            "category": h.get("category"),
            "tags": h.get("tags") or [],
            "summary": h.get("summary"),
            "score": round(float(h.get("score") or 0), 6),
            "status": h.get("status") or "",
            "stale": bool(h.get("stale")),
        }

    # ── 路由模块 ──
    from .routes_sources import register_sources_routes
    from .routes_content import register_content_routes
    register_sources_routes(app)
    register_content_routes(app)

    # ── Web UI 静态包（最后挂载，兜底 /）──
    web_dist = Path(__file__).resolve().parent.parent / "web" / "public"
    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True),
                  name="web")
    else:
        @app.get("/")
        async def _index():
            return {"app": "NASKB 知识库系统", "version": VERSION,
                    "hint": "Web UI 静态包未构建（naskb/web/dist 缺失）；"
                            "API 文档见 /api/docs"}

    return app


def run(config, host: str = "127.0.0.1", port: int = 8765) -> None:
    """阻塞式启动平台服务。"""
    import uvicorn
    app = create_app(config)
    url_host = host if host not in ("0.0.0.0", "::") else "127.0.0.1"
    print(f"[naskb] 知识库系统 v{VERSION} 已启动: http://{url_host}:{port}/")
    print("[naskb] API 文档: /api/docs · Ctrl+C 停止")
    uvicorn.run(app, host=host, port=port, log_level="warning")
