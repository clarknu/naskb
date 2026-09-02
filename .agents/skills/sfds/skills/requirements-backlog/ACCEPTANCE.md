# REQUIREMENTS-BACKLOG · ACCEPTANCE

- 技能：REQUIREMENTS-BACKLOG（主链入口之前的"需求管理分诊环"）
- 来源：本枢纽**新生技能**（CASE-032，无跨项目分叉、无需仲裁版，R-006：只进 packages 不进 drafts）
- 版本：0.1.0
- 定位：L2 方法论主链前端（输入卫生之后、主链入口之前的需求管理环），常驻旁路（stage=bypass）

## 接受范围

| 项 | 结论 |
|---|---|
| 是否入册（pipeline-registry.js） | ✅ 已登记，非方法论孤岛 |
| 是否有脚本/工具 | 否——纯登记册（`docs/requirements-backlog.md`），零外部依赖 |
| 状态机 | 捕获 → 暂存中远期 → 回顾 → 细化中 → 充分待做 → 纳入主链/走 iterate；任一状态可转 放弃/长期搁置 |
| 捕获/细化 | **分两段**（需求方定案）：捕获只记录；细化是回顾后一次独立动作，"细化中"为独立中间态 |
| 唯一过程资产 | `docs/requirements-backlog.md`（项目填内容；模板 = `templates/requirements-backlog.md.template`） |
| 红线 | 只读写登记册 + `design/CHANGELOG.md` 记账一笔；绝不 Read→Edit→Write `design/`、`src/`、`tests/` 资产；把已细化需求交给 iterate/主链时只做交接、不代为执行 |
| 细化充分门槛 | 设计文档 §六 5 条，**默认从严**（需求方定案） |

## 已知边界 / 需后续完善

- 纯登记册机制，无脚本/自动化（有意为之：作为薄入口，避免空壳重技能）。
- "细化充分"门槛默认从严，实际使用中可能需按项目放宽（登记册支持逐条标注，不锁死）。
- 交接给 iterate/主链的具体排期由用户确认，技能不自动排期。

## 验收状态

- **L1 静态验收 ✅（2026-09-02）**：frontmatter 结构/lineage（CASE-032）/triggers 齐全；注册表 `pipeline-registry.js` 与技能目录一致（`requirements-backlog` 已登记 `layer=基础, stage=bypass, priority=0, 17 触发词`）；模板无实例值（grep 智能床/boxing/zy-/IPv4/端口 全为零）；模板必填 schema 字段（RB-/状态/登记日期/标题/原始描述/来源/细化记录/关联链路/状态流水/细化充分判定）齐全。
- **L2 加载测试 ✅（2026-09-02，sandbox 模拟 DSH discoverRoot）**：`discoverRoot` 扫 `.agents/skills/` 顶层仅发现 `sfds` 父技能（无嵌套泄漏）；父技能路由表命中 `requirements-backlog`；子技能 `skills/requirements-backlog/SKILL.md` 存在；children=21；frontmatter 正确（version 0.1.0）。测完即删 sandbox `.agents` 副本。
- **L3 沙盒推演 ✅（2026-09-02，`sandbox/_shared/l3-requirements-backlog.mjs`，13/13 通过）**：技能引用的每个路径存在（bundled 模板 / 下游 business-workflow / iterate）；首次接入从模板铺设 `docs/requirements-backlog.md` 成功；登记册 schema 字段完整；状态机全状态枚举 + 各瞬态有迁移出口；细化充分门槛 §三 5 条齐全；捕获与细化分两段（细化中独立状态）；交接边界正确（只读写登记册 + design/CHANGELOG 记账，不碰 design/src、不代为执行）。
- **L4 真项目试点**：待某自愿项目首采（`docs/requirements-backlog.md` 铺设 + 捕获/回顾/细化/纳入全流程实测）。
