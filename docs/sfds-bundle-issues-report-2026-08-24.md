# SFDS 方法论 Bundle 问题报告

> **来源项目**：NASKB 知识库系统（存量项目 SFDS 全量接入，2026-08-24）
> **对象**：`.agents/skills/sfds`（仲裁版 bundle，父技能 + 20 子技能 + `_shared/`）
> **实测方式**：完整读取全部子技能 SKILL.md/模板/共享规范（10 份消化报告 + 逐文件核对），
> 并在真实项目上跑通：架构契约运行器（node run.mjs + Python 静态探针，退出码 0）、
> pytest 门禁（356 passed）、5 个 viewer Playwright file:// 渲染核实（0 console error）。
> 六项主问题均在本项目接入中**实际触发**，非理论推演；每项附定位（文件+行号）与修复建议。
> 归档：本项目 `design/review/remaining-issues.md` 已登记（M-01~M-06），本报告为其完整版。

---

## 主问题清单（M-01 ~ M-06）

### M-01：api-viewer.html 实际为 REST-only，协议/AI Tools 视图未落地（且与 SKILL 承诺脱节）

**定位**：
- `skills/api-design/templates/api-viewer.html`（全文仅处理 `window.API_DATA` 与 `window.API_CONVENTIONS`，无 `IOT_DATA`/`protocol-*` 渲染路径）
- `skills/api-design/SKILL.md` L393「数据文件 `data/ai-tools/tools.js`，协议定义 `data/ai-tools/protocol.js`，**Viewer 注册第三个 Tab**」；L320 自称「以下模式已在 api-viewer.html 参考实现中验证」；§4.5 协议定义文件挂载 `window.API_DATA["protocol-{id}"]`

**现象**：
1. viewer 无协议 Tab/三级 hash 路由/流式 RPC 渲染（SKILL §9 描述的能力在模板中不存在）；
2. 若按规范把 `protocol.js`、`ai-tools/protocol.js` 经 `data/loader.js` 加载，viewer 会把每个 `API_DATA` 键当作「领域」加入左上角域下拉（`initDomainSelect` 用 `(d.domain||'') + ' — ' + d.title`），协议文件无 `domain/title` → 下拉出现 `— undefined` 且协议内容无渲染路径；
3. 检查清单（SKILL §6.3/6.4 末尾）写「Viewer `dataFiles` 数组注册新文件」，viewer 实际无 `dataFiles` 数组机制（用 `data/loader.js` 注入）。

**本项目处置**（佐证）：NASKB 的 MCP（14 工具）只能以 `data/ai-tools/{protocol,tools}.js` 纯数据文件交付（`window.AI_TOOLS_DATA`，命名空间为本项目声明），**无渲染视图**，人工以数据文件查阅；REST `protocol.js` 未注册进 loader（避免污染域下拉）。

**影响**：API 设计资产的**第三类协议（IoT/AI Tools）无法人读**；`协议无关`的方法论主张在交付物层断链；新增协议项目必然重复踩坑（本项目已在 remaining-issues 登记 G/公开）。

**修复建议**：
- 方案 A（推荐）：把 SKILL §9 描述的实现真正落地进 `api-viewer.html`（协议 Tab + `sections`/`protocolContent`/`envelopeContent` 渲染 + `dataFiles` 或 loader 子目录约定），并把 §6.3/6.4 检查清单的「dataFiles」改成与实际一致的表述；
- 方案 B（最小）：**降级文档**——在 SKILL.md 中明确「当前分发的 api-viewer.html 为 REST 视图参考实现；协议/AI Tools 视图为规划中（§10.5 已标注 🟡）」，并给出协议资产的备查阅方式；
- 同时：给 `api-design` 增补 `templates/loader.js`（与 WF/ER/UI 各 skill 一致；viewer 引用 `data/loader.js` 但模板目录无此文件）。

**R-010 契约关联**：按 document-asset-format.md「Viewer 交付物契约」，viewer 头部注释须声明数据契约——本 viewer 是否声明、与 `protocol-*` 是否一致需一并核查。

---

### M-02：document-asset-format §6 强制验证流程引用的 `tools/viewer-tests/verify-fixed.mjs` 在 bundle 中不存在

**定位**：`_shared/document-asset-format.md` L129 回归门禁条款；bundle 全树无 `viewer-tests` 目录、无 `verify-fixed.mjs`（`Get-ChildItem -Recurse -Filter '*verify*'` 结果为空）。

**现象**：规范把「viewer/数据模板/loader 变更必须跑 verify-fixed.mjs（0 console error、0 pageerror、emptyTexts 为空）+ 截图人工复核」写成强制门禁，但**门禁工具缺失**——项目只能自建替代（本项目落地 `scripts/viewer-smoke.mjs`，Playwright + chromium，逻辑与规范的 0 error/pageerror 判定一致）。

