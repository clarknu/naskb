---
name: review
version: 2.0.0
description: |
  全项目复查 skill——贯穿七步流水线的逐层一致性校核 + 交互式迭代修复闭环。
  按标准 §10（迭代与收敛）执行，覆盖工作流/ER/API/页面架构/代码五层对照。
  输出复查报告 + 迭代修复直至收敛。
triggers:
  - 复查
  - 一致性检查
  - 全量复查
  - review
  - consistency check
  - 校核
  - 整体检查
  - 全面审查
  - 质量审查
  - 合规检查
  - 对齐检查
  - 差异分析
  - 收敛检查

lineage:
  origin: arb-hub
  rulings: [R-001]
  sources:
    boxing:        {sha256: 6ce1505add1f}
    zy-iot-ai:     {sha256: 66091bfa03f0}
    zy-ai-consult: {sha256: 7527ea01ce6d}
---

# Review — 全项目复查与迭代修复 Skill

## 0. 自动化脚本与跨项目可移植性

> 本技能附带两个自动化校验脚本（位于 `scripts/` 子目录），用于 D6/D7/D12 维度的细粒度检查。
> 脚本与技能同目录分发——安装技能时脚本自动跟随。

### 0.1 脚本清单

| 脚本 | 功能 | 适用技术栈 |
|------|------|-----------|
| `scripts/validate-frontend-api-alignment.mjs` | 扫描前端 API 调用 vs 后端路由 + DTO，逐条比对路径/参数/字段 | 微信小程序 + ASP.NET Core |
| `scripts/smoke-test-miniprogram.mjs` | 验证小程序页面文件完整性 + JS 语法 | 微信小程序 |

> **项目级复用：** 本项目（Vue 3 + FastAPI）已生成 `scripts/validate-frontend-api-alignment.mjs`（项目根 `scripts/`，FastAPI 路由 + DTO 版），复查 D6/D7 时优先复用项目脚本；技能自带版本作为跨项目默认实现，技术栈不匹配时按 §0.2 生成/适配。

### 0.2 跨项目使用规则

> **铁律：脚本是"默认实现"，不是"唯一实现"。** 技能的核心价值在于检查逻辑，而非特定脚本。

**Step 0 — 启动复查前必须执行的技术栈适配检查：**

| 情形 | 处理方式 |
|------|---------|
| **项目技术栈与脚本匹配**（微信小程序 + ASP.NET Core） | 直接运行脚本，路径由 `--project-root` 或 Git root 自动检测 |
| **技术栈不匹配**（如 React + Express / Vue + FastAPI / Vue + Spring Boot） | **AI 必须先分析项目的 API 调用模式和路由注册模式，然后当场生成等效的校验脚本**。核心检查逻辑不变：① 提取前端 API 调用（method + path + params + body fields）→ ② 提取后端路由（method + route + DTO fields）→ ③ 归一化比对 → ④ 输出不匹配报告 |
| **脚本运行失败**（项目结构变化导致路径检测失败） | 使用 `--project-root=/path/to/project` 显式指定，或 AI 修复脚本中的路径模式 |

**Step 1 — 全维度技术栈映射（D5/D12 等运行时维度必须执行）：**

> 本 skill 的 D5（ORM 一致性）与 D12（运行时启动验证）默认按 **ASP.NET Core + EF Core + SQLite** 编写。
> 当项目技术栈不同（从项目 `AGENTS.md` 读取 `runtime` / `framework` / `orm` / `test_command` / 启动命令），必须按下表逐项映射，**不得直接套用 .NET 专属命令**：

| 技术栈要素 | .NET 默认（文档原样） | 映射规则（其他技术栈） |
|-----------|---------------------|----------------------|
| 服务启动 | `dotnet run --launch-profile http`（从 launchSettings 读取） | 从 AGENTS.md 读取启动命令（如 `uvicorn app.main:app --reload`、`npm run dev`） |
| ORM schema 比对 | EF model snapshot vs `PRAGMA table_info` | 用对应 ORM 的 schema 检查（如 SQLAlchemy `metadata.create_all` diff、Django `makemigrations --check`、TypeORM migration diff） |
| 启动日志扫描 | `no such column` / `could not be translated`（EF 专属） | 按框架扫描等价错误：ORM 查询异常、类型转换异常、路由缺失、模块加载失败 |
| 测试执行 | `dotnet test --collect:"XPlat Code Coverage"` | 从 AGENTS.md 读取测试命令（如 `python -m pytest`）+ 对应覆盖率工具 |
| 健康检查 | `GET /api/v1/health`（curl） | 使用项目约定的健康检查端点（可从路由或 AGENTS.md 获取） |
| API 对齐校验 | 扫描 `api.get/post/put` + `[Route]+[Http*]` 属性 + DTO `record` | 按项目实际调用模式（`axios`/`fetch`/`$http`）与路由注册（FastAPI 装饰器/Express router/Spring mapping） |

> **铁律：D12 的"服务器启动 + 健康检查 + 冒烟请求"三步骤是技术栈无关的，必须执行；具体命令一律从 AGENTS.md / 项目启动脚本读取，禁止照抄 .NET 命令。**

**脚本生成只需覆盖 4 个核心函数：**
1. `extractFrontendApiCalls()` — 扫描前端代码，输出 `{ method, path, queryParams, bodyFields, file, line }[]`
2. `extractBackendRoutes()` — 扫描后端代码，输出 `{ method, fullPath, params, dtoType, file }[]`
3. `extractDtoFields()` — 提取请求体 DTO 字段名列表
4. `main()` — 比对并输出不匹配报告

> AI 生成脚本时，先探查项目中的 API 调用模式（如 `fetch()`, `axios.get()`, `$http.get()`）和路由注册模式（如 `@GetMapping`, `app.get()`, `router.get()`），然后按项目的实际模式编写提取逻辑。**生成后的脚本保存到 `scripts/` 子目录（与本 skill 同目录），下次复查可直接复用。**

### 0.3 脚本查找顺序

```
1. scripts/validate-frontend-api-alignment.mjs  ← 技能自带（与本 SKILL.md 同目录分发）
2. 如果技术栈不匹配 → AI 生成新脚本到同目录（scripts/）
3. 如果生成失败 → AI 手动执行等价检查（grep + 逐条比对）
```

> **手动回退不可跳过：** 如果脚本无法生成或运行，AI 必须用 `grep` 扫描前端 API 调用和后端路由，手工完成比对并报告结果。D7 维度不得因"脚本不可用"而跳过。

## 适用场景

| 场景 | 说明 |
|------|------|
| **阶段复查** | 某个领域的流水线走完一轮后，检查所有产出物是否一致 |
| **全量复查** | 所有领域全部设计+代码实现完成后，做整体一致性校核 |
| **变更后复查** | 大规模修改后检查是否引入了一致性问题 |
| **发布前复查** | 代码提交或发布前，确保设计与实现完全对齐 |

## 前置条件：Review 的执行时机

> **⚠️ Review 必须最后执行，绝不可与设计/实现步骤并行。** 以下规则是强制约束。

### Review 的依赖链

Review 检查的是全链条产物的一致性。所有被检查的产物必须已存在且为最新版本。具体依赖：

1. Review 依赖 business-workflow（§8.1）—— 工作流数据是校核的起点
2. Review 依赖 entity-relationship（§8.2）—— ER 数据用于对照工作流和 API
3. Review 依赖 api-design（§8.3）—— API 契约用于对照代码实现
4. Review 依赖前端页面设计（§8.4）—— tree.js 用于对照前端代码
5. Review 依赖 TDD 设计（§8.5）—— 测试规格用于对照测试代码
6. Review 依赖 API 代码实现（§8.6）—— 后端代码用于对照 API 设计和 TDD
7. Review 依赖前端代码实现（§8.7）—— 前端代码用于对照页面设计和 API 调用

