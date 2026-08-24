---
name: sfds
description: "单人全栈开发标准（SFDS）方法论 · 联邦仲裁版。本技能是整套研发方法论的入口（父技能），内部按能力域以子技能组织（skills/<能力>/SKILL.md + 内置模板），迁移只需整体复制本文件夹。被触发后，按下方触发词路由到对应子技能，读取其 SKILL.md 并按它的「触发条件→执行流程→输出格式」执行；设计资产随子技能内置模板落地到项目 design/，共享资产在 _shared/。"
whenToUse: "用户要进行任何开发方法论相关操作时：项目初始化、业务/ER/API/架构/页面设计、后端或端代码生成、TDD 测试设计与执行、全量复查、功能迭代与 Bug 修复、发布管理、设计稿对外发布，或询问『按什么标准开发』。"
lineage:
  origin: arb-hub
  case: CASE-011
  note: NASKB 试行版：父技能+子技能单目录打包，迁移即整夹复制。子技能正文内的 .agents/skills/_shared/… 一律解释为 <本文件夹>/_shared/…。
  children: 20
---

# SFDS 方法论（仲裁版，父技能入口）

本文件夹 = **整套研发方法论**。只有本 `SKILL.md` 被框架直接发现；各能力域以子技能放在 `skills/<能力>/SKILL.md`（含内置模板/脚本）。**父技能负责路由与调度，子技能承载具体方法论**——迁移 = 整体复制本文件夹；升级 = 替换子技能。

> 不在项目 `.agents/skills/` 顶层平铺，避免同名分叉污染，并保证迁移是「一个文件夹的事」。

## 触发词路由（用户话术 → 子技能）

| 用户意图（代表性触发词） | 子技能 |
|---|---|
| 初始化项目 / 项目骨架 / SFDS / 标准 / 方法论 / 下一步 / 当前进度 | `development-standard` |
| 业务设计 / 工作流 / 流程 / 状态机 / 业务规则 | `business-workflow` |
| ER 图 / 实体关系 / 数据建模 / 领域建模 | `entity-relationship` |
| API 设计 / 接口 / REST / 路由设计 / 端点 | `api-design` |
| 后端架构 / 架构模式 / 分层 / 模块边界 / 服务拓扑 | `backend-architecture-design` |
| 移动端/前端画面设计 / TabBar / 页面功能 | `mobile-app-design` |
| PC/桌面端页面设计 / 后台页面 | `desktop-ui-design` |
| 后端代码生成 / API 实现 / ORM 生成 | `api-code-gen` |
| 移动端代码生成 / 页面代码生成 | `mobile-code-gen` |
| 桌面端代码生成 / PC 代码生成 | `desktop-code-gen` |
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
5. **共享层**：`_shared/`（pipeline-registry.js、document-asset-format.md、arch-contract-spec.md、consistency-check-format.md 等）被相关子技能引用；bundle 模式下子技能正文的 `.agents/skills/_shared/…` 一律解释为 `<本文件夹>/_shared/…`。
6. **审计/裁决件**：各子技能的 MERGE-NOTES / ACCEPTANCE / CHANGELOG 已移到 `_audit/<能力>/` 下，供查证该能力域的三方分歧与仲裁结论，不参与运行。

## 项目首次接入（初始化）

- 先执行 `development-standard` 子技能的**项目初始化**流程：生成 `AGENTS.md`、`design/` 骨架（01~07，模板在 `skills/development-standard/templates/`）、`domain-registry.js`、`pipeline-state.js`。
- 设计资产目录编号、发布目标（`release/` 配置、设计稿发布节点）按 `release-management` / `sync-design-to-publish` 的项目侧配置补齐。
- 若项目此前无设计资产，初始化会把各子技能模板铺出最小可用骨架，之后由对应子技能按需生成每一层数据。

## 版本

Bundle 版本以各子技能 frontmatter 的 version/lineage 为准；本父技能仅做编排，不含方法论自身条款。
