# 检索问答

> 文档 ID: REQ-retrieval-qa | 最后更新：2026-08-24 | 从 3 个存量文档整合（original-logs/）
> 本文档为整合后的当前设计结论。原始讨论记录见 `original-logs/`。

## 一、核心决策

> **[REQ-R2]** 检索只用文件的摘要+描述（用户拍板，DD-007）：全文不参与向量/关键词检索，避免高频词稀释主题；全文（ocr_text 等）保留为元数据，仅 RAG 生成阶段作为上下文。

> **[REQ-R2]** 双引擎自动选择：语义向量（bge-small-zh-v1.5 ONNX，512 维，numpy 余弦，索引 db/vectors.npz+json）为主，BM25（k1=1.5, b=0.75）自动降级；PG pgvector（HNSW, cosine）为多 NAS 增强层。

> **[REQ-R4]** 回退链：PG → numpy → BM25（PG down 自动回退；降级不报错，仅提示引擎）。

> **[R3]** 内置问答服务契约 = 后端抽象边界：`GET /api/search`、`POST /api/ask`（换实现不换接口；MaxKB 远期可插拔）。

> **[R3]** RAG 问答：召回 top-k → DeepSeek 生成，带来源（sources）；无 LLM → 明确错误兜底；诚实性优先于编造。

> **[REQ-R5-06 两级引用]** 条款级问答输出 citations{path, chunk_seq, title_path, score}（文件+条款两级，见 04 域）。

## 二、详细设计

### 2.1 检索管线

1. 查询归一（query → 嵌入：onnxruntime 本地推理）。
2. 引擎链判定：PG 可用且命中 → pgvector；否则本地向量索引（npz）；否则 BM25（jieba 分词）。
3. 结果组装：hits[]{resource_id/rid, path, rel_path, summary, tags, category, score, stale, nas/source_alias, chunk 级字段}。
4. 问答：top_k 召回 → 上下文拼装（摘要 + 相关全文段）→ DeepSeek 生成 → 来源列表。

### 2.2 关键业务规则

- `top_k` 默认 5（问答）/ 20（检索，可配）；`nas`/`sources` 过滤（多 NAS 下拉）。
- 索引陈旧提示：`sync-status`（只读一致性报告）/ `pg-status`（已注册 NAS 统计）。
- 术语表：jieba 自定义词典，关键词通道二期启用。

### 2.3 与下游的关系

- ER：VectorRow（vectors 表：vector512/summary_text/full_text/resource_id/source_hash/level）、TermEntry（termbase 表）、Doc（摘要/上下文结构）——见 03-retrieval-qa.js。
- API：`/api/kb/search`、`/api/ask`、`/api/stats`、`/api/search`（遗留契约）——见 04/rest/03。
- MCP：kb_search/kb_ask（ai-tools）。

## 三、仍待决策

- ⚠️ 待定：`/api/ask` 与 `/api/kb/ask` 的匿名/认证口径不一致（见 design-code-gap）。
- ✅ 已实现（2026-08-24）：R5-05 混合检索（**opt-in**）——PG tsvector 关键词通道（CJK N-gram 预分词）+ 向量 top-k RRF 融合，engine=pg-hybrid；开启方式 `/api/kb/search?hybrid=1` / CLI `--hybrid`（细节见 DD-010；原草案 blend 公式未采用，见决策 rationale）。

## 四、来源索引

| 原始文件 | 主要贡献内容 |
|---------|-------------|
| requirement.md | R2/R3/R4 检索问答需求组 |
| pg-vector-multi-nas.md | 回退链、四要素向量 |
| agent-interface-design.md | 四出口同源（/api/search /api/ask 契约） |