### 启动前置检查清单

> **核心理念：前置检查只验证"各步骤产物存在且格式正确"——存在性 ≠ 正确性。**
> 正确性（设计是否正确、TDD 是否全绿、代码与设计是否一致）是 Review 要检验的**结果**，不是启动 Review 的**门槛**。
>
> 设计可能被修改但测试尚未跟进、代码已变更但 TDD 尚未适配——这些恰恰是 Review 要发现并修复的问题。
> 如果要求一切都正确才能启动 Review，Review 本身就没有存在的必要了。

在启动 Review 之前，必须逐项确认：

- [ ] §8.1 business-workflow 数据文件存在且非空，格式合法
- [ ] §8.2 entity-relationship 数据文件存在且非空，格式合法
- [ ] §8.3 api-design 数据文件存在且非空，格式合法
- [ ] §8.4 页面设计数据文件（tree.js 等）存在且非空，格式合法
- [ ] §8.5 tdd-build TDD 设计文档存在且非空，测试代码编译通过（0 错误）
- [ ] §8.6 API 代码已实现，编译通过（0 错误）
- [ ] §8.7 前端代码已实现，无语法错误
- [ ] §8.8 tdd-execute 报告存在（最新一次执行记录即可，不要求 0 失败）

任一前置条件未满足，Review 不得启动。应报告缺失项并等待补充。

### 在 Workflow 编排中的约束

当使用 Workflow 或 Agent 编排多个 SFDS 步骤时：

- Review Agent **禁止**与任何 §8.1-§8.7 的 Agent 并行调度
- Review Agent 的启动必须放在所有设计+实现 Agent 完成之后
- 串行编排方式：在所有设计和实现的 `await agent()` / `await parallel()` 全部返回后，才调用 Review Agent
- 并行编排方式（禁止）：将 Review Agent 与设计/实现 Agent 放入同一个 `parallel()` 调用

---

## 1. 复查流程总览

```
触发复查
    │
    ├── 1. 采集所有设计资产与代码现状
    │       ├── 域注册表 (domain-registry.js)
    │       ├── 设计决策日志 (design-decisions.js)
    │       ├── 同步状态 (review/sync-status.js)
    │       ├── 业务工作流 (business-workflow/data/)
    │       ├── ER 实体关系 (entity-relationship/data/)
    │       ├── API 设计数据 (platform-api/data/)
    │       ├── 页面架构设计 (design/{端-slug}/data/)
    │       ├── 原始交互存档 (design/01-raw-input/)
    │       └── 代码实现
    │
    ├── 2. 真相仲裁（发现不一致时，先确定以哪边为准）
    │       ├── 读取 design-decisions.js —— 不一致可能是"有意为之"的决策
    │       ├── 如果决策日志中有记录 → 以决策为准，不报问题
    │       ├── 如果决策日志中无记录 → 启动仲裁协议：
    │       │   ├── 代码行为更优/更新 → 以代码为真相源，触发同步螺旋上溯
    │       │   ├── 设计规格是正确的 → 以设计为真相源，触发代码修复
    │       │   └── 无法判断孰优孰劣 → 生成 ⚖️ arbitrate 问题，暂停等用户裁决
    │       └── 仲裁结果写入 design-decisions.js
    │
    ├── 3. 逐维度校核（13个维度 D0-D12，覆盖全链条 26+ 对追溯关系）
    │       ├── D0 用户旅程完备性走查（旅程模拟执行）
    │       ├── D1 原始需求追溯（原始需求→工作流/ER/前端）
    │       ├── D2 工作流一致性（工作流→ER/API/前端/TDD）
    │       ├── D3 ER数据一致性（ER→API/ORM/TDD/前端）
    │       ├── D4 API设计一致性（API→API代码/ORM/前端/TDD）
    │       ├── D5 ORM代码一致性（ORM→数据库/TDD/前端/API代码）
    │       ├── D6 前端功能一致性（前端设计→前端代码/TDD/API）
    │       ├── D7 前后端集成一致性（前端代码→API代码）
    │       ├── D8 TDD闭环一致性（TDD设计→TDD代码→API代码）
    │       ├── D9 API功能完备性（跨来源完整性检查）
    │       ├── D10 跨级追溯（跨级全链正反向验证）
    │       ├── D11 标准与架构合规
    │       ├── D12 运行时启动验证（服务器启动 + 健康检查 + 冒烟请求）
    │       └── D13 AI工作流合规（可选：仅项目含 AI 工作流架构资产时启用；按 ai-workflow-orchestration-design 的 P1-P6 自检清单核对）
    │
    ├── 4. 生成复查报告（问题清单 + 修复计划）
    │
    └── 5. 交互式迭代修复
            ├── 用户分批裁决 → 修复 → 更新报告
            ├── 循环直至收敛
            └── 归档
```

---

## 1b. 真相仲裁协议

> **核心理念：** 复查发现不一致时，不要直接报错。先判断"哪边是正确的"——这个判断决定了修复方向。
> 不预设"设计永远正确"——代码实现可能揭示了更好的方案，原始需求可能记录不清晰。

### 仲裁流程

```
发现不一致
    │
    ├── 1. 查设计决策日志（design-decisions.js）
    │      这个不一致是否由已知的设计决策解释？
    │      ├── 是 → 不报问题，记录"已由 DD-XXX 解释"
    │      └── 否 → 继续
    │
    ├── 2. 确定不一致方向
    │      比较两边的内容：
    │      ├── 代码比设计更新/更完整 → 代码可能是真相源
    │      ├── 设计比代码更新/更完整 → 设计可能是真相源
    │      └── 无法判断 → 需要用户裁决
    │
    ├── 3. 仲裁
    │      ├── 代码是真相源 → 触发同步螺旋（§10.3b），以代码为起点上溯更新设计
    │      │   记录决策到 design-decisions.js：trigger: "implementation-feedback"
    │      ├── 设计是真相源 → 生成 ✅ fix 问题，要求代码对齐设计
    │      └── 无法判断 → 生成 ⚖️ arbitrate 问题，列出两边差异，等待用户裁决
    │          用户裁决后，记录决策到 design-decisions.js
    │
    └── 4. 后续
           仲裁确定了方向后，后续所有维度校核按仲裁方向执行。
           同一轮复查中，同一资产对的不一致不重复仲裁。
```

### 仲裁输出格式

在复查报告中，经仲裁的问题标注仲裁结果：

```markdown
### P-001: 退款端点幂等策略不一致

- **维度**: 后端架构合规
- **严重度**: 🟡 中等
- **不一致**: `resilience-policy.js` 未列出 `POST /refunds`，但代码实现了 Idempotency-Key 校验
- **仲裁**: ⚖️ 代码为真相源（代码实现更优，已在实际运行中验证）
- **决策**: 触发同步螺旋 → 更新 resilience-policy.js 的 idempotency.requiredEndpoints
- **决策 ID**: DD-042
```

---

## 2. 校核维度

> 以下按"上游产物 → 下游产物"方向组织。在 D1 之前增加 D0（用户旅程完备性走查），共 13 个维度（D0-D12），覆盖从原始需求到代码实现的全链条追溯一致性。
> 箭头方向明确了**谁对谁负责**——上游的定义须在下游中得到正确传递和实现。
>
> **技能委托机制：** 以下维度中标注为 `→ 委托 {skill}` 的检查项，由对应 skill 的**一致性检查模式**负责执行深度校验，
> 而非由通用检查代理自行比对。复查时须先调取对应 skill 的一致性检查模式获取结构化报告，
> 再将报告中的问题纳入复查问题清单。各 skill 的检查模式定义参见对应 SKILL.md。
> 委托覆盖关系见 development-standard §8 技能网络结构。

