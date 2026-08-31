# ACCEPTANCE — release-management（L1 自检）

> 版本：v1.2.0-arb.1（2026-08-31，CASE-023/024）。
> 本次 L1 要点：§八 增 #18-20（多线并存+Nginx 生成器纪律／端口收敛三方核对／多环境共主机端口唯一）——项目专名（域名/端口/路径）均泛化为模式，无实例值；#17 与多线模型对齐（Tunnel=并存线非默认）。新增 §九 环境退役/停用（只停不删／红线表／归属勘察三分／先 stop 再 `--restart=no` 防复活／清单=唯一真相源），源自 consult decommission 实践泛化，命令示例项目中性。frontmatter/lineage 已更新；§六 过程资产与 §八 #1-17 未动。

---

- 日期：2026-08-23 ｜ 检查对象：`drafts/release-management/SKILL.md` vs 底座 `inbox/zy-ai-consult/release-management/SKILL.md`

| 检查项 | 方法 | 结果 |
|--------|------|------|
| L1-1 与底座 diff 仅含预期修改 | `git diff --no-index` | **PASS** — 共 2 个 hunk 区：①frontmatter 追加 lineage + `case: CASE-005`（+6 行）②§二 发布门禁表前适配说明引言（+4 行）与门禁表 G1/G2/G3/G5/G7/G8 六行通用化改写（G4/G6/G9 原文保留）。其余章节零改动 |
| L1-2 标题结构草稿 ⊇ 底座 | 提取 `^#{1,6} ` 标题做有序包含校验 | **PASS** — 底座 12 条标题全部按序包含于草稿（12=12） |
| L1-3 frontmatter 含 lineage | 正则检查 | **PASS** — `case: CASE-005` 存在；sources: zy-iot-ai=28bc8805eb1b, zy-ai-consult=e81304f0379e |
| L1-4 无凭空新造条款 | 门禁并集逐条对照两方原文 | **PASS** — 并集 9 条均来自两侧原文：通用要求句式为两侧说明的泛化重写，「示例（项目侧适配）」内命令逐字取自 consult 或 zy-iot 原文（推导见 MERGE-NOTES 第二节）；未引入任何一侧不存在的门禁或要求。G5 要求口径取 consult（强随机、不入库），zy-iot 固定 JWT_SECRET 实例仅存推导表 |

结构抽查：门禁行数 9（`| n |` 行）；「示例（项目侧适配）」出现 7 次；`case: CASE-005` ×1。
