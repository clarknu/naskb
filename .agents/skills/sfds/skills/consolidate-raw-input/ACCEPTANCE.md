# ACCEPTANCE — consolidate-raw-input（L1 自检）

- 日期：2026-08-23 ｜ 检查对象：`drafts/consolidate-raw-input/SKILL.md` vs 底座 `inbox/zy-ai-consult/consolidate-raw-input/SKILL.md`

| 检查项 | 方法 | 结果 |
|--------|------|------|
| L1-1 与底座 diff 仅含预期修改 | `git diff --no-index` | **PASS** — 唯一 hunk 为 frontmatter triggers 尾部追加 lineage 块（+6 行），正文零改动。预期修改＝仅血缘头 |
| L1-2 标题结构草稿 ⊇ 底座 | 提取 `^#{1,6} ` 标题做有序包含校验 | **PASS** — 底座 43 条标题全部按序包含于草稿（43=43） |
| L1-3 frontmatter 含 lineage | 正则检查 | **PASS** — sources: boxing=cf0e999d5258, zy-iot-ai=a96ad5954050, zy-ai-consult=a96ad5954050 |
| L1-4 无凭空新造条款 | diff 全文核对 | **PASS** — 正文无任何新增/删除/改写条款；本次仲裁对该技能为 0 回灌，差异处置全部记录于 MERGE-NOTES 待议组 |

补充说明：zy-iot-ai 版与底座逐字节相同（SHA256 同为 a96ad5954050），故 sources 中两者哈希一致属预期。
