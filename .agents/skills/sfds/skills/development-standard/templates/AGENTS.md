# {{project-name}}

{{project-description}}

> **开发标准**：本项目遵循单人全栈开发标准 v3（项目 `.agents/skills/sfds/skills/development-standard/SKILL.md`）。
> 设计原则、代码规范、流程约定等全部方法论由标准文档定义，不再在本文件重复。
> **文档资产模式（全局）**：所有设计阶段面向人的文档产物一律为「渲染器 viewer.html + 数据 data/*.js」分离形态——数据文件是单一真相源，渲染器只管表现；新产物先过准入判定（`.agents/skills/sfds/_shared/document-asset-format.md`），禁止手写 Markdown 长文平行承载设计内容。
> **管线调度**：阶段推进/下一步/进度类问题 → `development-standard` 调度模式（读 `_shared/pipeline-registry.js` + `design/pipeline-state.js` 判定，含出口门禁核对）。

---

## ⛔ 第一优先级：Skill 强制调用（铁律）

<!-- BEGIN skill-table (generated from pipeline-registry.js; edit registry, not here) -->

> **任何任务，只要其意图与下表触发词匹配，必须先调用对应 Skill，按技能规定的流程推进工作。**
> **禁止**在未加载 Skill 的情况下直接对 `design/` 或 `src/` 做 Read→Edit→Write 操作。
> 本表由 `.agents/skills/sfds/_shared/pipeline-registry.js` 生成（`node .agents/skills/sfds/_shared/gen/generate-trigger-table.mjs --write`），勿手编。

| 触发词 | 技能 | 层 | 一句话 |
|--------|------|----|------|
| 标准、方法论、项目初始化、SFDS、下一步、继续、当前进度、该做什么、拿不准、流程状态、新项目、项目启动、项目骨架、**new project** | `development-standard` | 基础 | SFDS v3 全标 + 新项目初始化 + **调度模式** |
| 整理原始输入、合并原始需求 | `consolidate-raw-input` | 基础 | 原始输入整合归档 |
| 迭代、更新、调整、修改、改一下、加功能、新增、重构、变更、修 bug、报错、500、崩溃、测试失败、不对、有问题、少了、缺了、错误、问题、修复、bug、诊断、问题排查、根因分析、联调、联调修正、集成调试、前后端对接、不匹配、遗漏、未同步、对不上、整体检查 | `iterate` | 编排 | 功能迭代 + Bug 修复 + 联调批量修正的统一级联编排器 |
| 业务设计、工作流、状态机 | `business-workflow` | 设计 | 业务梳理与流程设计 |
| ER 图、实体关系、数据建模 | `entity-relationship` | 设计 | 实体关系图设计 |
| API 设计、接口设计、**REST API** | `api-design` | 设计 | API 契约设计 |
| 后端架构设计、分层设计、模块边界、架构审计、全量分析 | `backend-architecture-design` | 设计 | 架构与服务体系设计 |
| 页面设计、移动端设计、小程序设计、App 设计、PC 端设计、桌面端设计、后台设计、**Web 后台设计** | `client-ui-design` | 设计 | 客户端页面功能设计 |
| 工作流编排、编排设计、**Dify 流程设计**、节点走向、会话隔离 | `ai-workflow-orchestration-design` | 设计（团队） | AI 工作流编排设计六原则 P1-P6 |
| TDD 设计、测试设计、写测试、API 测试、页面测试、集成测试 | `tdd-build` | 验证 | TDD 测试设计与编码 |
| TDD 执行、运行测试、测试报告、跑测试 | `tdd-execute` | 验证 | TDD 测试执行与验证 |
| 复查、一致性检查、全量复查 | `review` | 验证 | 多维度全项目复查 |
| **API 代码生成**、后端代码 | `api-code-gen` | 实现 | 服务端代码生成与一致性检查 |
| **客户端代码生成**、页面代码生成、前端代码、**移动端代码生成**、**桌面端代码生成**、后台代码、**Web 前端代码** | `client-code-gen` | 实现 | 客户端代码生成 |
| 发布设计文档、**同步设计文档到 publish** | `sync-design-to-publish` | 工具 | 设计文档同步到 publish/ 并部署 Cloudflare Pages |
| 发布线上、上线、发版、部署线上、发布流程、发线上、更新到线上、版本号、打 tag、回滚、环境切换、预发布、环境退役、停用环境、下线环境、**decommission** | `release-management` | 工具 | 发布管理方法论 |
| **微信开发者工具**、小程序预览、小程序调试 | `wechatide-automation` | 工具 | 微信开发者工具 |
| 密钥管理、密钥库、访问凭据、访问令牌、API 密钥、**API Key**、敏感配置、加密配置、部署密钥、环境变量注入、凭据管理、**credentials**、**access token**、**api key** | `credential-management` | 工具 | 项目加密密钥/配置库 |
| 部署环境、环境模型、环境架构、环境拓扑、预发布环境、预发环境、生产环境、线上环境、环境规范、子网、网络转发、Mock、数据隔离、同库主机、库名不同、逻辑隔离、环境隔离、部署架构、中间件、公共服务、宿主化、独立实例、数据库实例、**Redis 缓存**、**docker compose 自建**、部署原则、环境配置、服务隔离、网络拓扑、网络分层、宿主端口、**Docker 网络**、Nginx、反向代理、内网、公网、域名映射 | `deployment-principles` | 原则 | 部署总原则 |

<!-- END skill-table -->

> **匹配规则**：用户输入中包含左列任一关键词 → 立即调用对应 Skill。多技能匹配时按"编排 > 设计 > 验证 > 实现"优先级选择。
> **违规信号**：在没有调用 skill 的情况下直接 Read→Edit→Write `design/` 或 `src/` 文件。
> 技能定义见 `.agents/skills/sfds/skills/{skill-name}/SKILL.md`（项目级技能统一存放于项目工作空间 `.agents/skills/sfds/`）。

---

## 项目概况

| 维度 | 说明 |
|------|------|
| **目标用户** | {{target-users}} |
| **运行环境** | {{environment}} |
| **技术栈** | {{tech-stack}} |
| **技术栈状态** | {{tech-stack-note}} |

## 领域定义

本平台业务领域定义见 [`design/domain-registry.js`](design/domain-registry.js)——域注册表文件，
在初始域范围界定阶段创建初版，随流水线执行持续演进，为各步骤提供 `{domain-slug}` 参数。

## 管线状态

当前所处阶段/门禁证据见 [`design/pipeline-state.js`](design/pipeline-state.js)——调度模式数据源，随阶段推进更新（推进必须有 exitGates 证据，状态必须落盘）。
