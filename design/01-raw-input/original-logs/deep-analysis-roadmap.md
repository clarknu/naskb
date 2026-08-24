# 深度分析能力整合路线图（研讨固化 · 交接文档）

> 版本: v1.0（方向已获用户认可，实施冻结待恢复）
> 固化日期: 2026-08-23
> 性质: 本文是 2026-08-23「MaxKB 整合 / 深度分析」专题研讨的**全部结论固化**。
>       用户指示：因另一线程正在对 NASKB 做平台化全量升级（见 platform-v3-design.md），
>       现在不改代码；**平台升级完成后，凭本文档恢复并继续本专题工作**。
> 支撑文档: [maxkb-integration-analysis.md](./maxkb-integration-analysis.md)（整合分析与法律边界详版）、
>           [chunk-retrieval-design.md](./chunk-retrieval-design.md)（D' 方案详细设计）
> 关系说明: 三份文档分工——本文=结论与路线（自足）；integration-analysis=论证过程与证据；
>           chunk-retrieval-design=可直接实施的工程细节。冲突时以本文的方向性结论为准。

---

## 0. 一页速览（恢复时先读这里）

1. **目标**：让 NASKB 具备「项目/研发文档、行业/实施标准类文档」的**条款级精细问答**能力
   （答案引用到「文件 + 条款」两级），不必购买 MaxKB 专业版，不引入重型外部系统。
2. **已定方向**：
   - **主线（近期做）＝ D‘ 自研 chunk 级检索增强**——利用现有 MinerU Markdown 产物 +
     PG(pgvector) 内核加条款级第二层检索。源码级评估确认可行且值得做；
     详细设计已成稿（chunk-retrieval-design.md），**待需求基线修订后即可开工**。
   - **远期可选 ＝ 路线 A 深度引擎独立实例**——MaxKB 社区版 / RAGFlow / FastGPT 三选一，
     经「同契约适配器」接入（REQ-R5-01/03/04）。触发条件：深析文档上百份 /
     多人共用 / 需工作流编排 / 要现成界面。届时重新选型，不锁定 MaxKB。
   - 备胎 C（fork 补管理 API）、赠品 B（页面嵌入）、禁止项（搬 GPL 代码、绕企业授权）。
3. **两个被纠正的关键前提**（详见 §4）：MaxKB 社区版**对话 API 本来就开放**；
   管理 API 代码就在开源实例里（直调可行、自担版本风险）；「API 收费」是 MaxKB 特有问题，
   RAGFlow/FastGPT/AnythingLLM 开源版 API 全部免费。
4. **当前状态**：❄️ 实施冻结（等待 v3 平台化线程完成）。恢复时按 §10 清单先改 requirement.md，
   再按 §9 阶段 1 开工，并先过一遍 §11 的 v3 对齐核查。

---

## 1. 背景与问题缘起

NASKB v2 现有检索模型是「文件发现模型」（ADR-20260811-1）：索引只用 AI 摘要+描述、
一文件一向量、全文只作生成上下文。这对「找文件」很好，但对标准/规范类文档的
**条款级问题**（“6.3.2 条怎么规定”“表 4 里耐压要求是多少”）召回粒度太粗。

原计划引入 MaxKB 补这块（REQ-R5 系列），但顾虑其「API 输入输出需企业版」。
本轮研讨依次完成：事实核查 → 法律边界分析 → 五条整合路线评估 → 替代品横评 →
MaxKB v2 源码三路精读 → D' 自研方案设计与可行性确认 → **用户认可方向，固化为本文**。

### 差距的准确定义（经源码核实维持原判断）

| 目标文档特征 | 要求 | 现状缺口 |
|---|---|---|
| 条款编号体系（章/节/条） | 标题层级分块，块内带条款上下文 | 无 chunking（REQ-R2-03） |
| 大量表格 | 表格结构随块进上下文 | MinerU 有产物，未到检索层 |
| 扫描件 | OCR 后同样分块 | 解析已解决，缺分块入库 |
| 跨页长条款 | 块重叠 / 父子块上下文 | 无 |
| 精确出处 | 引用到「文件+条款」两级 | sources 只到文件路径 |

