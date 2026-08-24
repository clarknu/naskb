// 03 检索问答 —— 业务工作流数据文件
// 依据：design/01-raw-input/03-retrieval-qa.md（REQ-R2/R3/R4、ADR-20260811-1）
// 域注册表：03-retrieval-qa

window.WF_DATA = window.WF_DATA || {};
window.WF_DATA["03-retrieval-qa"] = {
  "domain": "03",
  "title": "检索问答",
  "slug": "retrieval-qa",
  "description": "摘要索引检索与 RAG 问答：双引擎自动选择（向量 → BM25），带来源问答（DeepSeek），两级引用（条款级见 04 域），空结果诚实兜底",
  "last_updated": "2026-08-24",

  // ── 权限控制点（唯一定义源）──
  "permissions": [
    { "id": "KbSearch", "name": "知识检索",   "desc": "允许执行语义/关键词检索", "category": "retrieval_qa", "section_refs": ["main-flow"] },
    { "id": "KbAsk",    "name": "知识问答",   "desc": "允许发起 RAG 问答（DeepSeek 生成，带来源）", "category": "retrieval_qa", "section_refs": ["main-flow"] },
    { "id": "KbStats",  "name": "统计查看",   "desc": "允许查看引擎/文档数/向量索引状态统计", "category": "retrieval_qa", "section_refs": ["rules"] }
  ],

  // ── 角色定义 ──
  // 2026-08-24 拍板（DD-009）：移除匿名只读——“必须都得是有我的身份的才可以”；
  // 权限点保留（=正式契约，多用户/角色走 R7-15 演进）。
  "roles": [
    { "id": "PlatformAdmin", "name": "平台管理员", "desc": "拥有检索问答全部权限与统计查看", "client_group": "Staff",
      "permission_ids": ["KbSearch","KbAsk","KbStats"] },
    { "id": "MCPAgent", "name": "MCP 消费方 Agent", "desc": "通过 kb_search/kb_ask/kb_get_doc/kb_fetch_file 检索知识", "client_group": "Agent",
      "permission_ids": ["KbSearch","KbAsk"] }
  ],

  "sections": [
    {
      "id": "overview",
      "title": "业务概述",
      "level": 1,
      "blocks": [
        { "type": "p", "text": "用户输入查询 → 语义向量检索（bge-small-zh-v1.5 ONNX，512 维）为主，BM25（k1=1.5, b=0.75）自动降级；PG pgvector（HNSW cosine）为多 NAS 增强层。" },
        { "type": "note", "level": "info", "text": "回退链：PG → numpy 向量 → BM25。降级不报错，仅提示引擎来源。" },
        { "type": "note", "level": "warning", "text": "索引只用摘要+描述（用户拍板，DD-007）：全文不参与向量/关键词检索，避免高频词稀释主题；全文保留为元数据，仅 RAG 生成阶段作为上下文。" }
      ]
    },
    {
      "id": "main-flow",
      "title": "主流程：检索与问答",
      "level": 2,
      "blocks": [
        { "type": "p", "text": "查询归一 → 引擎链判定 → 召回组装 → （问答）上下文拼装 + LLM 生成 + 来源列表。" }
      ],
      "flowchart": {
        "layout": "topdown",
        "nodes": [
          { "id": "start",    "type": "start",    "label": "流程开始" },
          { "id": "query",    "type": "action",   "label": "输入查询/问题", "inputs": ["query","top_k","nas"], "outputs": ["normalized_query"], "consumers": ["engine_choose"] },
          { "id": "engine_choose","type": "decision", "label": "引擎链：PG 可用？" },
          { "id": "pg_engine","type": "action",   "label": "pgvector 检索\n（多 NAS schema）", "inputs": ["normalized_query"], "outputs": ["hits"], "consumers": ["result"] },
          { "id": "vec_engine","type": "action",  "label": "本地向量检索\n（npz + numpy 余弦）", "inputs": ["normalized_query"], "outputs": ["hits"], "consumers": ["result"] },
          { "id": "bm25",     "type": "action",   "label": "BM25 降级\n（jieba 分词）", "inputs": ["normalized_query"], "outputs": ["hits"], "consumers": ["result"] },
          { "id": "result",   "type": "action",   "label": "结果组装\n（path/summary/tags/score/stale/nas）", "inputs": ["hits"], "outputs": ["hit_list"], "consumers": ["ask_decision"] },
          { "id": "ask_decision","type": "decision", "label": "是否需要生成回答？" },
          { "id": "rag",      "type": "action",   "label": "RAG 问答\n（top_k 召回 → 上下文 → DeepSeek 生成）", "inputs": ["hit_list","question"], "outputs": ["answer","sources"], "consumers": ["end"] },
          { "id": "end",      "type": "end",      "label": "流程结束" }
        ],
        "edges": [
          { "from": "start",        "to": "query" },
          { "from": "query",        "to": "engine_choose" },
          { "from": "engine_choose","to": "pg_engine", "label": "可用" },
          { "from": "engine_choose","to": "vec_engine", "label": "不可用" },
          { "from": "pg_engine",    "to": "result" },
          { "from": "vec_engine",   "to": "result" },
          { "from": "bm25",         "to": "result" },
          { "from": "result",       "to": "ask_decision" },
          { "from": "ask_decision", "to": "rag", "label": "是" },
          { "from": "ask_decision", "to": "end", "label": "否（纯检索）" },
          { "from": "rag",          "to": "end" }
        ]
      }
    },
    {
      "id": "rules",
      "title": "业务规则表",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["规则编号", "规则内容", "优先级", "说明"],
          "rows": [
            ["R001", "top_k 默认：检索 20 / 问答 5（可覆盖）", "中", "参数化"],
            ["R002", "无向量索引 → BM25 自动降级（不报错，引擎徽章提示）", "高", "回退链"],
            ["R003", "问答无命中必须诚实兜底（'未找到依据'），禁止编造", "高", "诚实性"],
            ["R004", "无 LLM 配置 → 问答返回明确错误", "高", "依赖检查"],
            ["R005", "stale 命中显示过期徽章（stale_vector/stale_source）", "中", "状态口径"],
            ["R006", "`/api/search` `/api/ask` 为后端抽象边界契约（ADR-20260816-2）", "高", "换实现不换接口"]
          ]
        }
      ]
    },
    {
      "id": "permissions-table",
      "title": "权限清单",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["权限点", "说明", "功能组"],
          "rows": [
            ["KbSearch", "知识检索", "检索问答"],
            ["KbAsk", "知识问答", "检索问答"],
            ["KbStats", "统计查看", "检索问答"]
          ]
        }
      ]
    }
  ]
};
