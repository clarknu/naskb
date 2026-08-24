# Review 目录变更记录

## 2026-08-24 — 存量接入初始基线

- 建立 `design/review/` 资产：`sync-status.js`（窗口 SYNC_STATUS，14 资产对初始状态）、
  `remaining-issues.md`（方法论类 M-01~M-06 + 差距类 G-01~G-10 + 待决 D-01~D-06）、
  `design-code-gap.md`（差异基线 14 项 + 未实现项 + 补全引入项）、`arch-contract/`（契约运行报告目录，latest.json 已生成）。
- 正式 Review（D0-D12）未执行：按方法论规则，待 tdd-execute（§8.8）全量执行后启动（trigger 点 C）。
- 状态：未收敛（初始基线，非复查报告）——本目录根文件为资产追踪件；正式复查报告按 review §4 格式另建。

## 2026-08-24 — 全量复查收敛（naskb-review-v1）

- **收敛判定**（4 条全满足）：① 全部问题 resolved（P-001/003/004 修复；P-002 用户拍板延期登记后续实现项；P-005 观察项；P-006 外部 wontfix）② tdd-execute 全量 381 passed / 1 skipped ③ 修复轮后无新增实质问题类别 ④ sync-status 无 dirty
- P-003 用户裁决 = 方案 A（实现 A'：显式要求条款级回退→level=summary+note；成功→level=chunk；契约/测试同步）
- P-004 用户拍板 = 设计与实现对齐：ER 补派生 VO（source_stats / folder_entry_view）
- 归档：naskb-review-v1.md → design/review/_archived/（根目录仅保留活跃文件）
