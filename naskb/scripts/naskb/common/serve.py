"""内置知识库服务 — naskb desc serve。

标准库 http.server 实现，零第三方依赖，单机/局域网内部问答入口：

- GET  /            单页 Web UI（搜索 + RAG 问答）
- GET  /api/search  检索（向量优先，索引缺失/陈旧降级 BM25）
- POST /api/ask     RAG 问答（DeepSeek 生成，带来源路径）
- POST /api/reload  重新收集 .naskb 描述数据（analyze 后热刷新）
- GET  /api/stats   索引/引擎状态

接口与实现解耦：未来 MaxKB 扩展包实现相同 /api/search、/api/ask
契约即可切换检索后端（换实现不换接口，serve 前端无需改动）。
"""
from __future__ import annotations

import json
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

from .retrieval import BM25Index, Doc, ask as rag_ask


class _SchemaBound:
    """把 PgSearchEngine 绑定到指定 NAS schema 的轻量视图。

    rag_ask 只依赖 search(query, top_k)，本视图按需绑定 schema，
    避免共享可变默认 schema 的并发问题。
    """

    def __init__(self, engine, schema: str):
        self._engine = engine
        self._schema = schema

    def search(self, query: str, top_k: int = 10, kind=None) -> list[dict]:
        return self._engine.search(query, top_k=top_k, kind=kind,
                                   schema=self._schema)


class KnowledgeCore:
    """检索/问答内核：持有文档集合与当前索引，供 HTTP handler 调用。

    线程模型：reload 用锁串行化；search/ask 只读共享索引（引用替换是
    原子的），不持锁——问答 LLM 调用耗时长，不应阻塞搜索。
    """

    def __init__(self, work_path: str, loader: Callable[[], list[Doc]],
                 pg_engine=None):
        self._work_path = work_path
        self._loader = loader          # 重新收集描述数据（热刷新用）
        self._llm = None               # llm client（complete(prompt)）
        self._pg_engine = pg_engine    # PgSearchEngine（可选，REQ-R4-12）
        self._lock = threading.Lock()
        self._docs: list[Doc] = []
        self._index = None
        self._engine = "bm25"
        self._vector_count = 0
        self._vector_stale = False

    # ── 索引构建 / 状态 ──

    def load(self, docs: list[Doc]) -> None:
        """初始加载：优先向量索引（与 desc index-vectors 产物一致），
        否则 BM25。"""
        with self._lock:
            self._docs = list(docs)
            self._build_index(self._docs)

    def _build_index(self, docs: list[Doc]) -> None:
        self._engine = "bm25"
        self._vector_count = 0
        self._vector_stale = False
        emb = None
        try:
            from .embeddings import Embedder, model_ready
            from .vector_index import VectorIndex

            if not model_ready(self._work_path):
                # 读路径不触发联网下载（下载由 desc index-vectors 显式触发），
                # 模型缺失直接回退 BM25，避免无网环境 180s×N 阻塞
                raise RuntimeError("向量模型未下载（运行 desc index-vectors 下载并建索引）")
            emb = Embedder(self._work_path)
            vindex = VectorIndex(emb, self._work_path)
            if vindex.load():
                # 向量索引须与当前文档集合一致，否则视为陈旧（内容
                # 已变化，需要重新 desc index-vectors）
                if set(vindex.paths()) == set(d.path for d in docs):
                    self._index = vindex
                    self._engine = "vector"
                    self._vector_count = vindex.count()
                    return
                self._vector_stale = True
        except Exception:
            pass
        finally:
            if emb and self._engine != "vector":
                emb.close()
        index = BM25Index()
        index.build(docs)
        self._index = index

    def reload(self) -> dict:
        """重新收集描述数据并重建索引；收集为空则保留旧索引。"""
        with self._lock:
            docs = self._loader()
            if not docs:
                return {"ok": False,
                        "error": "没有找到任何描述数据（先运行 desc analyze）"}
            self._docs = list(docs)
            self._build_index(self._docs)
            return {**self.stats(), "ok": True}

    def stats(self) -> dict:
        out = {
            "engine": self._engine,
            "docs": len(self._docs),
            "vector_count": self._vector_count,
            "vector_stale": self._vector_stale,
            "pg": self._pg_engine is not None,
            "nas_options": [],
        }
        if self._pg_engine is not None:
            try:
                out["nas_options"] = self._pg_engine.nas_options()
            except Exception:
                out["pg"] = False
        return out

    # ── 检索 / 问答 ──

    def search(self, query: str, top_k: int = 10,
               nas_schema: Optional[str] = None) -> tuple[str, list[dict]]:
        """nas_schema 给出且 PG 可用 → PG 检索（失败自动回退本地引擎）。"""
        if nas_schema and self._pg_engine is not None:
            try:
                hits = self._pg_engine.search(query, top_k=top_k,
                                              schema=nas_schema)
                return "pg", hits
            except Exception:
                pass  # PG 失败 → 回退本地引擎（REQ-R4-13）
        hits = self._index.search(query, top_k=top_k)
        return self._engine, hits

    def ask(self, question: str, top_k: int = 5,
            context_chars: int = 6000,
            nas_schema: Optional[str] = None) -> dict:
        """RAG 问答；LLM 未配置时返回带 error 的结果（不抛异常）。"""
        if self._llm is None:
            return {"answer": "", "sources": [],
                    "error": "LLM 未配置：在 config.toml [llm.text] 填写 "
                             "api_key 后重启服务"}
        if nas_schema and self._pg_engine is not None:
            try:
                # 绑定 schema 的轻量视图：rag_ask 只调 search(query, top_k)
                bound = _SchemaBound(self._pg_engine, nas_schema)
                result = rag_ask(self._llm, bound, question,
                                 top_k=top_k, context_chars=context_chars)
                result["engine"] = "pg"
                return result
            except Exception:
                pass  # PG 失败 → 回退本地引擎（REQ-R4-13）
        if not self._docs:
            return {"answer": "知识库中没有找到与问题相关的描述。",
                    "sources": []}
        result = rag_ask(self._llm, self._index, question,
                         top_k=top_k, context_chars=context_chars)
        result["engine"] = self._engine
        return result

    def set_llm(self, client) -> None:
        self._llm = client