差距集中在 **chunk 级精细 RAG** 一段；文件管理/OCR/多模态恰是 NASKB 强项
（MinerU 全格式、MiMo 图音、音视频分级——即 ADR-20260816-1 所言「MaxKB 短板恰是 NASKB 已做的部分」）。

---

## 2. 我们要做的事（一句话）

> 在 NASKB 现有 PG 向量内核上加「条款级第二层检索」（D' 方案），把标准/规范类文档的
> 问答精度提升到条款级并给出两级引用；同时保留向「独立深度引擎」（MaxKB/RAGFlow 等）
> 平滑升级的接口与触发条件，不在本轮实施任何外部系统集成。

范围边界：
- ✅ 本轮范围：chunk 分段器、PG schema 扩展、三模式检索、问答组装改造（直返/兜底/两级引用）、
  深析目录圈定机制、固定问题集评测。
- ❌ 本轮不做（也非本专题范围）：任何外部系统部署/集成；v3 平台化本身的工作；
  多用户/权限/工作流编排（留给路线 A 触发后的选型）。

---

## 3. 遵循的原则

继承 requirement.md §4 四条架构原则（全文有效）：

1. **确定性层与 AI 编排层分离**——分段/入库/检索是确定性代码；柔性判断才交给 LLM。
2. **内容处理层是长期资产**——`.naskb` 描述仓库与 MinerU 产物不变不重做，后端可插拔。
3. **事实源唯一**——NAS 文件→`.naskb` 快照→PG 行的派生链不变；chunk 行同样可随时重建。
4. **轻量起步、按需升级**——每步升级有明确触发条件，不做超前建设。

本轮新增五条（研讨中确立，恢复实施时必须遵守）：

5. **开源法律纪律**：GPL/AGPL 项目只读源码学设计，**不拷贝任何代码进 NASKB 仓库**
   （MIT/Apache/BSD 除外，拷贝时保留许可证头部）；不用 MaxKB 商标/Logo 做背书；
   不尝试规避企业授权（且经核实企业模块根本不在开源仓库里，无对象可解）。
6. **引擎可插拔**：所有深度分析能力走 `/api/search` `/api/ask` 稳定契约（ADR-20260816-2），
   「自研增强」与「外部引擎」是同一抽象边界的两个实现，切换不改前端。
7. **诚实性优先**：检索不到依据时明确说明（默认 designated 兜底模式），绝不裸答冒充有据；
   标准条款场景提供「保真直返」防 LLM 改写原文。
8. **评测先行**：分段参数、融合公式、阈值一律用固定问题集前后对比说话（§9 阶段 3），
   不凭感觉调参。
9. **增量零破坏**：摘要行（kind='summary'）行为与现状完全一致；新能力只作用于显式圈定的
   深析目录；numpy 回退链不含 chunk 行，PG 不可用时自然退回现状能力。

---

## 4. 事实核查结论（本轮确认的事实底座）

### 4.1 MaxKB 社区版