### 2.0 D0 — 用户旅程完备性走查

> **这是复查的第一个维度，在 D1（需求追溯）之前执行。** D1 查"需求有没有进设计"，D0 查"设计出来的东西能不能串成完整流程"。
> D0 与 D1 互补：D1 是文档级对照，D0 是流程级模拟。

**检查方式：**
1. 从 business-workflow 的 flowchart 中提取每条从 `start` 走到 `end` 的完整路径作为用户旅程
2. 对每条旅程，模拟执行：

| 检查步骤 | 方法 | 失败标记 |
|---------|------|---------|
| 页面文件齐全 | 旅程中涉及的页面文件是否齐全（按该端技术栈约定的页面文件结构检查，如小程序为 js/wxml/wxss/json 四件套，Web 端为 tsx/css 等） | 🔴 page_missing |
| 页面间数据传递 | 上一页的 `page_output.params[]` 是否全部出现在下一页的 `page_input.params[]` 中 | 🔴 data_flow_broken |
| 组件绑定 API | 组件 `api_ref` 指向的端点是否存在 | 🔴 api_mismatch |
| API 返回字段可用 | API `produces[].field` 是否被页面组件消费 | ⚠️ dead_endpoint |
| 全链可追溯 | 旅程终点的数据能否通过 produces→consumers 链反推回 business-workflow 节点和原始需求 | 🔴 untraceable |

3. 输出：对每条旅程输出一行状态。有 🔴 断点 → 旅程不通过

**与 D1 的关系：** D0 的结果为 D1 提供上下文——如果 D0 发现某条旅程有断点，D1 会正对断点对应的原始需求做深度追溯。

### 2.1 原始需求追溯

> 原始需求是项目的起点。须确保需求中的每一项——业务场景、角色、规则、实体——都被设计产物完全承接。

| 追溯方向 | 检查项 | 方法 |
|---------|--------|------|
| 原始需求 → 工作流 | 业务场景在工作流中是否有对应流程 | 逐条对照 raw-input → sections |
| 原始需求 → 工作流 | 用户提到的角色在工作流中是否有定义 | roles/actors 对照 |
| 原始需求 → 工作流 | 用户提到的业务规则在工作流中是否有记录 | constraints/rules 对照 |
| 原始需求 → 工作流 | 用户提到的状态转换在工作流中是否有状态机 | state machine 覆盖度 |
| **原始需求 → ER** | **需求中提到的业务实体在 ER 中是否有对应** | entity ← raw-input |
| **原始需求 → ER** | **需求中提到的业务属性在 ER 实体中是否有字段** | field ← raw-input |
| **原始需求 → ER** | **需求中提到的实体关系在 ER 中是否有关系连线** | relationship ← raw-input |
| **原始需求 → 前端功能设计** | **需求中描述的用户界面/页面在前端设计中是否有对应** | page/screen ← raw-input |
| **原始需求 → 前端功能设计** | **需求中提到的用户交互操作在前端设计是否有对应组件** | interaction/component ← raw-input |
| **原始需求 → 前端功能设计** | **需求中提到的数据展示需求在前端设计是否有对应呈现** | data display ← raw-input |

> 结构化输出时 source 取 `_shared/consistency-check-format.md` §3 注册的 `raw-input-to-workflow` / `raw-input-to-er` / `raw-input-to-frontend`。

### 2.2 工作流一致性

> 业务工作流是业务行为的精确描述。须确保每个业务概念、操作、规则、状态转换都被下游产物一致实现。

| 追溯方向 | 检查项 | 方法 |
|---------|--------|------|
| **工作流 → ER** | **业务概念在 ER 中是否有对应实体** | **→ 委托 `entity-relationship`**（实体覆盖检查） |
| **工作流 → ER** | **状态机在 ER 中是否有对应状态字段** | **→ 委托 `entity-relationship`**（枚举值一致性检查） |
| 工作流 → ER | ER 中的关系是否在工作流中有业务依据 | 关系 ← 流程（由通用检查代理反向对比） |
| 工作流 → ER | 操作步骤涉及的字段在 ER 中是否有定义 | 字段覆盖度（由通用检查代理反向匹配） |
| **工作流 → API** | **每个 action 节点是否有对应 API 端点** | **→ 委托 `api-design`**（端点覆盖检查） |
| **工作流 → API** | **每个状态转换是否有对应操作 API** | **→ 委托 `api-design`**（状态转换对照检查） |
| 工作流 → API | 每个 subprocess 是否有对应 API 组 | subprocess → endpoint group |
| 工作流 → API | 业务校验逻辑在 API 层是否有对应 | rules → validation |
| **工作流 → 前端功能设计** | **每个操作步骤在前端有对应页面/交互组件** | **→ 委托 `client-ui-design` 一致性检查模式**（工作流覆盖检查） |
| **工作流 → 前端功能设计** | **工作流角色在前端有对应权限/视图控制** | role → UI permission（由通用检查代理比对角色定义与页面权限标注） |
| **工作流 → 前端功能设计** | **流程步骤在前端有对应导航路径** | flow → navigation（由通用检查代理比对 flow 定义与 tree.flows 步骤序列） |
| **工作流 → API → 前端** | **权限点全链路一致性：business-workflow 定义的每个权限点是否被 API 端点和前端组件正确引用，三处标注的权限点 id 是否一致** | **→ 通用检查代理执行：读取 business-workflow `permissions` 数组 → 比对 API 端点权限标注 → 比对前端组件 `perm_ref` 标注。标记三处不一致的权限点** |
| **工作流 → TDD** | **每个状态转换在 TDD 中有对应测试用例** | state transition → TC |
| **工作流 → TDD** | **每个业务规则在 TDD 中有校验用例** | business rule → validation TC |

### 2.3 ER 数据一致性

> ER 设计定义了数据结构和约束。须确保每个实体、字段、关系、约束都被下游产物一致继承。

| 追溯方向 | 检查项 | 方法 |
|---------|--------|------|
| **ER → API** | **API 参数字段在 ER 中有定义且类型一致** | **→ 委托 `api-design`**（字段一致性检查） |
| **ER → API** | **ER 中的必填字段在 API 中是否有校验** | **→ 委托 `api-design`**（约束传递检查） |
| **ER → API** | **ER 中的唯一约束在 API 中是否有校验** | **→ 委托 `api-design`**（唯一性约束传递检查） |
| **ER → API** | **ER 与 API 的枚举值集合一致** | **→ 委托 `api-design`**（枚举值集合一致性检查） |
| **ER → ORM** | **ER 中的每个实体在 ORM 中有对应类** | **→ 委托 `api-code-gen`**（实体→类映射检查） |
| **ER → ORM** | **字段映射：类型/长度/精度一致** | **→ 委托 `api-code-gen`**（字段→属性映射检查） |
| **ER → ORM** | **关系（1:N, N:M）在 ORM 中有导航属性** | **→ 委托 `api-code-gen`**（关系→导航属性检查） |
| **ER → ORM** | **约束（PK, FK, UQ, NN）在 ORM 中有标注** | **→ 委托 `api-code-gen`**（约束→注解检查） |
| **ER → TDD** | **每个字段约束在 TDD 中有校验用例** | constraint → validation TC |
| **ER → TDD** | **每个唯一约束在 TDD 中有重复插入用例** | uq → duplicate TC |
| **ER → TDD** | **关系完整性在 TDD 中有引用完整性测试** | FK → referential integrity TC |
| **ER → 前端功能设计** | **ER 中每个核心实体在前端是否有对应列表/详情/编辑页面** | **→ 委托 `client-ui-design` 一致性检查模式**（实体覆盖检查） |
| **ER → 前端功能设计** | **ER 中的枚举类型在前端是否有对应选择器/展示映射** | enum → picker/display mapping（由通用检查代理比对 ER 枚举值与前端组件描述） |
| **ER → 前端功能设计** | **ER 中的实体关系在前端是否有对应导航/联级操作** | relationship → navigation/cascade UI（由通用检查代理比对 ER 关系与 tree.js 中的 refs 导航标注） |

