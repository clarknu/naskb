---
name: api-design
version: 4.0.0
description: |
  API 设计技能——将业务工作流和实体关系图转化为 API 设计数据文件，
  通过 api-viewer.html 提供交互式查阅。支持 REST、IoT（MQTT/WebSocket）等协议。
triggers:
  - API 设计
  - API 端点
  - 接口设计
  - REST API
  - 路由设计
  - 端点设计
  - API 契约
  - 接口定义
  - 路由规划
lineage:
  origin: arb-hub
  sources:
    boxing:        {sha256: 0aa6835bbf99}
    zy-iot-ai:     {sha256: aa635742c3cc}
    zy-ai-consult: {sha256: aa635742c3cc}
---

# API Design

将业务工作流和 ER 实体关系转化为 API 设计数据文件（`design/04-platform-api/data/`），
通过 `api-viewer.html` 渲染为交互式文档。**协议无关**，同一套方法论同时适用于 REST、IoT 和内部模块接口（Internal API）。

## 设计规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | **契约先行** | API 设计文档是实现和测试的核心合约。每个端点穷尽 6 个维度（前置条件→执行步骤→后置效果→状态机→副作用→关联 API） |
| 2 | **与 ER 一致性** | 请求参数、响应字段、枚举值必须与 ER 图中的实体定义一致 |
| 3 | **域注册表同步** | 开工前先读 `design/domain-registry.js`，改领域边界前先写注册表 |
| 4 | **决策可追溯** | 每次设计操作前，将原始输入追加到 `design/01-raw-input/{domain-slug}.md` |
| 5 | **错误可预期** | 每个端点明确列出 3-6 个典型错误场景（状态码 + error_code + 触发条件） |
| 6 | **CHANGELOG 必写** | 每次变更后在 `design/04-platform-api/CHANGELOG.md` 记录 |
| 7 | **权限点映射** | 端点标注对应权限点（引用 business-workflow）。**只做映射，不定义新权限点**；缺失时反推 business-workflow 补充 |

---

## 1. 设计流程

```
业务工作流 → [1. 输入采集] → [2. 实体→端点映射] → [3. 逐端点详设] → [4. 输出 JS 数据文件] → [5. Viewer 验证]
  ER 数据 ↗                                                                              ↘ 原始需求
```

**每次被调用时，先输出执行计划与用户确认，再开始执行。**

---

## 2. 输入来源

| 输入 | 来源 | 必要性 |
|------|------|:---:|
| 业务工作流数据 | `design/02-business-workflow/data/{slug}.js` | ★★★ |
| 实体关系数据 | `design/03-entity-relationship/data/{slug}.js` | ★★★ |
| 原始需求记录 | `design/01-raw-input/` | ★★☆ |
| 现有 API 设计 | `design/04-platform-api/data/{slug}.js` | ★★☆ |
| 终端对话 | 用户直接输入 | ★☆☆ |

---

## 3. 设计过程

### 3.1 输入采集

1. 读取域注册表，获取领域 slug 列表
2. 从工作流提取：角色、业务流程、状态机、业务规则、异常流程
3. 从 ER 提取：实体、字段、关系、跨域引用链
4. 从原始需求补充：场景、历史决策、非功能需求
5. 存档所有输入到 `design/01-raw-input/{domain-slug}.md`，标注时间戳

### 3.2 端点映射

**REST**——实体 → 路由：

| 映射规则 | 示例 |
|---------|------|
| 实体 CRUD | `Article` → `GET/POST /articles`, `GET/PUT/DELETE /articles/{id}` |
| 状态机操作 | `publish` → `POST /articles/{id}/publish` |
| 关系操作 | `Article`↔`Category` → `GET /articles/{id}/category` |
| 个人视图 | `/me` 前缀 |
| 管理视图 | 运营 `Staff*` 权限 |

**IoT**——功能 → 动作：

- 每个设备功能产生一个 action（如 `angle_adjust`、`massage`）
- action 方向：`device-to-cloud`（上报）/ `cloud-to-device`（指令）
- 流式传输：`type: "call+stream"` + `streaming` 配置

### 3.3 逐端点详设（6 维度核心）

| 维度 | 内容 | 来源 |
|------|------|------|
| **前置条件** | 调用前必须满足的业务状态 | 工作流状态机前置状态 |
| **执行步骤** | ①→②→③ 关键处理步骤 | 工作流处理步骤 |
| **后置效果** | 成功后数据如何变化 | 状态机目标状态 |
| **状态机影响** | 涉及哪些字段的状态转换 | 工作流状态定义 |
| **副作用** | 通知/日志/推送等次要操作 | 需求隐性要求 |
| **关联 API** | 上下游链路中的其他接口 | 流程顺序 |