**影响**：§6「不允许改完就放」的纪律缺少官方工具支撑，各项目各自实现、口径不一（emptyTexts 判定等无法对齐）；新 viewer 准入（R-010）无可用检查器。

**修复建议**：在 `_shared/` 下补 `viewer-tests/verify-fixed.mjs`（含回归门禁声明：数据模板样例 → file:// 渲染 → 采集 console error/pageerror + emptyTexts + 关键内容命中断言 + 截图），并更新 document-asset-format.md 把该脚本的调用路径/参数写实；或将本条款降级为「以任一等价实现验证」，二选一不可含糊。

---

### M-03：文档/脚本中大量「扁平布局」路径引用，与 bundle 实际「伞形布局」不符

**定位**（均为扁平 `.agents/skills/<x>/`，实际为 `.agents/skills/sfds/<x>/`，`_shared/` 实际在 `.agents/skills/sfds/_shared/`）：
- `skills/development-standard/templates/AGENTS.md` L5：`项目 .agents/skills/development-standard/SKILL.md`；L7：`.agents/skills/_shared/document-asset-format.md`
- `_shared/gen/generate-trigger-table.mjs` L5-6（用法注释）、**L41（生成进 AGENTS.md 的注释文案）**：`.agents/skills/_shared/…`
- `skills/development-standard/SKILL.md` L132（§1.3 生成命令）、L210（管线注册表路径）、L243（迭代说明的工作副本路径）、L432（规范路径）
- `skills/review/SKILL.md` L568（D11 架构契约运行器命令 `.agents/skills/_shared/arch-contract/run.mjs`）
- `_shared/pipeline-registry.js` L156（admission.procedure：「跑 `scripts/generate-trigger-table.mjs --write`」，实际 `_shared/gen/`）

**现象**：按文档原样执行的命令多数会在 bundle 布局下“路径不存在”（本项目已全部替换为 `sfds/` 前缀实际路径并跑通）。generate-trigger-table.mjs 生成的 AGENTS.md 铁律表注释仍写扁平路径——本项目中生成后需手工感知偏差。

**影响**：任何项目按文档「照抄命令」即失败，或被迫沿途修正；生成器输出的持久注释（铁律表）带错误路径，误导后续维护者；**这属于"方法论首次接入必踩"类问题，值得在方法论项目内一次性根治**。

**修复建议**：把 bundle 内的路径引用统一改为伞形实际路径（`sfds/skills/…`、`sfds/_shared/…`），或将「bundle 模式路径换算规则」写入父技能 SKILL.md（如「本文中 `<skillName>` 一律解释为 `<本文件夹>/skills/<skillName>`，`_shared/` 一律解释为 `<本文件夹>/_shared/`」——父技能已有类似条款（使用规则 5），但**只覆盖了子技能正文**，未覆盖脚本输出、模板、其他 SKILL 正文）；建议把该换算规则从「父技能条款」升级为「全 bundle 通用约定」并逐处清扫。

---

### M-04：pipeline-registry 登记名 `wechatide-skill` 与 bundle 实际技能名 `wechatide-automation` 不一致

**定位**：`_shared/pipeline-registry.js` L131 `{ name: "wechatide-skill", … }`；技能目录/文件为 `.agents/skills/sfds/skills/wechatide-automation/SKILL.md`，frontmatter `name: wechatide-automation`；父技能触发词路由表、dev-standard §4 全生态表均称 `wechatide-automation`。

**现象**：generate-trigger-table.mjs 从注册表生成 AGENTS.md 铁律表 → 表中技能名显示 `wechatide-skill`，与磁盘/其他文档不一致；调度器/API 若按注册表名查找技能会找不到文件（本项目无小程序端，未受影响，但任何含小程序的项目必踩）。

**影响**：登记名与实际名“双名”，触发词路由与技能加载可能断链；铁律表派生物错误传播。

**修复建议**：二选一——注册表改名 `wechatide-automation`（与 frontmatter/templates 一致，推荐）；或把技能目录改名为 `wechatide-skill` 并同步全部正文引用。**注意**：注册表为单一真相源，改后重跑 generate-trigger-table.mjs 即可（派生物自动跟随）。

---

### M-05：review SKILL 要求 D1 使用 `raw-input-to-*` source，但共享规范 §3 source 注册表未登记该枚举

**定位**：`skills/review/SKILL.md` L300「结构化输出时 source 取 `_shared/consistency-check-format.md` §3 注册的 `raw-input-to-workflow` / `raw-input-to-er` / `raw-input-to-frontend`」；`_shared/consistency-check-format.md` §3 source 注册表（13 行）**无任何 `raw-input-*` 条目**（全文 grep 亦无）。