> 委托归属依据 CASE-001 裁决（2026-08-23）：API 契约一致性由契约所有者 api-design 执行。

### 2.4 API 设计一致性

> API 设计是系统对外契约。须确保每个端点、参数、响应、错误处理被下游正确实现，且定义本身与上游数据模型一致。

| 追溯方向 | 检查项 | 方法 |
|---------|--------|------|
| **API → API 代码** | **API 文档中的端点全部实现** | **→ 委托 `api-code-gen`**（端点覆盖检查） |
| **API → API 代码** | **请求参数与代码入参一致** | **→ 委托 `api-code-gen`**（参数一致性检查） |
| **API → API 代码** | **响应结构与代码出参一致** | **→ 委托 `api-code-gen`**（DTO 字段一致性检查） |
| **API → API 代码** | **错误场景在代码中有处理** | **→ 委托 `api-code-gen`**（错误码覆盖检查） |
| API → API代码 | 权限标注在代码中有对应 | permission → attribute |
| **API → ORM** | **API 引用的字段在 ORM 模型中有对应属性** | API field → ORM property |
| **API → ORM** | **请求/响应 DTO 与 ORM 实体字段类型兼容** | DTO type ↔ entity type |
| API → 前端功能设计 | 页面引用的 API 都存在 | 逐 component 确认 |
| API → 前端功能设计 | 页面展示数据在 API 响应中有返回 | fields ← response |
| API → 前端功能设计 | 页面操作有对应 API | action → endpoint |
| API → 前端功能设计 | 分页/筛选参数满足列表需求 | params ← page |
| **API → TDD** | **每个 API 端点在 TDD 中有对应测试用例** | endpoint → TC |
| **API → TDD** | **每个错误码在 TDD 中有错误场景用例** | error code → error TC |
| **API → TDD** | **API 权限要求在 TDD 中有越权测试用例** | permission → unauthorized TC |

### 2.5 ORM 代码一致性

> ORM 是数据模型在代码层的具象化。须确保 ORM 与实际数据库对齐，并为前端和测试提供正确数据契约。
> **技术栈提示：** 下表默认按 EF Core + SQLite 编写。非 .NET 技术栈（如 SQLAlchemy + PostgreSQL、TypeORM、Django ORM）按下表检查项逐一映射执行（详见 §0.2 Step 1），检查意图不变：迁移已应用、模型与库表对齐、无孤儿表、无 schema drift、FK 一致。

| 追溯方向 | 检查项 | 方法 |
|---------|--------|------|
| **ORM → 数据库实际结构** | **EF 迁移全部已应用，无待执行迁移** | 列出文件系统中 `src/server-api/**/Migrations/*.cs` 的迁移文件名（排除 Designer.cs 和 snapshot），与数据库 `SELECT MigrationId FROM __EFMigrationsHistory` 对比。标记文件系统中有但数据库中无的迁移。 |
| **ORM → 数据库实际结构** | **EF model snapshot 与实际数据库表列一致（列名/类型/可否为空）** | 对每张 EF 实体对应的表，通过 `PRAGMA table_info({table})` 获取实际列名、类型、notnull，与 `BoxingDbContextModelSnapshot.cs` 中的 `b.Property<T>("{col}").HasColumnType(...)` 定义逐列比对。标记列名不同、类型不同、nullable 不同的所有差异。 |
| **ORM → 数据库实际结构** | **数据库中无孤儿表（存在但 EF 模型未引用的表）** | 执行 `SELECT name FROM sqlite_master WHERE type='table'`，排除 EF 模型已知表及系统表（`__EFMigrationsHistory`、`__EFMigrationsLock`、`sqlite_sequence`），标记孤儿表。 |
| **ORM → 数据库实际结构** | **数据库无 schema drift（`PRAGMA table_info` 与 EF model snapshot 完全对齐）** | 逐表执行 `PRAGMA table_info` 与 model snapshot 的 columns 定义比对（列名、类型、约束），将所有差异标记为 schema drift。 |
| **ORM → 数据库实际结构** | **ORM 关系映射与 FK 约束一致** | navigation → FK（通过数据库 `.schema {table}` 检查 FK 存在性与 EF 导航属性匹配） |
| **ORM → 数据库实际结构** | **ORM 索引与数据库索引一致** | annotation → DB index（通过 `PRAGMA index_list` 检查索引与 EF 索引标注一致） |
| **ORM → TDD** | **ORM 字段约束在 TDD 中有校验用例** | constraint → validation TC |
| **ORM → TDD** | **ORM 导航属性在 TDD 中有关联查询用例** | navigation → query TC |
| **ORM → 前端代码** | **ORM 字段是否满足前端展示数据需求** | entity fields → UI display |
| **ORM → 前端代码** | **ORM 枚举值在前端有对应展示映射** | enum → display label mapping |
| **ORM → API代码** | **ORM 中每个实体属性在 API 的 DTO/ViewModel 中是否有对应字段** | entity property → DTO field |
| **ORM → API代码** | **ORM 实体关系在 API Controller 中是否有对应级联操作端点** | navigation → API action endpoint |
| **ORM → API代码** | **ORM 中新增/修改的字段是否同步更新了 API 的请求/响应结构** | ORM change → DTO sync |
| 数据库实际结构 → ORM | 实际数据库表结构与 ORM 模型是否一致（反向检查 schema drift） | table → class (reverse) |
| 数据库实际结构 → ORM | 数据库中的附加索引/约束在 ORM 中是否有标注 | DB index → annotation |

### 2.6 前端功能一致性

> 前端功能设计定义了用户交互方式。须确保每个页面、组件、流程都被代码实现，且与 API 的消费关系正确。
>
> **前置条件：** 在检查"前端功能设计 → 前端代码"之前，应先通过 `client-ui-design` 的
> 一致性检查模式确认前端设计与上游（ER、工作流）一致。如果设计本身已过期，检查代码实现没有意义——
> 先对齐设计，再对齐代码。

| 追溯方向 | 检查项 | 方法 |
|---------|--------|------|
| **前端功能设计 → 前端代码** | **功能树中的页面在代码中有对应文件** | **→ 委托 `client-code-gen`**（页面存在性检查） |
| **前端功能设计 → 前端代码** | **功能组件在代码中有实现** | **→ 委托 `client-code-gen`**（组件映射检查） |
| 前端功能设计 → 前端代码 | 公共组件在代码中被复用 | shared → import |
| **前端功能设计 → 前端代码** | **前端流程有完整代码实现** | **→ 委托 `client-code-gen`**（导航路径检查） |
| **前端功能设计 → TDD** | **每个交互场景在 TDD 中有对应用户交互用例** | interaction → UI test TC |
| **前端功能设计 → TDD** | **每个输入校验规则在 TDD 中有校验用例** | validation rule → validation TC |
| 前端功能设计 → API | 页面引用的 API 是否存在 | 逐 component 确认 |
| 前端功能设计 → API | 页面操作有对应 API 端点 | action → endpoint |
| **前端功能设计 → i18n 翻译表** | **每个 display/rich_text 组件的 `text` 是否在 i18n 文件中有对应条目** | **→ 委托 `client-ui-design` 一致性检查模式（文本与 i18n 完整性检查，step 6）** |
| **前端功能设计 → i18n 翻译表** | **每个 button/link 组件的 `label`、每个 input 的 `placeholder`/`hint`/`validation[].error` 是否有 i18n key 定义** | **→ 委托 `client-ui-design` 一致性检查模式** |
| **前端功能设计 → 工作流** | **`show_when` 条件和 `text.variants[].condition` 中引用的状态值是否与工作流状态机一致** | **→ 委托 `client-ui-design` 一致性检查模式** |

