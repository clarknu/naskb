# 架构契约规范（Architecture Contract Spec）

> **本文件是 SFDS 架构约束机械化的单一真相源。** 架构设计资产中的约束如何表达为
> 机器可判定的谓词、事实如何提取、如何比较、如何接入门禁，全部以本规范为准。
> `backend-architecture-design` 产出契约，`api-code-gen` 消费契约，`review` / `iterate` /
> 发布门禁执行契约——三方的接口定义都在这里。
>
> **版本：v0.1-draft**（待首个项目完成实例化并跑通一轮门禁后转 v1.0）
> **报告格式：** 遵循 [`consistency-check-format.md`](consistency-check-format.md)，复用已注册的
> `type = arch_rule_violation`、`source = architecture-to-code`，不新增枚举。

---

## 0. 定位与设计立场

### 0.1 解决什么问题

架构设计资产（分层策略、模块边界、事件契约、横切策略）中声明的约束，目前由 LLM 在
review / 一致性检查时"阅读并理解"来执行。LLM 执行大范围、机械、精确集合比对的可靠性不足，
导致架构设计与代码实现之间的顺承关系缺乏硬保障。

**本规范的核心分工：AI 生产约束（写谓词、写探针），机器执行约束（跑比较器、过门禁）。
AI 是约束的作者和被约束者，不是约束的裁判。**

### 0.2 中性性承诺

本规范及 skill 分发的运行器/比较器是**技术中性 + 项目中性**的：

| 中性维度 | 保障方式 |
|---------|---------|
| 不同技术栈（语言/框架/ORM） | 技术特异性全部隔离在**项目探针**中（一次性生成、提交入库）；文法、事实格式、比较器、门禁不含任何技术词汇 |
| 不同架构形式（单体/模块化单体/微服务/事件驱动） | 架构差异只是喂进文法的不同**谓词数据**（分组、白名单、边类型）；文法不感知架构风格 |
| 不同分层模式（三层/六层/六边形/无分层） | 层定义是项目数据（unit 分组的 glob 模式）；无分层项目不生成 direction 谓词 |
| 不同项目规模（L1-L5） | 复杂度门控矩阵（§9）决定激活哪些约束类型；L1 零谓词 |

与既有机制的同构关系：`api-code-gen`"技术栈从 AGENTS.md 读取，不内置"——本规范把同一模式
推广到约束执行层。

### 0.3 与现有体系的关系

- **不替代** tdd-build 的架构承诺测试（那是**行为承诺**：幂等真的生效、缓存真的命中）；
  本规范管的是**结构承诺**（层没穿、域没破、注册没漏）。两者互补。
- **不替代** review 的语义检查；review D11 改为"契约校验器报告为准 + AI 只处理
  heuristic / review 账本残留"（§10）。
- **不改变**设计资产的产出流程；`backend-architecture-design` 在现有产物之外
  增量产出一份 `arch-contract.js`（§5）。

---

## 1. 核心模型

```
设计资产（layering / boundaries / event-contracts / resilience ...）
    │  backend-architecture-design 派生
    ▼
契约谓词  arch-contract.js          ← 项目资产（技术中性数据 + 指向上游的指针）
    │
    ├──→ 探针 probes（static / manifest / runtime）   ← 项目资产（技术相关，一次性生成）
    │        │  产出
    │        ▼
    │    事实 facts.json（中性 schema，§2）
    │
    ├──→ 运行器 runner.mjs           ← skill 分发（中性）
    │        │  解析 design:// 指针 → 纯 JSON 声明集
    │        ▼
    │    比较器 compare.mjs           ← skill 分发（中性，只做集合运算）
    │        │  产出
    │        ▼
    │    报告 report.json（consistency-check-format 结构）
    │
    └──→ 门禁（pytest 包装 / release / iterate / review）← 项目接线
```

**分发与归属：**

| 组成 | 归属 | 稳定性 |
|------|------|--------|
| 本规范 + runner.mjs + compare.mjs | skill 分发（`.agents/skills/sfds/_shared/arch-contract/`） | 随 skill 版本升级，项目不修改 |
| arch-contract.js | 项目 `design/05-backend-architecture/data/` | 随架构设计演进 |
| 探针脚本 + golden 快照 | 项目 `scripts/probes/` | 换技术栈时重写，仅此一处 |
| 门禁接线 | 项目（release policy / iterate C3.1 / pytest） | 一次接线 |

**关键推论：** 换技术 = 重写探针；换架构/分层/规模 = 换谓词数据；文法、事实格式、
比较器、门禁规则永远不动。

