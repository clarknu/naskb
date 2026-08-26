---
name: sfds
description: "单人全栈开发标准（SFDS）方法论 · 联邦仲裁版。**本项目所有开发方法的唯一入口**：任何开发、设计、编码、测试、复查、迭代、发布、调试行为，只要涉及工作流/ER/API/架构/页面设计、代码生成、TDD、复查、迭代、发布、设计稿发布、小程序自动化等，一律先经本技能路由——内部按能力域以子技能组织（skills/<能力>/SKILL.md + 内置模板），读取对应子技能并按它的「触发条件→执行流程→输出格式」执行。迁移只需整体复制本文件夹；不把技能平铺到项目顶层。"
whenToUse: "任何时候，只要工作与项目研发相关：项目初始化、业务设计、ER/API/架构/页面设计、后端或端代码生成、测试设计/执行、全量复查、功能迭代、Bug 修复、联调、发布、设计稿发布、小程序自动化调试，或询问『按什么标准开发/下一步做什么』——都应先加载本技能并按其路由。若尚未触发，先调用技能工具加载本文件。"
lineage:
  origin: arb-hub
  case: CASE-011
  note: NASKB 试行版：父技能+子技能单目录打包，迁移即整夹复制。bundle 内所有 `.agents/skills/…` 路径（子技能正文、模板、共享规范、脚本输出）一律解释为 `<本文件夹>/…`（本项目即 `.agents/skills/sfds/…`），即 `.agents/skills/_shared/…` → `.agents/skills/sfds/_shared/…`、`.agents/skills/<skill>/…` → `.agents/skills/sfds/skills/<skill>/…`；`~/.agents/skills/…`（全局分发）保持原样。
  children: 18
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
| 原始输入整理 / 需求归档 / 整理原始需求 | `consolidate-raw-input` |
| AI 工作流设计 / 编排设计 / Dify / 自定义节点 | `ai-workflow-orchestration-design` |
| 微信小程序自动化 / 小程序调试 / wechatide | `wechatide-automation` |

> 微信开发者工具本体（wechatide）是**外置工具**（随 DevTools 单向同步），不在 bundle 内置；`wechatide-automation` 说明的是"有该外置工具→可做自动化+做法 / 无该工具→做不了、需补充"的判定与用法。
> 上表为代表性路由；每个子技能的**完整触发词集合见其 frontmatter 的 `triggers`**。若用户话术未命中，打开子技能 `skills/<name>/SKILL.md` 看它的「触发条件」章节再定。

## 使用规则（怎么"用"一个子技能）

1. **定位**：按上表路由到子技能目录 `skills/<name>/`。
2. **读取全文**：读 `skills/<name>/SKILL.md` 的完整正文——它的 frontmatter（name/description/triggers）在 bundle 模式下只是元数据（不自动触发），**真正要执行的是它正文里的「触发条件 → 执行流程 → 输出格式」**。
3. **按其执行**：遵循该子技能给出的步骤、命令、输出；需要模板/数据时引用同目录下的资源。
4. **设计资产落地**：子技能内置的模板（viewer.html、data/*.js、域注册表/pipeline-state 等）在首次使用时**物化到项目 `design/` 对应编号目录**（由 `development-standard` 初始化流程统一铺设骨架）。方法论升级必须连同这些资产更新（见其 frontmatter `assets`）。
5. **共享层（全 bundle 通用路径约定）**：`_shared/`（pipeline-registry.js、document-asset-format.md、arch-contract-spec.md、consistency-check-format.md 等）被相关子技能引用；bundle 模式下**正文/模板/共享规范/脚本输出**中的 `.agents/skills/…` 一律解释为 `<本文件夹>/…`（本项目 = `.agents/skills/sfds/…`）——即 `.agents/skills/_shared/…` → `.agents/skills/sfds/_shared/…`、`.agents/skills/<skill>/…` → `.agents/skills/sfds/skills/<skill>/…`；`~/.agents/skills/…`（全局分发）保持原样。
6. **审计/裁决件**：各子技能的 MERGE-NOTES / ACCEPTANCE / CHANGELOG 已移到 `_audit/<能力>/` 下，供查证该能力域的三方分歧与仲裁结论，不参与运行。

## 项目首次接入（初始化）

- 先执行 `development-standard` 子技能的**项目初始化**流程：生成 `AGENTS.md`、`design/` 骨架（01~07，模板在 `skills/development-standard/templates/`）、`domain-registry.js`、`pipeline-state.js`。
- 设计资产目录编号、发布目标（`release/` 配置、设计稿发布节点）按 `release-management` / `sync-design-to-publish` 的项目侧配置补齐。
- 若项目此前无设计资产，初始化会把各子技能模板铺出最小可用骨架，之后由对应子技能按需生成每一层数据。

## 版本

Bundle 版本以各子技能 frontmatter 的 version/lineage 为准；本父技能仅做编排，不含方法论自身条款。