> 提示：「前端功能设计 → API」的检查已在 2.4 中从 API 端做了反向确认，此处从组件端再做正向确认，双向覆盖。
>
> 提示：「前端功能设计 → i18n」和「前端功能设计 → 工作流（文本条件）」是细粒度检查维度，对应 client-ui-design 方法论的原则七（文本精确化）。

#### 2.6.1 API 调用正确性验证

> **D6 检查粒度必须与 D3（字段级）、D4（端点级）、D9.4（stub 级）对齐。** 仅检查"页面是否存在"不够——须验证每个页面调用后端 API 的**路径、参数名、请求体字段、响应体字段**是否与后端实际实现一致。

| 检查项 | 方法 |
|--------|------|
| **每个页面的每个 API 调用路径在后端是否有对应路由** | 执行 `node scripts/validate-frontend-api-alignment.mjs`（相对本 skill 目录），读取输出的 PATH NOT FOUND 清单，逐条标记为 🔴 严重 |
| **每个页面的请求体字段名是否与后端 DTO 属性名一致** | 读取脚本输出的 BODY FIELD mismatch 清单，逐条标记为 🔴 严重（字段名不同会导致后端无法正确绑定） |
| **每个页面的查询参数名是否与后端 Action 参数名一致** | 读取脚本输出的 QUERY PARAM mismatch 清单，逐条标记为 🟡 中等 |
| **页面中的硬编码数据是否应来自 API** | 扫描页面 JS 中的硬编码数组/对象（如票种列表、价格数据），标记"应来自 API"的数据源断裂 |

> **执行方式：** 运行 `node scripts/validate-frontend-api-alignment.mjs`（相对本 skill 目录）→ 将输出的不匹配项逐一纳入复查问题清单。脚本扫描前端 `api.get/post/put` 调用、后端 `[Route]+[Http*]` 属性、DTO `record` 字段（非 .NET 技术栈时按 §0.2 Step 1 映射），做归一化路径比对和字段名比对。
>
> **Mock API 层免检规则：** 后端 Controller 实现完成后，Mock API 层（`utils/api.js`）不再是免检区。D7 验证以真实后端路由为准，Mock 层偏差必须在同一次复查中暴露和修复。

### 2.7 前后端集成一致性

> 前端代码与后端 API 的协作是系统可运行的关键。须确保前端调用与后端实现完全对齐。
>
> **执行顺序：** D7 在 D6.1（API 调用正确性验证）之后执行。D6.1 确保前端调用的 API 在后端存在且参数/字段正确；D7 在此基础上做更深入的运行时集成验证。

| 追溯方向 | 检查项 | 方法 |
|---------|--------|------|
| **前端代码 → API 代码** | **前端 API 调用地址与后端路由一致** | 运行 `node scripts/validate-frontend-api-alignment.mjs`（相对本 skill 目录），确认 PATH NOT FOUND = 0 |
| **前端代码 → API 代码** | **前端请求参数格式与后端 DTO 一致** | 运行 `node scripts/validate-frontend-api-alignment.mjs`，确认 BODY FIELD mismatch = 0 |
| **前端代码 → API 代码** | **前端响应解析与后端返回结构一致** | 对关键页面做运行时请求验证（D12 冒烟测试）：逐页面对后端发请求，对比响应字段名与前端解析字段名 |
| 前端代码 → API 代码 | 前端错误处理覆盖后端所有错误码 | error handling → error codes |
| 前端代码 → API 代码 | 前端调用频率/节流与 API 限流一致 | throttle → rate limit |

> **铁律：** D7 维度报告必须包含 `validate-frontend-api-alignment.mjs` 的输出。PATH NOT FOUND > 0 时，D7 状态不得标记为 ✅。

### 2.8 TDD 闭环一致性

> TDD 设计 → 测试代码 → API 实现，构成完整的红-绿-重构闭环。
>
> **⚠️ 铁律：本维度不是"看代码估计"——必须引用 tdd-execute 的实际执行结果。**
> Review 自身不执行测试。测试执行由 `tdd-execute` skill（流水线 §8.8）独立负责。
> Review 读取 tdd-execute 产出的测试报告作为本维度的输入。

#### 2.8.1 测试执行（引用 tdd-execute 报告）

| 检查项 | 方法 |
|--------|------|
| **tdd-execute 已执行且报告存在** | 检查 `test-reports/tdd-execute-report-*.md` 存在。若不存在 → 生成 P 级问题，建议执行一次 §8.8 tdd-execute 获取测试基线，Review 继续 |
| **测试失败记录为问题条目** | 读取 tdd-execute 报告中的「整体结果」表。如有失败 → 将每个失败的测试生成为问题条目（P 级），纳入本轮修复计划与设计/代码问题统一处置——**不阻塞 Review 继续**。失败本身就是 Review 要发现的问题，无需暂停复查去单独修复 |
| **每个测试项目均已执行** | 交叉核对 tdd-execute 报告中的「测试项目明细」与实际存在的 `*Tests.csproj` / `*Test.csproj` 文件列表。标记报告中遗漏的测试项目 |
| **覆盖度未达标生成问题条目** | 读取报告中的覆盖统计，确认所有生产项目覆盖率 ≥ 60%。不达标 → 生成 P 级问题，纳入修复计划（修复路径：回到 tdd-build 补充测试） |

#### 2.8.2 测试覆盖率分析

| 检查项 | 方法 |
|--------|------|
| **所有 `IHostedService` / `BackgroundService` 有专属测试** | 搜索 `services.RemoveAll<IHostedService>()` 或 `services.RemoveAll<*Service>()` 出现在测试基类中的位置。每个被禁用的服务代表一个测试盲区——必须确认有独立的单元测试覆盖该服务。若无，生成 P 级问题。 |
| **所有 `Replace`/`RemoveAll` 在测试工厂中的替换有补偿测试** | 逐条检查 `CustomWebApplicationFactory` / `TestBase` 中的 DI 替换。每处 `RemoveAll` 或 `Replace` 代表生产代码的真实分支被测试绕过——需要独立的测试补偿。 |
| **代码覆盖率报告** | 读取 tdd-execute 覆盖率报告（§2.8.1），自测不运行测试。标记覆盖率 < 80% 的代码路径。**最低要求：所有生产代码覆盖率 ≥ 60%。** |

#### 2.8.3 静态覆盖检查

| 追溯方向 | 检查项 | 方法 |
|---------|--------|------|
| **TDD 设计 → TDD 代码** | **TDD 设计文档中每个用例在测试代码中有实现** | **→ 委托 `tdd-build`**（用例覆盖检查） |
| **TDD 设计 → TDD 代码** | **测试数据与测试代码中的 fixture 一致** | **→ 委托 `tdd-build`**（fixture 一致性检查） |
| **TDD 设计 → TDD 代码** | **预期结果与测试代码中断言一致** | **→ 委托 `tdd-build`**（断言一致性检查） |
| **TDD 代码 → API 代码** | **测试调用的端点与 API 实现一致** | **→ 委托 `api-code-gen`**（端点覆盖交叉确认） |
| **TDD 代码 → API 代码** | **测试 mock/stub 覆盖 API 外部依赖** | **→ 委托 `api-code-gen`**（mock 覆盖检查） |
| TDD 覆盖 | TDD 设计文档是否存在且完整 | `design/07-tdd/{stage}/{slug}-tdd-design.md`（stage = api / page-mock / miniprogram / integration）存在 |
| TDD 覆盖 | 正常路径覆盖 — 每端点至少 1 通过用例 | happy path |
| TDD 覆盖 | 参数校验覆盖 — 每必填参数有缺失/非法值用例 | validation |
| TDD 覆盖 | 状态转换覆盖 — 工作流每状态转换有对应用例 | state transition |
| TDD 覆盖 | 错误场景覆盖 — API 每错误码有对应用例 | error scenario |
| TDD 覆盖 | 边界条件覆盖 — 分页/空列表/越界/并发 | boundary |
| TDD 覆盖 | 权限覆盖 — 每权限等级有越权访问用例 | unauthorized |