# ═══════════════════════════════════════════════════════════════════
# HTTP 层
# ═══════════════════════════════════════════════════════════════════

_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NASKB 知识库</title>
<style>
:root { --bg:#f6f7f9; --card:#fff; --line:#e3e6ea; --ink:#1f2933;
        --sub:#6b7280; --accent:#2f6fed; --ok:#1a7f4b; --warn:#b45309; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;
       background:var(--bg); color:var(--ink); line-height:1.6; }
header { display:flex; align-items:center; gap:12px; flex-wrap:wrap;
         padding:14px 20px; background:var(--card); border-bottom:1px solid var(--line);
         position:sticky; top:0; }
header h1 { font-size:18px; }
.badge { font-size:12px; padding:2px 10px; border-radius:10px;
         background:#eef4ff; color:var(--accent); border:1px solid #c9dbff; }
.badge.warn { background:#fff4e6; color:var(--warn); border-color:#f3d9b8; }
.badge.ok { background:#e9f7ef; color:var(--ok); border-color:#c2e5d0; }
#stats { font-size:13px; color:var(--sub); }
main { max-width:900px; margin:20px auto; padding:0 16px; display:grid; gap:18px; }
section { background:var(--card); border:1px solid var(--line);
          border-radius:10px; padding:18px; }
section h2 { font-size:15px; margin-bottom:10px; }
.input-row { display:flex; gap:8px; }
input[type=text] { flex:1; padding:9px 12px; border:1px solid var(--line);
         border-radius:8px; font-size:14px; outline:none; }
input[type=text]:focus { border-color:var(--accent); }
button { padding:9px 16px; border:none; border-radius:8px; background:var(--accent);
         color:#fff; font-size:14px; cursor:pointer; white-space:nowrap; }
button:hover { opacity:.9; }
button.ghost { background:#fff; color:var(--ink); border:1px solid var(--line); }
.hit { padding:12px; border-bottom:1px solid var(--line); }
.hit:last-child { border-bottom:none; }
.hit .path { font-weight:600; font-size:14px; word-break:break-all; }
.hit .meta { font-size:12px; color:var(--sub); margin-top:3px;
             display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.hit .summary { font-size:13px; margin-top:5px; color:#3f4853; }
.kind { font-size:11px; padding:0 7px; border-radius:8px;
        background:#f0f2f5; color:var(--sub); }
.kind.stale { background:#fff4e6; color:var(--warn); }
select { padding:7px 10px; border:1px solid var(--line); border-radius:8px;
         font-size:13px; background:#fff; max-width:260px; }
#answer { white-space:pre-wrap; font-size:14px; padding:12px;
          background:#f8fafc; border-radius:8px; border:1px solid var(--line); }
#sources { font-size:12px; color:var(--sub); margin-top:8px; }
#sources div { word-break:break-all; }
.error { color:#c0392b; font-size:13px; margin-top:8px; }
.hint { font-size:12px; color:var(--sub); margin-top:6px; }
.spinner { color:var(--sub); font-size:13px; margin-top:8px; }
</style>
</head>
<body>
<header>
  <h1>📚 NASKB 知识库</h1>
  <span id="engine-badge" class="badge">…</span>
  <span id="stats">加载中…</span>
  <select id="nas-select" title="选择 NAS 向量库（PG 模式）"></select>
  <button id="reload-btn" class="ghost" title="analyze 之后点此热刷新描述数据">刷新索引</button>
</header>
<main>
  <section>
    <h2>🔍 搜索</h2>
    <div class="input-row">
      <input type="text" id="q" placeholder="输入关键词（如：合同 租赁 / 装修预算），回车搜索">
      <button id="search-btn">搜索</button>
    </div>
    <div id="search-results"></div>
  </section>
  <section>
    <h2>💬 问答</h2>
    <div class="input-row">
      <input type="text" id="question" placeholder="向知识库提问（如：月租金是多少？和谁签的？）">
      <button id="ask-btn">提问</button>
    </div>
    <div id="answer-area"></div>
  </section>
</main>
<script>
const $ = id => document.getElementById(id);
const esc = s => (s ?? "").replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

async function refreshStats() {
  try {
    const r = await fetch("/api/stats");
    const s = await r.json();
    const b = $("engine-badge");
    b.textContent = s.engine === "vector" ? "向量检索"
      : (s.pg ? "PG 多 NAS" : "BM25 关键词");
    b.className = "badge " + (s.engine === "vector" || s.pg ? "" : "warn");
    $("stats").textContent =
      `${s.docs} 条描述` + (s.vector_count ? `（向量 ${s.vector_count}）` : "");
    if (s.vector_stale)
      $("stats").textContent += " · 向量索引已陈旧，可运行 naskb desc index-vectors";
    // NAS 下拉（PG 模式）
    const sel = $("nas-select");
    const options = s.nas_options || [];
    sel.style.display = options.length ? "" : "none";
    const cur = sel.value;
    sel.innerHTML = '<option value="">本地引擎（numpy/BM25）</option>' +
      options.map(o =>
        `<option value="${esc(o.schema)}">${esc(o.label)}` +
        (o.resources != null ? `（${o.resources}）` : "") + "</option>").join("");
    if (cur && options.some(o => o.schema === cur)) sel.value = cur;
  } catch (e) { $("stats").textContent = "状态获取失败"; }
}

function selectedNas() {
  const sel = $("nas-select");
  return sel.style.display === "none" ? "" : sel.value;
}

async function doSearch() {
  const q = $("q").value.trim();
  const box = $("search-results");
  if (!q) return;
  box.innerHTML = '<div class="spinner">搜索中…</div>';
  const nas = selectedNas();
  try {
    const r = await fetch(`/api/search?q=${encodeURIComponent(q)}&top_k=10` +
      (nas ? `&nas=${encodeURIComponent(nas)}` : ""));
    const d = await r.json();
    if (d.error) { box.innerHTML = `<div class="error">${esc(d.error)}</div>`; return; }
    if (!d.hits.length) { box.innerHTML = '<div class="hint">没有匹配的描述。</div>'; return; }
    box.innerHTML = d.hits.map((h, i) => `
      <div class="hit">
        <div class="path">${i + 1}. ${esc(h.path)}</div>
        <div class="meta">
          <span class="kind">${esc(h.kind)}</span>
          <span>分数 ${Number(h.score).toFixed(3)}</span>
          <span>${esc(h.category || "未分类")}</span>
          ${h.stale ? '<span class="kind stale">⚠️ 可能已过期</span>' : ""}
          ${(h.tags || []).map(t => `<span class="kind">${esc(t)}</span>`).join("")}
        </div>
        ${h.summary ? `<div class="summary">${esc(h.summary)}</div>` : ""}
      </div>`).join("");
  } catch (e) { box.innerHTML = `<div class="error">请求失败: ${esc(e)}</div>`; }
}

async function doAsk() {
  const question = $("question").value.trim();
  const box = $("answer-area");
  if (!question) return;
  box.innerHTML = '<div class="spinner">检索并生成中（可能需 10~30 秒）…</div>';
  const nas = selectedNas();
  try {
    const r = await fetch("/api/ask", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: question, top_k: 5,
                            nas: nas || undefined})});
    const d = await r.json();
    if (d.error) { box.innerHTML = `<div class="error">${esc(d.error)}</div>`; return; }
    let html = `<div id="answer">${esc(d.answer)}</div>`;
    if (d.sources && d.sources.length) {
      html += '<div id="sources"><b>来源:</b>' +
        d.sources.map(s => `<div>${esc(s)}</div>`).join("") + "</div>";
    }
    box.innerHTML = html;
  } catch (e) { box.innerHTML = `<div class="error">请求失败: ${esc(e)}</div>`; }
}

$("search-btn").onclick = doSearch;
$("q").onkeydown = e => { if (e.key === "Enter") doSearch(); };
$("ask-btn").onclick = doAsk;
$("question").onkeydown = e => { if (e.key === "Enter") doAsk(); };
$("reload-btn").onclick = async () => {
  $("reload-btn").disabled = true;
  try {
    const r = await fetch("/api/reload", {method: "POST"});
    const d = await r.json();
    await refreshStats();
    if (!d.ok) alert(d.error || "刷新失败");
  } catch (e) { alert("刷新失败: " + e); }
  $("reload-btn").disabled = false;
};
refreshStats();
</script>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    """HTTP handler：所有状态来自 self.server.naskb_core。"""
    server_version = "NASKB/2"

    @property
    def core(self) -> KnowledgeCore:
        return self.server.naskb_core  # type: ignore[attr-defined]

    # ── 输出辅助 ──

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, code: int = 200) -> None:
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", code)

    def _read_json_body(self) -> Optional[dict]:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 1_000_000:
                return None
            return json.loads(self.rfile.read(n))
        except Exception:
            return None

    # ── 路由 ──

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path == "/":
            self._send(_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if u.path == "/api/stats":
            self._send_json(self.core.stats())
            return
        if u.path == "/api/search":
            qs = urllib.parse.parse_qs(u.query)
            query = (qs.get("q") or [""])[0].strip()
            if not query:
                self._send_json({"error": "缺少查询参数 q"}, 400)
                return
            try:
                top_k = max(1, min(int((qs.get("top_k") or ["10"])[0]), 100))
            except ValueError:
                top_k = 10
            nas = (qs.get("nas") or [""])[0].strip() or None
            engine, hits = self.core.search(query, top_k=top_k,
                                            nas_schema=nas)
            self._send_json({
                "query": query, "engine": engine,
                "hits": hits, "total_docs": self.core.stats()["docs"],
                "nas": nas,
            })
            return
        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path == "/api/ask":
            body = self._read_json_body() or {}
            question = str(body.get("question") or "").strip()
            if not question:
                self._send_json({"error": "缺少 question 字段"}, 400)
                return
            top_k = body.get("top_k") or 5
            try:
                top_k = max(1, min(int(top_k), 20))
            except (TypeError, ValueError):
                top_k = 5
            nas = str(body.get("nas") or "").strip() or None
            result = self.core.ask(question, top_k=top_k, nas_schema=nas)
            result["nas"] = nas
            self._send_json(result)
            return
        if u.path == "/api/reload":
            self._send_json(self.core.reload())
            return
        self._send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):  # 静默访问日志（可选调低噪音）
        pass


def serve(core: KnowledgeCore, host: str, port: int,
          open_browser: bool = False) -> None:
    """阻塞式启动服务（Ctrl+C 停止）。"""
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.naskb_core = core  # type: ignore[attr-defined]
    actual = httpd.server_address[1]
    url_host = host if host not in ("0.0.0.0", "::") else "127.0.0.1"
    print(f"[naskb] 知识库服务已启动: http://{url_host}:{actual}/"
          f"（引擎: {core.stats()['engine']}，{core.stats()['docs']} 条描述）")
    print("[naskb] Ctrl+C 停止服务")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(
            f"http://{url_host}:{actual}/")).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[naskb] 服务已停止")
    finally:
        httpd.server_close()
