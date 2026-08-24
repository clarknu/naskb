# ACCEPTANCE — iterate（L1 自检）

- 日期：2026-08-23 ｜ 检查对象：`drafts/iterate/SKILL.md` vs 底座 `inbox/zy-ai-consult/iterate/SKILL.md`

| 检查项 | 方法 | 结果 |
|--------|------|------|
| L1-1 与底座 diff 仅含预期修改 | `git diff --no-index` | **PASS** — 共 7 个 hunk：①触发词「更新」移入修正组（修复之后）②从新增意图组移除③`- 不匹配` 加派发注记④frontmatter 追加 lineage+rulings⑤派发表存量修改行移出「更新…」并新增「修复…/更新…视范围而定」行⑥⑦「不匹配/遗漏/未同步/对不上/接口对不上」一行拆为单点→B、批量→C 两行。全部属于 R-002 回灌范围与血缘头 |
| L1-2 标题结构草稿 ⊇ 底座 | 提取 `^#{1,6} ` 标题做有序包含校验 | **PASS** — 底座 65 条标题全部按序包含于草稿（65=65） |
| L1-3 frontmatter 含 lineage | 正则检查（复核：首次脚本只读前 30 行致误报 FAIL，扩窗至 75 行复检通过） | **PASS** — sources: boxing=3665d6c3ebab, zy-iot-ai=949efb39d412, zy-ai-consult=37bd78e52cf1；`rulings: [R-002]` 存在 |
| L1-4 无凭空新造条款 | 逐 hunk 对照 boxing 原文 | **PASS** — 所有新增文本逐字取自 boxing（触发词行、注记、派发两行）；唯一非逐字处已在 MERGE-NOTES B3 披露：单点问题行保留 consult 关键词枚举全集（未同步/接口对不上）套入 boxing 判定结构，防止关键词失去条目 |

结构抽查：触发词区 `- 更新` 恰 1 次（位于修正组）；派发注记 ×1；单点 B 行 ×1、批量 C 行 ×1。
