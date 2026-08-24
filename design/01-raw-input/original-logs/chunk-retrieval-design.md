# NASKB chunk 级检索增强设计（D' 方案详细设计）

> 版本: v0.1（设计已确认；❄️ 实施冻结中——**恢复工作请从 [deep-analysis-roadmap.md](./deep-analysis-roadmap.md) 进入**，
> 先按其 §10 落需求、§11 过 v3 对齐核查，再回到本文 §2.8 开工）
> 创建: 2026-08-23
> 定位: 回答「自研 chunk 增强（D'）能不能学到 MaxKB 的精华、补上八成差距」——结论：**能**，
>       本文把学到什么、怎么落到 NASKB 写成可实施方案。
> 依据: [requirement.md](./requirement.md)（REQ-R2 系列、REQ-R4、REQ-R3-04）、
>       [maxkb-integration-analysis.md](./maxkb-integration-analysis.md) §4-D'、
>       [pg-vector-multi-nas.md](./pg-vector-multi-nas.md)
> 设计参考: MaxKB v2 源码只读调研纪要（2026-08-23）。**法律边界：只学设计不搬代码**，
>           本文所有正则/SQL/伪代码均为自行编写；参数默认值属公开产品行为，不受版权保护。

---

## 0. 结论速览

1. **能学到什么**：MaxKB 在「段落级 RAG」上的工程答案基本都被我们读透了——标题树递归分段、
   三路可嵌入源（段落/标题/问题）、单表多源向量行 + 段级去重、jieba 预分词 tsvector +
   术语词典、加法混合检索（候选池 top×10 cap500、阈值后置）、字符预算上下文组装、文档级
   保真直返（阈值 0.9）、两种无命中兜底、FAQ 向量化加速重复问题。这些设计**全部可以合法
   借鉴并落地到我们的 PG 内核**。
2. **它没做的恰好是我们的机会**：MaxKB 的 chunk（`Paragraph.chunks` 数组，256 字符）只是
   展示/存储结构，**检索仍按段落整条召回，没有 chunk 级打分**；PDF 表格处理也是空白
   （pypdf 抽行会拍平大表）。而我们有 MinerU 结构化 Markdown（表格天然保留），做 chunk 级
   双层检索反而是超越它的部分。
3. **八成差距的账**：原判断「差距集中在 chunk 级精细 RAG」经源码核实成立。D' 落地后覆盖：
   条款级召回 ✓、表格进上下文 ✓、两级引用（文件+条款）✓、中文关键词通道 ✓、保真直返 ✓、
   诚实兜底 ✓。仍不覆盖（也不打算覆盖）：工作流编排、多用户权限、现成聊天界面——这三样
   正是将来「深度引擎独立实例」（路线 A）的触发条件，两者不冲突。
4. **成本**：全部落在现有栈内——PG 扩列 + 一段确定性分段器 + 检索 SQL 扩展 + serve/MCP
   组装改造。无新系统、无新依赖（jieba 一个纯 Python 包除外）、无许可证风险。

---

## 1. 从 MaxKB 学到的设计清单（证据索引）