---

## 2. 事实模式（Fact Schema）

探针的输出必须是以下中性格式的 `facts.json`。**所有技术特异性终结于此文件的生产过程，
不进入格式本身。**

```json
{
  "probe": { "name": "python-static", "tech": "python", "version": "1.0.0", "generatedAt": "ISO-8601" },
  "units": [
    { "path": "app.services.message_router", "kind": "module", "files": ["app/services/message_router.py"] }
  ],
  "facts": {
    "dependency": [
      { "from": "app.api.chat", "to": "app.channels.wecom_adapter", "kind": "import", "evidence": { "file": "app/api/chat.py", "line": 5 } }
    ],
    "reference": [
      { "unit": "app.channels.web_adapter", "target": "app.services.identity", "via": "get_bound_api_key", "evidence": { "file": "...", "line": 12 } }
    ],
    "assetRef": [
      { "unit": "app.services.task_import", "asset": "WebInboxMessage", "assetKind": "entity", "evidence": { "file": "...", "line": 8 } }
    ],
    "literal": [
      { "unit": "app.api.chat", "domain": "channel", "value": "wecom", "evidence": { "file": "app/api/chat.py", "line": 40 } }
    ],
    "registry": [
      { "set": "routes", "key": "POST /api/v1/web/inbox", "evidence": { "file": "app/api/web_messages.py", "line": 20 } }
    ]
  }
}
```

### 2.1 字段约定

| 字段 | 约定 |
|------|------|
| `units[].path` | 探针自定义的**技术原生单元路径**（Python 点分模块、TS 相对路径、Go package、微服务名皆可）；必须输出全部单元清单供分组匹配 |
| `units[].kind` | `module` / `package` / `component` / `service` |
| `evidence` | **强制**。至少含 `file`，尽量含 `line`。没有证据的事实不可信 |
| `dependency[].kind` | `import`（代码级）/ `package`（清单级）/ `http`（服务间调用）/ `topic`（消息订阅） |
| `registry[].set` | 事实集合名，与契约中 `set-relation.actualSet` 对应；key 按 set 声明的 keyStyle 归一化（§3.5） |
| `literal[].domain` | 值域名，与契约 `valueDomains` 对应 |

### 2.2 分组匹配语义

契约中的 unit 分组使用 glob 模式匹配 `units[].path`：`*` 单段、`**` 跨段、其余精确匹配；
`.` 与 `/` 均视为段分隔符。分组未命中的 unit 不参与任何规则判定（比较器须在报告中
列出未分组单元数量，供人核查分组覆盖度）。

---

## 3. 约束文法（五种谓词类型）

> **文法边界铁律：** 约束类型是**封闭集合**。新类型必须先修改本规范并升版本，禁止项目
> 自造类型。无法归入以下五类的规则一律标 `review`（§4），不做变通表达。

每条规则的公共字段：

| 字段 | 必填 | 说明 |
|------|:---:|------|
| `id` | ✅ | 项目内唯一，格式 `AC-NNN`，登记后不复用 |
| `type` | ✅ | 五种之一 |
| `enforcement` | ✅ | `mechanical` / `heuristic` / `review`（§4） |
| `rationale` | ✅ | 人可读的约束意图（一句话） |
| `source` | ✅ | 上游设计资产定位（`design://` 指针或文件+锚点），保证谓词可追溯到设计决策 |

### 3.1 dependency-direction（依赖方向）

**语义：** `from` 分组的依赖边，不得指向 `forbid` 分组。（v0.1 只判**直连边**，不做传递闭包。）

```js
{ id: "AC-001", type: "dependency-direction", enforcement: "mechanical",
  from: ["core"], forbid: ["channels"], kinds: ["import"],
  rationale: "核心层零渠道感知", source: "design://05-backend-architecture/data/layering-strategy.js#rules[0]" }
```

比较器行为：遍历 `facts.dependency`，`matchGroup(from) ∧ matchGroup(to) ∧ kind ∈ kinds` → 违规。
适用：分层方向、六边形端口方向、前端 feature/shared 方向——只要能表述为"分组 A 的边不得进入分组 B"。

### 3.2 reference-whitelist（引用白名单）

**语义：** 跨分组引用必须是声明白名单的子集。

```js
{ id: "AC-003", type: "reference-whitelist", enforcement: "mechanical",
  whitelist: "design://05-backend-architecture/data/module-boundaries.js#crossModuleCalls",
  rationale: "跨模块访问只走所属模块 service", source: "design://...module-boundaries.js" }
```