每个端点还应列出：错误场景（3-6 个）、幂等标注、IoT 指令的 RPC 超时和重试策略。

### 3.4 REST 附加维度

REST 端点额外包含：

| 维度 | 要点 |
|------|------|
| 请求参数 | Path / Query / Body 三表，每字段含类型、必填、约束、示例 |
| 响应格式 | 完整 JSON 示例 + 字段说明表；分页用 `{ list, total, page, page_size }` |
| 缓存策略 | 公开数据 HTTP 缓存 + TTL；私有数据 `no-store`；配置类 Redis 缓存 |
| 频率限制 | 默认 per-IP 1000/min，认证 10/min，写操作 60/min，敏感 5/min |

---

## 4. 文件结构与渲染架构

### 4.1 文件布局

```
design/04-platform-api/
├── api-viewer.html              ← 通用渲染器（项目无关）
├── data/
│   ├── loader.js                ← 数据加载入口（files 数组注册所有数据文件）
│   ├── rest/
│   │   ├── protocol.js          ← REST 协议定义
│   │   └── {domain}.js          ← REST 领域端点
│   ├── iot/
│   │   ├── protocol.js          ← IoT 协议定义
│   │   ├── {device}.js          ← IoT 设备指令
│   │   └── {device}-examples.js ← 调用示例
│   ├── internal/                ← 内部模块接口（可选，含 protocol.js）
│   └── ai-tools/                ← AI Tools 协议（规划中，含 protocol.js）
```

### 4.2 协议定义文件（data/{category}/protocol.js）

挂载到 `window.API_DATA["protocol-{id}"]`。核心字段：

```js
{
  envelope: {                         // 消息封包格式
    fields: { type: { ref: "message_type" }, action: { ref: "action_name" }, ... },
    deduplication: { mechanism, window, algorithm },
    maxMessageSize: "..."
  },
  protocolContent: [ ... ],           // 📋 协议定义菜单内容
  envelopeContent: [ ... ],           // 📨 消息封包菜单内容（流式/RPC/状态码/字段编码/返回约定）
  sections: [                         // 左侧导航菜单
    { id: "protocol",  label: "📋 协议定义", type: "protocol" },
    { id: "envelope",  label: "📨 消息封包", type: "envelope" },
    { id: "{device}",  label: "{设备}",      type: "device", device: "{device}", children: [...] },
    { id: "enums",     label: "📊 公共枚举",  type: "sharedEnums", dataSource: "{device}" },
    { id: "examples",  label: "📋 调用示例",  type: "examples", dataSource: "{device}" }
  ],
  renderRules: { actions: {...}, enums: {...} }
}
```

**`protocolContent` vs `envelopeContent` 归属：**

| protocolContent（协议本身） | envelopeContent（消息形式） |
|---------------------------|---------------------------|
| 协议概述、术语表、部署模型 | 流式传输帧格式 |
| 承载层（MQTT/WebSocket） | RPC 调用语义（call/ack） |
| 设备身份与认证、心跳 | 状态码体系 |
| 版本历史、相关文档 | 字段定义与编码、返回约定 |

### 4.3 设备指令文件（data/iot/{device}.js）

挂载到 `window.IOT_DATA["{device-id}"]`。**第一行必须** `window.IOT_DATA = window.IOT_DATA || {};`。

```js
{
  endpoints: [{ action, direction, type, envelope: { payload }, rpc, response, errors, notes }],
  categories: { "{cat}": { label, icon, actions: [...] } },
  sharedEnums: {
    message_type: { values: [{ value: "call", desc: "请求" }, { value: "ack", desc: "响应" }] },
    action_name:  { values: [/* 全部 action 名称 */] },
    // 业务枚举...
  }
}
```

### 4.4 REST 领域文件（data/{domain}.js）

挂载到 `window.API_DATA["{slug}"]`。端点结构（从 boxing 项目验证）：

