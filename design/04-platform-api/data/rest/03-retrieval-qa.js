/**
 * REST 领域数据文件 — 检索问答
 * 依据：server/app.py 实际注册（/api/kb/search、/api/search、/api/ask、/api/reload、/api/stats、/api/pg/rebind）
 */

window.API_DATA = window.API_DATA || {};
window.API_DATA["03-retrieval-qa"] = {

  domain: "03",
  title: "检索问答",
  slug: "retrieval-qa",
  description: "摘要索引双引擎检索、RAG 问答（带来源）、统计与向量库管理",
  last_updated: "2026-08-24",
  workflow_ref: "../../02-business-workflow/data/03-retrieval-qa.js",
  er_ref: "../../03-entity-relationship/data/03-retrieval-qa.js",

  _permission_lookup: {
    "KbSearch": "知识检索",
    "KbAsk": "知识问答",
    "KbStats": "统计查看"
  },

  overview_blocks: [
    { type: "table", headers: ["子域", "核心实体", "说明"], rows: [
      ["文档级检索", "VectorRow (level=summary)", "/api/kb/search 主入口（PG→向量→BM25 引擎链）"],
      ["RAG 问答", "Hit / Citation", "/api/ask（抽象边界契约）+ DeepSeek 生成"],
      ["遗留契约", "serve 模式", "/api/search /api/ask /api/reload 保留（ADR-20260816-2 换实现不换接口）"],
      ["向量库管理", "NasReg / VectorRow", "/api/pg/rebind 重新绑定 NAS schema"]
    ]},
    { type: "note", level: "info", text: "索引文本只用摘要+描述（DD-007）；全文仅作为 RAG 上下文。" }
  ],

  design_decisions: [
    { title: "引擎链显式返回", detail: "响应带 engine 字段（pg/vector/bm25），前端展示与降级提示据此渲染" },
    { title: "legacy 契约保留", detail: "/api/search /api/ask /api/reload 与 serve 保持同构，避免外部调用方（MCP/历史脚本）断裂" }
  ],

  endpoints: [

    // ── GET 文档级检索 ──
    { id: "kb-search", protocol: "rest", method: "GET", path: "/api/kb/search", permission: "login_required",
      summary: "文档级语义/关键词检索", scenario: "检索问答页『检索』（Web UI 主入口）",
      description: "query 归一 → 引擎链（PG→本地向量→BM25）→ hits[]（含 score/stale/nas/source_alias；条款级命中含 kind/chunk_seq/title_path）。",
      business_logic: {
        preconditions: ["（匿名时）命中匿名前缀；检索前置：索引已建（无索引自动 BM25）"],
        steps: ["① query 预处理与嵌入", "② 引擎链判定与召回", "③ 组装 hits（含 stale 徽章数据）"],
        post_effects: [],
        state_machine: "无状态变更",
        side_effects: [],
        related_apis: ["POST /api/kb/ask — 条款级问答（04 域）", "POST /api/ask — 文档级问答"]
      },
      query_params: [
        ["query","string","是","查询词","非空","出行要带的证件"],
        ["top_k","int","否","返回条数","1-100","20"],
        ["sources","string[]","否","来源过滤","—","—"],
        ["dir","string","否","目录过滤","rel_path","docs/合同"]
      ],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "engine": "vector",\n  "hits": [\n    {\n      "resource_id": "uuid",\n      "path": "docs/合同.pdf",\n      "score": 0.83,\n      "summary": "…",\n      "category": "合同",\n      "tags": ["租赁"],\n      "stale": false,\n      "nas": "home-nas",\n      "source_alias": "home-nas-docs"\n    }\n  ]\n}',
          fields: [["engine","enum","pg|vector|bm25"],["hits[].resource_id","UUID","资源 ID"],["hits[].path","text","相对路径"],["hits[].score","decimal","相似度"],["hits[].summary","text","摘要"],["hits[].category","text","分类"],["hits[].tags","text[]","标签"],["hits[].stale","bool","过期标记"],["hits[].nas","text","NAS 别名"],["hits[].source_alias","text","来源别名"]] }
      ],
      errors: [
        ["400","INVALID_PARAMETER (40001)","query 为空","—"],
        ["401","UNAUTHORIZED (41001)","认证开启且未命中匿名","口径差异见 _conventions.auth"],
        ["500","INTERNAL_ERROR (50001)","检索异常","—"]
      ],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "HTTP 缓存（演进）", ttl: "—", note: "当前 no-store" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── POST 文档级问答 ──
    { id: "ask", protocol: "rest", method: "POST", path: "/api/ask", permission: "login_required",
      summary: "RAG 问答（文档级，抽象边界契约）", scenario: "检索问答页『提问』；CLI desc ask 同构",
      description: "top_k 召回（摘要+上下文）→ DeepSeek 生成 → 带 sources；无 LLM 配置 → 明确错误。",
      business_logic: {
        preconditions: ["（匿名时）命中匿名前缀；LLM 已配置"],
        steps: ["① 召回 top_k", "② 拼装上下文（summary + 相关全文段）", "③ DeepSeek 生成 + 来源"],
        post_effects: [],
        state_machine: "无状态变更",
        side_effects: ["LLM 调用计费"],
        related_apis: ["GET /api/kb/search — 检索", "POST /api/kb/ask — 条款级（04 域）"]
      },
      body_params: [
        ["question","string","是","问题","非空","月租金是多少？"],
        ["top_k","int","否","召回条数","1-20","5"],
        ["nas","string","否","NAS 过滤","—","home-nas"]
      ],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "answer": "月租金为 3,200 元…",\n  "sources": ["docs/合同.pdf"],\n  "engine": "vector"\n}',
          fields: [["answer","text","回答"],["sources","string[]","来源路径"],["engine","enum","引擎"]] }
      ],
      errors: [
        ["400","INVALID_PARAMETER (40001)","question 为空","—"],
        ["503","DEPENDENCY_ERROR (45001)","LLM 未配置/不可达","外部依赖缺失，诚实报错"],
        ["401","UNAUTHORIZED (41001)","认证开启且未命中匿名","口径差异见 _conventions.auth"]
      ],
      idempotency: { is_idempotent: false, method: "生成型接口（结果可不同）", retry: "重复提问安全（无副作用）" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项（LLM 成本控制）" }
    },

    // ── GET legacy search ──
    { id: "legacy-search", protocol: "rest", method: "GET", path: "/api/search", permission: "login_required",
      summary: "检索（legacy serve 契约）", scenario: "旧版内置问答服务调用方",
      description: "与 /api/kb/search 语义同构（engine/hits/total_docs），保留兼容。",
      business_logic: {
        preconditions: ["同 kb-search"],
        steps: ["① 引擎链召回", "② 同构输出（total_docs）"],
        post_effects: [],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/kb/search"]
      },
      query_params: [["q","string","是","查询词","—","出行要带的证件"],["top_k","int","否","条数","—","10"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "engine": "bm25",\n  "hits": [],\n  "total_docs": 0\n}',
          fields: [["engine","enum","引擎"],["hits","array","命中"],["total_docs","int","文档总数"]] }
      ],
      errors: [["400","INVALID_PARAMETER (40001)","q 为空","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "—" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── POST legacy reload ──
    { id: "legacy-reload", protocol: "rest", method: "POST", path: "/api/reload", permission: "KbStats",
      summary: "热刷新描述数据（legacy serve 契约）", scenario: "CLI analyze 后刷新 serve 数据",
      description: "重新加载描述集合（增量变更后调用）。",
      business_logic: {
        preconditions: ["已认证"],
        steps: ["① 重扫描述集合", "② 刷新索引上下文"],
        post_effects: ["检索/问答上下文更新"],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/kb/search"]
      },
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "ok": true\n}', fields: [["ok","bool","是否成功"]] }
      ],
      errors: [["401","UNAUTHORIZED (41001)","未认证","—"]],
      idempotency: { is_idempotent: true, method: "重加载幂等", retry: "可重试" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 统计 ──
    { id: "stats", protocol: "rest", method: "GET", path: "/api/stats", permission: "login_required",
      summary: "平台统计（引擎/文档数/索引状态）", scenario: "状态展示/运维查看",
      description: "返回引擎可用性、文档数、向量索引状态（editable 指标）。",
      business_logic: {
        preconditions: [],
        steps: ["① 聚合计数", "② 引擎可用性探测"],
        post_effects: [],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/config/public"]
      },
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "engine": "vector",\n  "docs": 120,\n  "vector_index": "ready"\n}',
          fields: [["engine","enum","当前引擎"],["docs","int","文档数"],["vector_index","string","索引状态"]] }
      ],
      errors: [],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "实时" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── POST rebind ──
    { id: "pg-rebind", protocol: "rest", method: "POST", path: "/api/pg/rebind", permission: "KbStats",
      summary: "PG 向量重绑定（多 NAS）", scenario: "PG 迁移/重建后重新绑定",
      description: "把既有向量按 NAS 五要素重绑定到新 schema（RebindIn：nas alias 等）。",
      business_logic: {
        preconditions: ["已认证", "PG 已配置"],
        steps: ["① 解析 nas 身份", "② 迁移/重绑定 vector 行", "③ 返回统计"],
        post_effects: ["schema 归属变化"],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/stats"]
      },
      body_params: [["nas","string","否","NAS alias","—","home-nas"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "ok": true,\n  "rebound": 0\n}', fields: [["ok","bool","成功"],["rebound","int","重绑定行数"]] }
      ],
      errors: [["503","DEPENDENCY_UNAVAILABLE (45001)","PG 不可达","—"]],
      idempotency: { is_idempotent: true, method: "重绑定幂等", retry: "可重试" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    }
  ]
};
