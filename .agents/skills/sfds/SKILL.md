---
name: sfds
description: "单人全栈开发标准（SFDS）方法论 · 联邦仲裁版。**本项目所有开发方法的唯一入口**：任何开发、设计、编码、测试、复查、迭代、发布、调试行为，只要涉及工作流/ER/API/架构/页面设计、代码生成、TDD、复查、迭代、发布、设计稿发布、小程序自动化等，一律先经本技能路由——内部按能力域以子技能组织（skills/<能力>/SKILL.md + 内置模板），读取对应子技能并按它的「触发条件→执行流程→输出格式」执行。迁移只需整体复制本文件夹；不把技能平铺到项目顶层。"
whenToUse: "任何时候，只要工作与项目研发相关：项目初始化、业务设计、ER/API/架构/页面设计、后端或端代码生成、测试设计/执行、全量复查、功能迭代、Bug 修复、联调、发布、设计稿发布、小程序自动化调试，或询问『按什么标准开发/下一步做什么』——都应先加载本技能并按其路由。若尚未触发，先调用技能工具加载本文件。"
lineage:
  origin: arb-hub
  case: CASE-011
  note: NASKB 试行版：父技能+子技能单目录打包，迁移即整夹复制。bundle 内所有 `.agents/skills/…` 路径（子技能正文、模板、共享规范、脚本输出）一律解释为 `<本文件夹>/…`（本项目即 `.agents/skills/sfds/…`），即 `.agents/skills/_shared/…` → `.agents/skills/sfds/_shared/…`、`.agents/skills/<skill>/…` → `.agents/skills/sfds/skills/<skill>/…`；`~/.agents/skills/…`（全局分发）保持原样。
  children: 21
---

# SFDS 方法论（仲裁版，父技能入口）

本文件夹 = **整套研发方法论**。只有本 `SKILL.md` 被框架直接发现；各能力域以子技能放在 `skills/<能力>/SKILL.md`（含内置模板/脚本）。**父技能负责路由与调度，子技能承载具体方法论**——迁移 = 整体复制本文件夹；升级 = 替换子技能。

> 不在项目 `.agents/skills/` 顶层平铺，避免同名分叉污染，并保证迁移是「一个文件夹的事」。

## 规则 0：触发要求（每次必读）