白名单条目归一化为 `{fromGroup, toGroup, via?}`（来源数据中的 `target`/`via` 字段由运行器
按 §5.2 桥接表解析到分组）。可选限定字段：
- `from`：仅检查来源分组属于该列表的引用（层间调用如 API→Application Service 不在跨模块白名单检查范围）；
- `allowToGroups`：目标分组级许可——上游 layering 资产 `dependsOn` 已声明的**层间依赖**直接放行
  （层间方向由 dependency-direction 规则管辖，不按跨模块白名单判定）；
- `ignoreToGroups`：目标分组豁免（如底层基础设施客户端，任何模块经接口调用均为合法）。

比较器行为：解析每条 `facts.reference` 的 unit 分组与 target 分组
（target 先查 units 清单，再查契约 `externalGroups`），跨分组、不在白名单、不属分组级许可 → 违规。
适用：模块间调用白名单、微服务间只可经 API 契约调用（kinds 含 http 的边）。

### 3.3 ownership（资产归属）

**语义：** 某类资产只可被属主分组的单元**直接引用**；跨组访问必须经服务接口（由 3.2 接管）。

```js
{ id: "AC-004", type: "ownership", enforcement: "mechanical",
  assetKind: "entity",
  ownership: "design://05-backend-architecture/data/module-boundaries.js#modules",
  moduleGroups: { "task-management": "modules.task", "identity-permission": "modules.identity" },
  rationale: "禁止跨域直查表", source: "..." }
```

比较器行为：从指针数据构建 `资产 → 属主分组` 映射（读 `modules[*].ownsEntities`），
遍历 `facts.assetRef`（同 assetKind），引用单元分组 ≠ 属主分组 → 违规。
适用：实体归属、表归属、前端组件归属。

### 3.4 value-domain（值域常量引用）

**语义：** 离散值域的裸字面量只允许出现在声明单元（通常是常量/枚举定义处），其余一律引用命名常量。

```js
{ id: "AC-005", type: "value-domain", enforcement: "mechanical",
  domain: "channel", allowLiteralIn: ["app.channels.__init__"],
  rationale: "渠道枚举唯一权威定义在 Channels", source: "..." }
```

比较器行为：遍历 `facts.literal`（同 domain），unit 不匹配 `allowLiteralIn` → 违规。
**heuristic 变体**（`enforcement: "heuristic"` + `flagComparisonContext: true`）：
允许单元内的字面量若出现在比较上下文（if/elif/switch 判等）也报告 WARN——探针尽力而为，
不支持此模式的探针在报告中标注 `not-supported`。

### 3.5 set-relation（集合关系）

**语义：** 声明集合与实际集合满足指定关系。它是"注册完整性"和"设计覆盖度"的统一形式。

```js
{ id: "AC-007", type: "set-relation", enforcement: "mechanical",
  declared: "design://05-backend-architecture/data/event-contracts.js#events",
  actualSet: "event-handlers", mustMatch: "equal",
  rationale: "事件契约与 handler 注册一致", source: "..." }

{ id: "AC-009", type: "set-relation", enforcement: "mechanical",
  declared: "design://04-platform-api/data/rest/channel-access.js#endpoints",
  actualSet: "routes", mustMatch: "equal", keyStyle: "METHOD path-lowercase-noslash",
  rationale: "路由与 API 设计一致", source: "..." }
```

| `mustMatch` | 语义 | 典型用途 |
|-------------|------|---------|
| `equal` | 双向无差 | 事件↔handler、路由↔API 设计、前端调用↔API 设计 |
| `declared-in-actual` | 声明的每一项都已实现（缺 = 违规） | 幂等端点全覆盖、架构策略覆盖的端点真实存在、API 设计端点全覆盖 |
| `actual-in-declared` | 实际的每一项都有声明来源（多 = 违规） | 页面只可调用声明端点、无未声明路由 |

`keyStyle`：key 的归一化规则名（探针按此产出 `registry[].key`，比较器只做精确字符串比对）。
keyStyle 词表（封闭）：`exact` / `METHOD path-lowercase-noslash`。需要新词 → 先改本规范。

> v0.1 设计记录：初稿曾设六个类型（含独立 `coverage`），desk-check（§12）确认其语义
> 完全被 `declared-in-actual` 覆盖，故合并。

---

## 4. 强制性等级（enforcement）

