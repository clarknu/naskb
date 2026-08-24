---
name: desktop-code-gen
version: 1.0.0
description: |
  桌面端代码生成与一致性检查——从 tree.js 功能树（pages 格式）生成桌面端页面骨架代码，
  并对已实现的页面与功能树进行组件级、路径级、API 调用级一致性校核。
  注：本技能与技术框架无关（Web 后台 / Electron / WPF 等均适用），
  只定义代码生成的通用原则。
triggers:
  - 桌面端代码生成
  - PC 端代码生成
  - 后台代码生成
  - 桌面端一致性检查
  - 后台实现检查

lineage:
  origin: arb-hub
  sources:
    boxing:        {sha256: 871b0a794bd6}
    zy-iot-ai:     {sha256: a60ddf36c67a}
    zy-ai-consult: {sha256: a60ddf36c67a}
---

# desktop-code-gen — 桌面端代码生成与一致性检查

## 技能说明
- 所属流水线：页面功能设计（步骤 8.4）→ 用户端代码实现（步骤 8.7）
- 输入源：`design/06-{client-slug}/data/tree.js`（页面功能树，`tree.pages` 格式，由 `desktop-ui-design` 产出）

> **输入规格契约：** tree.js 节点字段以 desktop-ui-design「节点字段说明」为唯一 schema（含 refEntity/refFields/page_input/page_output/api_ref/sends）；字段缺失或改名时先回上游补齐再生成。ER 数据以 entity-relationship §2 四数组结构为准。

- 输出目录：`src/{client-slug}/`（Web 后台 `src/web-{name}/`、原生桌面端 `src/desktop-{name}/`，遵循 development-standard §5.2.1 三层结构规则；`{client-slug}` 见 AGENTS.md 客户端命名规范）
- 与 `mobile-code-gen` 平行——移动端使用 `tree.tabs` 格式，桌面端使用 `tree.pages` 格式
- 具体的目标框架由项目 AGENTS.md 定义，本技能只描述通用生成原则

## 核心原则：设计即代码，零兼容冗余

**本技能生成的代码永远只反映当前设计。不保留、不兼容、不迁就旧页面/旧组件/旧 API 调用。**

| 场景 | 做法 |
|------|------|
| 功能树有变更 | 旧页面/旧组件直接删除，不保留两套 |
| 设计删除了页面/区域/组件 | 代码中对应删除，不保留注释掉的死代码 |
| refEntity/refFields 变更 | API 调用直接更新为新字段，不保留旧字段的兼容请求 |
| 设计字段改名 | 模板绑定、数据模型全部更新为新名称，不保留旧字段映射 |
| 线上运行环境 | 同样适用——页面结构以设计为准，不做兼容层 |

> **反例：** 设计把 `UserProfile` 页面的 `Avatar` 组件改成 `PhotoWall`，于是同时保留两个组件 → **错误。**
> **正例：** 删除 `Avatar` 组件代码，新增 `PhotoWall` 组件，页面只有当前设计。

### 枚举值处理原则

**桌面端代码中，所有业务状态/类型值必须引用共享常量定义，严禁在模板或逻辑中硬编码字符串字面量。**

| 规则 | 说明 |
|------|------|
| **定义共享枚举映射** | 在 `src/shared/enums.ts`（或项目约定的常量文件）中集中定义所有后端枚举的前端映射（key + label），格式：`export const ORDER_STATUS = { PENDING_PAYMENT: 'pending_payment' as const, PAID: 'paid' as const, ... }` |
| **组件中引用常量，不写死字符串** | `status === ORDER_STATUS.PAID` ✅ / `status === 'paid'` ❌ |
| **状态筛选/展示用映射表** | 下拉选择器的选项列表从枚举映射文件导出，不手写 `<el-option label="已支付" value="paid">` |
| **API 请求中的枚举值从常量取** | POST body 中 `{ status: ORDER_STATUS.PENDING_PAYMENT }`，不写 `{ status: 'pending_payment' }` |
| **与后端枚举保持命名一致** | 前端常量 key 与后端枚举成员名对应（如 Python Enum 成员名），值以项目约定的序列化格式（如 snake_case）为准 |