| 事项 | 结论 |
|---|---|
| 许可证 | GPLv3 全文（GitHub 1Panel-dev/MaxKB，v2 分支 ~22.6k★，最新 v2.10.5-lts）；飞致云社区协议追加商标条款与企业版权利保留 |
| 应用对话 API | **社区版可用**：OpenAI 兼容 `/api/application/{id}/chat/completions`（`Bearer application-xxx`）；v1 手册原文+v2 源码路由+社区实测三重证实 |
| 管理 REST API | **代码完整存在于开源仓库**（v2 `/admin/api/*`，内置 Swagger `/admin/api-doc`），非公开契约、无稳定性承诺；官方收费的是平台级「开放 API」SDK 包装 |
| 嵌入第三方/工作流/MCP 节点 | 社区版可用 |
| 社区版上限 | **50 知识库 / 5 应用 / 2 用户** |
| 专业版 ¥4.8 万/套 | SSO/LDAP、操作日志、问答页身份验证、自定义 Logo、飞书同步、开放 API、ARM |
| 企业模块位置 | **不在开源仓库**（独立闭源包+license 动态加载）——不存在「解锁」对象 |
| 技术栈 | Python 3.11+Django 5.2/DRF+Celery/Redis；Vue3 双 SPA；PG+pgvector（blend_search+jieba）；解析层 pypdf/python-docx/openpyxl/bs4 + 自研分段策略（未用 unstructured） |

> 用户最初「API 输入输出都要企业版」的认知据此修正：「问」免费，「管」的接口也在
> 自己部署的开源实例里，只是官方不给文档承诺。

### 4.2 替代品横评（2026-08 GitHub/官方文档核对）

| 项目 | 许可证 | 开源版 API | 部署重量 | 标准类版式解析 |
|---|---|---|---|---|
| RAGFlow | Apache-2.0 纯净 | 全量+OpenAI 兼容 | 重 ≥4核16GB（ES+MySQL+MinIO+Redis） | ★★★ DeepDoc（唯一强项） |
| FastGPT | Apache-2.0+附加（禁相似 SaaS/保 LOGO） | 全量 | 轻 3 容器 | ★★ |
| AnythingLLM | MIT | 完整 | 极轻单容器 | ★ |
| Dify | Apache-2.0+附加 | 全量 | 中重 ~10 容器 | ★★ |
| QAnything | AGPL-3.0 | —— | —— | **停更（2025-03 起），出局** |

关键事实：**「API 收费」是 MaxKB 特有问题**；若将来走路线 A 且追求标准类解析质量，
RAGFlow DeepDoc 是首选候选（代价 16GB 内存门槛）；我们的 MinerU 前置解析可拉平其余方案的短板。

---

## 5. 法律边界结论（GPLv3 逐动作判定）

GPL 红线 = 「是否分发」+「是否衍生作品」，与「整体还是部分」无关。逐动作判定：

| 动作 | 判定 |
|---|---|
| 自部署社区版内部使用 | ✅ 自由（不分发无义务） |
| HTTP 调它的 API（公开或管理接口） | ✅ 安全（进程间通信=mere aggregation） |
| 修改源码自用自部署 | ✅ 安全（留档改动记录即可） |
| fork 后对外分发 | ⚠️ 整体 GPLv3 开放义务触发 |
| 抄源码片段进 NASKB（仅内部用） | 🟡 低风险但禁止（血缘污染） |
| 抄源码片段进 NASKB（对外分发） | ❌ 违反 GPLv3 |
| 规避企业授权校验 | ❌ 禁止（且无对象） |

**落地纪律**（已写入 §3 原则 5）：本轮全部源码调研均为只读学习；设计文档中的正则/SQL/
伪代码均自行编写；参考克隆位于 `%LOCALAPPDATA%\dsh-ref\MaxKB`（临时性质，可随时重克隆，
**不得移入 NASKB 仓库树**）。

---

## 6. 整合路线决策总表