**现象**：D1（原始需求追溯）一致性检查若严格执行「source 必须来自 §3 注册表」→ 无合法枚举可用；若自造 `raw-input-to-*` → 违反「禁止 skill 内联自定义枚举造成 review 无法归一化」的铁律（同文件 §1 字段约定）。**规范自相矛盾**。

**影响**：D1 维度只能「违规执行」或「跳过”，两者都破坏检查体系的一致性。

**修复建议**：在共享 §3 注册表补登记三个 source 值（`raw-input-to-workflow` / `raw-input-to-er` / `raw-input-to-frontend`，使用方标 review/各 skill），并把 review L300 保持为引用（无需改）；同时检查共享 §2 type 注册表是否需同步补 `layer_missing` 等 D1/D10 用到的 type（review 自己的 `review-skills-check` 表格里 D1/D10 未声明专用 type，当前 review 以 `review-*` 前缀自理——见 §4 汇总规则 4，与新枚举的边界需一并划清：建议 D1/D10 用共享枚举，review 自增仅用于 review 专属问题）。

---

### M-06：tdd-build 一致性检查输出与共享规范不一致（缺 `ref_path`/`source`，type 部分未注册）

**定位**：`skills/tdd-build/SKILL.md` §6.4（L800-821）输出结构：
```json
{ "summary": { "stage", "scope", "tc_in_design", "tc_in_code", "matched_tc", "total_issues", "code_compiles" },
  "issues": [ { "severity", "type", "detail", "suggestion" } ] }
```
与 `_shared/consistency-check-format.md` §1 要求的 `{ summary{end_slug,total_scanned,total_issues,high,medium,low}, issues[]{severity,type,source,ref_path,detail,suggestion} }` 对比：
- 缺 `issues[].ref_path`（共享 L43 标 ✅ 必填）、`issues[].source`（共享 L42 标 ✅ 必填）；
- `summary.end_slug/total_scanned/high/medium/low` 也有差异（stage/scope 语义漂移）。

更严重的是 **type 未注册**：tdd-build §6.4 的 type 枚举 `missing_endpoint_test / missing_component_test / missing_journey_test / fixture_mismatch / compile_error / architecture_contract_missing / untraced_tc / trace_chain_broken / orphan_tc`（9 个，部分如 `compile_error` 甚至含下划线组合）未在共享 §2 type 注册表（19 项）登记——违反「注册表铁律：新 type/source 必须先注册再引用」。

**现象**：review 按 §4 汇总规则执行「每 skill 检查报告作为独立 {skill}-check 块保留、去重按 ref_path+type、不改名」时：无法定位问题（无 ref_path）、无法归一化（source 缺失）、无法判定重复（type 不共享）。

**影响**：TDD 闭环一致性维度（review D8）无法机械合并；若强行对齐又会产生「按哪个版本」的歧义。

**修复建议**：
1. tdd-build §6.4 输出结构改为共享 §1 结构（summary 字段对齐 + issues 增 `source: "tdd-to-code"`、`ref_path`）；
2. 在共享 §2 type 注册表登记 tdd-build 全部 type（或把 9 个收敛映射到已有枚举：`test_case_missing`/`assertion_mismatch`/`data_flow_broken`/`untraceable` 等，避免枚举爆炸）；
3. 同批核查 mobile/desktop-code-gen、entity-relationship、api-design 各检查模式与共享结构的字段对齐（本项目核查时发现：mobile/desktop UI 一致性示例 summary 缺 `total_scanned` 等字段、示例写 `source:"er-to-api"` 与其声明 `er-to-frontend` 冲突——详见附注 A5）。

---

## 附：核查中确认的补充项（建议一并纳入方法论项目 backlog）

