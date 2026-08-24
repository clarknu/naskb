---
name: mobile-code-gen
version: 1.0.0
description: |
  移动端代码生成与一致性检查——从 tree.js 功能树生成移动端页面骨架代码，
  并对已实现的页面与功能树进行组件级、路径级、API 调用级一致性校核。
  注：本技能与技术框架无关（小程序 / Flutter / React Native 等均适用），
  只定义代码生成的通用原则。
triggers:
  - 移动端代码生成
  - 前端代码生成
  - 手机端代码生成
  - 页面代码生成
  - 移动端一致性检查
  - 前端实现检查

lineage:
  origin: arb-hub
  sources:
    boxing:        {sha256: 56f84a5fbf62}
    zy-iot-ai:     {sha256: 58454bbc7d5b}
    zy-ai-consult: {sha256: 58454bbc7d5b}
---

# mobile-code-gen — 移动端代码生成与一致性检查

## 技能说明
- 所属流水线：页面功能设计（步骤 8.4）→ 用户端代码实现（步骤 8.7）
- 输入源：`design/06-{client-slug}/data/tree.js`（页面功能树，由 `mobile-app-design` 产出）

> **输入规格契约：** tree.js 节点字段以 mobile-app-design「节点字段说明」为唯一 schema（含 refEntity/refFields/page_input/page_output/api_ref/sends）；字段缺失或改名时先回上游补齐再生成。

- 输出目录：`src/{client-slug}/`（小程序 `src/miniprogram-{name}/`、App `src/app/`，遵循 development-standard §5.2.1 三层结构规则；`{client-slug}` 见 AGENTS.md 客户端命名规范）
- 每个页面生成页面框架文件（技术栈决定具体文件类型——模板/样式/逻辑/配置）
- 具体的目标框架（小程序/Flutter/RN等）由项目 AGENTS.md 定义，本技能只描述通用生成原则

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

**前端代码中，所有业务状态/类型值必须引用共享常量定义，严禁在模板或逻辑中硬编码字符串字面量。**

| 规则 | 说明 |
|------|------|
| **定义共享枚举映射** | 在 `src/shared/enums.js`（或项目约定的常量文件）中集中定义所有后端枚举的前端映射（key + label），格式：`{ ORDER_STATUS: { PENDING_PAYMENT: 'pending_payment', PAID: 'paid', ... } }` |
| **组件中引用常量，不写死字符串** | `status === ORDER_STATUS.PAID` ✅ / `status === 'paid'` ❌ |
| **状态筛选/展示用映射表** | 下拉选择器的选项列表从枚举映射文件导出，不手写 `<option value="paid">已支付</option>` |
| **API 请求中的枚举值从常量取** | POST body 中 `{ status: ORDER_STATUS.PENDING_PAYMENT }`，不写 `{ status: 'pending_payment' }` |
| **与后端枚举保持命名一致** | 前端常量 key 与后端枚举成员名对应（如 Python Enum 成员名），值以项目约定的序列化格式（如 snake_case）为准 |

> **反例：** 模板里写 `<view wx:if="{{order.status === 'pending_payment'}}">待支付</view>`，下拉框里手写 `<picker range="{{['待支付','已支付','已退款']}}">`。
> 枚举值改名或新增时，需要全局搜索替换字符串，极易遗漏。
>
> **正例：** `const { ORDER_STATUS, ORDER_STATUS_LABEL } = require('../../shared/enums');`，
> 模板里 `wx:if="{{order.status === ORDER_STATUS.PENDING_PAYMENT}}"`，
> 下拉框 range 从 `ORDER_STATUS_LABEL` 动态生成。

---

## 代码生成方法论
1. **读取 tree.js**：解析 `tabs` → `pages` → `zones` → `components` 的层级结构
2. **生成前校验（数据流完整性）**：在生成任何前端代码之前，先校验追溯字段：
   - 每个 page 节点是否已填写 `page_input` / `page_output`
   - 触发导航或 API 调用的 component 节点是否已填写 `api_ref` / `sends`
   - **数据流断路检查**：若 `page_output.params[]` 中包含下游页面的 `page_input.params[]` 中不存在的字段，标记为 ⚠️ `data_flow_broken`
   - **不阻塞生成**：缺失/断路的追溯字段以 ⚠️ 警告清单输出（`untraced` 项），仍生成骨架代码并在对应位置标注 TODO 注释；警告项由复查阶段（review D6/D10）兜底补齐后再移除
3. **解析组件**：对每个 component 节点：
   - `display` 类型 → 生成数据展示代码
   - `button` 类型 → 生成点击事件 + 导航/API 调用代码
     - 生成 `wx.navigateTo` 时，验证传递的 params 是否匹配目标页面的 `page_input.params[]`
     - 在生成的代码中标注 trace 注释：`// @trace from:{page_id}.page_output → to:{page_id}.page_input`
   - `input` 类型 → 生成输入表单代码
   - `modal` 类型 → 生成弹出框代码
