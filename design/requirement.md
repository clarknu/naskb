# NASKB 需求基线（Requirements Baseline）

> 版本: v1.0
> 状态: 现行（living document）
> 创建: 2026-08-16
> 定位: 本文件是 NASKB 全部功能设计、架构设计、代码实践的**来源与出发点**。
>       所有设计文档（design/*.md）与代码实现都应能回溯到本文件的某条需求/决策；
>       每次需求变化先改本文件，再改设计与代码。

---

## 0. 维护约定（如何更新本文件）

1. **需求编号只增不改**：每条需求有唯一编号（如 `REQ-R1-02`）。已发编号永不复用；
   需求废弃时不删除，改为在"状态"标注 `已废弃（被 REQ-x 取代）`。
2. **变更必须记录**：任何增删改都要在第 8 节"变更历史"追加一行（日期 / 编号 / 摘要）。
3. **拍板决策入 ADR**：用户拍板过的关键取舍记入第 5 节"决策记录（ADR）"，
   写明日期、决策、理由；ADR 编号 `ADR-<日期>-<序号>`，永不修改只可追加"后续变更"。
4. **设计文档引用需求**：design/ 下各详细设计文档在头部声明"依据 REQ-xxx"。
5. **状态取值**：`已实现`（代码已落地且有测试）/ `设计已确认`（方案已确认，待实施）/
   `设计草案`（有设计稿，待确认）/ `规划中`（列入路线，尚未设计）/ `已废弃`。

---

## 1. 项目定位与演进脉络

**NASKB（NAS Knowledge Base）**：对本地目录或 NAS（WebDAV）建立 `.naskb/` 描述仓库，
完成"扫描 — AI 分析（分类/摘要/标签、图片音频识别、扫描件 OCR）— 检索/问答 — 目录整理"闭环，
以 **Reasonix Skill** 形态交付（AI 通过 `naskb/SKILL.md` 调用 `naskb desc` 命令）。

演进脉络（历史事实，用于理解现状的由来）：

| 阶段 | 时间 | 内容 | 文档 |
|---|---|---|---|
| v0.1/v0.2 早期设计 | 2026-06 | 选型稿（LanceDB、bge-large、DirectML、fsspec）——多数选型已随演进被替代 | `design/requirement-v0.2-archived.md` |
| v1 sidecar 机制 | 2026-06~08 | 同行 `.sidecar.json` 描述 | 已废弃（ADR-20260810-1） |
| v2 描述仓库 | 2026-08-10 | `.naskb/` 隐藏仓库、MinerU 全格式、DeepSeek+MiMo 分工 | `design/analysis-engine-v2.md` |
| 检索层定型 | 2026-08-11 | 索引只用摘要+描述；向量（numpy）+BM25 | ADR-20260811-1 |
| 内置问答服务 | 2026-08-16 | `desc serve`（Web UI + API 契约） | `naskb/scripts/naskb/common/serve.py` |
| 多 NAS 向量库 | 2026-08-16 | PG + pgvector、五要素身份、哈希校验体系（设计已确认） | `design/pg-vector-multi-nas.md` |
| MaxKB 扩展包 | 规划中 | 社区版 RAG 扩展，后端同契约切换 | `design/pg-vector-multi-nas.md` §8 / 本文件 REQ-R5 |
| 平台化重定位 v3 | 2026-08-18 | 工具 → 知识库系统（自持知识 + Web UI + 开放 API + 下载/预览）；八项决策拍板；R7 需求组立项 | `design/platform-v3-design.md` / 本文件 REQ-R7 |

---

## 2. 术语表

| 术语 | 含义 |
|---|---|
| **NAS** | 网络存储，身份由五要素定义（REQ-R4-01）；当前支持 webdav/local 两种协议接入 |
| **.naskb 描述仓库** | 每个目录下的隐藏目录，存该目录的文件级/目录级描述（`meta.json`/`index.json`/`files/`/`folder.json`/`artifacts/`） |
| **描述条目** | 一个文件的 AI 分析结果（摘要、分类、标签、转写、OCR 文本、指纹等） |
| **工作区（NASKB_data）** | 工具的数据目录：config.toml、模型、db/（向量快照）、日志 |
| **向量库** | 每个 NAS（五要素）在 PG 中的一个独立 schema（resources + vectors） |
| **Doc.text / Doc.context** | 检索索引文本（仅摘要+描述）/ RAG 上下文（含全文）——AD-R2-01 的分层 |
| **事实源** | NAS 文件；`.naskb` 是抽取快照；PG 是派生库（可重建） |
| **知识源（source）** | 系统接入的一个知识库根（本地目录 / WebDAV / SMB / NFS / iSCSI 挂载视图），带读写属性 rw/ro |
| **来源注册表** | PG `sources` 表：运行时的来源登记与安全边界，资源一律凭 resource_id 寻址 |
| **原始仲裁端** | 可写源端的 `.naskb/` 提取数据权威记录；系统内 PG 维护其副本与衍生产物（ADR-20260818-1） |

---

## 3. 需求清单

### R1 内容采集与分析（已实现）

| 编号 | 需求 | 状态 |
|---|---|---|
| REQ-R1-01 | 对本地目录或 NAS（WebDAV）建立 `.naskb/` 描述仓库，AI 生成分类/摘要/标签 | 已实现 |
| REQ-R1-02 | 仓库结构：`meta.json`（schema 版本/更新时间/采集身份 access_identity）+ `index.json`（文件级）+ `files/`（大条目拆分）+ `folder.json`（目录级）+ `artifacts/`（解析产物） | 已实现（access_identity 由 REQ-R7-03 来源绑定校验承接，v3 落地） |
| REQ-R1-03 | 文档解析双路径：PyMuPDF 快速提取 + MinerU 全格式（PDF/DOCX/PPTX/XLSX → md/html/middle.json）；疑似扫描件自动转 OCR | 已实现 |
| REQ-R1-04 | 模型分工：文本（分类/摘要）→ DeepSeek；图片/音频多模态 → 小米 MiMo V2.5 | 已实现 |
| REQ-R1-05 | 音频：ffmpeg 16kHz 分段（25 分钟/段）→ MiMo 严格串行转写 → 拼接 | 已实现 |
| REQ-R1-06 | 图片描述全走 MiMo（不做纯 OCR）；按 hash 去重 | 已实现 |
| REQ-R1-07 | 视频分级：路径规则 + 关键词规则 + 时长兜底 → processing_policy（metadata_only / keyframes_only / full） | 已实现 |
| REQ-R1-08 | 目录级分析：代码/软件/发布包目录不逐文件，只分析结构 → folder.json | 已实现 |
| REQ-R1-09 | 旧格式兼容：.doc 用 Word COM 优先 + olefile 兜底（MinerU 不支持 .doc/.xls） | 已实现 |
| REQ-R1-10 | `analyze-tree` 增量幂等：**三级判定链**（L1 stat 免检 → L2 采样 hash 复核 → L3 重析），可反复跑可中断 | 已实现 |
| REQ-R1-13 | **指纹判定体系**：① 免检必要条件 = path+文件名+size+mtime+**ctime** 全一致，缺 ctime 不得免检（必须 hash 复核）；② 内容 hash 采样规则（见 ADR-20260816-4）：>512KB 文件取 8 段×64KB 均匀分布（首段含文件头、末段含文件尾，位置仅由 size 决定），≤512KB 全量；③ hash_algorithm 记录规则边界，算法变更须升版全量重析 | 已实现 |
| REQ-R1-11 | 整理原则：移动不删除；`.naskb` 整仓跟随；源/目标/上层 folder.json 级联更新；搬空目录自动删除；子路径先移 | 已实现 |
| REQ-R1-12 | 并发策略：DeepSeek 并发 4-6；MiMo 与 MinerU 严格串行（防风控/资源争抢） | 已实现 |
| REQ-R1-14 | 整理安全：越界硬校验 / 目标冲突三档（同 hash→noop、目标无分析→meta_only、否则 rename）/ plan 快照复检防 TOCTOU / plan_id 持久化 / root 互斥锁 | 已实现 |
| REQ-R1-15 | 整理闭环：apply 后本地向量索引 remap + PG 增量同步（移动保留 resource_id），同步失败不阻断整理、状态可查 | 已实现 |

### R2 检索与问答（已实现）

| 编号 | 需求 | 状态 |
|---|---|---|
| REQ-R2-01 | **检索索引只用摘要+描述**（summary/category/tags/content_description）；全文不进索引（防高频词稀释主题） | 已实现（ADR-20260811-1） |
| REQ-R2-02 | 全文照常提取、保留为元数据，仅作 RAG 生成阶段上下文（Doc.text / Doc.context 分层） | 已实现 |
| REQ-R2-03 | 不做文档级 chunking：一个文件一条向量 | 已实现 |
| REQ-R2-04 | 双引擎：语义向量（bge-small-zh-v1.5 ONNX 本地嵌入，512 维）+ BM25 关键词，无索引自动降级 | 已实现 |
| REQ-R2-05 | 问答（`desc ask`）必须带来源路径，答案只依据检索内容生成 | 已实现 |

### R3 内置问答服务（已实现）

| 编号 | 需求 | 状态 |
|---|---|---|
| REQ-R3-01 | `desc serve`：标准库 Web UI（搜索 + 问答）+ `/api/search` `/api/ask` `/api/reload` `/api/stats` | 已实现 |
| REQ-R3-02 | 引擎自动选择：向量索引与当前文档集合一致 → 向量；不一致标陈旧并降级 BM25 | 已实现 |
| REQ-R3-03 | `/api/reload` 热刷新（analyze 后无需重启） | 已实现 |
| REQ-R3-04 | **接口契约 = 检索后端抽象边界**：未来任何后端（PG、MaxKB）实现同一契约即可切换，前端不动 | 已实现（ADR-20260816-2） |

### R4 多 NAS 向量库（PG + pgvector，主体已实现；尾款并入 v3）

详细设计见 `design/pg-vector-multi-nas.md`（v2）。以下为需求条目：

| 编号 | 需求 | 状态 |
|---|---|---|
| REQ-R4-01 | NAS 身份 = **协议 + 主机 + 端口 + 用户账号**（五要素；账号视图不同即不同库）；五要素相同 = 同一 NAS 库 | 已实现 |
| REQ-R4-02 | 一个工具支持多个 NAS；每个 NAS 在 PG 中一个**独立 schema**（向量库），schema 名由五要素确定性生成（账号只入 sha1 前 12 位） | 已实现 |
| REQ-R4-03 | 资源按 NAS 内目录（分类文件夹）组织结构保存：rel_path + parent_dir（支持按目录范围检索），category/tags 与目录结构并存 | 已实现 |
| REQ-R4-04 | 每条向量必含四要素：① 向量数据 vector(512)；② 用于向量化的内容摘要 summary_text；③ 完整文本内容 full_text（纯文本，不含二进制）；④ 指向原始 NAS 资源（resource_id → resources.rel_path）。**任何向量可对应回一个 NAS 文件** | 已实现 |
| REQ-R4-05 | 哈希校验体系：指纹四元组（**ctime** + mtime + size + 内容采样 hash）；hash_algorithm 记录算法边界，算法变化须升版全量重析 | 已实现 |
| REQ-R4-06 | 三层版本对齐：NAS 文件 → .naskb 快照 → PG 行；任何一层落后可检出 | 部分实现（.naskb↔PG 两层已实现；NAS 源侧预检见 REQ-R4-10） |
| REQ-R4-07 | 新鲜度状态机：`ok` / `stale_vector`（快照重析、PG 未跟上）/ `stale_source`（NAS 已变、快照落后）；检索/问答带状态徽章，过期内容在问答上下文中显式标注 | 已实现 |
| REQ-R4-08 | 同步四操作：增/改/删/移，以 rel_path 为键 + hash 匹配区分"移动"与"删除+新增"（移动保留 resource_id）；增量幂等；批量提交；失败记日志不中断 | 已实现 |
| REQ-R4-09 | 版本自证：vectors.source_hash = 生成向量时的文件 hash；resources.prev_hashes 审计链（最近 N 版）——可回答"这条向量描述的是哪个文件版本、是否已过期" | 已实现 |
| REQ-R4-10 | sync 预检：WebDAV PROPFIND 取 mtime/size 与 .naskb 对比（零下载）；疑似变化只标记不重析（重析是 analyze-tree 职责）；`--verify-hash` 可选深度校验 | 规划中（v3 V1 实施，由 REQ-R7-06 承接） |
| REQ-R4-11 | 采集身份固化：.naskb/meta.json 记录 access_identity，sync 校验身份不一致拒绝同步（防串库） | 规划中（v3 由 REQ-R7-03 来源绑定校验承接） |
| REQ-R4-12 | 检索接入：search/ask/serve 的 PG 后端 + 多 NAS 选择（--nas；serve 下拉）；`--nas all` 每库 top-k 合并（分数不跨库比较） | 已实现（--nas all 跨库合并留待 v3 V2） |
| REQ-R4-13 | **回退链**：PG 不可用自动回退 numpy 向量 → BM25；现状功能完全保留（PG 是增强不是替换） | 已实现 |
| REQ-R4-14 | 身份迁移：NAS 主机变更（换 IP）可 `pg-rebind` 重绑五要素，不丢库 | 规划中（v3 V2，来源管理页操作） |
| REQ-R4-15 | PG 安全：专用库 naskb + 专用账号最小权限；密码明文存 config（与 llm key 同策略）；代码/日志不打印连接串 | 部分实现（阶段 0 已建 naskb 库+专用账号；其余纪律沿用） |

### R5 演进与扩展（规划中）

| 编号 | 需求 | 状态 |
|---|---|---|
| REQ-R5-01 | MaxKB 扩展包（独立目录，可选依赖）：前期用 NASKB 内部问答；后期需要深度 RAG/工作流/多用户时接入 MaxKB **社区版**（免费），不预设专业版费用 | 规划中 |
| REQ-R5-02 | 内容管道：export-maxkb（.naskb 干净文本导出 Markdown/ZIP）+ sync-maxkb（管理 API 增量同步，hash 对比；API 不稳定则降级手动导入） | 规划中 |
| REQ-R5-03 | Backend B：实现与 REQ-R3-04 相同的 search/ask 契约，config 开关切换 MaxKB 后端 | 规划中 |
| REQ-R5-04 | 分级检索（进阶可选）：NASKB 检索封装为 MCP server 接入 MaxKB 工作流（精库优先、全库兜底） | 规划中 |
| REQ-R5-05 | 混合检索（可选增强）：PG 全文检索（tsvector，仅摘要文本）+ 向量 RRF 融合排序 | 设计草案（pg-vector-multi-nas.md §8.1） |

### R6 非功能与实践要求（现行）

| 编号 | 需求 | 状态 |
|---|---|---|
| REQ-R6-01 | 写任何文本文件一律 UTF-8（无 BOM，除非场景明确要求其他编码） | 已实现（全局铁律） |
| REQ-R6-02 | 密钥管理：DeepSeek/MiMo key 存工作区 config.toml 或环境变量（DEEPSEEK_API_KEY / MIMO_API_KEY）；不加密、不打印 | 已实现 |
| REQ-R6-03 | 风控纪律：MiMo 多模态调用严格串行（并行触发平台风控冻结 key）；401/超时停止重试并提示检查 key | 已实现 |
| REQ-R6-04 | NAS 国内服务器连接显式加 NO_PROXY（防 VPN 分流导致上传断流截断——2026-08-13 教训） | 已实现 |
| REQ-R6-05 | 部署自包含：拷贝 naskb/ + NASKB_data/ 即可用；向量模型首次运行自动下载（~24MB）；MinerU 需独立 venv（Python<3.14） | 已实现 |
| REQ-R6-06 | 环境事实：分析在本机 Windows；PG 192.168.5.2:25432（PostgreSQL 18.6 + pgvector 0.8.6，Debian）；MaxKB 部署于用户 Linux 主机 | 现行 |

### R7 平台系统化（v3 重定位，2026-08-18 立项）

> 依据：ADR-20260818-1；详细设计 `design/platform-v3-design.md`（v0.2，八项决策已拍板）。
> 产品形态升级为「NASKB 知识库系统」，**版本自 v0.1 重新起版**。

| 编号 | 需求 | 状态 |
|---|---|---|
| REQ-R7-01 | 系统形态：常驻服务进程，Web UI + REST API + MCP 三出口；CLI/Skill 保留为高级/无人值守通道 | 规划中 |
| REQ-R7-02 | 知识自持：PG 为知识权威库（元数据+全文+向量）；分析中间产物**不持久保留**（临时暂存区 `store/tmp/` 用完即清）；可写源端 `.naskb` 为提取数据的原始仲裁端，系统内维护副本+衍生产物 | 规划中 |
| REQ-R7-03 | 来源注册表：PG sources 表 + 管理 API/UI；注册表即安全边界，资源一律凭 resource_id 寻址、不接受裸路径；含来源绑定校验（连接 ↔ 五要素 ↔ 注册信息三方核对，承接 REQ-R4-11） | 规划中 |
| REQ-R7-04 | 挂载式多协议接入：local/WebDAV（V1）、SMB 直连（V2）、NFS/iSCSI 以 OS 挂载注册为 local 源（V2）；挂载型协议不在应用层重复造客户端 | 规划中 |
| REQ-R7-05 | 只读知识库：access_mode=ro 绝不写源端；中间产物不留存；删除仅标记 missing_source 不清内部知识 | 规划中 |
| REQ-R7-06 | 更新校验体系：周期零下载预检（PROPFIND/readdir，承接 REQ-R4-10）+ 访问时 stat 轻校验 + 手动 verify-hash；状态机 ok/stale_vector/stale_source/**missing_source** | 规划中 |
| REQ-R7-07 | 下载代理：流式分块转发、Range 断点续传、ETag=file_hash、filename* 编码；源离线返回 503+指引 | 规划中 |
| REQ-R7-08 | 在线预览：图片/PDF/音视频原生格式/文本/解析视图（rw 源 MinerU HTML）先行；Office 及不支持类型提示"无法查看"+提供下载；复杂编辑后置 | 规划中 |
| REQ-R7-09 | Web UI：搜索问答、目录树浏览（罗列检索）、文件详情（预览+元数据）、来源管理、任务中心 | 规划中 |
| REQ-R7-10 | 开放 API：/api/sources /tree /files 族；旧 /api/search /api/ask 契约冻结不变（ADR-20260816-2）；OpenAPI 自动导出 function schema | 规划中 |
| REQ-R7-11 | 认证：单管理员 Bearer token + 局域网匿名只读开关；多用户/角色后置 | 规划中 |
| REQ-R7-12 | 调度：进程内定时扫描/同步预检/stale 复查（清偿原 R4"阶段 3 定时同步"） | 规划中 |
| REQ-R7-13 | adopt 收编：存量 `.naskb` 仓库一键导入系统库；export-repo 反向重建 | 规划中 |
| REQ-R7-14 | 部署纪律：PG 用统一独立实例（192.168.5.2:25432），业务进程不自建数据库/Redis/队列；凭据集中管理不入镜像 | 现行（全局部署规则引用） |
| REQ-R7-15 | 二级知识库体系：文档拆出物（图表/段落/实体等）的标准解析、存储与再组织——另行专项设计 | 规划中（本次不做） |

---

## 4. 架构原则（贯穿所有功能）

1. **确定性层与 AI 编排层分离**：确定性操作（抽取/入库/检索/移动/同步）由代码实现；
   柔性判断（分类/摘要/方案）由代码组织现状给 LLM，LLM 反馈后代码执行落地。
2. **内容处理层是长期资产**：无论检索后端如何演进（numpy → PG → MaxKB），
   `.naskb` 描述仓库不变、不重做——后端是可插拔的壳。
3. **事实源唯一**：NAS 文件是事实源，`.naskb` 是抽取快照，PG 是可重建派生库；
   任何派生层挂了都能从上游重建。
4. **轻量起步、按需升级**：当前量级（数千条目）numpy 快照即可；PG 向量库解决多 NAS/持久化/
   一致性；MaxKB 解决深度 RAG。每步升级都有明确触发条件，不做超前建设。

---

## 5. 决策记录（ADR）

### ADR-20260810-1：v2 架构拍板（取代 Phase 1 sidecar 机制）
- **决策**：废弃 `.sidecar.json` 同行文件，全面改 `.naskb/` 目录隐藏仓库；MinerU 全格式双路径；
  DeepSeek 文本 + MiMo 多模态分工；视频分级；并发策略（DeepSeek 4-6 并发、MiMo/MinerU 串行）；
  旧 .doc/.xls 用 Word COM 兜底。
- **理由**：sidecar 同行文件与文件移动/复制不同步、脆弱；仓库化统一管理产物与溯源。
- **详细设计**：`design/analysis-engine-v2.md`。

### ADR-20260811-1：检索索引只用摘要+描述
- **决策**：向量/BM25 索引只用 summary/category/tags/content_description；全文不进索引，
  仅作 RAG 生成阶段上下文（Doc.text/context 分层）；不做文档级 chunking。
- **理由**：全文进索引用高频词稀释主题、拖慢索引；描述是 AI 浓缩语义，检索更精准。
- **适用边界**：REQ-R2 全部；PG 后端（R4）与混合检索（R5-05）同样遵守。

### ADR-20260816-1：MaxKB 阶段方案（内部问答优先，扩展包后置）
- **决策**：前期以 NASKB 自身提供内部问答（serve + 现有检索）；MaxKB 不买专业版（4 万+），
  将来需要时以扩展包形式接入**社区版**，复用 .naskb 内容，后端同契约切换。
- **理由**：前期内容处理与检索本身已有价值；MaxKB 短板（OCR/音视频/思维导图）恰是 NASKB
  已做的部分；社区版免费已覆盖 RAG 核心能力。

### ADR-20260816-2：serve API 契约 = 检索后端抽象边界
- **决策**：`/api/search` `/api/ask` 定为稳定契约；PG 后端、MaxKB 后端都实现该契约，
  config 开关切换，前端零改动。
- **理由**：让"换后端"变成"换实现不换接口"，前期代码全部保留。

### ADR-20260816-3：PG 多 NAS 向量库设计 v2（五要素身份 + 哈希校验体系）
- **决策**：NAS 身份 = protocol+host+port+**username**；每 NAS 一个 PG schema；
  resources/vectors 两表；指纹三元组（sha256+mtime+size）；三层版本对齐；
  ok/stale_vector/stale_source 状态机；增/改/删/移四操作同步（hash 匹配识别移动）；
  vectors.source_hash + prev_hashes 版本审计；sync 做零下载 PROPFIND 预检；
  .naskb/meta.json 固化 access_identity 防串库；PG 不可用回退 numpy→BM25。
- **理由**：账号视图隔离是真实需求（不同账号看到不同文件夹）；"向量对应哪个文件版本、
  是否过期"必须有体系支撑而非散落逻辑。
- **用户确认**：2026-08-16 全部 7 条决策点确认（含 folder 条目暂不入库、物理删除+审计、
  precheck 默认开、--nas all 每库 top-k 合并、授权建 naskb 专用库/账号）。
- **详细设计**：`design/pg-vector-multi-nas.md`（v2）。

### ADR-20260816-4：指纹判定体系（ctime 必要要素 + 采样 hash 规则）
- **决策（用户 2026-08-16 确认）**：
  1. **免检必要条件**：path + 文件名 + size + mtime + **ctime** 五项全一致才可跳过 hash 校验；
     **ctime 必须参与**——取不到 ctime 就认为"无法完整获取文件摘要信息"，必须走 hash 复核（L2）。
     atime 不参与判定（与内容无关且现代系统本身不可靠）。
  2. **内容 hash 采样规则**：原始数据来源限定 512KB。文件 ≤512KB 全量 hash；
     文件 >512KB 取 **8 段 × 64KB，均匀分布**：第 i 段（i=0..7）起始偏移
     `start_i = i * (S - 64K) // 7`（整数运算，首段=文件头、末段=文件尾，位置仅由 size 决定，
     同大小文件永远取同位置），按 i=0..7 顺序喂入 sha256。
     目的：防止"文件头相同、后续内容不同"的伪装文件（如压缩包打包机制，前 1MB 相同 4GB 不同）。
  3. `hash_algorithm` 记录规则边界（`sha256:full` / `sha256:sample8x64k`）；规则变更须升版并全量重析。
- **理由**：NAS（WebDAV）场景算 hash 要下载内容；stat 免检最大化性能；
  采样 hash 用有限读取覆盖文件头/中/尾，兼顾成本与防伪能力；
  WebDAV 的 ctime（creationdate）可能缺失，缺失时 hash 复核兜底，不牺牲正确性。
- **适用边界**：REQ-R1-13、REQ-R4-05/06/07；`.naskb` 与 PG resources 的指纹字段一致。

### ADR-20260818-1：v3 平台化重定位（工具 → 知识库系统）
- **决策（用户 2026-08-18 逐项确认）**：
  1. 项目从"附着 NAS 的本地工具"重定位为**自持知识的知识库系统**：Web UI + 开放 API +
     存储/检索/分析一体；NAS 及可挂载文件系统均为"知识源"，支持只读源（提取后自行存储）；
  2. 新增用户能力：下载代理（流式转发）、在线预览（简单档先行，不支持则提示"无法查看"+下载）、
     目录树罗列检索、来源注册管理；
  3. 技术栈：后端 **FastAPI**；前端 **Vue3+Vite 静态包**由服务托管；
  4. **分析中间产物不持久保留**——临时暂存区用完即清；文档拆出物的标准解析/存储与再组织
     立项为"二级知识库体系"（REQ-R7-15）后置；
  5. 认证起点：单管理员 token（+匿名只读开关），多用户后置；
  6. 可写源维持双写，语义定为：源端 `.naskb` 是**原始仲裁端**（权威记录），
     系统内 PG 维护**副本 + 衍生产物**；
  7. folder 描述入独立 `folders` 表（仅元数据入库；folder 仍不建向量，
     "向量↔文件一一对应"边界不变）；
  8. 多来源组织：schema 仍按 NAS 五要素，`resources.source_id` 列区分同 NAS 多来源；
  9. 产品以「NASKB 知识库系统」**v0.1 重新起版**。
- **理由**：工具形态无法承载"用户可见的知识库系统"目标；既有 PG 存储层/指纹体系/AI 分析管线
  可直接升格为系统内核，改造成本集中在交互层与内容访问层（下载代理/预览/UI）。
- **详细设计**：`design/platform-v3-design.md`（v0.2）。

---

## 6. 设计文档索引

| 文档 | 对应需求 | 状态 |
|---|---|---|
| `design/requirement.md` | 本文件（需求基线） | 现行 |
| `design/requirement-v0.2-archived.md` | 历史归档（v0.2 选型稿） | 已归档 |
| `design/analysis-engine-v2.md` | R1（内容采集与分析详细设计） | 现行 |
| `design/implementation-plan.md` | R1 早期实施计划 | 参考 |
| `design/pg-vector-multi-nas.md` | R4（PG 多 NAS 向量库详细设计，v2） | 现行 |
| `design/platform-v3-design.md` | R7（平台化重定位总体设计 v0.2，含决策记录与路线图） | 现行 |
| `design/mcp-kb-design.md` / `mcp-tech-reassessment.md` | 早期 MCP 探索（R5-04 的前身） | 参考 |
| `README.md` / `naskb/SKILL.md` | 能力速查（AI 操作手册） | 现行 |

---

## 7. 已知问题与待办（从需求反推）

- **R4 尾款四项**：REQ-R4-10 sync 预检、REQ-R4-11 access_identity（→REQ-R7-03 承接）、
  REQ-R4-14 pg-rebind、`--nas all` 跨库合并——全部纳入 v3 路线图（platform-v3-design.md §8，V1/V2）。
- **v3 实施主线**：V0.1 固化提交 → V1 系统底座 → V2 体验补全 → V3 深度能力（platform-v3-design.md §8）。
- REQ-R5 系列（MaxKB/RRF 混合检索）：维持规划中，排在 v3 V3 阶段。
- 文档小债：README 测试数（164→253）、cli.py 头注释命令清单——随 V0.1 固化一并清理。

---

## 8. 变更历史

| 日期 | 变更 |
|---|---|
| 2026-06-04 | v0.2 选型稿（现归档为 requirement-v0.2-archived.md） |
| 2026-08-16 | v1.0 需求基线创建：整合 v2 架构、检索层决策、serve、PG 多 NAS 设计（含 5 条 ADR）；确立编号体系与维护约定 |
| 2026-08-16 | 新增 ADR-20260816-4（指纹判定体系：ctime 必要要素 + 8×64KB 采样 hash）；新增 REQ-R1-13；REQ-R1-10/REQ-R4-05 更新 |
| 2026-08-16 | 阶段 0+1 实施完成：PG 初始化（naskb 库/专用账号/vector 0.8.6）；三级判定链（fs ctime/read_ranges、hashing.py 采样规则、FileEntry ctime/hash_algorithm、batch.py L1/L2/L3）；pgstore.py（registry/schema/DDL/sync 四操作/检索）+ sync-vectors/sync-status/pg-status 命令；测试 117+ passed |
| 2026-08-16 | 阶段 2 实施完成：pgsearch.py（PgSearchEngine 同构接口）；search/ask 增 --pg/--nas；serve 增 --pg（NAS 下拉/状态徽章）；PG 失败自动回退本地引擎链（REQ-R4-12/13）；端到端实测 PG 检索/问答/serve 全链路通过 |
| 2026-08-18 | 补录 REQ-R1-14/R1-15（整理安全/整理闭环——reorganize-refactor-plan P0+P1 已实现部分的追认）；刷新 R1/R4 各条状态与 §7 待办清单 |
| 2026-08-18 | **v3 平台化重定位立项**（ADR-20260818-1）：新增需求组 R7（REQ-R7-01~15）；产品以「NASKB 知识库系统 v0.1」重新起版；技术栈拍板 FastAPI + Vue3 |
