# CHANGELOG — tdd-build（仲裁版草稿）

## 2026-08-23 · arb-hub 仲裁版草稿 v1

- 底座：zy-ai-consult 版（与 zy-iot-ai 版哈希一致：`c16853e0c671`）。
- 新增 frontmatter `lineage` 血缘头（boxing `7b1586e18413` / zy-iot-ai `c16853e0c671` / zy-ai-consult `c16853e0c671`）。
- 回灌 3 处（boxing → 草稿，原文复制/配套）：
  - §6 新增第 4 步「fixture 一致性检查」（设计声明 ↔ 测试代码 fixture 对照），原第 4/5 步顺延为第 5/6 步；
  - 问题类型枚举增加 `fixture_mismatch`；
  - §2.1 规则 #3 追加「按 §2.5 复杂度分级裁剪」括注（§2.5 在底座中存在，引用有效）。
- 待议 2 项（未并入）：「目录说明（.NET 实例）」blockquote 组（含 Stage1/3 按用例层级门控理念）、Stage 2b 完成清单 MCG-L1~L6 布局检查行。详见 MERGE-NOTES.md。
- wechatide harness 本地扩展判定为 boxing 项目侧扩展，不回灌。

## 2026-08-24 · arb-hub 修复回填

- 一致性检查输出对齐（M-06）：§6.4 输出结构改为共享 `consistency-check-format.md` §1 结构（summary 用 `end_slug/total_scanned/total_issues/high/medium/low`；issues 增 `source:"tdd-to-code"`、`ref_path`）；共享 §2 注册表登记全部 type（`missing_*_test`/`fixture_mismatch`/`compile_error`/`architecture_contract_missing`/`untraced_tc`/`trace_chain_broken`/`orphan_tc`）。
- boxing 回填 §4b（Stage 2b 小程序）：执行流改为 harness 自动拉起（`harness up/down`）+ 工具名位置参数（禁用 `-t`）+ 截图用 `simulator_screenshot`，对齐 `wechatide-automation`；工具速查表增「自动拉起」行、`open_project_window` 标注为未走 harness 的 fallback。