| 路线 | 内容 | 决策 | 触发条件 | 对应需求 |
|---|---|---|---|---|
| **D‘ 自研 chunk 增强** | PG 内核加条款级第二层检索（§7） | ✅ **主线，近期做**（方向已获认可） | 标准/条款级问答已是现实痛点（已成立）；待 v3 平台线程完成后开工 | 拟新增 REQ-R5-06 |
| **A 独立实例+API** | MaxKB/RAGFlow/FastGPT 之一 docker 部署于 Linux 主机，Backend B 同契约接入；分级检索（引擎出面、NASKB MCP/REST 兜底）；页面嵌入附带 | 🔮 远期可选，**届时二次选型** | 深析文档上百份 / 多人共用 / 工作流编排 / 现成界面需求 | REQ-R5-01/03/04 维持 |
| B 页面嵌入 | MaxKB 嵌入浮窗/iframe 进 Web UI | 附属于 A，不单独做 | 同 A | —— |
| C fork 补丁 | fork 封一层稳定管理 API | 🛟 备胎 | 所选引擎管理 API 缺失且手动导入不可忍 | 拟新增 REQ-R5-07 |
| D 拆组件 | 搬 MaxKB 代码 | ❌ 不做（降级为「读码学设计」，已完成一轮） | —— | 编码纪律 |
| export-clean | `.naskb`→干净 Markdown 导出命令 | ✅ 近期顺带（公共资产，无论选谁都需要） | 与 D’ 同批 | REQ-R5-02 前半段升格 |

---

## 7. D‘ 技术方案要点（详情见 chunk-retrieval-design.md）

### 7.1 数据流

```
NAS 文件 ──analyze──► .naskb/artifacts/*.md (MinerU，已有)
                        │ md_chunker.py（新增确定性模块，仅深析圈定目录）
                        ▼
                 chunks[] {seq, title_path[], text}
                        │ sync-vectors 扩展（chunk 行先删后建）
                        ▼
                 vectors 表 kind='chunk'/'title' 行 + search_vector(jieba tsvector)
                        │ pgsearch 三模式扩展
                        ▼
                 serve /api/search /api/ask + MCP kb_*（契约不变，返回字段纯新增）
```

### 7.2 Schema（vectors 表扩列，单表多源制）

`kind('summary'|'chunk'|'title'|'qa')` + `chunk_seq` + `title_path TEXT[]` +
`search_vector tsvector`；`WHERE kind='chunk'` 部分索引 HNSW + GIN。
摘要行零迁移零行为变化；chunk 行 resource_id 仍指文件（REQ-R4-04 不变量保持）；
full_text 存块文本（有意区别于 MaxKB 的行外回查——单表取齐免二次查）；
同步语义=资源变更时该资源 chunk 行整体先删后建，source_hash 记 MinerU md 采样 hash
（复用 ADR-20260816-4），状态机沿用。

### 7.3 分段规则（核心参数初值，阶段 3 评测定稿）

标题树递归切分（ATX 六级、代码围栏掩码、空段治理）→ 目标 800 字符/硬上限 1200 →
超限句末切分（保后半段约束）+ 相邻块 12% 重叠（标题切断处不加）→ 表格随块、大表按行切段重复表头 →
`content_for_embedding = title_path 平铺 + "\n" + text`（标题前置提升召回）→
另产 title 短向量行（章节名查询直达）→ `chunker_version` 入 config，变更须升版重建。

### 7.4 检索（三模式渐进）

embedding 先行 → keywords/blend 二期（jieba 全模式预分词 tsvector + per-schema 术语表
双向注入词典）。blend 公式 `(1-余弦距离)+ts_rank_cd(...,32)`，候选池 `LEAST(top_n×10,500)`，
阈值后置；已知局限（关键词分捞不回向量漏网）→ 备好 UNION 真·双路变体，评测决定。
跨 NAS 合并沿用 R4 决策。reranker（bge-reranker ONNX）三期可选。

### 7.5 问答组装

`<data>条款面包屑：正文</data>` 成对标签 + `max_context_chars=5000` 字符预算顺序装入；
**保真直返**（per-目录开关，阈值默认 0.9，命中即回原文跳过 LLM）；**无命中兜底**
（默认 designated 诚实话术，可选 llm_fallback 裸问+声明）；响应新增
`hits[].{kind,title_path,chunk_seq,score}` 与 `sources[].title_path`（向后兼容纯新增）。

### 7.6 圈定与配置

config `[deep]` 段：roots 目录前缀圈定、enabled、chunker_version、分段参数、直返开关、
预算与阈值、no_hit_mode。普通文档零开销。

