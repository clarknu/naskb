// 03 检索问答 —— 单域 ER 数据文件
// 依据：{schema}.vectors / {schema}.termbase DDL + 索引/检索事实基线
// 域注册表：03-retrieval-qa

window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["03-retrieval-qa"] = {
  "domain":      "03",
  "title":       "检索问答",
  "slug":        "retrieval-qa",
  "description": "向量库与检索标题：vectors 行（文档级 summary / 条款级 chunk，见 04 域）、术语表（jieba 词典）、检索/问答输出结构。",

  "enums": [
    { "id": "VectorLevel", "name": "向量层级", "description": "vectors.level：检索粒度",
      "values": [
        { "code": "summary", "zh": "文档级", "desc": "一文件一向量（摘要+描述）" },
        { "code": "chunk", "zh": "条款级", "desc": "标题树分段向量（REQ-R5-06，见 04 域）" },
        { "code": "title", "zh": "标题级", "desc": "标题行向量" }
      ] },
    { "id": "EngineKind", "name": "检索引擎", "description": "引擎链标识",
      "values": [
        { "code": "pg", "zh": "PG 向量库", "desc": "pgvector HNSW（多 NAS schema）" },
        { "code": "vector", "zh": "本地向量", "desc": "npz + numpy 余弦" },
        { "code": "bm25", "zh": "BM25", "desc": "降级引擎（k1=1.5,b=0.75）" }
      ] }
  ],

  "entities": [
    {
      "id": "vector_row",
      "name": "向量行",
      "table": "{schema}.vectors",
      "description": "向量库行（文档级/条款级按 level 区分；resource_id 级联删除）",
      "fields": [
        {"name": "vector_id", "type": "bigserial", "pk": true, "nn": true, "desc": "向量行 ID"},
        {"name": "resource_id", "type": "UUID", "pk": false, "nn": true, "fk": "resource.resource_id", "desc": "关联知识资源（级联删除，跨域）"},
        {"name": "model", "type": "text", "pk": false, "nn": true, "default": "bge-small-zh-v1.5", "desc": "嵌入模型"},
        {"name": "dim", "type": "integer", "pk": false, "nn": true, "default": "512", "desc": "维度"},
        {"name": "embedding", "type": "vector(512)", "pk": false, "nn": true, "desc": "向量（cosine）"},
        {"name": "summary_text", "type": "text", "pk": false, "nn": false, "desc": "索引文本（摘要+描述）"},
        {"name": "full_text", "type": "text", "pk": false, "nn": false, "desc": "RAG 上下文（含全文）"},
        {"name": "source_hash", "type": "text", "pk": false, "nn": false, "desc": "来源指纹（变更检测）"},
        {"name": "level", "type": "VectorLevel", "pk": false, "nn": true, "default": "summary", "desc": "层级（R5-06 扩展列）"},
        {"name": "chunk_seq", "type": "integer", "pk": false, "nn": false, "desc": "条款序号（level=chunk 必填）"},
        {"name": "title_path", "type": "text[]", "pk": false, "nn": false, "desc": "标题路径（两级引用）"},
        {"name": "search_vector", "type": "tsvector", "pk": false, "nn": false, "desc": "关键词混合检索（二期 blend）"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"},
        {"name": "updated_at", "type": "datetime", "pk": false, "nn": true, "desc": "更新时间"}
      ],
      "indexes": [
        {"fields": ["resource_id", "model"], "where": "level='summary'"},
        {"fields": ["resource_id", "model", "chunk_seq"], "where": "level='chunk'"},
        {"fields": ["embedding"], "using": "hnsw vector_cosine_ops"},
        {"fields": ["search_vector"], "using": "gin"}
      ]
    },
    {
      "id": "term_entry",
      "name": "术语表条目",
      "table": "{schema}.termbase",
      "description": "NAS 术语表（jieba 自定义词典，关键词通道二期）",
      "fields": [
        {"name": "term", "type": "text", "pk": true, "nn": true, "desc": "术语"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"}
      ]
    }
  ],

  "value_objects": [
    {
      "id": "hit",
      "name": "命中结果（VO）",
      "type": "vo",
      "description": "检索命中项（与 API 响应 hits[] 同构）",
      "fields": [
        {"name": "resource_id", "type": "UUID", "pk": false, "nn": false, "desc": "资源 ID"},
        {"name": "path", "type": "text", "pk": false, "nn": false, "desc": "相对路径"},
        {"name": "score", "type": "decimal", "pk": false, "nn": false, "desc": "相似度/相关度"},
        {"name": "summary", "type": "text", "pk": false, "nn": false, "desc": "摘要"},
        {"name": "category", "type": "text", "pk": false, "nn": false, "desc": "分类"},
        {"name": "tags", "type": "text[]", "pk": false, "nn": false, "desc": "标签"},
        {"name": "stale", "type": "boolean", "pk": false, "nn": false, "desc": "过期标记"},
        {"name": "nas", "type": "text", "pk": false, "nn": false, "desc": "NAS 别名"},
        {"name": "source_alias", "type": "text", "pk": false, "nn": false, "desc": "来源别名"},
        {"name": "kind", "type": "VectorLevel", "pk": false, "nn": false, "desc": "命中层级"},
        {"name": "chunk_seq", "type": "integer", "pk": false, "nn": false, "desc": "条款序号"},
        {"name": "title_path", "type": "text[]", "pk": false, "nn": false, "desc": "标题路径"}
      ]
    },
    {
      "id": "citation",
      "name": "回答引用（VO）",
      "type": "vo",
      "description": "RAG 回答来源引用（两级：文件+条款）",
      "fields": [
        {"name": "path", "type": "text", "pk": false, "nn": true, "desc": "文件路径"},
        {"name": "chunk_seq", "type": "integer", "pk": false, "nn": false, "desc": "条款序号"},
        {"name": "title_path", "type": "text[]", "pk": false, "nn": false, "desc": "标题路径"},
        {"name": "score", "type": "decimal", "pk": false, "nn": false, "desc": "相似度"}
      ]
    }
  ],

  "services": [
    { "id": "embedder", "name": "嵌入器",
      "description": "bge-small-zh-v1.5 ONNX 本地推理（512 维）",
      "methods": [
        {"name": "embed", "sig": "(text[]) → ndarray", "desc": "批嵌入（_BATCH=64）"},
        {"name": "available", "sig": "() → bool", "desc": "模型就绪（自动下载 ~24MB）"}
      ] },
    { "id": "retrieval_service", "name": "检索服务",
      "description": "引擎链调度（PG → 本地 → BM25）",
      "methods": [
        {"name": "search", "sig": "(query, top_k, nas?) → Hit[]", "desc": "语义检索"},
        {"name": "bm25_search", "sig": "(query, top_k) → Hit[]", "desc": "关键词降级"},
        {"name": "engine_chain", "sig": "(query) → EngineKind", "desc": "引擎判定"}
      ] },
    { "id": "qa_service", "name": "问答服务",
      "description": "RAG 生成（DeepSeek，带来源；无命中诚实兜底）",
      "methods": [
        {"name": "answer", "sig": "(question, top_k) → {answer, sources}", "desc": "文档级问答"},
        {"name": "answer_deep", "sig": "(question, top_k, direct_return) → {answer, citations}", "desc": "条款级问答（两级引用，见 04 域）"}
      ] }
  ],

  "relations": [
    {"from": "vector_row.resource_id", "to": "resource.resource_id", "type": "N:1", "desc": "向量行归属资源（级联删除）", "cross_domain": "02"}
  ]
};
