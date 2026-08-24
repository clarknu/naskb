# NASKB 项目指令（AGENTS.md）

> 本文件由 DSH 在每个会话中作为持久基线注入（Instruction from: AGENTS.md）。
> 冲突时：特定指令 > 宽泛指令；项目内的具体规则 > 本节通用规则。

## 方法论铁律（最高优先级）

1. **本项目采用 SFDS 方法论（仲裁版）**，唯一入口是技能 `.agents/skills/sfds`（父技能 `sfds`）。
2. **每次会话的任何研发行为，先加载 `sfds` 并按其中的「触发词路由」定位到子技能**，读取
   `skills/<能力>/SKILL.md` 后按其「触发条件→执行流程→输出格式」执行。
3. **禁止绕过方法论**：未加载 `sfds` 就修改 `design/`、`tests/`、`src/`、`naskb/` 关键结构等，
   一律视为违规；需要先说明将走哪个能力域的子技能。
4. 设计资产必须服从 `sfds` 子技能的模板与格式（viewer + data/*.js，可 diff 可回滚）；
   方法论升级必须连同资产一起更新。
5. 若 `sfds` 未在技能目录中出现（异常状态），先向用户报告，不得自行替代执行。

## 提交纪律（R-009）

- 任何一次改动直接 `git commit` 并推送（本地不变更就要进版本库）；对外发布由用户决定；
  不强制语义化版本，只要求所有改动都落实到版本上（见 development-standard §5.1）。

## 快速路由（详见 sfds 父技能）

| 意图 | 子技能（sfds/skills/<name>/SKILL.md） |
|---|---|
| 初始化/标准/调度 | development-standard |
| 业务/ER/API/架构设计 | business-workflow / entity-relationship / api-design / backend-architecture-design |
| 页面/代码生成 | mobile-app-design / desktop-ui-design / api-code-gen / mobile-code-gen / desktop-code-gen |
| 测试/复查/迭代 | tdd-build / tdd-execute / review / iterate |
| 发布/设计稿发布 | release-management / sync-design-to-publish |
| 小程序自动化 | wechatide-automation |
| 任务编排（若干任务队列） | pipeline-controller |

> 手动兜底：会话中可直接说「按 SFDS 方法论处理」或输入 `sfds` 触发父技能加载。
