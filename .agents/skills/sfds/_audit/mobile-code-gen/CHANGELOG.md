# CHANGELOG — mobile-code-gen（仲裁版草稿）

## 2026-08-23 · arb-hub 仲裁版草稿 v1

- 底座：zy-ai-consult 版（与 zy-iot-ai 版哈希一致：`58454bbc7d5b`）。
- 新增 frontmatter `lineage` 血缘头（boxing `56f84a5fbf62` / zy-iot-ai `58454bbc7d5b` / zy-ai-consult `58454bbc7d5b`）。
- 回灌 2 处（boxing → 草稿，原文复制）：
  - 「输入规格契约」blockquote（tree.js 字段以 mobile-app-design 为唯一 schema）；
  - 检查步骤新增第 7 步「@trace 注释完整性检查」，原第 7 步（枚举硬编码检查）顺延为第 8 步——补齐 consult 完成清单已有 @trace 要求但无检查步骤的内部缺口。
- 待议 3 项（未并入）：「布局合理化设计规范」整节及其 6 行清单项、missing_source/field_dropped/untraced_send 分级编码检查、tdd-build/tdd-execute 协同关系行。详见 MERGE-NOTES.md。
- 校验阻断策略（🔴 拒绝生成 vs ⚠️ 不阻塞+review 兜底）按规则以 consult 为准。