### 2.9 API 功能完备性

> 区别于 2.3（字段一致性）和 2.4（API→下游一致性），本维度检查 **API 是否覆盖了所有需要的操作**——工作流中的每个动作、页面上的每个功能组件、需求中的每个场景，都必须有对应的 API 端点。

#### 2.9.1 工作流操作 → API

| 检查项 | 方法 |
|--------|------|
| 工作流中每个 action 节点是否有对应 API | action node → endpoint |
| 工作流中每个状态转换是否有对应操作 API | state transition → action endpoint |
| 工作流中每个 subprocess 引用的子流程是否有 API | subprocess → endpoint group |
| 工作流中的业务校验逻辑在 API 层是否有对应 | rules → validation |

检查方式：逐 business-workflow 的 flowchart nodes，标记每个 action 和 decision 节点，确认对应的 API 端点存在。工作流中有 N 个操作步骤，就应该有至少 N 个对应的 API 端点。

#### 2.9.2 页面功能组件 → API

| 检查项 | 方法 |
|--------|------|
| 每个列表/表格组件是否有对应的列表查询 API | list/table → GET list endpoint |
| 每个详情展示组件是否有对应的详情 API | detail display → GET detail endpoint |
| 每个编辑按钮是否有对应的更新 API | edit button → PUT/PATCH endpoint |
| 每个新增按钮是否有对应的创建 API | add/create → POST endpoint |
| 每个操作按钮（审核/通过/驳回等）是否有对应动作 API | action button → POST action endpoint |
| 每个搜索/筛选控件是否有对应的搜索 API | search/filter → GET with query params |
| 每个文件上传组件是否有对应的上传 API | upload → POST upload endpoint |

检查方式：逐页面功能树的功能组件，按 componentType 和功能描述判断需要的 API 类型。一个 `[button]：提交审核` 就需要一个对应的审核提交 API。

#### 2.9.3 原始需求场景 → API

| 检查项 | 方法 |
|--------|------|
| 原始需求中描述的核心业务流程是否可通过 API 走通 | scenario → endpoint chain |
| 用户提到的异常处理场景是否有 API 覆盖 | error → error response |
| 用户提到的批量操作是否需要对应 API | batch → batch endpoint |

检查方式：逐条阅读 raw-input 中的需求描述，提取"用户需要能 XX"的句式，确认对应的 API 端点存在。

#### 2.9.4 D9.4 可用性验证

> 区别于 D9.1-D9.3 的**存在性**检查（端点是否存在），本子维度检查**可用性**（端点是否真的能用）。

| 检查项 | 方法 | 失败标记 |
|--------|------|---------|
| 模拟实现检测 | grep Controller 代码中的 `Simulate*` / `Stub*` / `Mock*` 方法调用 | ⚠️ simulated_impl |
| 数据流断裂检测 | 对每个端点的 `produces[].field`，检查是否被至少一个前端组件 `sends[]` 引用。无 consumer | ⚠️ dead_endpoint |
| 前端 API 调用绑定 | 前端 `api_ref` 指向的端点是否存在且方法/路径匹配 | 🔴 api_mismatch |
| 后台任务覆盖 | 检查 business-workflow 中"自动""超时""定时"语义的节点，是否有对应的 BackgroundService 注册 | ⚠️ scheduler_missing |
| 端到端数据管道 | 选一条用户旅程，检查 page_output → api_ref.sends → API consumes → API produces → page_input 全链数据字段匹配 | 🔴 data_pipe_broken |

### 2.10 D10 — 跨级追溯

> 区别于 D1-D9 的**相邻层**比较（§8.1↔§8.2、§8.2↔§8.3），本维度执行**跨越多级**的全链追溯。
> 经验表明大量设计缺陷藏在跨级链路中——每一对相邻层都 ✅，但整条链路断了。

**正向跨级追溯（需求 → 最终产物）：**

| 追溯链 | 检查方法 | 失败标记 |
|--------|---------|---------|
| raw-input → workflow → ER → API → page → code | 对每条原始需求，逐层验证是否有对应产物 | 🔴 layer_missing |
| workflow.outputs → API.consumes → page.sends → code | 工作流产出的字段是否逐层传递到代码 | 🔴 output_lost |
| ER.field → API.produces → page.page_output → next_page.page_input | ER 字段是否逐层传递到前端并被下游页面接收 | 🔴 field_dropped |

**反向跨级追溯（最终产物 → 需求）：**

| 追溯链 | 检查方法 | 失败标记 |
|--------|---------|---------|
| code → page → API → ER → workflow → raw-input | 每个代码产物必须能反推回至少一条原始需求 | ⚠️ orphan |
| page_input.params → page_output → API.produces → ER.field | 页面接收的参数必须能反向追溯到数据来源 | 🔴 untraced_param |

检查方式：对每个域选 2-3 个核心实体，各走一条正向+反向全链追溯。

> 结构化输出时 source 取 `_shared/consistency-check-format.md` §3 注册的 `cross-level-trace`。

### 2.11 标准与架构合规

| 检查项 | 方法 |
|--------|------|
| **架构契约机械校验（L2+，先行）** | **运行器判定，非人读：`node .agents/skills/sfds/_shared/arch-contract/run.mjs --contract design/05-backend-architecture/data/arch-contract.js --facts scripts/probes/out/facts.json --report design/review/arch-contract/latest.json`（探针先跑）。退出码 0 = mechanical 全过；非 0 → 逐条看 high 未豁免违规。mechanical 部分以报告为准不再人读代码，AI 仅走查 heuristic WARN 与契约 reviewLedger（规范 `_shared/arch-contract-spec.md` §10）** |
| 跨域实体引用是否在 core-er.js 中注册 | cross_domain → core_relations |
| 引用实体的 slug 是否与域注册表一致 | slug → domain-registry |
| API 跨域调用链是否完整 | 上下游端点 |
| 设计资产是否按标准 §5.2 目录结构存放 | path check |
| 域注册表是否遵循标准 §5.3 格式和规则 | format check |
| 原始存档是否按标准 §7 执行 | raw-input/ 存在+时间戳 |
| 数据文件格式是否符合对应 schema | format validation |
| 功能组件是否遵循原则七（文本精确化）—— display/button 组件有 `text`/`label` 字段 | text field check |
| i18n key 命名是否遵循规范（domain.component.element 三段式） | i18n key naming convention |
| **命名一致性检查** | **路由路径/名称、视图文件名、i18n 键名满足命名一致性约束（kebab-case 全英文、层级完全对应、无旧项目遗留术语）。扫描 `src/router/modules/*.ts` + `src/views/**/*.vue` + `public/locales/*.json` 中的残留旧术语和键名不一致** |

### 2.12 运行时启动验证

> 代码和数据库的一致性检查只能在静态层面发现部分问题。数据库 schema drift、EF 迁移未应用、
> LINQ 翻译兼容性等问题只有在服务器实际启动并执行查询时才会暴露。
> **本维度是所有复查的最后一步——必须先通过 D0-D11 静态校核，再执行运行时验证。**

#### 2.12.1 验证流程

