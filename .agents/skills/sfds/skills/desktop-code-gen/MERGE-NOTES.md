# MERGE-NOTES · desktop-code-gen 三方合并记录

> 批量生产组2产出 · 底座 inbox/zy-ai-consult@2026-08-23 · 补录于 2026-08-23（枢纽全量复核发现本文件缺失，依据实际 diff 与生产简报补写）

## 三方处置表

| 内容 | boxing | zy-iot | zy-ai-consult（底座） | 处置 |
|---|---|---|---|---|
| tree.js 输入规格契约节点字段说明（refEntity/refFields/page_input/page_output/api_ref/sends；缺失先回上游） | 有 | ≡ consult | 无 | **✅ 回灌**：与已回灌的 mobile-code-gen 版同构，补齐"有要求无步骤"缺口；零技术栈实例 |
| tdd 协同关系行（与 tdd-build 的衔接表述差异） | 有变体（Web Stage 2 措辞） | ≡ consult | 另一种表述 | ✅已裁（R-007 定案：选其它——按通用表述并入关系表，去实例措辞，2026-08-23），与 mobile-code-gen 同批同口径 |
| 技术栈实例（WPF/Electron 框架名、启动命令、目录示例） | boxing 实例 | ≡ consult | consult 实例 | 留项目侧（AGENTS.md 读栈原则不变） |

## 血缘核验

- zy-iot 与 zy-ai-consult 哈希一致（a60ddf36c67a）——底座即两方共同状态；
- boxing 独有差异经逐段核对仅上述两项具备讨论价值。

## L1 复核结论

与基座 diff = 10 insertions / 0 deletions：lineage 块（6 行）+ 输入规格契约 callout（含空行）。无删除、标题集合为基座超集。
（R-007 补记 2026-08-23：另 +1 行——关系表并入通用表述的 `tdd-build` / `tdd-execute` 协同行，当前 diff = 11 insertions / 0 deletions。）
