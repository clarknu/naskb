# {{project-name}}

{{project-description}}

> **开发标准**：本项目遵循单人全栈开发标准 v3（项目 `.agents/skills/sfds/skills/development-standard/SKILL.md`）。
> 设计原则、代码规范、流程约定等全部方法论由标准文档定义，不再在本文件重复。
> **文档资产模式（全局）**：所有设计阶段面向人的文档产物一律为「渲染器 viewer.html + 数据 data/*.js」分离形态——数据文件是单一真相源，渲染器只管表现；新产物先过准入判定（`.agents/skills/sfds/_shared/document-asset-format.md`），禁止手写 Markdown 长文平行承载设计内容。
> **管线调度**：阶段推进/下一步/进度类问题 → `development-standard` 调度模式（读 `_shared/pipeline-registry.js` + `design/pipeline-state.js` 判定，含出口门禁核对）。

---

## ⛔ 第一优先级：Skill 强制调用（铁律）

<!-- BEGIN skill-table (generated from pipeline-registry.js; edit registry, not here) -->
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
