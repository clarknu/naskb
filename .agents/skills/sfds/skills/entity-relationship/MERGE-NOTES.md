# MERGE-NOTES — entity-relationship（仲裁版草稿）

- 底座：inbox\zy-ai-consult\entity-relationship\SKILL.md（sha256 前 12 位：284168bb484a）
- 三方关系：zy-iot-ai 版与 zy-ai-consult 版哈希完全相同；boxing 版多出约 33 行（追溯字段、一致性检查模式、CHANGELOG 格式行）
- 仲裁方向：内容冲突以 zy-ai-consult 为准

## 三方处置表

| 章节/内容 | boxing | zy-iot | zy-ai-consult | 处置 | 理由 |
|-----------|--------|--------|---------------|------|------|
| §2.6 Field 结构：`source` / `consumers` 追溯字段两行（引 development-standard §2.6，复查阶段 D1/D10 必填） | 有 | 无 | 无 | ✅已裁（R-007 定案：注明成立，2026-08-23） | 经核 development-standard §2.6 数据协议表已定义 ER 字段 `source`/`consumers`（§8.2 行），悬空引用解除；本技能正文无该引用，两行不回灌，字段级定义以标准为准 |
| 原 §3 一致性检查模式（工作流→ER 4 项检查、输入输出、review D2 委托、_shared/consistency-check-format.md） | 有 | 无 | 无 | ✅已裁（R-007 定案：一致性检查上收 review 成立，2026-08-23） | 跨资产校验由 review 统一调度；本技能不设独立一致性检查模式，正文规则表后已加注 |
| CHANGELOG 单行格式 + 示例（`- {YYYY-MM-DD} {类型} {域-slug}：{变更摘要}…`） | 有 | 无 | 无 | **待议** | consult 已保留必写要求（规则 7 + §7），仅缺格式模板；该单行格式与 business-workflow 的结构化 CHANGELOG 模板并存于 boxing，是否统一为枢纽级约定需仲裁 |
| 事件层级模板章号 | ## 4 | ## 3 | ## 3 | 以 consult 为准 | 因删除原 §3 整体前移重排 |
| 渲染器特性 / 编辑约束 / 设计原则 / CHANGELOG 规范章号 | §5–§8 | §4–§7 | §4–§7 | 以 consult 为准 | 同上，顺序重排 |
| 技能规则表规则 4「域注册表同步」 | 有 | 有 | 有 | 基座保留 | 三方一致，域注册表原则在本技能已存在 |

## 清单

### 已回灌
（无——boxing 的三处独有内容均因证据不足进入待议，未达「明显通用」标准）

### 不回灌 · 留项目侧
- 「域 07 事件基础设施」继承结构（platform/device/domain 事件族）为 IoT 设备域实例内容，但三方版本一致、属底座既有正文，不构成裁决点，仅备注其项目侧属性。

### 待议
1. ~~`source`/`consumers` ER 字段追溯定义是否恢复~~ ✅已裁（R-007 定案：注明成立，2026-08-23）：字段已在 development-standard §2.6 定义，本技能正文无该引用，两行 schema 不回灌。
2. ~~工作流→ER 一致性检查模式归属：留在本技能、上收 review，还是废弃~~ ✅已裁（R-007 定案：一致性检查上收 review 成立，2026-08-23）：由 review 统一调度，本技能不设独立一致性检查模式。
3. ER CHANGELOG 是否采用单行格式模板（见处置表第 3 行）。

## L1 相关事实
- 草稿对底座的唯一修改：frontmatter 增加 lineage 血缘头。正文零改动。