---

## 8. 源码学习成果索引（22 项，详表在 chunk-retrieval-design.md §1）

- **分段侧**：标题树递归正则、代码块掩码、句末智能切分、xlsx/csv 表头跟随转管道表、
  PDF 字号→标题映射（我们不需）、清洗规则集、空段治理
- **数据侧**：单 embedding 表多源（PROBLEM/PARAGRAPH/TITLE）+ DISTINCT ON 段级去重、
  向量化文本=title+'\n'+content、TermBase 术语词典双向注入（Tokenizer 1h 缓存）、
  任务链路（先删后建/批量 bulk_create/业务键幂等/状态位取消）
- **检索侧**：blend 加法融合公式与候选池策略、per-库部分 HNSW 逐库归并（印证 --nas all 决策）、
  is_active 过滤下推、dims≥2000 不建索引、归一化与排序解耦
- **应用侧**：字符预算上下文组装、保真直返（文档级 mode+阈值 0.9）、两种无命中兜底、
  FAQ 问题文本向量化=Q→A 缓存、问题补全（最近 3 轮改写）、reranker 独立节点拓扑、
  文档标签路由预筛
- **反向确认（它没做/我们超越点）**：chunk 级打分、PDF 表格还原、块间重叠、页眉页脚识别、
  RRF、真·双路召回

---

## 9. 分阶段执行计划（恢复后按此推进）

| 阶段 | 内容 | 验收 |
|---|---|---|
| 0 需求落账 | 按 §10 清单修订 requirement.md（先改需求再改代码） | REQ-R5-06/07 入表、新 ADR 入册 |
| 1 分段与入库 | md_chunker.py + vectors 扩列 + sync 扩展 + termbase 表 | 单测：真实 MinerU md 分段快照；sync 幂等（二次 0 变化、改/删正确） |
| 2 检索与问答 | embedding 模式 SQL + search/ask 扩展 + 直返/兜底 + 两级引用 | 条款号提问命中正确 chunk；serve/MCP 显示 title_path；停 PG 回退正常 |
| 3 评测调参 | 固定问题集 20~30 条（条款级/表格级/章节级）对比基线；keywords/blend 上线；参数定稿 | 条款命中率与引用准确率显著优于纯摘要基线，误报率不升 |
| 4 收尾 | SKILL.md/README 更新、export-clean 命令、文档收口 | 文档齐全 |

环境事实（不变）：PG 192.168.5.2:25432（PostgreSQL 18.6 + pgvector 0.8.6，Debian）；
分析机 Windows；Linux 主机可供将来路线 A 部署。新增依赖仅 jieba（纯 Python）。

---

## 10. 恢复时第一步：需求基线修订清单

以下修订**已获方向认可但尚未写入 requirement.md**（当时冻结），恢复时按序落账：

1. 新增 **REQ-R5-06**：chunk 级检索增强（内容按 chunk-retrieval-design.md §2~§7；
   状态：设计已确认）；
2. 新增 **REQ-R5-07**：深度引擎管理 API 兜底（fork 补丁，条件触发；状态：规划中）；
3. REQ-R5-02 拆分：导出命令前移为近期项，改名 `export-clean`（解耦 MaxKB 语义）；
4. 新增 **ADR-20260823-X**：修订 REQ-R2-03/ADR-20260811-1 适用边界——「摘要索引层不做
   chunking」不变；新增条款级第二层（kind='chunk'），仅限 `[deep].roots` 圈定范围、
   仅 PG 后端、numpy 快照不含 chunk 行；防稀释初衷不受影响（入索引的是条款级语义单元）；
5. REQ-R5-01 措辞微调：「MaxKB 扩展包」→「深度分析引擎（候选 MaxKB 社区版/RAGFlow/FastGPT，
   选型后置至触发条件成立）」；