```js
{
  domain, title, slug, description,
  _permission_lookup: { "PermId": "名称" },
  overview_blocks: [{ type: "table", headers, rows }, { type: "note", ... }],
  design_decisions: [{ title, detail }],
  endpoints: [{
    id, protocol: "rest", method, path, permission, summary, scenario, description,
    business_logic: { preconditions, steps, post_effects, state_machine, side_effects, related_apis },
    path_params, query_params, body_params,     // 请求参数（各为 7 列数组）
    responses: [{ description, json, fields }],  // 响应（含 JSON 示例 + 字段表）
    errors: [["HTTP码", "error_code", "条件", "说明"]],
    idempotency: { is_idempotent, method, retry },
    caching: { method, ttl, note },              // 仅 GET
    rate_limit: { limit, dimension, note }
  }]
}
```

> **完整模板**：`.agents/skills/sfds/skills/api-design/templates/rest-domain-template.js`（含 GET 列表 + POST 创建两个带注释的示例端点）

### 4.5 模板文件

新项目从以下模板启动，替换 `{PLACEHOLDER}` 即可：

| 模板 | 路径 |
|------|------|
| 协议定义 | `.agents/skills/sfds/skills/api-design/templates/protocol-template.js` |
| 设备数据（IoT） | `.agents/skills/sfds/skills/api-design/templates/device-data-template.js` |
| 领域数据（REST） | `.agents/skills/sfds/skills/api-design/templates/rest-domain-template.js` |

---

## 5. 实战铁律（跨项目协议设计踩坑沉淀）

### 铁律 1：Section 内容归属

**判断标准**：描述"消息长什么样、怎么收发"→ 归 `envelopeContent`。描述"协议在什么链路上跑"→ 归 `protocolContent`。

### 铁律 2：信封字段引用公共枚举

```js
// ✅ type: { type: "enum", ref: "message_type" }
// ❌ type: { type: "enum", values: ["call","ack"] }
```
`sharedEnums` 中必须有对应的 `message_type` 和 `action_name`。

### 铁律 3：数据定义 = 必须渲染

每新增一个属性，检查 `api-viewer.html` 中是否有对应渲染路径。重点关注：`deduplication`、`maxMessageSize`、全部 `statusCodes`（每条都要 code+meaning+description，不可只列概要）。

### 铁律 4：调用示例包裹完整信封

数据文件只存 payload。`renderExamples` 在渲染时自动包裹完整 call/ack 信封（ver/msg_id/type/action/ts + payload；ack 额外含 ref_id/code）。

### 铁律 5：JS 对象禁止重复 key

`envelope`、`addressing`、`security` 易出现重复定义（后写静默覆盖）。检查：`grep -n "^\s*\w+:" protocols/{name}.js | sort | uniq -d`。

### 铁律 6：导航锚点设在自身元素

```js
// ✅ el.id = 'cat-' + catKey;
// ❌ el.parentNode.id = 'cat-' + catKey;
```

### 铁律 7：发布同步覆盖子目录

`cp data/*.js` 不递归子目录。必须显式 `cp data/iot/*.js publish/api/data/iot/`。同步后验证：`grep "enum_name" publish/api/data/ -r`。
> **职责归属：** 完整发布流程委托 `sync-design-to-publish` skill 执行（见 §6.2）。

---

## 6. 验证与发布

### 6.1 输出验证

| 检查项 | 方法 |
|--------|------|
| 工作流覆盖 | 每个 action 节点有对应端点 |
| 状态转换覆盖 | 每个状态转换有对应操作 |
| 权限点覆盖 | 每个权限点有端点引用，无死权限 |
| 6 维度完整 | 每个端点 preconditions/steps/post_effects/side_effects/related_apis 非空 |
| 枚举附录 | 文档末尾有完整枚举值表 |
| Viewer 验证 | `file://` 加载 api-viewer.html，0 console errors，所有 section 可点击展开 |

### 6.2 同步到 publish/

> **职责归属：** 设计文档发布（复制到 publish/ + 部署）统一由 `sync-design-to-publish` skill 负责。
> 本 skill 仅负责 API 设计资产自身的正确性；需要发布时委托 `sync-design-to-publish`，不在本 skill 内重复实现发布逻辑。

```bash
# 提示：完整发布流程（含 data/rest、data/iot、data/internal、data/ai-tools 子目录）见 sync-design-to-publish 的映射表与执行流程
cp design/04-platform-api/api-viewer.html publish/api/index.html
```

### 6.3 新增 REST 领域检查清单

- [ ] 领域数据文件 `data/{domain-slug}.js`
- [ ] `_permission_lookup` 与本域权限点一一对应
- [ ] `overview_blocks` 含子域概述表 + 设计说明
- [ ] 每个端点：6 维度 business_logic 完整
- [ ] 每个端点：错误场景引用 §7.2 错误码区间
- [ ] GET 端点标注 `caching`、POST 标注 `idempotency`
- [ ] 响应定义含 JSON 示例 + 字段说明表
- [ ] 新文件经 `data/loader.js` 的 files 列表注册（viewer 通过 `data/loader.js` 注入数据）

