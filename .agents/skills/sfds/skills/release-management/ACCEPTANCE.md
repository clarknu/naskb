# ACCEPTANCE — release-management（L1 自检）

> 版本：v1.1.0-arb.1（2026-08-30，CASE-014 教训回流 + 过程资产定义）。
> 本次 L1 要点：§八 教训回流为 17 条（A 14 + B 3），无项目专名硬编码（Dify/Cloudflare/命令/端口均泛化为「示例」）；§六 改为唯一过程资产 `deployment-config-guide.md`（含必记 ①-⑦/引用定义/文档 vs 密钥库边界），原 `release/`、`docs/ecs-deploy-design.md` 等陈旧引用已清零；交叉引用指向 `deployment-principles` 与 `credential-management`；frontmatter/lineage（reclaim: CASE-014）齐全。CASE-005 门的并集（§二）与红线/四层级/版本/回滚未动（沿用 v1.0.0-arb1 验收）。

---

- 日期：2026-08-23 ｜ 检查对象：`drafts/release-management/SKILL.md` vs 底座 `inbox/zy-ai-consult/release-management/SKILL.md`

| 检查项 | 方法 | 结果 |
|--------|------|------|
| L1-1 与底座 diff 仅含预期修改 | `git diff --no-index` | **PASS** — 共 2 个 hunk 区：①frontmatter 追加 lineage + `case: CASE-005`（+6 行）②§二 发布门禁表前适配说明引言（+4 行）与门禁表 G1/G2/G3/G5/G7/G8 六行通用化改写（G4/G6/G9 原文保留）。其余章节零改动 |
| L1-2 标题结构草稿 ⊇ 底座 | 提取 `^#{1,6} ` 标题做有序包含校验 | **PASS** — 底座 12 条标题全部按序包含于草稿（12=12） |
| L1-3 frontmatter 含 lineage | 正则检查 | **PASS** — `case: CASE-005` 存在；sources: zy-iot-ai=28bc8805eb1b, zy-ai-consult=e81304f0379e |
| L1-4 无凭空新造条款 | 门禁并集逐条对照两方原文 | **PASS** — 并集 9 条均来自两侧原文：通用要求句式为两侧说明的泛化重写，「示例（项目侧适配）」内命令逐字取自 consult 或 zy-iot 原文（推导见 MERGE-NOTES 第二节）；未引入任何一侧不存在的门禁或要求。G5 要求口径取 consult（强随机、不入库），zy-iot 固定 JWT_SECRET 实例仅存推导表 |

结构抽查：门禁行数 9（`| n |` 行）；「示例（项目侧适配）」出现 7 次；`case: CASE-005` ×1。