| 等级 | 语义 | 违规后果 | 依据 |
|------|------|---------|------|
| `mechanical` | 已表达为谓词，比较器确定性判定 | **FAIL**（未登记豁免时，退出码 1） | 本规范文法 |
| `heuristic` | 有脚本但只能启发式判定（如比较上下文检测） | **WARN**（退出码 0，报告留痕） | 探针能力边界 |
| `review` | 无法谓词化的语义规则 | 不检查，但**必须登记**（§4.1） | 语义判断留给人/AI 复查 |

**登记铁律：** `backend-architecture-design` 产出契约时，架构设计中的每条约束必须三选一：
表达为 `mechanical` 谓词 / 降级 `heuristic` / 登记 `reviewLedger`。**不允许"既没进文法、
又不在账上"的隐式约束**——这是"哪些约束有保障、哪些靠自觉"成为显式账目的保证。

### 4.1 reviewLedger（语义约束账本）

```js
reviewLedger: [
  { id: "RL-001", rule: "Controller/API 层禁止包含业务逻辑（状态判断、业务规则）",
    checkHint: "review D11 + 人抽查；关注 api/ 下出现状态机转换或业务校验",
    source: "design://...layering-strategy.js#layers[1]" }
]
```

review D11 执行时逐条走查本账本；账本外的语义问题按常规复查流程。

---

## 5. 契约文件格式（arch-contract.js）

**落位决策（v0.1）：** 谓词独立存放于 `design/05-backend-architecture/data/arch-contract.js`，
不并入 `layering-strategy.js` / `module-boundaries.js`。理由：机器权威源单一、viewer 数据
文件保持人类可读、探针输入单点。**单一来源铁律：** mechanical 规则只在契约中存在一次；
上游设计文件中的散文规则可引用 `ruleId`（如"见 AC-001"）但**不得重述谓词内容**，防止双写漂移。

```js
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["arch-contract"] = (function () {
  var _trace = {
    consumes: ["architecture:layering-strategy", "architecture:module-boundaries",
               "architecture:event-contracts", "architecture:resilience-policy"],
    produces: ["constraint:arch-contract"]
  };
  return {
    _trace: _trace,
    version: "1",
    complexityLevel: "L3",
    groups: {                          // 分组 = glob 模式（§2.2）
      "core": ["app.core.**", "app.services.message_router"],
      "channels": ["app.channels.**", "app.api.wecom_callback", "app.api.web_messages", "app.api.debug"],
      "api": ["app.api.**"],
      "modules.task": ["app.services.task_*"],
      "modules.identity": ["app.services.identity*"]
    },
    externalGroups: { "openproject": "external.openproject", "dify": "external.dify" },
    valueDomains: {
      "channel": { constantsUnit: "app.channels.__init__", values: ["wecom", "web", "debug"] }
    },
    registrySets: {                    // actualSet 名 → 探针约定
      "routes":        { probe: "static|runtime", keyStyle: "METHOD path-lowercase-noslash" },
      "event-handlers": { probe: "static", keyStyle: "exact" },
      "idempotent-endpoints": { probe: "static", keyStyle: "METHOD path-lowercase-noslash" }
    },
    rules: [ /* §3 定义的谓词，公共字段 + 类型字段 */ ],
    reviewLedger: [ /* §4.1 */ ],
    knownDebts: [ /* §8 */ ]
  };
})();
```

### 5.1 design:// 指针协议

格式：`design://<相对 design/ 的路径>#<点分路径>`。运行器在 Node VM 中加载目标 JS
（所有设计数据文件遵循 `window.XXX_DATA` 挂载约定，天然可加载），解析 `#` 后路径取值，
注入比较器。点分路径支持末段数组投影记法 `path[].field`（如 `modules[].ownsEntities`）。
**指针只用于读取已存在于设计资产中的声明集合**；不存在于设计资产的集合允许 inline，
但必须在 `rationale` 中说明来源。

### 5.2 分组桥接

`module-boundaries.js` 等资产使用模块名（如 `IdentityPermission`），契约分组使用 unit 模式。
桥接表：ownership 规则的 `moduleGroups`、whitelist 解析时同名复用。桥接表是唯一允许
"模块名 → 分组"双写的地方，比较器对桥接表中指向不存在分组的条目报 WARN。

---

## 6. 探针契约

### 6.1 三类探针