### 6.4 新增协议检查清单

- [ ] 协议定义文件 `protocols/{id}.js`
- [ ] `sections` 含 `protocol` + `envelope` + device section
- [ ] `envelope.fields` 中枚举字段用 `ref`（铁律 2）
- [ ] `protocolContent`/`envelopeContent` 归属正确（铁律 1）
- [ ] 状态码每条完整列出 code+meaning+description（铁律 3）
- [ ] 设备数据文件第一行 `window.IOT_DATA = window.IOT_DATA || {}`
- [ ] `sharedEnums` 含 `message_type` + `action_name`
- [ ] `categories` 与 device section `children` 对应
- [ ] 示例文件创建
- [ ] 新文件经 `data/loader.js` 的 files 列表注册（viewer 通过 `data/loader.js` 注入数据）
- [ ] `file://` 验证通过，0 errors
- [ ] 发布同步覆盖子目录（铁律 7）

---

## 9. Viewer 增强模式（实战沉淀）

> ⚠️ **当前分发的 `api-viewer.html` 为 REST 视图参考实现**（已落地域下拉、端点卡片、公共约定渲染）；本节描述的协议 Tab、三级 hash 路由、流式 RPC 渲染等增强**尚未实现于模板**（属规划中，见 §10.5 🟡）。新增项目参照时须先确认 viewer 已具备这些能力，勿将本节当作已验证事实直接套用。

### 9.1 侧边栏二级菜单

对于内容较长的 section（如公共枚举、调用示例），在侧边栏自动生成二级菜单，无需在页面内部加导航：

- **共享枚举**：`section.type === 'sharedEnums'` 时，读取 `dataSource.sharedEnums` 的 key 列表，生成子项。点击子项时，如果在同一 section 内则跳过 `showSection` 重建，直接 `scrollIntoView`
- **调用示例**：`section.type === 'examples'` 时，读取示例数据的 action 列表生成子项
- **设备子分类**：设备 section 的 `children` 自动渲染为二级菜单，点击时定位到对应 `cat-{category}` 锚点

### 9.2 URL Hash 路由

支持三级 hash 路由：`#/{协议}/{section}/{sub}`

- `updateHash(sub?)` 在切换 tab/section/子项时自动更新 `history.replaceState`
- `restoreFromHash()` 在页面加载时解析 hash，自动恢复到对应位置
- 恢复时绕过 `switchTab`（避免其覆盖 hash），直接设置 `currentProtocol` + 延迟 `showSection`
- 恢复含 sub 时：延迟 500ms 后 `scrollIntoView` + `updateHash(sub)` 保持路由完整

### 9.3 同 section 内跳转优化

当用户已在某 section 内，点击侧边栏子项时，不调用 `showSection`（会 `innerHTML = ''` 清空重建导致闪烁），直接 `scrollIntoView`。

---

## 10. 协议设计模式（实战沉淀）

### 10.1 设备能力边界（limits）

设备在 `connect` 注册时通过 `configurations[].limits` 上报能力边界，平台据此校验指令合法性 + AI 据此生成提示。

