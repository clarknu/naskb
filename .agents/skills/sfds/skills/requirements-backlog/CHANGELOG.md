# REQUIREMENTS-BACKLOG · CHANGELOG

## [0.1.0] - 2026-09-02
- **新生技能（CASE-032）**：需求积压/中远期暂存机制——面向"未排期的未来研发需求"的主链入口分诊环。
- 状态机：`捕获 → 暂存中远期 → 回顾 → 细化中 → 充分待做 → 纳入主链/走 iterate`；任一状态可转 放弃/长期搁置。
- 只维护项目侧过程资产 `docs/requirements-backlog.md`（+模板），不碰 `design/`、`src/`、`tests/` 资产。
- 需求方 2026-09-02 定案：独立轻 Skill、捕获与细化分两段（"细化中"为独立中间态）、命名 `requirements-backlog`、"细化充分"门槛=设计文档 §六 5 条（默认从严）。
- 与 `consolidate-raw-input`（向后整理当前设计讨论）语义正交；与 `iterate`（下游：想法充分后从它开始）分工。
