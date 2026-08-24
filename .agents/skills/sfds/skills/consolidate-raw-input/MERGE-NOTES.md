# MERGE-NOTES — consolidate-raw-input（仲裁版）

- 日期：2026-08-23 ｜ 底座：`inbox/zy-ai-consult/consolidate-raw-input/SKILL.md`（a96ad5954050）
- 三方关系：zy-iot-ai 与 zy-ai-consult 逐字节相同（SHA256 同为 a96ad5954050）；差异全部来自 boxing 一侧。

## 一、处置表（boxing → consult 全部差异）

| # | boxing 差异内容 | 处置 | 理由 |
|---|----------------|------|------|
| B1 | 「本技能目标」后新增 ⚠️ 与 development-standard §7.2 的边界 blockquote：本技能从不修改/删除原文，原文字节级原样移入 original-logs/ 并保留原时间戳，整合文档是当前结论视图，review §7 检查针对 original-logs/ 原文 | 不回灌，✅已裁（R-007 定案：不回灌——语义已被红线覆盖，2026-08-23）（原组①） | 核心不变量并非缺失：底座红线 #4「不修改原始文件内容」、步骤 8「移动（不是复制）」、红线 #3 Git 安全检查已覆盖同语义；且注记绑定 development-standard §7.2 / review §7 的项目框架编号，通用化需改写正文 |
| B2 | 前置步骤读 `AGENTS.md` / `CLAUDE.md`（consult 仅 `AGENTS.md`） | 不回灌 | 技术栈实例，冲突以 consult 为准 |
| B3 | 步骤 6.1 文档头注扩写：逐条决策原文与时间戳见 original-logs/，review §7 检查针对原文 | ✅已裁（R-007 定案：不回灌，2026-08-23）（原组①，随 B1 绑定裁决） | 同 B1：依赖 review §7 编号；语义已被「原始讨论记录见 original-logs/」+ 红线覆盖 |
| B4 | 写作原则表新增「原文完整性」行（绝不修改/删除原文，归档保持字节级原样含时间戳） | ✅已裁（R-007 定案：不回灌，2026-08-23）（原组①，随 B1 绑定裁决） | 语义已被底座红线 #4 覆盖，不再整组落地 |
| B5 | 清理与归档的 manifest 设计分叉：boxing 将 `_archive-manifest.md` 置于 `{raw-input-dir}` 根目录（与整合文档同级）、按 `## {YYYY-MM} 批次` 追加历史链、表头含「归档文件/原位置/归档日期/说明」；清理安全检查要求 git status 输出为空（manifest 在根目录故不受清空影响）。consult 将 manifest 置于 original-logs/ 内、单表格式「创建或更新」、清理时允许仅 manifest 改动并跳过删除 manifest | ✅已裁（R-007 定案：不回灌——保留 consult 的 original-logs/ 内单表设计，2026-08-23）（原组②） | 两地各自自洽的行为设计分叉；按"非 Boxing 优先"选 consult 设计（original-logs/ 内单表） |
| B6 | 目录树示意与步骤 8 第 4 步确认清单随 B5 相应差异 | 待议（组②，随 B5 绑定裁决） | 随 B5 |

## 二、三类清单

- **已回灌**：0 项
- **待议**：1 组（组②＝B5+B6 归档清单位置与批次链设计）；~~组①＝B1+B3+B4 原文不可变边界注记~~ ✅已裁（R-007/P-13 定案：不回灌——语义已被红线覆盖，2026-08-23），正文零改动
- **挂起**：0 项

> 备注：台账 `arbitration/pending-items.md` 显示 P-14（组②）亦已于 2026-08-23 定为不回灌，但非本次任务范围，本文件未改动组②状态，留枢纽统一收口。

## 三、结论

SKILL.md 正文零修改，仅在 frontmatter 内新增 lineage 血缘头。
