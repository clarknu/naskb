"""NASKB MCP Server — 智能 NAS 知识库的标准 Agent 接口（阶段 A）。

工具面（kb_*，17 个）由 common/capabilities.py 注册表驱动注册；
handler 全部落在 NasKbService 上，复用 common/ 既有实现
（retrieval / serve.KnowledgeCore / batch.analyze_tree / pgstore /
reorganizer / plan_store / vector_index），不 shell 到 CLI。

传输：阶段 A 为 stdio（本地桌面 Agent：Claude Desktop / Cursor 等）；
阶段 B 增加 streamable HTTP。启动：`naskb desc serve-mcp` 或
`python -m naskb.mcp.server`。
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..common.capabilities import CAPABILITIES
from ..common.jobs import JobManager


class NasKbService:
    """MCP 服务对象：持 config / 已登记 roots / 检索内核 / JobManager。

    全部 kb_* 工具方法在此实现；长任务（job=True）提交给 JobManager
    异步执行并返回 job_id。
    """

    def __init__(self, work_path: str, roots: Optional[list[str]] = None,
                 pg: bool = False):
        from ..common.config import Config
        self.work_path = str(Path(work_path).resolve())
        self.config = Config.from_work_path(self.work_path)
        self.pg_flag = bool(pg)
        # root 登记：webdav 模式（config.webdav_url + 远程风格路径）vs 本地
        self._webdav = self._detect_webdav(roots)
        self.roots: list[str] = []
        for r in (roots or ["."]):
            self.roots.append(r if self._webdav else str(Path(r).resolve()))
        self.jobs = JobManager()
        self._pg_engine = None
        self._main_fs = None
        self._main_store = None
        self._core = None
        self._llm = None
        from ..common.source_registry import SourceRegistry
        self.registry = SourceRegistry(self.config)
        self._build_core()

    # ── 初始化 / 资源 ──

    def _detect_webdav(self, roots) -> bool:
        if not self.config.webdav_url:
            return False
        hint = (roots or ["."])[0] or "."
        return hint.startswith("/") and not hint.startswith("//")

    def _fresh_fs_store(self, root: str):
        """为调用创建独立 fs/store（本地或 webdav），避免共享连接状态。"""
        from ..common.desc_store import NaskbStore
        from ..common.fs.base import FileSystemAdapter
        cfg = self.config
        if self._webdav:
            auth = {"username": cfg.webdav_user,
                    "password": cfg.webdav_password,
                    "verify_ssl": cfg.webdav_verify_ssl}
            import urllib.parse
            host = urllib.parse.urlparse(cfg.webdav_url).hostname or ""
            if host:  # NAS 国内服务器：显式 NO_PROXY 防 VPN 截断（2026-08-13 教训）
                cur = os.environ.get("NO_PROXY", "")
                os.environ["NO_PROXY"] = f"{cur},{host}" if cur else host
            fs = FileSystemAdapter.create("webdav", cfg.webdav_url, auth)
        else:
            fs = FileSystemAdapter.create("local", root)
        store = NaskbStore(fs, analyzer_version=cfg.desc_analyzer_version,
                           hash_max_bytes=cfg.desc_hash_max_bytes)
        return fs, store

    def _build_core(self) -> None:
        from ..common.llm import LLMConfig, create_llm_client
        from ..common.retrieval import collect_docs
        from ..common.serve import KnowledgeCore
        fs, store = self._fresh_fs_store(self.roots[0])
        self._main_fs, self._main_store = fs, store
        docs: list = []
        for r in self.roots:
            docs.extend(collect_docs(fs, r))
        pg_engine = None
        if self.pg_flag:
            try:
                pg_engine, _schema = self._make_pg_engine()
                self._pg_engine = pg_engine
            except Exception as e:
                print(f"[naskb-mcp] PG 不可用（回退本地引擎）: {e}")
        self._core = KnowledgeCore(self.work_path, self._reload_docs,
                                   pg_engine=pg_engine)
        if docs:
            self._core.load(docs)
        try:
            self._llm = create_llm_client(
                LLMConfig.from_dict(self.config.llm_text))
            self._core.set_llm(self._llm)
        except Exception as e:
            print(f"[naskb-mcp] LLM 未就绪（kb_ask 不可用）: {e}")

    def _reload_docs(self) -> list:
        from ..common.retrieval import collect_docs
        out: list = []
        for r in self.roots:
            out.extend(collect_docs(self._main_fs, r))
        return out

    def _make_pg_engine(self):
        from ..common.pgsearch import PgSearchEngine
        from ..common.pgstore import PgStore
        pg = PgStore(self.config)
        protocol, host, port, username = self._resolve_nas_identity(None)
        nas = pg.get_or_create_nas(protocol, host, port, username)
        engine = PgSearchEngine(pg, self.config.work_path,
                                default_schema=nas["schema_name"])
        return engine, nas["schema_name"]

    def _resolve_nas_identity(self, nas_alias: Optional[str]):
        """NAS 五要素身份解析（复用 reorganizer 的静态方法，无 CLI ctx）。"""
        from ..common.reorganizer import Reorganizer
        return Reorganizer._resolve_nas_identity(
            self._main_store, self.config, nas_alias)

    def _resolve_root(self, root: str) -> str:
        """root 白名单校验：写类操作只能针对已登记的 root。"""
        from ..common.reorganizer import _norm_compare
        want = root if self._webdav else str(Path(root).resolve())
        nw = _norm_compare(want)
        for r in self.roots:
            if _norm_compare(r) == nw:
                return r
        raise ValueError(
            f"root 不在已登记知识库内: {root}（已登记: {self.roots}）")

    @staticmethod
    def _resolve_compare(p: str) -> str:
        """规范化 + 展开 Windows 8.3 短路径名（与 root 登记时 Path.resolve 一致）。

        tempfile/TMP 可能返回 CLARKN~1 短名，而 root 初始化用 Path.resolve()
        展开了长名——两者直接比较会误判"不在知识库内"。
        """
        from ..common.reorganizer import _norm_compare
        if os.name == "nt" and p and not p.startswith("/") \
                and not p.startswith("\\\\"):
            try:
                p = os.path.realpath(p)
            except Exception:
                pass
        return _norm_compare(p)

    def _store_for_path(self, path: str):
        """校验 path 位于已登记 root 内（读取白名单），返回 (fs, store, root)。"""
        from ..common.reorganizer import _is_under
        np = self._resolve_compare(path)
        for r in self.roots:
            if _is_under(self._resolve_compare(r), np):
                fs, store = self._fresh_fs_store(r)
                return fs, store, r
        raise ValueError(f"路径不在已登记知识库内: {path}")

    def _new_llm(self):
        """创建文本 LLM 客户端（测试可注入替换）。"""
        from ..common.llm import LLMConfig, create_llm_client
        return create_llm_client(LLMConfig.from_dict(self.config.llm_text))

    def shutdown(self) -> None:
        """释放资源（等待进行中的任务）。"""
        self.jobs.shutdown(wait=True)
        for closer in (self._pg_engine, self._llm):
            if closer is not None:
                try:
                    closer.close()
                except Exception:
                    pass
        if self._main_fs is not None:
            try:
                self._main_fs.close()
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════
    # A 组：检索与问答（read，同步）
    # ═══════════════════════════════════════════════════════════

    def kb_search(self, query: str, top_k: int = 10,
                  nas: Optional[str] = None,
                  level: str = "summary") -> dict:
        """语义检索知识库。query 必填；nas 指定时走 PG（失败自动回退本地）。

        level: 'summary'（文档级，默认）/ 'chunk'（条款级，REQ-R5-06）。
        """
        if level not in ("summary", "chunk"):
            level = "summary"
        engine, hits = self._core.search(
            query, top_k=max(1, min(int(top_k), 100)), nas_schema=nas)
        if level == "chunk" and self._pg_engine is not None:
            # 条款级：走 chunk 检索并暴露两级引用字段
            chunk_hits = self._pg_engine.search_chunks(
                query, top_k=max(1, min(int(top_k), 100)), schema=nas)
            hits = chunk_hits
            engine = "pg-chunk"
        return {"engine": engine, "hits": hits, "nas": nas,
                "level": level, "total_docs": self._core.stats()["docs"]}

    def kb_ask(self, question: str, top_k: int = 5,
               nas: Optional[str] = None, deep: bool = False) -> dict:
        """RAG 问答（DeepSeek 生成，带来源路径）。

        deep=True 走条款级（两级引用 citations + 保真直返 + 无命中兜底），
        需要 PG + 该来源已建 chunk 行（REQ-R5-06）。
        """
        if deep and self._pg_engine is not None and self._llm is not None:
            try:
                from ..common.retrieval import ask_deep
                schema = nas or getattr(self._pg_engine, "_default_schema", None)
                if schema:
                    deep_cfg = self.config.deep_doc_cfg()
                    deep_cfg["enabled"] = True

                    class _ChunkBound:
                        def __init__(self, eng, sch):
                            self._eng, self._sch = eng, sch

                        def search_chunks(self, q, top_k=None):
                            return self._eng.search_chunks(
                                q, top_k=top_k, schema=self._sch)

                    res = ask_deep(
                        self._llm, _ChunkBound(self._pg_engine, schema),
                        question, top_k=max(1, min(int(top_k), 20)),
                        direct_return=deep_cfg.get("direct_return", False),
                        direct_return_similarity=float(
                            deep_cfg.get("direct_return_similarity", 0.9)),
                        no_hit_mode=str(deep_cfg.get("no_hit_mode", "designated")),
                    )
                    res["nas"] = nas
                    res["level"] = "chunk"      # A'（P-003）：条款级命中，显式标注层级
                    return res
            except Exception:
                pass        # 深析失败 → 回退文档级
        result = self._core.ask(question,
                                top_k=max(1, min(int(top_k), 20)),
                                nas_schema=nas)
        if deep:
            # A'（P-003）：显式要求条款级却回退 → 显式提示"已回退文档级"
            result["level"] = "summary"
            result["note"] = "已回退文档级（条款索引不可用或深析检索失败）"
        return result

    def kb_get_doc(self, path: str, include_fulltext: bool = False) -> dict:
        """取单文件完整元数据（摘要/分类/标签/EXIF/转录/OCR）。"""
        fs, store, _root = self._store_for_path(path)
        try:
            e = store.get_entry(path)
            if e is None:
                return {"path": path,
                        "error": "无描述条目（先运行 kb_ingest 分析该目录）"}
            d = e.to_dict()
            if not include_fulltext:
                d.pop("ocr_text", None)
                d.pop("transcription", None)
            return d
        finally:
            fs.close()

    def kb_fetch_file(self, path: str,
                      max_bytes: int = 8 * 1024 * 1024) -> dict:
        """取原始资源内容（base64；超过上限返回错误提示）。"""
        fs, store, _root = self._store_for_path(path)
        try:
            if fs.is_dir(path):
                return {"path": path,
                        "error": "目录不支持 fetch，请用 kb_get_doc 或 kb_search"}
            st = fs.stat(path)
            if st is None:
                return {"path": path, "error": "文件不存在"}
            if st.size_bytes > max_bytes:
                return {"path": path, "size": st.size_bytes,
                        "error": f"文件过大（{st.size_bytes} 字节，上限 "
                                 f"{max_bytes}），请直接访问 NAS 或用 kb_get_doc"}
            data = fs.read_bytes(path, max_bytes)
            return {"path": path, "size": len(data),
                    "content_base64": base64.b64encode(data).decode("ascii")}
        finally:
            fs.close()

    # ═══════════════════════════════════════════════════════════
    # B 组：入库与索引（write，job 模式）
    # ═══════════════════════════════════════════════════════════

    def kb_ingest(self, root: str, llm: bool = True, workers: int = 4,
                  force: bool = False) -> dict:
        """增量幂等批量分析目录树（hash 对比跳过已分析，可反复调用）。"""
        r = self._resolve_root(root)
        job_id = self.jobs.submit("ingest", self._run_ingest,
                                  r, bool(llm), int(workers), bool(force))
        return {"job_id": job_id,
                "note": "长任务异步执行，用 kb_job_status 查询进度"}

    def _run_ingest(self, job, root: str, llm: bool, workers: int,
                    force: bool):
        from ..common.batch import analyze_tree
        fs, store = self._fresh_fs_store(root)
        try:
            def _progress(done, total, name="", status=""):
                job["progress"] = (done / total) if total else 0.0
                job["message"] = f"{done}/{total} {name} {status}".strip()

            result = analyze_tree(fs, store, self.config, root, llm=llm,
                                  workers=max(1, min(workers, 8)),
                                  mineru=True, force=force,
                                  on_progress=_progress)
            try:  # 检索内核热刷新：analyze 后搜索立即可见
                self._core.reload()
            except Exception:
                pass
            return {
                "total": result.total, "supported": result.supported,
                "analyzed": result.analyzed, "skipped": result.skipped,
                "folder_updated": result.folder_updated,
                "orphans_removed": result.orphans_removed,
                "failed": result.failed,
                "elapsed_sec": result.elapsed,
            }
        finally:
            fs.close()

    def kb_sync_vectors(self, root: str, nas: Optional[str] = None,
                        rebuild: bool = False) -> dict:
        """把 .naskb 描述同步进 PG 多 NAS 向量库（增量：增/改/删/移）。"""
        r = self._resolve_root(root)
        if not self.config.pg_enabled:
            return {"error": "config.toml 未配置 [pg]（PG 为可选增强）"}
        job_id = self.jobs.submit("sync_vectors", self._run_sync_vectors,
                                  r, nas, bool(rebuild))
        return {"job_id": job_id,
                "note": "长任务异步执行，用 kb_job_status 查询进度"}

    def _run_sync_vectors(self, job, root: str, nas, rebuild: bool):
        from ..common.pgstore import PgStore
        from ..common.retrieval import collect_docs
        fs, store = self._fresh_fs_store(root)
        try:
            pg = PgStore(self.config)
            protocol, host, port, username = self._resolve_nas_identity(nas)
            nas_rec = pg.get_or_create_nas(protocol, host, port, username)
            schema = nas_rec["schema_name"]
            if rebuild:
                with pg.connect() as conn:
                    with conn.cursor() as cur:
                        from psycopg import sql
                        cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE")
                                    .format(sql.Identifier(schema)))
            docs = [d for d in collect_docs(fs, root) if d.kind == "file"]
            if not docs:
                return {"schema": schema, "docs": 0, "note": "无描述数据"}
            job["message"] = f"同步 {len(docs)} 条描述 → {schema}"
            stats = pg.sync_vectors(schema, docs)
            return {"schema": schema, "docs": len(docs), **stats}
        finally:
            fs.close()

    def kb_index_vectors(self, root: str) -> dict:
        """构建本地语义向量索引（bge-small-zh 嵌入全部描述，首次较慢）。"""
        r = self._resolve_root(root)
        job_id = self.jobs.submit("index_vectors", self._run_index_vectors, r)
        return {"job_id": job_id,
                "note": "长任务异步执行，用 kb_job_status 查询进度"}

    def _run_index_vectors(self, job, root: str):
        from ..common.embeddings import Embedder
        from ..common.retrieval import collect_docs
        from ..common.vector_index import VectorIndex
        fs, store = self._fresh_fs_store(root)
        try:
            docs = collect_docs(fs, root)
            job["message"] = f"编码 {len(docs)} 条描述…"
            emb = Embedder(self.work_path)
            try:
                idx = VectorIndex(emb, self.work_path)
                n = idx.build(docs)
                return {"indexed": n, "work_path": self.work_path}
            finally:
                emb.close()
        finally:
            fs.close()

    def kb_job_status(self, job_id: str) -> dict:
        """查询长任务进度（进度 0~1/阶段消息/结果/错误）。"""
        j = self.jobs.get(job_id)
        if j is None:
            return {"error": f"任务不存在: {job_id}"}
        return j

    def kb_list_jobs(self, status: Optional[str] = None) -> dict:
        """列出长任务（可按状态过滤）。"""
        return {"jobs": self.jobs.list(status=status)}

    # ═══════════════════════════════════════════════════════════
    # C 组：整理与重组（plan → apply 两段式）
    # ═══════════════════════════════════════════════════════════

    def kb_plan_reorganize(self, root: str, max_items: int = 300) -> dict:
        """AI 生成目录重组方案并持久化，返回 plan_id（只规划不移动）。"""
        r = self._resolve_root(root)
        job_id = self.jobs.submit("plan_reorganize", self._run_plan,
                                  r, int(max_items))
        return {"job_id": job_id,
                "note": "长任务异步执行，用 kb_job_status 查询进度"}

    def _run_plan(self, job, root: str, max_items: int):
        from ..common.plan_store import save_plan
        from ..common.reorganizer import Reorganizer
        fs, store = self._fresh_fs_store(root)
        llm = None
        try:
            llm = self._new_llm()
            rz = Reorganizer(llm, max_files=max_items)
            plan = rz.plan(store, root)
            snapshot = plan.pop("snapshot", {})
            plan_id = save_plan(self.work_path, plan, snapshot,
                                root=plan.get("root") or root)
            return {"plan_id": plan_id,
                    "plan_name": plan.get("plan_name") or "(未命名)",
                    "total": plan.get("total", 0),
                    "moves": len(plan.get("moves", [])),
                    "rejected": plan.get("rejected", []),
                    "rationale": plan.get("rationale", "")}
        finally:
            if llm is not None:
                llm.close()
            fs.close()

    def kb_preview_reorganize(self, plan_id: str) -> dict:
        """对已生成方案 dry-run：逐条判定，不移动任何文件。"""
        from ..common.plan_store import load_plan
        from ..common.reorganizer import (Reorganizer, _norm_compare,
                                          validate_move)
        rec = load_plan(self.work_path, plan_id)
        if rec is None:
            return {"error": f"方案不存在: {plan_id}"}
        plan = rec.get("plan") or {}
        snapshot = rec.get("snapshot") or {}
        root = rec.get("root", "")
        fs, store = None, None
        try:
            if root:
                fs, store = self._fresh_fs_store(root)
            rz = Reorganizer()
            classified: list[dict] = []
            for m in plan.get("moves") or []:
                src, dst = str(m.get("from", "")), str(m.get("to", ""))
                item = {"from": src, "to": dst,
                        "reason": str(m.get("reason", ""))}
                ok, why = validate_move(src, dst, root)
                if not ok:
                    item["action"] = "rejected"
                    item["detail"] = why
                    classified.append(item)
                    continue
                if snapshot and fs is not None:
                    if not fs.exists(src):
                        item["action"] = "not_found"
                        classified.append(item)
                        continue
                    if not fs.is_dir(src):
                        want = snapshot.get(
                            _norm_compare(src))
                        if want:
                            try:
                                _a, cur = store.compute_hash(src)
                            except Exception:
                                cur = ""
                            if cur != want:
                                item["action"] = "stale_source"
                                classified.append(item)
                                continue
                if fs is not None and fs.is_dir(src):
                    item["action"] = "move_dir"
                else:
                    action, target = rz._decide_conflict(store, src, dst)
                    item["action"] = action
                    if action == "move" and target != dst:
                        item["to"] = target   # rename 后的实际目标
                classified.append(item)
            counts: dict[str, int] = {}
            for c in classified:
                counts[c["action"]] = counts.get(c["action"], 0) + 1
            return {"plan_id": plan_id,
                    "plan_name": plan.get("plan_name") or "",
                    "root": root,
                    "summary": counts,
                    "moves": classified}
        finally:
            if fs is not None:
                fs.close()

    def kb_apply_reorganize(self, plan_id: str, sync: bool = True) -> dict:
        """执行方案（凭 plan_id；服务端复校验；整理后自动同步索引与 PG）。"""
        from ..common.plan_store import load_plan
        rec = load_plan(self.work_path, plan_id)
        if rec is None:
            return {"error": f"方案不存在: {plan_id}"}
        if rec.get("status") == "applied":
            return {"error": f"方案已执行过: {plan_id}",
                    "result": rec.get("result")}
        job_id = self.jobs.submit("apply_reorganize", self._run_apply,
                                  plan_id, bool(sync))
        return {"job_id": job_id,
                "note": "长任务异步执行，用 kb_job_status 查询进度"}

    def _run_apply(self, job, plan_id: str, sync: bool):
        from ..common.plan_store import load_plan, mark_applied
        from ..common.reorganizer import Reorganizer
        rec = load_plan(self.work_path, plan_id)
        if rec is None:
            raise ValueError(f"方案不存在: {plan_id}")
        root = rec.get("root", "")
        fs, store = self._fresh_fs_store(root)
        llm = None
        try:
            llm = self._new_llm()
            rz = Reorganizer(llm)
            result = rz.apply_with_housekeeping(
                store, rec["plan"], rec.get("snapshot") or {},
                llm_client=llm, config=self.config, sync=sync)
            mark_applied(self.work_path, plan_id, result)
            return result
        finally:
            if llm is not None:
                llm.close()
            fs.close()

    # ═══════════════════════════════════════════════════════════
    # D 组：管理与状态
    # ═══════════════════════════════════════════════════════════

    def kb_status(self, root: Optional[str] = None,
                  nas: Optional[str] = None) -> dict:
        """知识库一致性报告（valid/stale/missing + PG 差异，只读）。"""
        targets = [self._resolve_root(root)] if root else list(self.roots)
        out: dict = {"roots": []}
        for r in targets:
            fs, store = self._fresh_fs_store(r)
            try:
                out["roots"].append({"root": r, "scan": store.scan(r)})
            finally:
                fs.close()
        if nas and self.config.pg_enabled:
            try:
                from ..common.pgstore import PgStore
                pg = PgStore(self.config)
                protocol, host, port, username = self._resolve_nas_identity(nas)
                nas_rec = pg.get_or_create_nas(protocol, host, port, username)
                schema = nas_rec["schema_name"]
                out["pg"] = pg.nas_stats(schema)
                out["pg"]["schema"] = schema
            except Exception as e:
                out["pg"] = f"failed: {e}"
        return out

    def kb_stats(self) -> dict:
        """全局状态：引擎/文档数/向量索引状态/PG 注册 NAS。"""
        try:
            stats = self._core.stats()
        except Exception:
            stats = {}
        return {**stats, "roots": self.roots, "work_path": self.work_path}

    # ── v3 来源化工具（V2 扩展）──

    def kb_list_sources(self) -> dict:
        """已注册的知识来源清单（平台 v0.1 来源注册表）。

        复用 registry.list() 并取每条 to_api()（默认对密码脱敏），
        与同文件 kb_status/kb_stats 一致只在服务对象上取数、不重复造轮子。
        """
        return {"sources": [r.to_api() for r in self.registry.list()]}

    def kb_list_tree(self, source: str, dir: str = "") -> dict:
        """罗列指定来源的目录树（来源/目录浏览，REQ-R7-09）。

        底层复用 pgstore.PgStore.list_dir（与 REST /api/tree 同一取数函数），
        输出收敛为规范结构：dirs[{rel_path,name,file_count,summary}]、
        files[{resource_id,name,size_bytes,summary,category,status}]，
        资源一律用 resource_id 定位（安全边界，REQ-R7-03）。
        """
        rec = self.registry.get(source)
        if rec is None:
            raise ValueError(f"来源不存在: {source}")
        rel = (dir or "").strip().strip("/")
        if not self.config.pg_enabled:
            return {"source": rec.alias, "dir": rel, "dirs": [], "files": [],
                    "error": "目录浏览需要配置 [pg] 知识主库"}
        pg = self._pg()
        dirs, files = pg.list_dir(rec.schema_name, rec.source_id, rel)
        return {
            "source": rec.alias,
            "dir": rel,
            "dirs": [{"rel_path": d["rel_path"], "name": d["name"],
                      "file_count": d["file_count"],
                      "summary": d["summary"]} for d in dirs],
            "files": [{"resource_id": f["resource_id"], "name": f["name"],
                       "size_bytes": f["size_bytes"], "summary": f["summary"],
                       "category": f["category"],
                       "status": f["status"]} for f in files],
        }

    def kb_get_file_url(self, resource_id: str, source: str) -> dict:
        """取原始资源直链（下载代理路径或协议级 canonical uri）。

        server_base_url 从配置读（getattr 兜底），缺失时输出相对路径；
        下载直链本身不依赖 PG，canonical 仅在 [pg] 就绪时给出。
        """
        rec = self.registry.get(source)
        if rec is None:
            raise ValueError(f"来源不存在: {source}")
        base = getattr(self.config, "server_base_url", "") or ""
        url = f"/api/files/{resource_id}/download?src={rec.alias}"
        if base:
            url = base.rstrip("/") + url
        return {"url": url,
                "note": "需 serve-platform 提供下载代理；否则用 canonical 直连",
                "canonical": self._canonical_uri(rec, resource_id)}

    def _canonical_uri(self, rec, resource_id: str) -> str:
        """生成协议级直链（无认证；仅供展示/告知，实际下载走代理）。"""
        if not self.config.pg_enabled:
            return ""
        row = None
        try:
            row = self._pg().get_resource(rec.schema_name, resource_id)
        except Exception:
            pass
        if row is None:
            return ""
        if rec.protocol == "webdav" and rec.url:
            return f"{rec.url.rstrip('/')}/{row['rel_path'].lstrip('/')}"
        return f"{rec.root_path or ''}/{row['rel_path']}"

    def _pg(self):
        from ..common.pgstore import PgStore
        return PgStore(self.config)

    def _audit(self, op: str, **fields) -> None:
        """写操作审计日志（追加式 JSONL，工作区 store/audit/）。"""
        try:
            day = datetime.now().strftime("%Y%m%d")
            d = os.path.join(self.work_path, "store", "audit")
            os.makedirs(d, exist_ok=True)
            line = json.dumps({
                "t": datetime.now().astimezone().isoformat(timespec="seconds"),
                "op": op, **fields}, ensure_ascii=False)
            with open(os.path.join(d, day + ".log"), "a",
                      encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# FastMCP 组装与入口
# ═══════════════════════════════════════════════════════════

def build_mcp(svc: NasKbService):
    """由能力注册表注册全部 kb_* 工具（单一事实源）。"""
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP(
        "naskb-kb",
        instructions=(
            "智能 NAS 知识库（企业文档/资源库）。工具前缀 kb_。"
            "用法要点：检索 kb_search / 问答 kb_ask / 元数据 kb_get_doc；"
            "新文件入库 kb_ingest（增量幂等可反复跑）；"
            "目录整理必须两段式：先 kb_plan_reorganize 拿到 plan_id 并向"
            "用户展示方案，确认后才 kb_apply_reorganize 执行。"
            "分钟级操作为长任务：工具立即返回 job_id，用 kb_job_status 查询。"
        ),
    )
    def _mk_wrap(capname, base):
        def _wrap(*a, **k):
            try:
                r = base(*a, **k)
                svc._audit(capname, ok=True)
                return r
            except Exception as e:
                svc._audit(capname, ok=False, error=str(e))
                raise
        return _wrap

    for cap in CAPABILITIES:
        fn = getattr(svc, cap.name)
        if cap.kind in ("write", "apply"):
            fn = _mk_wrap(cap.name, fn)
        mcp.tool(name=cap.name, description=cap.description)(fn)

    # ── Resources（只读视图，agent 直接"读"不用"调"）──
    @mcp.resource("kb://stats")
    def r_stats() -> str:
        return json.dumps(svc.kb_stats(), ensure_ascii=False)

    @mcp.resource("kb://sources")
    def r_sources() -> str:
        return json.dumps(svc.kb_list_sources(), ensure_ascii=False)

    @mcp.resource("kb://status/{alias}")
    def r_status(alias: str) -> str:
        rec = svc.registry.get(alias)
        if rec is None:
            return json.dumps({"error": f"来源不存在: {alias}"},
                              ensure_ascii=False)
        pg = svc._pg()
        return json.dumps(
            {"source": rec.to_api(),
             "knowledge": pg.source_stats(rec.schema_name, rec.source_id)},
            ensure_ascii=False)

    # ── Prompts（工作流模板，固化"正确使用 KB"的守则）──
    @mcp.prompt(name="kb-find")
    def p_find() -> str:
        return ("先 kb_search 定位相关文件 → 必要时 kb_get_doc 看知识细节 → "
                "再用 kb_ask 总结并带出引用来源。")

    @mcp.prompt(name="kb-ingest")
    def p_ingest() -> str:
        return ("新增文档先 kb_ingest（增量幂等）→ kb_status 核对覆盖 → "
                "kb_sync_vectors 把描述同步进 PG 向量库。")

    @mcp.prompt(name="kb-reorganize")
    def p_reorganize() -> str:
        return ("整理必须两段式：先 kb_plan_reorganize 生成方案（只输出），"
                "向用户展示并取得确认后，才 kb_apply_reorganize 执行。")
    return mcp


def run_stdio(work_path: str, roots: Optional[list[str]] = None,
              pg: bool = False) -> None:
    """stdio 传输（本地桌面 Agent：Claude Desktop / Cursor 等）。"""
    svc = NasKbService(work_path, roots, pg=pg)
    mcp = build_mcp(svc)
    try:
        mcp.run(transport="stdio")
    finally:
        svc.shutdown()


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="NASKB MCP server（stdio）")
    ap.add_argument("--work-path", "-w",
                    default=os.environ.get("NASKB_WORK", ""),
                    help="工作区路径（默认 NASKB_WORK 或 ./NASKB_data）")
    ap.add_argument("--root", action="append", default=None,
                    help="知识库根目录（含 .naskb/），可多次传入；默认 .")
    ap.add_argument("--pg", action="store_true",
                    help="启用 PG 多 NAS 向量库后端")
    args = ap.parse_args()
    work = args.work_path or str(Path.cwd() / "NASKB_data")
    run_stdio(work, args.root, pg=args.pg)


if __name__ == "__main__":
    main()