> **反例：** 表格列里用 `v-if="row.status === 'pending_payment'"` 判断显示文本，下拉框里手写 `<el-option v-for="item in ['待支付','已支付']">`。
> 枚举值改名或新增时，需要全局搜索替换字符串，极易遗漏。
>
> **正例：** `import { ORDER_STATUS, ORDER_STATUS_OPTIONS } from '@/shared/enums';`，
> 模板里 `v-if="row.status === ORDER_STATUS.PENDING_PAYMENT"`，
> 下拉框 options 从 `ORDER_STATUS_OPTIONS` 动态生成。

### 生成前追溯校验

**在生成任何代码之前，必须先校验 tree.js 中每个 page / component 节点的追溯字段完整性：**

| 校验项 | 方法 | 失败处理 |
|--------|------|---------|
| `page_input` 已设置 | 检查每个 page 节点是否定义了 `page_input`（`{from, params}`） | 标注 ⚠️ untraced_page，提示补充上游来源 |
| `page_output` 已设置 | 检查每个 page 节点是否定义了 `page_output`（`{to, params}`） | 标注 ⚠️ untraced_page，提示补充下游去向 |
| `api_ref` 已设置 | 检查每个含数据交互的 component 是否定义了 `api_ref` | 标注 ⚠️ untraced_api，提示绑定 API 端点 |
| `sends` 与 `api_ref` 配套 | 检查有 `api_ref` 的 component 是否定义了 `sends[]`，且字段可追溯至 `page_input.params` 或本页产出数据 | 标注 ⚠️ untraced_sends，提示补充发送字段 |
| `page_output.params` → 下游 `page_input.params` | 检查上游 `page_output.params[]` 的每个字段是否全部出现在下游页面的 `page_input.params[]` 中 | 标注 ⚠️ data_flow_broken |
| `api_ref` 端点存在 | 检查 `api_ref` 指向的 API 端点是否在 API 设计中存在 | 标注 ⚠️ api_mismatch |

> 校验结果以 ⚠️ 警告清单输出，**不阻塞生成**——缺失/断路的追溯字段在生成的骨架代码中标注 TODO 注释，由复查阶段（review D6/D10）兜底补齐后再移除警告。

## 代码生成方法论

1. **读取 tree.js**：解析 `pages` → `zones` → `components` 的层级结构（桌面端无 TabBar，以 pages 为根）
2. **解析组件**：对每个 component 节点：
   - `display` 类型 → 生成数据展示代码
   - `button` 类型 → 生成点击事件 + API 调用代码
   - `input` 类型 → 生成输入表单代码
   - `modal` 类型 → 生成弹出框代码
3. **生成页面文件**：每个 page 节点生成对应的页面文件
4. **解析 api_ref/sends**：组件标注的 API 绑定 → 生成对应的 API 调用代码：
   - 验证 `sends[]` 中每个字段是否匹配 API 端点的 `consumes[]`（请求体字段）
   - 生成的 API 调用代码中，对每个 send 字段添加 `@trace` 注释标注数据来源：
     ```
     // @trace seat_id ← page_input.params[seat_id] (来源: 选座页 page_output)
     // @trace tier_id ← 本页数据 (来源: API GET /tiers 响应)
     ```
   - 如果 `sends[]` 中有字段无法追溯来源，标注 ⚠️ untraced_send 并提示补充
5. **注册页面并实现导航**：更新应用的路由/导航配置：
   - 验证导航参数与目标页 `page_input.params[]` 匹配
   - 在导航调用代码中添加 `@trace` 注释标注数据传递：
     ```
     // @trace → 订单确认页 page_input.params[seat_id, tier_id]
     router.push({ name: 'OrderConfirm', params: { seat_id, tier_id } })
     ```
   - 如果导航参数与目标页 `page_input.params[]` 不匹配，标注 🔴 param_mismatch

## 一致性检查模式

### 输入
- 功能树设计: `design/06-{client-slug}/data/tree.js`（pages 格式）
- 已实现的页面代码: `src/{client-slug}/`
- 应用路由配置

### 检查步骤