| 类型 | 事实来源 | 典型产出 | 成本 |
|------|---------|---------|------|
| **static** | 源码 AST / 正则扫描 | dependency(import)、assetRef、literal、registry(静态可提的) | 一次性生成，CI 每跑 |
| **manifest** | package.json / go.mod / pyproject / pom.xml | dependency(package) | 极低 |
| **runtime** | 框架内省（路由表 / DI 容器 / 事件总线注册表） | registry(路由、handler、中间件) | 需可启动环境 |

**降级阶梯：** static 提不干净（动态 import、反射、DI 自动装配）→ runtime 内省 →
仍不行 → 该规则降级 `heuristic` 或 `review`，在契约中声明，不视为失败。

### 6.2 探针 I/O 契约

- 输入：项目自定义（建议：契约文件路径 + 探针配置），无约束。
- 输出：`facts.json`，**必须通过 §2 schema 校验**（运行器先校验后比较，校验失败 = 退出码 2）。
- 生成：**AI 在项目实例化时一次性生成**，技术栈从 `AGENTS.md` 读取（与 api-code-gen 同款机制），
  提交入库，之后只随技术栈演进维护。

### 6.3 golden 快照（防探针自身漂移）

`scripts/probes/golden/facts-snapshot.json`：同一代码基线下探针输出的快照。
AI 修改探针后必须重跑并 diff 快照——**非预期 diff 即探针回归**，防止"改探针让违规消失"。
快照仅通过显式命令 `--update-golden` 再生。

---

## 7. 运行器与比较器（skill 分发）

```
.agents/skills/sfds/_shared/arch-contract/
  run.mjs        # 运行器：加载契约 → 校验 facts schema → 解析 design:// 指针 → 调比较器 → 出报告
  compare.mjs    # 比较器：纯 JSON in / JSON out，只做分组匹配 + 集合运算，无 IO 副作用
```

- 调用：`node .agents/skills/sfds/_shared/arch-contract/run.mjs --contract design/.../arch-contract.js --facts scripts/probes/out/facts.json --report design/review/arch-contract/<date>.json`
- **退出码：** `0` = 通过（含 warn-only）；`1` = 存在未豁免的 mechanical 违规或豁免已过期；`2` = 基础设施失败（schema 不合、指针解析失败、探针崩溃）。
- 报告结构遵循 `consistency-check-format.md`，扩展字段：`issues[].ruleId`、`issues[].enforcement`、`issues[].debtMatched`；`summary` 增加 `rulesChecked` / `debtsActive` / `unmatchedUnits`。type 用 `arch_rule_violation`，source 用 `architecture-to-code`，report producer 记 `backend-architecture-design`。

---

## 8. knownDebts（存量违规豁免）

```js
knownDebts: [
  { ruleId: "AC-005", scope: "app/api/chat.py", issue: "#141", registered: "2026-08-26",
    expires: "2026-09-30", note: "channel=wecom 硬编码，待 web 适配器接入后消除" }
]
```

| 字段 | 约定 |
|------|------|
| `ruleId` + `scope` | 豁免匹配键：违规证据（evidence.file 或 unit）匹配 scope 模式且规则相同 → 降级 WARN |
| `issue` | **强制**——豁免必须挂在明确的工作项上 |
| `expires` | **强制**——到期后比较器自动恢复 FAIL（不等人工清理） |

**豁免铁律：** 豁免是给**存量**技术债的宽限期，不是给新代码的后门。登记时代码中该违规
必须已存在；review 时抽查豁免清单，无 issue 或已到期未续的清理出账。

---

## 9. 复杂度门控矩阵

对齐 `backend-architecture-design` §1.2；等级判定复用既有问卷，不另设。

| 等级 | 激活的约束类型 | 必备探针 | 契约文件 |
|------|--------------|---------|---------|
| L1 | 无 | — | 不生成 |
| L2 | dependency-direction、ownership、value-domain | static | ✅ |
| L3 | L2 + reference-whitelist、set-relation | static（registry 可借 runtime） | ✅ |
| L4 | L3 + dependency/reference 纳入 `http`/`topic` 边（跨服务） | + manifest | ✅ |
| L5 | 全类型；跨服务 set-relation 必检 | + runtime | ✅ |

---

## 10. 门禁接线

四处接线，全部是现有机制 +1：

| 接线点 | 变更 |
|--------|------|
| **pytest / 测试套件** | `tests/test_arch_contract.py` 包装运行器（subprocess + 断言退出码 0），进入"pytest 全绿"——自动挂上 iterate 规则 #14 与 tdd-execute 循环 |
| **发布门禁** | release-management 门禁表新增第 9 项：架构契约校验通过（退出码 0） |
| **iterate C3.1** | 前置脚本清单新增架构契约校验 |
| **review D11** | 先取运行器报告；mechanical 部分以报告为准不再人读代码；AI 仅走查 heuristic WARN 与 reviewLedger |