```json
"limits": {
  "min": -90, "max": 90, "unit": "degree",
  "options": ["sleep", "flat", "custom"]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `min` / `max` | int | 数值边界。替代 angle_min/target_min 等专用字段 |
| `unit` | enum:limit_unit | 单位。22 个值（degree/celsius/fahrenheit/kelvin/second/millisecond/minute/hour/hz/khz/rpm/percent/lux/decibel/bpm/mmhg/ppm/volt/millimeter/centimeter/meter/kilogram） |
| `options` | string[] | 离散枚举约束，泛型，不绑死特定枚举 |

原则：全行业通用范围（如亮度/音量 0-100）在协议字段 desc 中写死，不放入 limits。只有因设备型号而异的物理边界才上报。

### 10.2 分区能力推导

不单独上报 `zone_capabilities`（9 个 bool），而是由平台从 `configurations` 自动推导——同一 `position + device_type` 出现 `left` + `right` 两条即判定为双区。

### 10.3 统一设备标识

`configurations[]` 项中加 `id` 字段（可选），需要独立标识的设备（如 sleep_monitor、smart_terminal）通过此字段上报，不另建顶层对象。

### 10.4 故障上报机制

故障从 `status_notification` 根级下沉到 `sub_device_events[]` 子设备级，每个子设备独立上报两个平级字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `fault` | enum:device_fault | 7 大类（communication/mechanical/execution/power_supply/protection/user_intervention/sensor_acquisition） |
| `fault_code` | int | 具体故障码，与 fault 配合查表。编码段 1xx~7xx |

### 10.5 AI Tools 协议（第三类 API）

> 🟡 本节规划中，待实现。

为 AI Agent 提供 OpenAI Tool Calling 格式的 Tool 定义。每个 Tool 映射到一个 ZYRIC 设备操作指令，关键设计点：

- **动态 limits 注入**：调用 AI 时根据设备 `limits` 动态改写 Tool 的 JSON Schema `minimum`/`maximum`，让 AI 天然知道设备边界
- **参数描述带单位**：利用 limits.unit 提供多地区单位转换提示
- **不暴露的指令**：connect/heartbeat/status_notification/firmware_update 等平台/设备内部指令不对 AI 暴露

数据文件 `data/ai-tools/tools.js`，协议定义 `data/ai-tools/protocol.js`，Viewer 注册第三个 Tab（**规划中**：当前 `api-viewer.html` 未实现协议/AI Tools 视图，协议资产现阶段以数据文件 + 人工查阅方式交付，见本节 🟡）。

### 10.6 AI 工具契约设计铁律（LLM 消费者视角，2026-08-23 教训固化）

> **教训来源**：设备使用策略「用户设定更新工具」首版采用 `updates` 数组（批量直觉映射），
> 用户指出「单目标工具 + 一个回复多个 tool_calls」更优。根因：用面向**确定性 API** 的直觉
> （批量操作 → 批量参数）设计**概率模型消费者**（LLM）的工具契约。
> 本节约束此类失误再发生——**凡设计 AI tool schema，强制过本节清单**。

**核心原则：工具契约的消费者是概率模型（LLM），不是确定性程序。**

| # | 铁律 | 说明 |
|---|------|------|
| 1 | **参数尽量扁平** | 避免嵌套数组/对象——嵌套越深，LLM 结构化生成错误率越高。能用扁平参数表达的需求不用数组 |
| 2 | **单职责** | 一个工具调用 = 一个原子动作（如「更新一个目标」）。批量 = 一个回复内多个调用（parallel tool_calls 是模型原生能力，tool-calling 循环天然逐个执行 + 按 tool_call_id 回填） |
| 3 | **部分失败独立反馈** | 每个 tool_call 独立执行、独立结果回填 → AI 精确反馈（「A 成功，B 失败因为…」），执行器无需定义「整批/部分」语义 |
| 4 | **先列方案空间再选型** | 涉及接口形态的决策至少列 2 个备选，用显式标准对比（生成可靠性 / 模型原生能力 / 部分失败粒度 / 执行器复杂度 / 反馈精度 / token 开销），把选型理由写进设计资产（raw-input 决策记录） |
| 5 | **语义与形态分开评审** | 先确认需求语义（做什么），再单独评审接口形态（怎么表达）——形态层对 LLM 消费者有专门维度，不复用 REST 批量直觉 |
| 6 | **无把握时主动暴露** | 对形态选择无十足把握时，把 2~3 个方案 + 推荐一起提交评审，不直接落一个（等用户发现不如主动暴露） |

**何时适用**：所有 AI Tools 协议设计（`data/ai-tools/`）、`tool_definitions` 实现、以及与 LLM 交互的任何函数契约。REST/内部 API 不套用（消费者是确定性程序，批量参数合理）。

---

## 7. REST 公共约定

> 以下约定来自 boxing-competition-operation 项目，适用于所有 REST API 设计。
> 已固化为 `design/04-platform-api/data/_conventions.js`（api-viewer 自动渲染为附录）。

### 7.1 通用响应格式

```json
// 成功:  { code: 0, message: "ok", data: {...}, request_id: "..." }
// 错误:  { code: 4xxxx, message: "...", error_code: "INVALID_PARAMETER", detail: {...}, request_id: "..." }
// 分页:  { list: [...], total: 120, page: 1, page_size: 20, total_pages: 6 }
```

### 7.2 业务错误码分配

| 范围 | 类别 | 常用 error_code |
|------|------|----------------|
| `0` | 成功 | — |
| `40001`–`40999` | 客户端参数错误 | `INVALID_PARAMETER`(40001) |
| `41001`–`41999` | 鉴权与权限 | `UNAUTHORIZED`(41001), `TOKEN_EXPIRED`(41002), `FORBIDDEN`(41011) |
| `42001`–`42999` | 资源状态 | `NOT_FOUND`(42001), `CONFLICT`(42011), `DUPLICATE_REQUEST`(42012) |
| `43001`–`43999` | 业务规则 | 按领域自定 |
| `44001`–`44999` | 频率限制 | `RATE_LIMITED`(44001) |
| `45001`–`45999` | 外部依赖 | `DEPENDENCY_ERROR`(45001) |
| `50001`–`50999` | 服务器内部错误 | `INTERNAL_ERROR`(50001) |

### 7.3 幂等性

| HTTP 方法 | 天然幂等 |
|-----------|:---:|
| GET / PUT / DELETE | ✅ |
| PATCH | ⚠️ 使用 If-Match / 版本号可达成 |
| POST | ❌ 关键操作通过 `Idempotency-Key` 头部支持 |

Idempotency-Key：**支付发起（强制）**、订单创建（推荐）、退款申请（推荐）。缓存：成功 24h，失败 5min。

### 7.4 缓存策略

| 数据类型 | 策略 | TTL |
|---------|------|-----|
| 公开资源 | HTTP 缓存 | 5 min |
| 用户档案（公开视图） | HTTP 缓存 | 2 min |
| 订单/个人数据 | `no-store` | — |
| 系统配置 | Redis 缓存 | 10 min |

Redis 键格式：`cache:{domain}:{resource}:{id}:{view}`（单条）/ `cache:{domain}:{resource}:list:{query_hash}`（列表）。

### 7.5 频率限制

| 层级 | 维度 | 限额 |
|------|------|------|
| G1 全局 | per-IP | 1000/min |
| G2 认证 | per-IP | 10/min |
| G3 写操作 | per-user | 60/min |
| G4 敏感操作 | per-user | 5/min |
| G5 公开查询 | per-IP | 300/min |

超限返回 HTTP 429 + `RATE_LIMITED` + `Retry-After` 头部。

### 7.6 数据格式约定

| 类型 | 规则 |
|------|------|
| **分页** | `page`(int32, ≥1), `page_size`(int32, 1-100, 默认20), `sort`(string, 格式 `field:dir`) |
| **日期时间** | ISO 8601: `yyyy-MM-ddTHH:mm:ss`，纯日期 `yyyy-MM-dd`。服务端 UTC 存储 |
| **金额** | 统一以「分」为单位（int32/int64），前端自行 `/100` |
| **枚举命名** | 代码层 PascalCase（`OrderStatus.PendingPayment`），API 层 snake_case（`"pending_payment"`） |

---

## 8. 一致性检查（工作流 → API）

检查 API 设计是否完整覆盖工作流中的操作需求。review skill 在工作流→API 维度中自动委托调用。

> （R-007 定案：一致性检查上收 review 成立——ER→API 等跨资产契约校验由 review 统一调度，本节保持工作流→API 单向口径，2026-08-23）

### 检查步骤

| # | 检查项 | 方法 |
|---|--------|------|
| 1 | **端点覆盖** | 工作流中每个 action 节点 → 对照端点列表，标记缺失 |
| 2 | **状态转换覆盖** | 状态机中每个状态转换 → 对照状态变更端点，标记缺失 |
| 3 | **subprocess 覆盖** | 工作流引用的 subprocess → 检查对应 API 端点组 |
| 4 | **权限点覆盖** | 每个权限点 → 检查有端点引用，标记冗余/遗漏 |

### Issue 类型

| type | severity | 含义 |
|------|:---:|------|
| `missing_endpoint` | high | 工作流有 action 但无对应 API 端点 |
| `missing_state_transition` | high | 状态转换无对应操作端点 |
| `missing_subprocess` | medium | subprocess 无对应端点组 |
| `permission_unused` | low | 权限点无任何端点引用（可能是冗余） |
| `dead_endpoint` | low | 端点产出无前端消费 |
| `untraced` | low | 端点缺少 consumes/produces 标注 |
| `simulated_impl` | low | 实现为 Mock/Stub 而非真实逻辑 |

> （R-007 定案：`untraced` 所引 `consumes`/`produces` 端点追溯字段已在 development-standard §2.6「正向定义」数据协议表中定义（§8.3 API endpoint 行），引用成立，2026-08-23）

输出格式遵循共享规范：`_shared/consistency-check-format.md`（与本 skill 同目录分发的 `_shared/` 子目录），`source` = `workflow-to-api`。
