# 深度分析（条款级）

> 文档 ID: REQ-deep-analysis | 最后更新：2026-08-24 | 从 4 个存量文档整合（original-logs/）
> 本文档为整合后的当前设计结论。原始讨论记录见 `original-logs/`。

## 一、核心决策

> **[REQ-R5-06]** 条款级精细问答：标准/规范/研发类文档需要"6.3.2 条怎么规定"级问答时启用——摘要级检索（文档级）保持默认，深度分析在圈定目录上叠加**条款级第二层**（chunk 向量行）。

> **[ADR-20260823-1]** 深析主线 = 自研增强（D'）；MaxKB 社区版/RAGFlow/FastGPT 仅远期可插拔（路线 A，Backend B 同契约）。

> **[REQ-R5-06]** 分段参数（`[deep]`）：`target_chars=800` / `limit_chars=1200` / `overlap_ratio=0.12`（句末智能切分+12% 重叠；表格随块重复表头；代码围栏掩码；空段治理；ATX 六级标题树递归）。

> **[REQ-R5-06]** 两级引用：问答可引用到「文件 + 章节 title_path」两级；响应新增 hits[]{kind:'chunk'|'title', chunk_seq, title_path, score}。

> **[REQ-R5-06]** 保真直返：命中相似度 ≥ `direct_return_similarity`（0.9）直接返回条款原文不调 LLM（防改写）；`no_hit_mode`（designated | llm_fallback）——无命中默认"未找到依据"（诚实性）。

> **[REQ-R5-06 系统级]** 来源开关（`SourceRecord.deep`）→ 扫描/分析/定时自动建条款级 chunk 行；只读源用暂存 md（钩子挂在 sync_vectors 之后、cleanup_artifacts 之前），中间产物不留存。

## 二、详细设计

### 2.1 条款级链路

1. 圈定：`[deep] enabled=true` + `roots`（目录圈定）；或按来源 deep 开关。
2. 解析：MinerU（PDF/DOCX/PPTX/XLSX → md/html/middle.json/images；快速路径 PyMuPDF+30% 文本阈值）。
3. 分段：md_chunker 标题树递归（段 = {seq, title_path, text, start, end}）；content_for_embedding = title_path + 正文；chunker_version 幂等。
4. 入库：vectors 扩展列（kind='chunk'/'title'、chunk_seq、title_path、search_vector；HNSW/GIN 部分索引）。
5. 检索：embedding 先行（候选池 top×10 cap 500、阈值后置）；blend 检索二期。
6. 问答：两级引用 + 保真直返 + 无命中兜底；`/api/kb/ask`（direct_return 参数）。

### 2.2 关键业务规则

- 变更确认清单（来源页 /changes + /confirm）驱动深析再建 chunk（只读源用暂存 md）。
- 条款级仅 PG 场景（无 PG 回退文档级）；`kb_ask.deep` 无 nas/默认 schema 时静默回退文档级（见 design-code-gap）。
- `sync-chunks`（CLI）与系统级深析共用同一 chunker（deep/desc_store 分层）。

### 2.3 与下游的关系

- ER：Chunk（seq/title_path/text/start/end）、ChunkVector（kind/chunk_seq/title_path）——见 04-deep-analysis.js。
- API：`/api/kb/ask`（deep 相关参数）——见 04/rest/04。
- 同源接口：`POST /api/ask`（文档级）、`/api/kb/search`（文档级）。

## 三、仍待决策

- ⚠️ 待定：真实标准文档（20-30 条）人工验证未做（当前用合成基准 9 题：recall@3/@5=100%）；Roadmap 后续阶段 2-4（分级检索 R5-01/03/04/07）。
- ⚠️ 待定：`kind`（列）vs `level`（参数）术语统一。

## 四、来源索引

| 原始文件 | 主要贡献内容 |
|---------|-------------|
| chunk-retrieval-design.md | 分段/向量/两级引用/检索三模式 |
| deep-ingestion-system-flow.md | 系统级深析落地流程（变更确认、暂存 md） |
| deep-analysis-roadmap.md | D' 拍板、阶段划分、合成基准 |
| maxkb-integration-analysis.md | 远期路线 A 与许可分析 |