---

## 11. 新项目实例化流程（六步）

1. `backend-architecture-design` 创建模式按 §9 矩阵同步产出 `arch-contract.js`（谓词从
   分层/边界/横切设计派生，每条标 enforcement；无法谓词化的进 reviewLedger）。
2. AI 按项目技术栈生成探针（读 `AGENTS.md` techStack），输出过 schema 校验 + golden 快照。
3. 引用 skill 分发的 `run.mjs` / `compare.mjs`（不修改、不复制进项目脚本）。
4. pytest 包装测试挂入测试套件。
5. 首跑登记：存量违规逐条入 knownDebts（带 issue 号与期限）。
6. 接线 §10 四处门禁。

---

## 12. 表达力对照表（v0.1 desk-check 记录）

> 验证方法：取现有 skill / 本项目设计资产中的真实架构约束，逐条尝试用文法表达。
> 结论：14 条中 12 条 mechanical、1 条 heuristic、1 条 review——文法表达力足够，
> 且跨技术（Python 后端 / TS 前端）、跨架构形式（单体 / 微服务）均有代表。

| # | 真实规则（出处） | 文法表达 | 等级 |
|---|----------------|---------|------|
| 1 | 核心层禁止 import 渠道实现（本项目 layering-strategy rule 1） | dependency-direction | mechanical |
| 2 | API 层禁直调 Infrastructure 客户端（layering-strategy rule 4） | dependency-direction | mechanical |
| 3 | 跨模块访问只走所属模块 service（module-boundaries 规则 2） | reference-whitelist（指针 → crossModuleCalls） | mechanical |
| 4 | 禁止跨域直查表（module-boundaries 规则 2） | ownership + reference-whitelist 组合 | mechanical |
| 5 | 渠道字面量必须引用 Channels 常量（layering-strategy rule 3） | value-domain | mechanical |
| 6 | 禁止 if/elif 渠道分支（layering-strategy rule 2） | value-domain + flagComparisonContext | heuristic |
| 7 | 事件契约 ↔ handler 注册一致（event-contracts + api-code-gen 步骤 6） | set-relation equal | mechanical |
| 8 | 幂等端点全覆盖（resilience-policy.requiredEndpoints） | set-relation declared-in-actual | mechanical |
| 9 | 路由 ↔ API 设计一致（review D7 / validate-frontend-api-alignment 同构） | set-relation equal + keyStyle | mechanical |
| 10 | ER 跨域关系 ↔ 跨域白名单（backend-architecture §3.2 检查 2） | set-relation | mechanical |
| 11 | 前端页面只可调用 API 设计声明的端点（client-code-gen 检查 3） | set-relation actual-in-declared | mechanical |
| 12 | TS 前端 feature/shared 依赖方向（跨技术代表） | dependency-direction（unit=前端模块路径） | mechanical |
| 13 | 微服务间只可经 API 契约调用（跨架构代表，L4） | reference-whitelist（含 http 边） | mechanical |
| 14 | Controller/API 层禁止包含业务逻辑（skill 步骤 3 硬规则） | 无法谓词化 | review |

---

## 13. 非目标与边界

1. **不做语义规则**——"职责划分是否合理""是否含业务逻辑"永远留给 review + 人。
2. **不做传递依赖分析**（v0.1 只判直连边）——传递闭包在动态语言下误报率高，收益存疑，待实例化数据决策。
3. **不做运行时行为验证**——那是 tdd 架构承诺测试（行为承诺）的领地。
4. **不追求零 WARN**——heuristic WARN 是线索不是罪证；mechanical FAIL 才是拦截线。
5. **规则语言保持封闭**——五种类型 + 封闭 keyStyle 词表；扩展的唯一途径是升版本改本规范。

---

## 14. 变更管理

- 本文件随 `_shared/` 目录整体分发（项目级 `.agents/skills/sfds/_shared/` ↔ 全局 `~/.agents/skills/_shared/`），与 `consistency-check-format.md` 同步策略一致。
- 修改文法/事实 schema/退出码 → 升版本号并在文首记录；下游（runner/compare、各 SKILL.md 接线、项目契约）同步检查。
- v0.1 → v1.0 的转正条件：首个项目完成 §11 六步实例化 + 一轮发布门禁真实拦截记录。