```
Step 1 — 启动服务器
  使用项目启动命令（从 AGENTS.md 或 launchSettings/package.json 读取，如 `dotnet run --launch-profile http` / `uvicorn app.main:app --reload`）
  捕获 stdout/stderr 输出

Step 2 — 检查启动日志
  扫描启动日志中的异常和错误：
  - SQLite Error / no such column / no such table → schema drift
  - could not be translated / LINQ expression → EF Core provider 兼容性问题
  - fail: / FATAL → 任何致命错误

Step 3 — 验证健康检查
  curl /api/v1/health（或项目约定的健康检查端点）
  确认返回 200 且 status = healthy

Step 4 — 前端冒烟测试
  执行 `node scripts/smoke-test-miniprogram.mjs [端名]`（相对本 skill 目录）
  验证：页面文件完整性（js/wxml/wxss/json 四文件不缺）+ JS 语法正确性 + TabBar 注册一致性 + 孤儿目录

Step 5 — 分类与修复
  将运行时错误与 D0-D11 的静态问题关联，生成修复项
```

#### 2.12.2 检查项

| 检查项 | 方法 |
|--------|------|
| **服务器可正常启动，进程无致命退出** | 按 AGENTS.md 启动命令运行后确认进程保持运行，exit code 不为非 0 |
| **启动日志无数据库 schema 异常** | 扫描日志中无 `no such column`、`no such table`、`SQLite Error` —— 此类错误表明 EF model snapshot 与实际 DB 不同步 |
| **启动日志无 LINQ 翻译错误** | 扫描日志中无 `could not be translated`、`InvalidOperationException` —— 此类错误表明 EF Core provider 无法翻译 LINQ 表达式（常见于 enum cast、复杂布尔组合等） |
| **后台服务无持续性运行时错误** | 启动后等待至少一个 timer 周期（通常 60s），检查 BackgroundService 日志无 repeated/looping 异常 |
| **健康检查端点返回正常** | `GET /api/v1/health`（或项目约定的健康检查路由）→ 200 + healthy/degraded（非 fatal） |
| **关键 API 端点可访问** | 对每个域的至少一个 GET 端点做快速冒烟请求，确认无 500 错误 |
| **前端页面文件完整、JS 语法正确** | 执行 `node scripts/smoke-test-miniprogram.mjs`，确认 missingFiles = 0 且 syntaxErrors = 0 |
| **前端-后端 API 完全对齐** | 执行 `node scripts/validate-frontend-api-alignment.mjs`，确认 PATH NOT FOUND = 0 且 BODY FIELD mismatch = 0 |

#### 2.12.3 与其他维度的关系

| 启动错误类型 | 对应静态检查维度 | 说明 |
|-------------|-----------------|------|
| `no such column: r.Name` | D5 ORM→DB | 迁移未应用，model snapshot 与 DB schema 不同步 |
| `could not be translated` | D5 ORM→DB | EF Core provider 兼容性，LINQ 表达式需拆分 |
| `no such table: X` | D5 ORM→DB（孤儿表反向） | 代码引用了不存在的表 |
| 孤儿表存在 | D5 DB→ORM | 数据库中有表但 EF 模型无对应实体 |
| 健康检查失败（表查询异常） | D5 ORM→DB | schema drift 导致运行时查询失败 |
| 小程序 WXML/WXSS 编译错误 | D6 前端功能一致性 | 模板/样式语法错误，导致模拟器无法渲染 |

---

## 3. 问题分类体系

### 3.1 严重度

| 标记 | 定义 | 示例 |
|------|------|------|
| 🔴 严重 | 导致功能不可用或数据不一致 | 实体缺关键字段、API 未实现、display 组件缺 `text` 字段导致 i18n 翻译缺失 |
| 🟡 中等 | 影响体验或维护性 | 命名不一致、缺校验、button 缺 `label` 字段、`validation` 缺 `error` 文本 |
| 🟢 轻微 | 文档或格式问题 | 注释不准确、格式不规范、i18n key 命名不符合规范 |

### 3.2 问题类别（决定处理方式）

| 类别 | 标记 | Skill 的处理方式 |
|------|------|----------------|
| **明确修复** | ✅ fix | 直接修复，在报告中说明修复内容 |
| **有方案待修复** | 📋 planned | 执行修复方案，更新报告 |
| **建议待定** | 💡 suggest | 给出 1-3 个方案供用户选择 |
| **需仲裁** | ⚖️ arbitrate | 提出问题请用户解释意图 |
| **需决策** | 🎯 decide | 列出各方案优劣，请用户决策 |

### 3.3 问题状态流转

```
open ─→ in-progress ─→ resolved
  │                       │
  └──→ wontfix ←─────────┘
```

---

## 4. 复查报告格式

报告写入 `design/review/{slug}-review-v{version}.md`：

```markdown
# 复查报告：{标题}

> 领域范围：{domains} | 复查日期：{YYYY-MM-DD} | 状态：进行中

## 摘要

| 指标 | 数值 |
|------|------|
| 总问题数 | N |
| 已修复 | N |
| 待处理 | N |
| 需仲裁/决策 | N |
| 收敛状态 | ❌ 未收敛 / ✅ 已收敛 |

## 校核范围

| 维度 | 已检查 | 数据来源 |
|------|--------|---------|
| 原始需求追溯 | ✅/❌ | raw-input/ → business-workflow/ + er/ + frontend/ |
| 工作流一致性 | ✅/❌ | business-workflow/ → er/ + api/ + frontend/ + tdd/ |
| ER数据一致性 | ✅/❌ | entity-relationship/ → api/ + orm/ + tdd/ + frontend/ |
| API设计一致性 | ✅/❌ | platform-api/ → controller/ + orm/ + frontend/ + tdd/ |
| ORM代码一致性 | ✅/❌ | Models/ → migration/ + DB schema (PRAGMA table_info) + tdd/ + frontend/ + api/ |
| 前端功能一致性 | ✅/❌ | design/{端}/ → miniprogram/ + tdd/ + validate-frontend-api-alignment.mjs |
| 前后端集成一致性 | ✅/❌ | miniprogram/ → server-api/ + validate-frontend-api-alignment.mjs |
| TDD闭环一致性 | ✅/❌ | design/07-tdd/ → test/ → api/ |
| API功能完备性 | ✅/❌ | workflow + frontend + raw-input → api/ |
| 标准与架构合规 | ✅/❌ | path检查 + domain-registry + schema + 命名一致性检查（路由/i18n/视图文件） |
| 运行时启动验证 | ✅/❌ | 项目启动命令（AGENTS.md）+ 健康检查 + 关键 API 冒烟测试 + smoke-test-miniprogram.mjs + validate-frontend-api-alignment.mjs |

## 问题清单

### P-001: {标题}

- **维度**: 工作流 ↔ ER
- **严重度**: 🔴 严重 / 🟡 中等 / 🟢 轻微
- **来源**: `{文件路径}`
- **类别**: ✅ fix / 📋 planned / 💡 suggest / ⚖️ arbitrate / 🎯 decide
- **状态**: 🔄 open / 🛠 in-progress / ✅ resolved / ❌ wontfix
- **描述**: > {问题具体描述}
- **仲裁**（如有不一致）: > ⚖️ 代码为真相源 / 设计为真相源 / 等待用户裁决
- **仲裁决策 ID**: > {关联的 design-decisions.js DD-ID}
- **建议/方案**: > {修复建议}
- **决策记录**: > {用户的裁决内容}
- **修复结果**: > {实际执行的修复}

### P-002: ...

## 修复计划（按优先级排序）

| 优先级 | ID | 类别 | 工作量 | 依赖 |
|--------|-----|------|--------|------|
| P0 | P-001 | ✅ fix | 小 | 无 |
| P1 | P-003 | ⚖️ arbitrate | — | 等待用户 |
```

---

## 5. 交互式迭代修复流程