4. **生成页面文件**：每个 page 节点生成对应的页面文件（模板+样式+逻辑+配置）
5. **解析 refEntity/refFields**：组件标注的数据依赖 → 生成对应的 API 调用代码
   - 生成 `wx.request` / API 调用代码时，验证 `sends[]` 中的字段是否与 API 的 `consumes[]` 声明匹配
   - 在生成的代码中标注 trace 注释：`// @trace api:{method} {path} sends:[{fields}]`
6. **注册页面**：更新应用的页面路由配置

## 一致性检查模式

### 输入
- 功能树设计: `design/06-{client-slug}/data/tree.js`
- 已实现的页面代码: `src/{client-slug}/pages/`
- 应用页面配置: `src/{client-slug}/` 下的路由/配置入口文件
- 域注册表: `design/domain-registry.js`

### 检查步骤

1. **页面存在性检查**：tree.js 中的每个 page 节点 → 对照代码目录下的实际页面文件：
   - 标记设计中有但代码中没有的页面
   - 标记代码中有但设计中不存在的页面

2. **组件映射检查**：tree.js 中标注了 `refEntity` 的 component → 对照对应的页面模板文件：
   - 标记 refFields 中引用的字段在模板数据绑定中是否有对应
   - 标记 refEntity 指向的实体在页面逻辑中是否有对应的 API 调用

3. **API 调用一致性检查**：tree.js 中 refFields 暗示的 API 需求 → 对照页面逻辑文件中的网络请求：
   - 标记设计需要但代码中缺失的 API 调用
   - 标记代码中有但设计未暗示的 API 调用

4. **导航路径检查**：tree.js 中标注了 `refs` 的组件 → 对照代码中的页面跳转实现：
   - 标记 refs 指向的页面路径在代码中是否有对应导航实现

5. **数据流完整性检查**：`page_output` → `page_input` 全链字段匹配：
   - 比对每个 page 的 `page_output.params[]` 与下游页面的 `page_input.params[]`，标记不匹配的字段

6. **组件-API 绑定检查**：`api_ref` 端点存在且 `sends` 字段匹配：
   - 验证每个 component 的 `api_ref` 指向的端点是否存在
   - 验证 `sends[]` 中的字段是否与 API 声明的 `consumes[]` 一致

7. **`@trace` 注释完整性检查**：扫描生成的代码，确认每个 API 调用和页面导航处有 `@trace` 注释标注数据来源/去向（`// @trace from:... → to:...`）

8. **枚举字符串硬编码检查**：全量扫描页面代码（模板 + 逻辑文件），检查是否存在：
   - 硬编码的状态字符串字面量（如 `status === 'pending'`、`wx:if="{{status === 'active'}}"`）
   - 手写的下拉选项列表（如 `<picker range="{{['待支付','已支付']}}">`）
   - 应引用共享枚举常量但直接写了字符串的地方。详见「枚举值处理原则」

### 输出格式

> 输出格式遵循共享规范：`_shared/consistency-check-format.md`（与本 skill 同目录分发的 `_shared/` 子目录）。

输出结构化的一致性检查报告，涵盖严重度/类型/设计引用/代码路径/详情/建议。

## 使用方式
1. **代码生成**：对 Claude 说"使用 mobile-code-gen 生成 {app} 的页面代码"
2. **一致性检查**：对 Claude 说"使用 mobile-code-gen 检查 {app} 的页面与设计一致性"
3. **被 review 调用**：review skill 在前端代码一致性维度中自动委托本技能执行

## 域注册表同步

`{client-slug}` 参数从 `design/domain-registry.js` 获取。领域边界调整时，按 development-standard §5.3 规则操作。

## CHANGELOG 规范

每次代码生成或变更后，在对应 `src/{client-slug}/` 目录下更新 `CHANGELOG.md`。

## 完成检查清单

| 检查项 | 要求 |
|--------|------|
| 页面文件已生成 | 每个 tree.js 中的 page 节点有对应页面文件 |
| 页面已注册 | 新页面已添加到路由/配置入口 |
| API 调用已生成 | 标注了 refEntity 的组件有对应 API 调用代码 |
| 导航路径已实现 | tree.js 中 refs 标注的导航在代码中实现 |
| 一致性检查已通过 | 调用检查模式验证生成结果 |
| 页面数据流已验证 | 每个 page_output.params 是否被下游 page_input.params 接收 |
| 组件 API 绑定已验证 | 每个 api_ref 端点是否存在，sends 字段是否匹配 API consumes |
| 生成代码已标注 @trace 注释 | 所有 API 调用与页面导航代码均带有 @trace 注释 |

## 与相关技能的关系
| 技能 | 关系 |
|------|------|
| `mobile-app-design` | 上游——提供 tree.js 功能树 |
| `desktop-ui-design` | 平行——桌面端设计对应 desktop-ui-design |
| `api-code-gen` | 协同——前端 API 调用需与后端 API 端点对齐 |
| `tdd-build` / `tdd-execute` | 协同——生成完成后调用 tdd-execute 执行对应端测试 |
| `review` | 调度——review 委托本技能做前端代码一致性检查 |