6. 修正演进脉络表引用漂移：MaxKB 行误指 `pg-vector-multi-nas.md §8`（该节并无 MaxKB 内容）；
7. REQ-R6 增补编码纪律（§3 原则 5 全文）。

---

## 11. v3 平台对齐核查（恢复实施前必过）

另一线程正在把 NASKB 升级为自持知识的常驻平台（platform-v3-design.md）。本专题恢复时
**先核查以下假设是否仍成立**，不成立则先修 chunk-retrieval-design.md 再动手：

| # | 核查点 | 设计依赖 |
|---|---|---|
| 1 | vectors 表结构（resources/vectors 两表、full_text 在行内）是否被 v3 重构/改名 | §7.2 扩列方案直接依附现结构 |
| 2 | sync-vectors 四操作与指纹体系入口是否变化 | chunk 行同步挂靠同一链路 |
| 3 | serve `/api/search` `/api/ask` 契约及响应结构现状 | 响应扩展须向后兼容 v3 前端 |
| 4 | `.naskb/artifacts` MinerU md 产物路径与命名是否变化 | md_chunker 输入假设 |
| 5 | config.toml 结构（[deep] 段落位）与认证体系（Bearer token 下深析接口的权限面） | 配置与安全边界 |
| 6 | MCP kb_* 工具返回结构现状 | kb_search/kb_ask 同步扩展 |
| 7 | v3 是否已自行实现混合检索/RRF（platform-v3 把 RRF 列为 V3 可选） | 若已实现则 D' 检索段改为在其上扩展 kind 过滤 |

利好对齐：v3 定位（Web UI+REST+MCP 常驻服务）与本专题完全同向；platform-v3 明示
「REQ-R5 MaxKB 系列 V3 不变」；v3 的下载代理/预览能力将来可直接服务「直返原文」场景。

---

## 12. 风险登记（合并两份支撑文档，恢复时复核）

| 风险 | 对策 |
|---|---|
| chunk 行存储放大 | 仅深析目录启用；512 维×数千 chunk 量级可控；部分索引抑制膨胀 |
| 分段质量差拖垮召回 | 固定问题集评测先行；chunker_version 升版全量重建（派生可重建原则） |
| jieba 切词噪声 | 术语表先行录入高频术语；版本号/邮箱占位符保真技巧按需自研 |
| blend 分数量纲混搭 | embedding 先行保底；blend 阈值独立配置（0~2 语义） |
| GPL 血缘污染 | §3 原则 5 纪律 + code review 关注点 + 参考克隆不入仓库树 |
| v3 并行改动导致设计过时 | §11 核查清单前置 |
| MaxKB 社区版商业化收缩（远期路线 A 相关） | .naskb 为事实源、外引擎库随时可重建；选型保留多候选 |
| RAGFlow 类重型引擎内存门槛（远期） | 届时先量 Linux 主机余量，不够退 FastGPT 或继续自研 |

---

## 13. 相关文档地图

| 文档 | 角色 |
|---|---|
| **本文** | 结论固化 + 恢复入口（自足） |
| `design/chunk-retrieval-design.md` | D' 工程细节（DDL/分段规则/SQL 骨架/组装模板/验收） |
| `design/maxkb-integration-analysis.md` | 论证过程：事实核查证据、法律判定、五路线详析、替代品横评 |
| `design/requirement.md` | 需求基线（恢复时按 §10 修订） |
| `design/platform-v3-design.md` | 平台化升级设计（另一线程正在实施，本专题的上游依赖） |
| `%LOCALAPPDATA%\dsh-ref\MaxKB` | MaxKB v2 只读参考克隆（临时，可删可重克隆，严禁入仓库树） |

## 14. 变更历史

| 日期 | 变更 |
|---|---|
| 2026-08-23 | v1.0 固化：用户认可 D' 主线方向；因 v3 平台化线程并行，实施冻结；本文整合两份支撑文档全部结论，作为恢复工作的唯一入口 |