1. **本技能是项目方法论的唯一入口。** 任何涉及研发的行为——设计、编码、测试、修改、发布、调试、回答"怎么做/下一步"——都应在动作前加载本技能并按下方路由；
2. 若当前会话尚未加载本技能（模型未自动触发）：**先调用技能工具获取本文件**，再开始任何方法论动作；项目 `AGENTS.md` 也强制要求走本入口（见"项目首次接入"）；
3. 方法论类动作**不绕过本入口直接改 design/、tests/、src/**；绕过的行动按违规处理（与 AGENTS.md 铁律一致）。
4. **官方手势 `/sfds`：** 在支持技能手势的会话中，输入 `/sfds`（可带子技能名，如 `/sfds pipeline-controller`）即令本技能全文被注入，再按下表路由。子技能**没有独立手势**——它们在 bundle 内，框架只发现本父技能这一层；单独输入 `/pipeline-controller` 不触发任何东西。

## 触发词路由（用户话术 → 子技能）

| 用户意图（代表性触发词） | 子技能 |
|---|---|
| 初始化项目 / 项目骨架 / SFDS / 标准 / 方法论 / 下一步 / 当前进度 | `development-standard` |
| 业务设计 / 工作流 / 流程 / 状态机 / 业务规则 | `business-workflow` |
| ER 图 / 实体关系 / 数据建模 / 领域建模 | `entity-relationship` |
| API 设计 / 接口 / REST / 路由设计 / 端点 | `api-design` |
| 后端架构 / 架构模式 / 分层 / 模块边界 / 服务拓扑 | `backend-architecture-design` |
| 客户端页面功能设计 / 移动端 TabBar / PC·桌面后台页面 | `client-ui-design` |
| 后端代码生成 / API 实现 / ORM 生成 | `api-code-gen` |
| 客户端代码生成 / 页面代码生成 / 前端实现检查 | `client-code-gen` |
| TDD 设计 / 测试设计 / 写测试 | `tdd-build` |
| TDD 执行 / 跑测试 / 测试报告 / 回归 | `tdd-execute` |
| 复查 / 一致性检查 / 全量复查 / 对齐检查 | `review` |
| 报错 / bug / 诊断 / 改一下 / 修改 / 重构 / 迭代 / 联调 | `iterate` |
| 跨项目任务编排 / 队列 / 写锁 / 发布闭环调度 | `pipeline-controller` |
| 发布 / 发版 / 上线 / 版本管理 | `release-management` |
| 设计稿发布 / 同步 publish / 发布设计文档 | `sync-design-to-publish` |
| 密钥管理 / 密钥库 / 访问凭据 / 访问令牌 / API 密钥 / 敏感配置 / 部署密钥 / 环境变量注入 / 凭据管理 | `credential-management` |
| 部署环境 + 中间件 + 部署原则（子网/Mock/逻辑隔离/独立实例/宿主化/环境架构/部署架构…） | `deployment-principles` |
| 原始输入整理 / 需求归档 / 整理原始需求 | `consolidate-raw-input` |
| 先记下来 / 暂存 / 记到待办 / 这个需求先不急 / 中远期 / 回顾下待办 / 看看哪些能拎起来 / 细化一下这个需求 / 纳入方法论 / 从头开始迭代设计 | `requirements-backlog` |
| AI 工作流设计 / 编排设计 / Dify / 自定义节点 | `ai-workflow-orchestration-design` |
| 微信小程序自动化 / 小程序调试 / wechatide | `wechatide-automation` |
| 图文转文本 / 语音转文本 / 文档结构化 / 图片识别 / 录音转写 / 敏感证照识别 / 知识库预处理 | `media-preprocess`（外协技能组） |

> **媒体/信息预处理（media-preprocess-bundle，外协技能）引用约定**：把图片 / 语音 / 文档统一转成文本语言模型可消费的输入，并（产出方向）把合同文书生成/审查/修改/出正式档，作为开发主线的辅助层——`consolidate-raw-input`（原始输入整理：录音/图片/PDF 材料→文本化入库）、`review`（外部文档比对）等需要先文本化非文本材料时，引用 `packages/media-preprocess-bundle/`（独立 bundle，不进 SFDS 路由能力域）。四子技能（**无独立手势，经 `media-preprocess` 父技能点名 `/media-preprocess <子技能名>`**）：`image-preprocess`（图像，含敏感材料绕行）/ `voice-preprocess`（语音，识别+纠错+说话人分离+时间打点）/ `doc-preprocess`（文档，MinerU 封装+结构保持+图片子分析+HTML 复现）/ `contract-compose`（合同：起草/审查/修改/出正式档，产出方向）。**技能 zero-key**（密钥走项目配置 env / credentialctl）；**默认输出原文**（家庭知识库/自有材料），仅显式 `--redact` 才打码；合规由法律控制，不由项目或技能控制。大型引擎（MinerU/PaddleOCR/whisper）集中制 `C:\Soft\`。

> 微信开发者工具本体（wechatide）是**外置工具**（随 DevTools 单向同步），不在 bundle 内置；`wechatide-automation` 说明的是"有该外置工具→可做自动化+做法 / 无该工具→做不了、需补充"的判定与用法。
> 上表为代表性路由；每个子技能的**完整触发词集合见其 frontmatter 的 `triggers`**。若用户话术未命中，打开子技能 `skills/<name>/SKILL.md` 看它的「触发条件」章节再定。
> **默认流水线（2026-08-29，CASE-015/016）**：开发类工作（重构 / 需求 / bug 修复 / 迭代 / 联调修正）命中 `iterate` 时，阶段二的执行/验证**默认由 `pipeline-controller` 外壳调度**——登记为 `T-xxx` 任务进 `.pipeline/PIPELINE.md` 队列、后台持锁串行、一任务一 commit、落过程留痕到 `.pipeline/journal/T-xxx.journal.md`（跨会话可恢复）。见 `iterate` SKILL.md「默认执行载体」+ 规则 #15 与 `pipeline-controller` SKILL.md「默认激活与分层」。用户显式声明「一次性 / 直接改 / 不用管线」时才内联执行。

> **`credential-management`（密钥/配置管理）编排约定**：涉及密钥、访问令牌、环境变量、线上部署密钥时，自动取用 `credential-management` 子技能——
> ① **提取**：生成配置/脚本/产物需引用密钥时，先 `credentialctl get <proj> <key>` 拿 `<CREDENTIAL:proj/key>` 占位符，**绝不写真值**；
> ② **存储**：**机密**用 `credentialctl add <proj> <key> --secret --file <path>` 存入（值不落 argv）；**非密部署配置**（IP/域名/地址/端口/用户名/库名/URL/路径）**进部署配置文档**，不以 `--config --plain` 入库；
> ③ **初始化**：接入时先 `credentialctl init`（**自动建库并生成一把 master 密钥**给你保存，换机凭它恢复），再 `credentialctl project init <proj> --scope ... --config <项目根>\.credential\config` 一键登记；
> ④ **越权硬规则**：scope 外 key 一律拒绝；真值仅在部署注入（`--env`/`--reveal`，审计）时取。

> **`deployment-principles`（部署总原则/评审资产）使用约定**：属**原则/评审资产**（无步骤流程）。评审/规划项目环境拓扑、组件放置、第三方连接与部署架构、中间件资源放置、**宿主机网络访问**时，判定各项目环境/部署是否合规——线上结构一致不超既定范围；本地开发自建/中间件/业务系统**原则上不出子网**、外网以 Mock/网络转发绕过（数据库可在本机或子网内其它主机）；预发布与线上**共用同一第三方库主机、仅库名不同（逻辑隔离）**，自建组件复用同一主机（满足数据隔离即可）、轻量系统组件**独立部署一套**与主系统同构；数据库跨环境**一律逻辑隔离**（不引入主机级物理隔离）；通用中间件用宿主机原生/统一独立实例（RDS/云 Redis/统一容器），**禁止业务 compose 自建公共服务**；**网络分层**——公共中间件经**宿主端口**接入、**一个项目一个 Docker 网络**（同项目含全环境同宿主共用同一网络、服务名互访，仅公共资源经宿主端口）、对外**只经 Nginx 域名映射**（内网不出公网）；三环境同构、独立实例凭据集中管理；配置发布依赖架构文档圈定的整体架构、机密存 Credential Vault。由 `release-management` 发布门禁（§二 门禁10/11）与 `review` 校核维度（§2.13）**引用**，并可按触发词**独立触发**。与 `credential-management`（机密）/`release-management`（怎么发布）互补。

## 使用规则（怎么"用"一个子技能）

1. **定位**：按上表路由到子技能目录 `skills/<name>/`。
2. **读取全文**：读 `skills/<name>/SKILL.md` 的完整正文——它的 frontmatter（name/description/triggers）在 bundle 模式下只是元数据（不自动触发），**真正要执行的是它正文里的「触发条件 → 执行流程 → 输出格式」**。
3. **按其执行**：遵循该子技能给出的步骤、命令、输出；需要模板/数据时引用同目录下的资源。
4. **设计资产落地**：子技能内置的模板（viewer.html、data/*.js、域注册表/pipeline-state 等）在首次使用时**物化到项目 `design/` 对应编号目录**（由 `development-standard` 初始化流程统一铺设骨架）。方法论升级必须连同这些资产更新（见其 frontmatter `assets`）。
5. **共享层（全 bundle 通用路径约定）**：`_shared/`（pipeline-registry.js、document-asset-format.md、arch-contract-spec.md、consistency-check-format.md 等）被相关子技能引用；bundle 模式下**正文/模板/共享规范/脚本输出**中的 `.agents/skills/…` 一律解释为 `<本文件夹>/…`（本项目 = `.agents/skills/sfds/…`）——即 `.agents/skills/_shared/…` → `.agents/skills/sfds/_shared/…`、`.agents/skills/<skill>/…` → `.agents/skills/sfds/skills/<skill>/…`；`~/.agents/skills/…`（全局分发）保持原样。
6. **审计/裁决件**：各子技能的 MERGE-NOTES / ACCEPTANCE / CHANGELOG 已移到 `_audit/<能力>/` 下，供查证该能力域的三方分歧与仲裁结论，不参与运行。

## 项目首次接入（初始化）

- 先执行 `development-standard` 子技能的**项目初始化**流程：生成 `AGENTS.md`、`design/` 骨架（01~07，模板在 `skills/development-standard/templates/`）、`domain-registry.js`、`pipeline-state.js`；铺设 `docs/lessons-learned.md`（工程教训）与 `docs/tech-debt-register.md`（技术债登记册，§10.7 分记约定）。
- 设计资产目录编号、发布目标（`release/` 配置、设计稿发布节点）按 `release-management` / `sync-design-to-publish` 的项目侧配置补齐。
- 若项目此前无设计资产，初始化会把各子技能模板铺出最小可用骨架，之后由对应子技能按需生成每一层数据。

## 版本

Bundle 版本以各子技能 frontmatter 的 version/lineage 为准；本父技能仅做编排，不含方法论自身条款。