1. **页面存在性检查**：tree.js 中的每个 page 节点 → 对照代码目录下的实际页面文件
2. **组件映射检查**：标注了 `refEntity` 的 component → 对照对应的页面模板/逻辑文件
3. **API 调用一致性检查**：refFields 暗示的 API 需求 → 对照页面逻辑中的网络请求
4. **导航路径检查**：标注了 `refs` 的组件 → 对照代码中的页面跳转
5. **数据流完整性检查**：逐页验证 `page_output.params[]` → 下游 `page_input.params[]` 的全链传递：
   - 标记上游 `page_output.params[]` 中有但下游 `page_input.params[]` 中缺失的字段 → 🔴 data_flow_broken
   - 标记下游 `page_input.params[]` 中有但无法追溯到上游 `page_output.params[]` 或外部来源的字段 → 🔴 missing_source
   - 验证 `sends[]` → API `consumes[]` → API `produces[]` → `page_output.params[]` 链条中无字段丢失 → 🔴 field_dropped
6. **组件-API 绑定检查**：逐组件验证 `api_ref` 绑定：
   - 标记 `api_ref` 指向的端点不存在的组件 → 🔴 api_mismatch
   - 标记 `sends[]` 中有字段不在 API `consumes[]` 中的组件 → 🔴 api_mismatch
   - 标记 `sends[]` 中字段无法追溯至 `page_input.params` 或本页产出数据的组件 → ⚠️ untraced_send
7. **`@trace` 注释完整性检查**：扫描生成的代码，确认每个 API 调用和页面导航处有 `@trace` 注释标注数据来源/去向
8. **枚举字符串硬编码检查**：全量扫描页面代码（模板 + 逻辑文件），检查是否存在：
   - 硬编码的状态字符串字面量（如 `status === 'pending'`、`v-if="status === 'active'"`）
   - 手写的下拉选项列表（如 `<el-option label="待支付" value="pending_payment">`）
   - 应引用共享枚举常量但直接写了字符串的地方。详见「枚举值处理原则」

### 输出

> 输出格式遵循共享规范：`_shared/consistency-check-format.md`（与本 skill 同目录分发的 `_shared/` 子目录）。

结构化一致性检查报告（严重度/类型/设计引用/代码路径/详情/建议）

## 使用方式
1. **代码生成**：对 Claude 说"使用 desktop-code-gen 生成 {app} 的页面代码"
2. **一致性检查**：对 Claude 说"使用 desktop-code-gen 检查 {app} 与设计一致性"
3. **被 review 调用**：review skill 在前端代码一致性维度中自动委托本技能执行

## CHANGELOG 规范

每次代码生成或变更后，在 `src/{client-slug}/` 下更新 `CHANGELOG.md`。

## 完成检查清单

| 检查项 | 要求 |
|--------|------|
| 页面文件已生成 | 每个 page 节点有对应页面文件 |
| 页面已注册 | 新页面已添加到路由/导航配置 |
| API 调用已生成 | 标注了 `api_ref` 的组件有对应 API 调用 |
| API 绑定已验证 | `sends[]` 字段与 API `consumes[]` 匹配 |
| 导航路径已实现 | `refs` 标注的导航在代码中实现 |
| 导航参数已验证 | 导航传参与目标页 `page_input.params[]` 匹配 |
| 数据流完整性已验证 | `page_output.params[]` → 下游 `page_input.params[]` 全链通畅 |
| `@trace` 注释已添加 | 每个 API 调用和页面导航处有 `@trace` 注释标注数据来源/去向 |
| 一致性检查已通过 | 调用检查模式验证结果 |

## 与相关技能的关系
| 技能 | 关系 |
|------|------|
| `desktop-ui-design` | 上游——提供 tree.js（pages 格式） |
| `mobile-code-gen` | 平行——移动端代码生成使用 tree.tabs 格式 |
| `api-code-gen` | 协同——前端 API 调用需与后端端点对齐 |
| `tdd-build` / `tdd-execute` | 协同——生成完成后调用 tdd-execute 执行对应端测试 |
| `review` | 调度——review 委托本技能做桌面端代码一致性检查 |
