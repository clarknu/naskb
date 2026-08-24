/**
 * REST 领域数据文件 — 深度分析（条款级）
 * 依据：server/app.py POST /api/kb/ask（direct_return 参数；两级引用；无命中兜底）
 */

window.API_DATA = window.API_DATA || {};
window.API_DATA["04-deep-analysis"] = {

  domain: "04",
  title: "深度分析（条款级）",
  slug: "deep-analysis",
  description: "条款级问答（两级引用/保真直返/无命中兜底）——唯一 REST 出口 /api/kb/ask",
  last_updated: "2026-08-24",
  workflow_ref: "../../02-business-workflow/data/04-deep-analysis.js",
  er_ref: "../../03-entity-relationship/data/04-deep-analysis.js",

  _permission_lookup: {
    "ChunkAsk": "条款级问答",
    "DeepConfigManage": "深析配置"
  },

  overview_blocks: [
    { type: "table", headers: ["子域", "核心实体", "说明"], rows: [
      ["条款问答", "Chunk / VectorRow(level=chunk)", "POST /api/kb/ask（两级引用）"],
      ["深析配置", "config [deep]", "roots/target_chars/limit_chars/overlap_ratio/direct_return*/no_hit_mode"],
      ["变更联动", "ReconcileDiff（01 域）", "来源 deep 开关 + /confirm 驱动 chunk 再建"]
    ]},
    { type: "note", level: "info", text: "条款级仅 PG 场景；无 PG/无默认 schema 时回退文档级——A'（P-003，2026-08-24）：显式要求条款级时回退必须带 level='summary' + note 提示（诚实性设计），不再静默。" }
  ],

  design_decisions: [
    { title: "条款问答独立于文档级", detail: "文档级 /api/ask 保持纯文档语义；条款级 /api/kb/ask 新增 level 语义与 direct_return 控制，避免一个端点两套行为" },
    { title: "保真直返优先", detail: "命中 ≥ direct_return_similarity（0.9）直接返回条款原文，防 LLM 改写（法律/规范类文档保真）" },
    { title: "A'：显式回退提示（P-003 拍板）", detail: "显式要求条款级（body.deep=true 或配置启用）却回退文档级 → 响应带 level='summary'+note；未显式要求（默认文档级）不加提示，避免打扰" }
  ],

  endpoints: [

    { id: "kb-ask", protocol: "rest", method: "POST", path: "/api/kb/ask", permission: "login_required",
      summary: "条款级问答（两级引用 + 保真直返）", scenario: "检索问答页『提问』（条款级语义）；MCP kb_ask 同构",
      description: "标题树检索（top_n/min_score）→ 两级引用（file + title_path）→ 保真直返或 LLM 生成；无命中按 no_hit_mode 兜底。A'（P-003）：显式要求条款级却回退文档级时响应必须带 level='summary' + note（回退要讲清楚）。",
      business_logic: {
        preconditions: ["（匿名时）命中匿名前缀；deep 配置可用"],
        steps: ["① 候选池召回（top×10 cap 500、阈值后置）", "② 相似度 ≥0.9 → 保真直返", "③ 否则 LLM 生成（两级引用）", "④ 无命中 → no_hit_mode 兜底"],
        post_effects: [],
        state_machine: "无",
        side_effects: ["LLM 调用（非直返时）"],
        related_apis: ["GET /api/kb/search — 文档级检索", "POST /api/ask — 文档级问答"]
      },
      body_params: [
        ["question","string","是","问题","非空","6.3.2 条怎么规定？"],
        ["top_k","int","否","召回条数","1-20","5"],
        ["sources","string[]","否","来源过滤","—","—"],
        ["deep","bool","否","显式要求条款级（A' 回退提示触发条件之一）","—","true"],
        ["direct_return","bool","否","是否允许保真直返","—","true"]
      ],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "answer": "按表 4 耐压要求…（条款原文）",\n  "level": "chunk",\n  "citations": [\n    { "path": "标准.pdf", "chunk_seq": 12, "title_path": ["3 技术要求", "3.2 耐压"], "score": 0.93 }\n  ],\n  "engine": "pg",\n  "hits": []\n}',
          fields: [["answer","text","回答/条款原文"],["level","enum","chunk|summary（A' 层级提示）"],["citations[].path","text","文件路径"],["citations[].chunk_seq","int","条款序号"],["citations[].title_path","text[]","标题路径"],["citations[].score","decimal","相似度"],["engine","enum","pg|vector|bm25"],["hits","array","命中明细（可选）"],["note","text","已回退文档级提示（level=summary 时）"]] }
      ],
      errors: [
        ["400","INVALID_PARAMETER (40001)","question 为空","—"],
        ["503","DEPENDENCY_ERROR (45001)","LLM 未配置/不可达（非直返路径）","—"],
        ["401","UNAUTHORIZED (41001)","认证开启且未命中匿名","口径差异见 _conventions.auth"]
      ],
      idempotency: { is_idempotent: false, method: "生成型接口", retry: "重复提问安全（无副作用）" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    }
  ]
};