### 5.1 首次复查

执行完整的逐维度校核后输出首版报告。所有问题初始状态 `🔄 open`。

### 5.2 用户分批裁决 → 修复 → 更新

每次交互执行以下完整步骤：

```
Step 1 — 记录裁决
  用户对一批问题给出答案：
  - 明确指示 → 标记 ✅ fix，记录决策
  - 选择方案 → 标记 ✅ fix，记录选择
  - 仲裁澄清 → 标记 📋 planned，更新描述

Step 2 — 执行修复
  对所有 ✅ fix 的问题：
  - 定位到对应的数据/代码文件
  - 执行修改
  - 验证结果

Step 3 — 级联检查
  修复后执行以下验证，确认未引入新问题：

  3a. **重新触发 §8.8 tdd-execute** —— 运行全量测试，确认：
      - 之前通过的测试仍然通过（无回归）
      - 本轮修复的失败测试现在通过
      - 如有新失败 → 生成新的 P 级问题条目
  3b. **重新执行受影响维度的校核** —— 根据修复涉及的文件类型：
      - 涉及设计文件（workflow/ER/API/页面）→ 重新委托对应 skill 的一致性检查
      - 涉及代码文件（Controller/DTO/ORM）→ 重新委托 api-code-gen 检查
      - 涉及测试文件 → 重新委托 tdd-build 检查
  3c. 根据 3a+3b 的结果更新问题状态：
      - 自然解决 → 标记 ✅ resolved
      - 改变形态 → 更新描述和类别
      - 引入新问题 → 新增条目

Step 4 — 更新报告
  - 更新状态和统计数字
  - 保存新版本文件

Step 4.5 — 更新同步状态
  根据本轮修复涉及的文件，更新 `design/review/sync-status.js`：
  - 所有被修改的资产版本号 +1
  - 被修复的问题涉及的资产对 → dirty=false
  - 本轮未处理的问题涉及的资产对 → 保持 dirty=true（含 dirty_reason）
  - 更新 last_review 时间戳

Step 5 — 请求下一批
  询问用户是否继续
```

### 5.3 收敛判定

以下四个条件**同时**满足时视为收敛：

1. 所有问题状态为 `✅ resolved` 或 `❌ wontfix`
2. **§8.8 tdd-execute 全量测试通过（0 失败）**——修复循环未引入回归
3. 连续 2 轮修复后未发现新的实质性问题（在标准 §10.6 基础上增加第 3、4 条）
4. **`sync-status.js` 中无 dirty 资产**——所有资产对的同步状态已确认

### 5.4 报告版本管理

每次迭代更新后保存新版本：
- `design/review/{slug}-review-v1.md` — 初版
- `design/review/{slug}-review-v2.md` — 第一轮后
- ...
- `design/review/{slug}-review-final.md` — 最终版

> 收敛后所有版本（v1…final）移入 `_archived/`（见 §6.2 归档操作步骤）。根目录仅保留未收敛的复查报告。

---

## 6. 最终归档

### 6.1 归档目录约定

| 位置 | 存放内容 |
|------|---------|
| `design/review/`（根目录） | **仅活跃文件**：未收敛的复查报告（收敛状态为"进行中"或"未收敛"）+ `CHANGELOG.md` |
| `design/review/_archived/` | **所有已收敛的复查报告及过程文件**（包括各版本报告、合并策略讨论、执行计划等） |

> **归档规则：** 复查的目的是修复。每轮复查一旦收敛（所有问题 `✅ resolved` 或 `❌ wontfix`），该复查产生的全部文件应立即移入 `_archived/`。根目录永远只留「还没修完的」复查报告。
>
> **命名规范：** 归档目录使用 `_archived/`（下划线前缀），与 `design/` 下其他子目录（`02-business-workflow/_archived/`、`03-entity-relationship/_archived/` 等）保持一致。

### 6.2 归档操作步骤

每轮复查收敛后，按以下步骤执行归档：

**Step 0 — 清理上一轮的旧归档文件：**

1. 检查 `git status` 中 `design/review/_archived/` 下是否有未提交的变更（modified / deleted / new files）
2. 如有未提交变更 → `git add design/review/_archived/` + `git commit`，**然后 `git rm` 删除这些旧归档文件**
3. 如无未提交变更（已在上轮清理过）→ 跳过此步

> **为什么删除旧归档文件：** 上一轮的复查结果已保存在 git 历史中。每轮复查收敛后，上一轮的归档文件就从「最近的参考」降级为「纯历史」。Git 负责保存历史，工作区只保留本轮刚完成的复查作为最近参考点。需要查阅历史时 `git log -- design/review/_archived/` + `git show` 即可。

**Step 1 — 更新本轮复查文件并归档：**

1. 更新复查报告头部状态为 `✅ 已收敛`，确认所有问题状态为 `✅ resolved` 或 `❌ wontfix`
2. **归档门控检查：** 逐条确认
   - 所有 `📋 planned` / `💡 suggest` 的问题已写入 `remaining-issues.md` 或后续复查计划
   - 所有 `🔴 严重` 问题有对应的修复提交或明确的 `wontfix` 理由
   - **禁止将状态为 `open` 或 `in-progress` 的问题随报告一起归档**
   - **禁止将 `planned` 问题标记为 `resolved` 而不实际修复代码**
3. 将该复查的所有版本文件移入 `_archived/`（v1 → vN → final → 执行计划等全部移入）
4. 更新 `CHANGELOG.md` 记录此次复查的收敛结论和归档操作
5. 根目录仅保留当前未收敛的复查报告

**Step 2 — 提交（保留本轮文件）：**

1. `git add` 本轮新增/移动的归档文件 + CHANGELOG
2. `git commit`
3. **不删除本轮刚归档的文件**——它们是最新的参考点，保留在工作区供日常查阅

### 6.3 交互内容归档

修复过程中的所有对话——用户的仲裁、决策、澄清——以原始文本追加到 `design/01-raw-input/{slug}-review-discussion.md`：

```
## {YYYY-MM-DD} 复查修复对话

### 用户对 P-001 的裁决
{原文}

### 用户对 P-003 的选择
{原文}
```

> 这些内容本身就是对设计的澄清和补充，是重要的原始输入。按标准 §7 执行：存档即原文。

---

## 7. 完成检查清单

| 检查项 | 要求 |
|--------|------|
| 所有 13 个校核维度（D0-D12）已执行（覆盖全链条 26+ 对追溯关系） | 报告中每维有结果 |
| 问题分类完整 | 每项有严重度/类别/状态 |
| 修复方案已记录 | 每项有方案或建议 |
| 用户裁决已记录 | arbitrate/decide 类有用户输入 |
| 级联影响已处理 | 修复后重新检查 |
| 文本与 i18n 完整性已检查 | 所有 display/button/input 组件的 text/label/placeholder 字段完整，i18n key 已定义 |
| 命名一致性已检查 | 路由路径/名称、视图文件名、i18n 键名无旧术语残留，严格遵循命名一致性约束（kebab-case、层级对应） |
| **前端冒烟测试通过** | `node scripts/smoke-test-miniprogram.mjs` 确认 0 缺失文件、0 语法错误 |
| **前端-后端 API 对齐校验通过** | `node scripts/validate-frontend-api-alignment.mjs` 确认 PATH NOT FOUND = 0、BODY FIELD mismatch = 0 |
| **后端架构合规检查通过（L2+）** | 架构契约运行器退出码 0（mechanical 全过、债务未到期）+ heuristic WARN 与 reviewLedger 逐条走查（委托 `backend-architecture-design`，规范 `_shared/arch-contract-spec.md`） |
| 最终报告已归档 | 在 design/review/_archived/ 下 |
| 交互内容已存档 | 在 design/01-raw-input/ 下 |