| # | 定位 | 问题 | 优先级 |
|---|------|------|--------|
| A1 | `skills/entity-relationship/templates/er-viewer.html` L961 | 全景页标题**硬编码** `'跨域全景 — 全部 8 个域'`——项目域数 ≠8 时显示错误（本项目 6 域实测显示「8 个域」）；应为 `domains.length` | 高 |
| A2 | `skills/development-standard/SKILL.md` §6.1 目录树（L97/L571 行 `07-tdd/` 下未列 stage 子目录）vs §8.5（L843 `design/07-tdd/{stage}/{domain-slug}-tdd-design.md`，stage=api/page-mock/miniprogram/integration） | 目录树与产出路径两处不一致（树看起来是扁平存放）——首个接入项目按树建目录会漏 stage 层 | 中 |
| A3 | `skills/backend-architecture-design/SKILL.md` L476 「`data/example-topology.js` 提供最小示例」；模板目录 `templates/data/` 无 `example-topology.js`、无 `deployment-profile.js`（L4+ 必产文件，目录树 §6.1 提到） | 模板缺口（示例/部署模板缺失） | 中 |
| A4 | `skills/backend-architecture-design/templates/data/arch-contract.js`（模板） | 模板 type 用中文（`"分层"`）且结构极简（6 行）——与 `_shared/arch-contract-spec.md` 的五种英文谓词/完整字段（groups/valueDomains/registrySets/knownDebts/reviewLedger）**脱节**：照模板写出来的契约无法被 run.mjs 执行（本项目直接按规范手写，未用模板） | 高 |
| A5 | `skills/mobile-app-design/SKILL.md`/`desktop-ui-design/SKILL.md` 一致性检查输出示例 | 与共享规范字段漂移：示例 summary 只含 `end_slug/total_components_scanned/total_issues`（缺 `total_scanned/high/medium/low`）；示例 issue 写 `"source":"xx-to-xx"`、`ref_path` 命名为 `ref_path`…可核对；mobile 示例 issue 的 source 示例值为 `er-to-api`（与自身声明的 `er-to-frontend` 冲突） | 中 |
| A6 | `skills/pipeline-controller/SKILL.md` L107（bootstrap：「把 `templates/pipeline.md` 复制为…」）vs 实际模板 `templates/PIPELINE.md`；L107「在 `.pipeline/` 下放入 `scripts/lock.ps1`、`scripts/freshness.ps1`」vs 文件布局（L112-115）「`<项目根>/.pipeline/lock.ps1`」 | 模板文件名大小写不一致（Windows 下必踩）；脚本归属不统一 | 中 |
| A7 | `skills/development-standard/SKILL.md` §8.8（L864）「`test-reports/tdd-execute-report-{date}.md`」vs `skills/tdd-execute/SKILL.md` §3.3/§4.3/§4b.3/§5.3「`tests/test-reports/{stage}-execute-report-{date}.md`」 | 报告路径两处不一致（stage 化 vs 汇总一份）；另 §5.2.2（L487）写 `tests/` 五目录含 `tdd-design/`，与 tdd-build 的 stage 目录约定需统一 | 中 |
| A8 | `skills/entity-relationship/SKILL.md` §4（L180 等）「hash 路由 `#03`/`#all`」vs 模板 `er-viewer.html`（L62/341 `?domain=all`；渲染逻辑按 `?domain=` 参数，hash 仅用于表内锚点） | 文档与实现不符（hash 路由说法与 `?domain=` 参数机制冲突） | 低 |
| A9 | `skills/development-standard/SKILL.md` §6.1 目录树（L550 行 `raw-input/`）vs §1.2（L91 `01-raw-input/`）、§7（L692 `design/01-raw-input/{domain-slug}.md`）、review/iterate/consolidate 全部使用 `01-raw-input/` | 目录名残留歧义（终裁为 `01-raw-input/`，仅 §6.1 树两处未同步） | 低 |
| A10 | `_shared/pipeline-registry.js` 各阶段 exitGates 的 check 引用 | 「检查类」表述与实际命令存在弹性的地方（如 `design/{NN}-{client}/data/tree.js` 用了 `{NN}-` 而项目实际 `06-`；`tests/test_arch_contract.py` 为 Python 特定）——建议统一 `{stage}` 变量与语言无关性说明 | 低 |

## 附：修复与验收建议（给方法论项目的执行顺序）

1. **文档快修**（低风险高收益）：M-03 路径统一、M-04 改名、M-05 补注册表、A7 路径统一、A8/A9 措辞修正、A2 目录树同步——每项改完跑一次「空项目初始化演练」（`development-standard §1` 全流程）+ `generate-trigger-table.mjs --write` 验证派生物。
2. **工具补全**（中风险）：M-02 补 `viewer-tests/verify-fixed.mjs`、A4 重写 arch-contract 模板（对齐 spec 全字段）、A3 补 example-topology/deployment-profile 模板、M-01 补齐 api-viewer 协议视图或在文档中明示降级、A1 修硬编码计数。
3. **契约对齐**（中风险，治理性）：M-06 与 A5 的共享规范字段/枚举归一化，建议在共享规范升版本时**带迁移说明**，并同步各 skill 的「一致性检查输出」示例。
4. **验收基线**：修复后建议在至少一个真实项目（如 NASKB 或新起空项目）上重跑：契约运行器退出码 0、pytest 门禁、viewer smoke（本报告引用的 three-way 验证），并保留报告作为回归基线。

## 项目侧对应记录

- 本项目登记：`design/review/remaining-issues.md` §一（M-01~M-06 摘要）+ 本报告全文；
- 项目侧规避措施：路径统一用 `sfds/` 前缀（AGENTS.md 已注明）、协议资产以数据文件+IMPLEMENTATION-PLAN 人工查阅、viewer 验证自建 `scripts/viewer-smoke.mjs`。