| # | 设计点 | MaxKB 的做法（源码位置） | 采纳方式 |
|---|---|---|---|
| 1 | 标题树递归分段 | 6 条 ATX 标题正则逐级建树递归切块；先找第 i 级找不到自动降级；首标题前散文单独成块（common/utils/split_model.py） | 自行实现同思路；增加：结构化编号路径 |
| 2 | 代码块掩码 | 切分前把 ``` 围栏内容替换等长空格，防止代码里的 `#` 伪标题（split_model.py mask_code_blocks） | 采纳（MinerU md 含代码块时必要） |
| 3 | 超长块句末切分 | 窗口内从后向前找 。．！？句末点，至少保留窗口后半段（smart_split_paragraph） | 采纳 + 加 10-15% 重叠（MaxKB 无重叠，靠标题路径弥补；我们对跨页长条款加重叠，评测定去留） |
| 4 | 表格随块自带表头 | xlsx/csv 转 Markdown 管道表，超限落段时**新段重新拼表头**（xlsx_split_handle.py） | 采纳其「表头跟随」思想处理 MinerU 大表 |
| 5 | PDF 字号→标题映射 | 以字号众数为正文、+2pt→##、+0.5pt→###（pdf_split_handle.py） | 不需要（MinerU 已解决版面；且其 PDF 表格处理缺失正是我们强项） |
| 6 | 段落元数据最小化 | 仅 title=父链平铺 + content；DB 层 title≤256/content≤102400（knowledge/models/knowledge.py Paragraph） | 升级：title_path 结构化数组 + 平铺串前置拼入 content 提升召回（其 to_paragraph 思路） |
| 7 | 三路可嵌入源 | Embedding.source_type ∈ PROBLEM/PARAGRAPH/TITLE，同一张表参与统一召回（models/knowledge.py:308-358） | 采纳：vectors.kind ∈ summary/chunk/title/qa（qa 二期） |
| 8 | 单表多源 + 段级去重 | DISTINCT ON paragraph_id 取每段最高分——问题/标题向量命中直达所属段落（embedding_search.sql） | 采纳：DISTINCT ON (resource_id, chunk_key) 语义适配 |
| 9 | jieba 预分词 tsvector | 写入时 jieba 全模式切词→空格拼接→`'simple'` 配置 SearchVector；查询侧同款切词 websearch_to_tsquery（ts_vecto_util.py） | 采纳（这是 PG 中文全文通道能用的关键前提，我们 R5-05 混合检索同样需要） |
| 10 | 术语词典 | Termbase 按知识库存术语，作为 jieba 自定义词参与写入/查询双侧分词；Tokenizer 按词条缓存 1h（pg_vector._save/ts_vecto_util） | 采纳：per-schema 术语表，标准类文档必备（防「耐压强度」被切碎） |
| 11 | 加法混合检索 | blend 得分=(1-余弦距离)+ts_rank_cd(...,32)；候选池 LEAST(top_n*10,500)；阈值后置过滤；similarity 允许 0~2（blend_search.sql/i_search_knowledge_node.py） | 采纳公式与池策略；与我们原计划 RRF 并列为可选项，评测定默认 |
| 12 | per-库部分索引 | 多知识库时逐库查询以命中 `WHERE knowledge_id=?` 部分 HNSW 再归并（pg_vector.query 注释） | 印证我们 --nas all 决策；我们再加 `WHERE kind='chunk'` 部分索引 |
| 13 | 字符预算上下文 | `<data>标题:内容</data>` 换行连接，按 max_paragraph_char_number(5000) 顺序装入、末条可截断（base_generate_human_message_step.py） | 采纳成对标签+全局字符预算（替代按条数） |
| 14 | 保真直返 | Document.hit_handling_method∈{optimization,directly_return}+阈值 0.9；≥阈值只留最高分一条直接输出原文跳过 LLM（base_search_dataset_step/base_chat_step） | 采纳：per-深析目录开关，标准条款防改写 |
| 15 | 无命中兜底 | 仅两种：ai_questioning（裸问）/ designated_answer（模板话术不走 LLM）（application.py:290） | 采纳双模式；默认 designated（诚实性：明确说"库内未找到依据"） |
| 16 | FAQ 向量化 | LLM 按段落批量产相关问题，问题文本本身向量化入同表（source_type=PROBLEM），DISTINCT ON 直达段落=Q→A 缓存（task/generate.py/serializers/paragraph.py） | 二期采纳（先跑通主链路） |
| 17 | 问题补全 | problem_optimization 用最近 3 轮对话改写问题再检索（reset_problem_step） | 可选增强（serve 多轮场景） |
| 18 | 重排节点拓扑 | reranker 节点吃任意上游变量列表→合并打分→relevance_score 回写→预算截断（reranker_node） | 三期可选：接本地 bge-reranker，多路并行+汇聚重排 |
| 19 | 文档级标签路由 | search_document_node 用 jieba 匹配文档 tag 预筛检索范围（base_search_document_node.py） | 我们已有 category/tags/目录范围（REQ-R4-03），检索前路由天然可用 |
| 20 | 任务链路纪律 | 先删后建（delete_by_paragraph_id 再重建）；批内每 10 条 bulk_create；业务键幂等去重+状态位可取消（listener_manage.py/task/embedding.py） | 印证我们「chunk 行随资源整体重建」方案；sync 批量写按 ~50 行/批 executemany |
| 21 | 段落向量化文本 | 段落行的嵌入文本 = title + '\n' + content（list_embedding_text.sql），标题前置参与召回 | 印证我们 content_for_embedding=title_path 平铺+正文的决策 |
| 22 | 归一化与排序解耦 | 本地模型 normalize=True、API 模型不归一，检索统一 `<=>` 余弦排序不受影响（model/embedding/*） | 无需改我们现有 Embedder 归一化行为 |

**反向确认（MaxKB 没做、我们不学的）**：chunk 级打分（它只有段落级）、PDF 表格结构还原、
块间重叠、页眉页脚识别、RRF 融合（它用简单加法）、真·双路召回（它的 blend 关键词分只给
ANN 候选池加分，捞不回向量漏掉的文档——性能取舍，我们可选 UNION 变体补足）。

---

## 2. NASKB 落地设计

### 2.1 总体数据流

```
NAS 文件 ──analyze──► .naskb/artifacts/*.md (MinerU，已有)
                        │
                        ▼ (新增，确定性层，仅深析圈定目录)
                 md_chunker.py  标题树递归分段 → chunks[]
                   │   每个 chunk: {seq, title_path[], text, char_span}
                   ▼
                 pgstore.sync-vectors (扩展现有四操作)
                   │  vectors 表新增 kind='chunk'/'title' 行
                   │  + search_vector (jieba 预分词 tsvector)
                   ▼
                 pgsearch.PgSearchEngine (扩展三模式)
                   │  embedding / keywords / blend
                   ▼
                 serve /api/search /api/ask + MCP kb_* (契约不变，返回扩展)
```

原则对齐：事实源唯一（chunk 行是 `.naskb` 产物的派生，可重建）；接口契约不动
（ADR-20260816-2）；PG 不可用回退链不变（chunk 是 PG-only 增强，回退时自然消失，
剩余能力＝现状）。

### 2.2 Schema 扩展（pgstore DDL）

`vectors` 表扩列（沿用单表多源设计，学 MaxKB embedding 表）：

```sql
ALTER TABLE vectors ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'summary';
-- 'summary'=现有摘要行(不变) | 'chunk'=条款块 | 'title'=标题行(可选) | 'qa'=FAQ行(二期)
ALTER TABLE vectors ADD COLUMN IF NOT EXISTS chunk_seq INT;            -- 块序号
ALTER TABLE vectors ADD COLUMN IF NOT EXISTS title_path TEXT[];        -- 结构化标题路径
ALTER TABLE vectors ADD COLUMN IF NOT EXISTS search_vector tsvector;   -- jieba 预分词
CREATE INDEX IF NOT EXISTS vectors_chunk_hnsw ON vectors
  USING hnsw (vector vector_cosine_ops) WHERE kind = 'chunk';          -- 部分索引
CREATE INDEX IF NOT EXISTS vectors_chunk_tsv ON vectors USING gin (search_vector)
  WHERE kind IN ('chunk','title');
```

- **不变量保持核查**：REQ-R4-04「任何向量对应回一个 NAS 文件」——chunk 行 resource_id
  仍指文件 ✓；`summary_text`=被向量化文本（chunk 场景即块文本）✓；`full_text` 对 chunk 行
  存块全文（RAG 上下文用），父节上下文由相邻 chunk 行重组，不冗余存整节 ✓。
- 摘要行（kind='summary'）与现有行为完全一致；旧数据零迁移（DEFAULT 补齐）。
- **有意差异**：MaxKB 向量行不存正文（检索后按 paragraph_id 回查段落表）；我们让 chunk 行
  的 full_text 直接存块文本——单表取齐、免二次回查，与 R4「向量行四要素」既有设计一致
  （REQ-R4-04），代价是存储略增，量级可接受。
- **同步语义**：chunk 行随 resource 版本整体重建——sync 四操作判定资源变化时
  `DELETE WHERE resource_id=? AND kind<>'summary'` + 批量插入新 chunk 行；
  `source_hash` 记 MinerU md 的采样 hash（复用 ADR-20260816-4 规则）；
  状态机（stale_vector/stale_source）原样适用。
- 术语表（学 Termbase）：每 schema 一张 `termbase(term text primary key)`，
  config/管理命令维护；写入与查询分词双侧使用。

### 2.3 分段器（md_chunker.py，新模块 common/ 或 analyzer/）

> **2026-08-23 合成基准定稿**（`desc deep-bench`，自建结构/虚构数值，无需真实标准/人工标注）：
> 9 题固定问题集，条款级 recall@3 = recall@5 = **1.0**（摘要级只能整文件召回、无法到条款，
> 属结构性对照）；5 组参数扫描一致（合成文档条款较短、未触发超限切分），
> **推荐初始参数 target=800 / limit=1200 / overlap=0.12**（与 config 默认一致）。
> 真实标准/规范文档（条款更长、问题更模糊）可再跑 `desc deep-bench` 微调。

输入：`.naskb/artifacts/<file>.md`（MinerU 产物）。规则：

1. **预处理**：`\r\n|\r`→`\n`；删 `\0`；连续空行折叠为一行（学 MaxKB 清洗集，自行实现）。
2. **代码围栏掩码**：``` 围栏内容按行替换等长空格后再匹配标题，切完还原（防伪标题）。
3. **标题树递归切分**：ATX `#{1,6}` 六级各一条自写正则逐级扫描；某级无匹配自动降级；
   相邻同级标题之间为一个 block，block 内再用下一级切；首个标题前的前言单独成块。
4. **块大小**：目标 `target≈800` 字符、硬上限 `limit=1200`（初值，评测校准；
   参考 MaxKB 工作流默认 4096/UI 500——我们取中文条款密度折中）。超限块句末智能切分：
   窗口内从后向前找 `。！？!?；;` 断开，保证断后余量≥窗口一半。
5. **重叠**：句末切分的相邻块间携带上一块末尾约 12% 字符作前缀（标题树切断的块不加——
   标题路径本身就是上下文；此差异点用于评测对照）。
6. **表格处理**：md 管道表随所在块整体保留；单表超 limit 时按行累加切段，
   每个新段**重复表头行**（学 xlsx 处理器的表头跟随）。
7. **元数据**：每块产出 `{seq, title_path: ["第6章 试验方法","6.3 压力试验","6.3.2 ..."], text}`；
   入库时 `content_for_embedding = title_path平铺 + "\n" + text`（路径前置提升召回，
   to_paragraph 思路），`full_text` 存 text 原文。
8. **空段治理**：只有标题无内容的块丢弃；标题行另产出一条 kind='title' 短向量行
   （text=title_path 平铺，绑定后续第一个 chunk 的位置）——让「第6章试验方法」这类
   章节名查询可直接命中。
9. 幂等：同 md hash + 同分段配置版本（`chunker_version`，入 config）⇒ 产出相同；
   配置变更须升版触发重建（与 hash_algorithm 同纪律）。

### 2.4 检索扩展（pgsearch.py + SQL）

三模式（学 MaxKB 策略类，SQL 自行编写）：

| 模式 | 得分 | 说明 |
|---|---|---|
| embedding | `1 - (vector <=> q)` | 先行上线（最简） |
| keywords | `ts_rank_cd(search_vector, tsq, 32)`，需 `@@` 匹配 | 二期（BM25 本地引擎仍在，互不影响） |
| blend | `(1 - 余弦距离) + COALESCE(ts_rank_cd(...),0)` | 二期；similarity 阈值语义变为 0~2 |

公共骨架（所有模式一致）：

```sql
WITH cand AS (
  SELECT id, resource_id, chunk_seq,
         (vector::vector(:dim) <=> :qv) AS distance      -- 部分索引: kind='chunk'
  FROM vectors WHERE kind='chunk' AND model=:model AND ...
  ORDER BY distance LIMIT LEAST(:top_n * 10, 500)        -- 候选池
)
SELECT resource_id, chunk_seq,
       (1 - distance [+ ts_rank_cd(...)]) AS score
FROM ... GROUP BY resource_id, chunk_seq ...             -- 去重取最优
WHERE score > :min_score ORDER BY score DESC LIMIT :top_n -- 阈值后置
```

- 跨 NAS：沿用 R4 决策——每库 top-k 合并、分数不跨库比较（与 MaxKB per-库索引+归并同理）。
- **已知局限与对策**（源码核实所得）：MaxKB 的 blend 关键词分只作用于 ANN 候选池内，
  向量漏掉的关键词命中捞不回来。我们可选两种姿态：a) 接受同款取舍（实现简单，
  候选池 top×10 已提供缓冲）；b) UNION 变体——向量候选 ∪ FTS 候选各取 top_n 再统一
  打分排序（真双路，SQL 稍复杂）。默认 a，评测若见「关键词型问题漏召回」再切 b。
- 阈值位置：学 MaxKB 放最外层（实现简单）；若评测发现低阈值场景召回不足，
  可把距离条件前推进候选池子查询（`WHERE distance < 1-:min_score`）减少无效扫描。
- `--nas all` 与 kind 过滤组合：摘要行与 chunk 行各自出榜，serve 徽章区分「文档级/条款级」。
- reranker（三期可选）：bge-reranker-base ONNX 本地跑，拓扑=多路结果合并→重排→
  按 max_context_chars 截断。

### 2.5 问答组装（serve.py `/api/ask` 扩展）

1. 上下文模板（学成对标签+字符预算）：

```
已知信息（库内条款摘录）：
<data>第6章 试验方法 > 6.3 压力试验 > 6.3.2：{chunk 全文}</data>
<data>…</data>

要求：仅依据上述已知信息回答；引用时注明条款编号；已知信息不足以回答时明确说明。
问题：{question}
```

2. **字符预算** `max_context_chars=5000`（默认，可配）：顺序装入、末条截断。
3. **保真直返**：深析目录可开 `[deep] direct_return=true`（默认 false）、
   `direct_return_similarity=0.9`；开启时最高分 ≥ 阈值 ⇒ 直接返回该 chunk 原文 +
   出处，不调 LLM（标准条款防改写；DeepSeek 成本也省了）。
4. **无命中兜底**：`no_hit_mode`: `designated`（默认，返回固定诚实话术+
   「已尝试检索的范围」提示）/ `llm_fallback`（裸问模型，回答前缀声明“未依据库内文档”）。
5. **响应扩展**（向后兼容，纯新增字段）：`hits[]` 增加
   `{kind, title_path, chunk_seq, score}`；ask 的 `sources[]` 增加 `title_path`
   ——文件级来源字段原样保留，老前端不读新字段不受影响。
6. MCP `kb_search`/`kb_ask` 返回结构同步扩展；SKILL.md 更新调用示例。

### 2.6 深析范围圈定

config.toml：

```toml
[deep]
roots = ["D:\\docs\\standards", "/volume1/docs/specs"]   # 目录前缀圈定
enabled = true
chunker_version = 1
target_chars = 800
limit_chars = 1200
overlap_ratio = 0.12
direct_return = false
direct_return_similarity = 0.9
max_context_chars = 5000
top_n = 5
min_score = 0.6            # blend 时按 0~2 语义调整
no_hit_mode = "designated"
```

只对命中 roots 的文件产 chunk 行；其余文件维持纯摘要行——「轻量起步、按需升级」，
普通文档零开销。

### 2.7 与需求基线的边界修订（拟新 ADR 文字）

- **ADR-20260823-X（草案）**：REQ-R2-03「不做文档级 chunking」修订适用边界为
  「摘要索引层不做 chunking」；新增条款级第二层（kind='chunk'），仅限 `[deep].roots`
  圈定范围、仅 PG 后端、numpy 快照不含 chunk 行。ADR-20260811-1「全文不进索引」的
  防稀释初衷不受影响：进入索引的是条款级语义单元（非整文全文），且与摘要行分层并存、
  检索时可分开或合并出榜。

### 2.8 实施阶段与验收

| 阶段 | 内容 | 验收 |
|---|---|---|
| 1 分段与入库 | md_chunker + vectors 扩列 + sync 扩展 + termbase 表 | 单测：真实 MinerU md 分段快照测试；sync 后 chunk 行数=预期、二次同步 0 变化、改/删正确清理 |
| 2 检索与问答 | 三模式 SQL + search/ask 扩展 + 直返/兜底 + 引用两级 | 端到端：条款号提问命中正确 chunk；serve/MCP 展示 title_path；停 PG 回退正常 |
| 3 评测调参 | 固定问题集 20~30 条（条款级/表格级/章节级）前后对比；target/limit/overlap/min_score 校准 | 条款命中率与引用准确率显著优于纯摘要基线；误报率不升 |
| 4 收尾 | SKILL/README/requirement.md 修订落地 | 文档齐全 |

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| chunk 行放大存储（×几十倍向量数） | 仅深析目录启用；512 维 bge-small-zh 每 1k chunk ≈ 1MB 级，量级可控；部分索引减小膨胀 |
| 分段质量差拖垮召回 | 阶段 3 固定问题集评测先行；chunker_version 升版可全量重建（派生层可重建原则） |
| jieba 全模式切词噪声 | 术语表先行录入高频术语；对照 MaxKB 的占位符技巧（版本号/邮箱保真）按需自研简化版 |
| blend 分数量纲混搭难解释 | embedding 模式先上线保底；blend 作为增强，阈值独立配置 |
| GPL 血缘顾虑 | 本文设计均来自只读调研笔记；代码自行实现；正则/SQL 不抄原文；评审时对照检查 |

## 10. 变更历史

| 日期 | 变更 |
|---|---|
| 2026-08-23 | v0.1 创建：MaxKB 源码三路精读吸收清单（22 项设计点 + 反向确认）+ NASKB 落地设计（schema/分段/检索/问答/圈定/ADR 草案/实施阶段）；含 blend 局限与 UNION 变体、阈值前推优化、行内 full_text 有意差异说明 |
