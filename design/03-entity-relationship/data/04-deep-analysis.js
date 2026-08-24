// 04 深度分析 —— 单域 ER 数据文件
// 依据：REQ-R5-06 条款级链路（md_chunker / vectors level=chunk / 两级引用）
// 域注册表：04-deep-analysis（向量行实体归 03 域，本节引用不重复定义）

window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["04-deep-analysis"] = {
  "domain":      "04",
  "title":       "深度分析（条款级）",
  "slug":        "deep-analysis",
  "description": "条款级分析的领域模型：MinerU 结构化 md → 标题树分段（chunk VO）→ 条款级向量行（引用 03 域 vector_row）→ 两级引用问答。不持新表；复用 02 域 artifacts 与 03 域 vectors。",

  "enums": [
    { "id": "DeepMode", "name": "深析模式", "description": "条款级问答的触发/降级模式",
      "values": [
        { "code": "deep", "zh": "条款级", "desc": "两级引用 + chunk 向量行" },
        { "code": "summary", "zh": "文档级", "desc": "无 PG/无深析配置时回退" }
      ] },
    { "id": "NoHitMode", "name": "无命中模式", "description": "条款级问答无命中时的兜底",
      "values": [
        { "code": "designated", "zh": "诚实兜底", "desc": "明确回答'未找到依据'（默认）" },
        { "code": "llm_fallback", "zh": "LLM 兜底", "desc": "基于上下文 LLM 归纳" }
      ] }
  ],

  "entities": [],

  "value_objects": [
    {
      "id": "chunk",
      "name": "条款分段（VO）",
      "type": "vo",
      "description": "md_chunker 输出：标题树递归分段结果",
      "fields": [
        {"name": "seq", "type": "integer", "pk": false, "nn": true, "desc": "段序号（chunk_seq）"},
        {"name": "title_path", "type": "text[]", "pk": false, "nn": true, "desc": "标题路径（ATX 六级）"},
        {"name": "text", "type": "text", "pk": false, "nn": true, "desc": "段正文"},
        {"name": "start", "type": "integer", "pk": false, "nn": false, "desc": "起始偏移"},
        {"name": "end", "type": "integer", "pk": false, "nn": false, "desc": "结束偏移"},
        {"name": "content_for_embedding", "type": "text", "pk": false, "nn": false, "desc": "title_path + 正文"}
      ]
    },
    {
      "id": "mineru_md",
      "name": "MinerU 结构化 md（VO）",
      "type": "vo",
      "description": "MinerU 解析产物（.naskb/artifacts/*.md；快速路径 PyMuPDF+30% 文本阈值）",
      "fields": [
        {"name": "md_abs", "type": "text", "pk": false, "nn": true, "desc": "md 绝对路径"},
        {"name": "html_path", "type": "text", "pk": false, "nn": false, "desc": "HTML 预览路径"},
        {"name": "source", "type": "text", "pk": false, "nn": false, "desc": "persistent|staging（只读源暂存）"},
        {"name": "chunker_version", "type": "text", "pk": false, "nn": false, "desc": "分段器版本（幂等键）"}
      ]
    }
  ],

  "services": [
    { "id": "md_chunker", "name": "标题树分段器",
      "description": "条款级分段（recommend：target=800/limit=1200/overlap=0.12）",
      "methods": [
        {"name": "split", "sig": "(md_text, params) → Chunk[]", "desc": "标题树递归分段"},
        {"name": "table_passthrough", "sig": "(block) → text", "desc": "表格随块重复表头"}
      ] },
    { "id": "deep_retrieval", "name": "条款级检索",
      "description": "embedding 先行（候选池 top×10 cap 500、阈值后置）；blend 二期",
      "methods": [
        {"name": "search_chunks", "sig": "(query, top_n, min_score) → hit[]", "desc": "条款级召回"},
        {"name": "build_answer", "sig": "(hits, question, no_hit_mode) → {answer, citations}", "desc": "两级引用生成"}
      ] }
  ],

  "relations": [
    {"from": "vector_row.resource_id", "to": "resource.resource_id", "type": "N:1", "desc": "条款级向量行同样归属资源（跨域引用 02/03，不重复定义）", "cross_domain": "03"}
  ]
};
