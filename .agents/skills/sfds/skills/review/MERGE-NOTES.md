# MERGE-NOTES — review（仲裁版草稿 · 含 R-001 裁决执行）

- 底座：`inbox/zy-ai-consult/review/SKILL.md`（`7527ea01ce6d`；相对 zy-iot-ai 版 `66091bfa03f0` 新增「架构契约机械校验」运行器条款）
- 参照：`inbox/boxing-competition-operation/review/SKILL.md`（`6ce1505add1f`）
- 草稿：`drafts/review/SKILL.md`
- 附带脚本：`scripts/smoke-test-miniprogram.mjs`、`scripts/validate-frontend-api-alignment.mjs`——三方哈希完全一致（`40887dbf6f5e` / `dfc5e75b6914`），草稿原样保留、未改动。

## 一、R-001 裁决执行（CASE-001）

- **扫描结果**：consult 底座中，将 ER→API 契约一致性检查委托给 `entity-relationship` 的条目共 **4 条**，全部位于 §2.3「ER 数据一致性」表：
  1. API 参数字段在 ER 中有定义且类型一致；
  2. ER 必填字段在 API 中是否有校验；
  3. ER 唯一约束在 API 中是否有校验；
  4. ER 与 API 枚举值集合一致。
- **修改**：4 条委托对象 `entity-relationship` → `api-design`（括注说明保留 consult 原文）；表格之后新增注记一行：「> 委托归属依据 CASE-001 裁决（2026-08-23）：API 契约一致性由契约所有者 api-design 执行。」
- **未动条目**（非 API 契约维度，逐一核对后确认不改）：
  - §2.2 工作流→ER 两行（实体覆盖/枚举值一致性检查）——委托 `entity-relationship` 属 ER 本体检查，继续保留；
  - §2.3 ER→ORM 四行（委托 `api-code-gen`）、ER→TDD 三行、ER→前端三行；
  - §1 输入清单中对 entity-relationship 数据文件的依赖声明（第 104/122 行）。

## 二、特殊指令②：`_shared/consistency-check-format.md` 引用核查

- boxing 版含两处 source 注册引用而 consult 版缺失：
  1. §2.1 末尾：source 取 §3 注册的 `raw-input-to-workflow` / `raw-input-to-er` / `raw-input-to-frontend`；
  2. §2.10 末尾：source 取 §3 注册的 `cross-level-trace`。
- 判定：**通用且 zy 缺失 → 回灌**。佐证：consult 系的 mobile-code-gen / desktop-code-gen 输出格式节均已引用 `_shared/consistency-check-format.md`，review 作为调度方补齐注册引用后体系自洽。
- 两段均按 boxing 原文复制插入，未改写。

## 三、三方处置表

| # | 差异点 | boxing | zy-iot / consult | 处置 | 依据 |
|---|--------|--------|------------------|------|------|
| 1 | ER→API 委托归属 | 已指向 `api-design`（§8.2 括注） | 指向 `entity-relationship` | 按 R-001 改派 `api-design` + 注记 | CASE-001 裁决 |
| 2 | consistency-check-format source 注册 ×2 | 有 | 无 | **回灌** | 明显通用且 zy 缺失 |
| 3 | 架构契约机械校验行（arch-contract 运行器） | 无 | 有（consult 相对 zy-iot 新增） | 以 consult 为准（保留） | zy 侧演进；boxing 无对应物 |
| 4 | 维度树表述 | 10 行未编号维度 | D0–D12 共 13 维显式编号 | 以 consult 为准 | 冲突 → consult |
| 5 | 触发点路由（低风险跳过 D5/D12，对齐 development-standard §9.2 触发点 A/B） | 有 | 无 | 不并入，✅已裁（R-007 定案：不回灌——development-standard 现行 §9.2 仅存触发点 C、A/B 已删，本技能正文无该引用，2026-08-23） | consult 改为七步流水线口径；标准侧条款已删，悬空引用就此消除 |
| 6 | D8 铁律措辞 | 「不执行 TDD 测试套件…静态校验脚本不属 TDD 测试，按 §2.12 直接运行」 | 「Review 自身不执行测试…由 tdd-execute 负责」 | 以 consult 为准 | 冲突 → consult |
| 7 | D5 覆盖率获取 | 解析 tdd-execute 产出的覆盖率报告（自身不跑测试） | 直接运行项目测试命令收集覆盖率 | ✅已裁（R-007 定案：修其它侧——§2.8.2 改为「读取 tdd-execute 覆盖率报告，自测不运行测试」，2026-08-23） | 与 D8 铁律「Review 自身不执行测试」对齐 |
| 8 | 报告缺字段兜底核对 | 「测试项目明细」缺失时以实际报告+测试目录核对并提示补模板 | 无 | **记待议** | 通用健壮性改进，但引用实例路径，泛化后并入为宜 |
| 9 | 收敛条件计数 | 「四个条件」（与列表自洽） | 「三个条件」却列 4 条 | ✅已裁（R-007 定案：修其它侧——§5.3 计数修正为「四个」，与所列 4 条自洽，2026-08-23） | 底座内部计数缺陷，按实列条目数修正 |
| 10 | TDD 文档路径 | `design/06-tdd/` | `design/07-tdd/` | 以 consult 为准 | 实例差异不回灌 |
| 11 | 项目配置文件名 | CLAUDE.md | AGENTS.md | 以 consult 为准 | 冲突 → consult |
| 12 | 脚本路径标注 | 「相对本 skill 目录 `.agents/skills/review/`」 | 「相对本 skill 目录」 | 以 consult 为准 | 实例差异不回灌 |
| 13 | 项目级复用脚本注记 | 无 | 有（Vue 3 + FastAPI 项目适配版优先复用） | 以 consult 为准 | consult 自有内容 |

## 待议清单汇总（4 项，其中 3 项已由 R-007 裁决关闭）

1. ~~**触发点路由**~~ ✅已裁（R-007 定案：不回灌，2026-08-23）：development-standard 现行 §9.2 仅存触发点 C，A/B 已删；本草稿正文无该引用，悬空引用就此消除。
2. ~~**D5 覆盖率获取方式 vs D8 铁律张力**~~ ✅已裁（R-007 定案：修其它侧，2026-08-23）：§2.8.2 覆盖率获取改为「读取 tdd-execute 覆盖率报告，自测不运行测试」，与 D8 铁律一致。
3. **报告缺字段兜底核对条款**：泛化路径表述后可并入，暂缓。
4. ~~**收敛条件计数矛盾**~~ ✅已裁（R-007 定案：修其它侧，2026-08-23）：§5.3 计数已修正为「四个条件」。

## R-007 补充核对（2026-08-23）

- **P-03 维度编号数量核对**：本草稿实际 D0–D12 编号——§1 流程总览「13个维度 D0-D12」、§2 引言「共 13 个维度（D0-D12）」、§7 完成检查清单「所有 13 个校核维度（D0-D12）」与 §2.0–§2.12 共 13 个小节逐一对应，全文一致、无 12/13 分歧。以 review 自身为准，正文无需改动。

## 实例差异不回灌清单（留项目侧）

- `.agents/skills/review/` 安装路径标注、`tests/test-reports/*-execute-report-*` 与 `*Tests.csproj` 核对细节。
- 小程序 harness 相关表述（boxing 侧已随其他差异排除）。
- Vue 3 + FastAPI 项目脚本适配注记（consult 自有，保留于底座，非回灌）。

## 血缘

frontmatter 已加 `lineage:`：origin: arb-hub、`rulings: [R-001]`、三方 sha256 前 12 位。除本文件所列处置外，正文与底座逐字一致。
