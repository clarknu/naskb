# CHANGELOG · development-standard（仲裁版）

## 3.2.0-arb.1 — 2026-08-31（CASE-025）

从 zy-ai-consult 回收「技术债登记册 + 教训/债务分记」（需求方确认升为方法论约定）：

- **新增 §10.7 技术债登记（教训/债务分记）**：三分记（lessons-learned 工程教训 ∥ tech-debt-register 主动推迟的设计债 ∥ arch-contract knownDebts 契约豁免）；铁律"登记≠不做，登记=钉住"；有效性判据（缺待还方向/触发条件=无效）；登记流程（当轮登记 TD-xxx，迭代/复查顺带过表，命中触发条件转待办）。
- **§1.2 目录树 / §1.6 初始化摘要**：新增 `docs/lessons-learned.md` + `docs/tech-debt-register.md`（模板铺设）。
- **新增模板** `templates/tech-debt-register.md.template`（登记表 + TD 条目结构：结论/背景判断/暂缓原因/待还方向/触发条件/状态流水）。

## 3.1.0-arb.1 — 2026-08-23

CASE-002 仲裁版首次产出。

- **基座**: zy-ai-consult v3.0.0（inbox 快照 @2026-08-23）
- **回灌**（来自 boxing v1，共 3 项）:
  - 新增 §5.0 Skill 通用执行契约（强制）
  - 新增 §4.1 末尾一致性检查格式共享规范引用（`_shared/consistency-check-format.md`）
  - 新增 §8.5 覆盖率口径（唯一权威定义）
- **拒绝回灌**: 复查触发点 A/B（consult 有意下沉至 code-gen 后置检查，理由成立）
- **frontmatter**: version 3.0.0 → 3.1.0；新增 lineage 块（origin: arb-hub, sources 三方基线哈希）
- 详见 MERGE-NOTES.md
