---
name: client-ui-design
version: 1.0.0-arb.2
description: |
  客户端页面功能设计技能（移动端 + 桌面端）——使用 design-viewer.html + data/*.js 模式
  进行页面功能结构梳理、公共页面/组件定义、前端流程编排、设计风格决策与多语言方案制定，
  生成带交互式树状展开和 SVG 流程图的统一设计规格文档。
  A1 合并产物：统一 mobile-app-design 与 desktop-ui-design，仅以「客户端类型」区分根结构——
  移动端用 tree.tabs（TabBar 根），桌面端用 tree.pages（页面集根）；渲染器自动检测适配。
  触发词消歧：命中“页面设计/前端设计/功能结构树”等通用词时，按客户端类型路由——移动端/小程序/App → client_type=mobile；PC/桌面/后台/管理端 → client_type=desktop。
triggers:
  - 页面功能设计
  - 页面结构
  - UI 结构
  - 功能结构树
  - 页面架构
  - 前端设计
  - screen design
  - page structure
  - 功能架构
  - 页面设计
  - 移动端设计
  - 小程序设计
  - App 设计
  - mobile design
  - mini-program design
  - app design
  - PC 端设计
  - 桌面端设计
  - desktop design
  - 后台设计
  - 管理端设计
lineage:
  origin: arb-hub
  case: CASE-A1
  note: A1 结构重组：将 mobile-app-design + desktop-ui-design 合并为 client-ui-design。两者共享同一方法论、节点体系、design-viewer.html 渲染器（已自动检测 tree.tabs/tree.pages），差异仅为「客户端类型」根结构（tabs vs pages）与桌面端工程约束（原规则 8–11）。合并后模板单份、路由单入口。
  sources:
    mobile-app-design: {sha256: 6626dcfc12e0, location: zy-ai-consult}
    desktop-ui-design: {sha256: 9a9299955294, location: zy-ai-consult}
---

# Client UI Design (客户端页面功能设计：移动端 + 桌面端)

本技能封装了 `design-viewer.html` + `data/*.js` 的完整工具链，覆盖**移动端（TabBar 结构）**和**桌面/PC 端（页面集结构）**的客户端 UI 设计。
所有模板文件内置在技能的 `templates/` 目录下，无需依赖外部项目。

> **客户端类型（`client_type`）：** 移动端（小程序/App）与桌面端（PC/后台/管理端）共享同一方法论、节点体系与渲染器，唯一差异是**根结构**：
> - **移动端 `client_type=mobile`**：有固定 TabBar，功能树用 `tree.tabs`（Tab组→Tab→页面）。
> - **桌面端 `client_type=desktop`**：无固定 TabBar，导航可能是侧边栏/顶部/面包屑/混合，功能树用 `tree.pages`（页面集→页面）。
> 渲染器 `design-viewer.html` **自动检测**数据格式：读到 `tree.tabs` 按 TabBar 模式渲染，读到 `tree.pages` 按页面集模式渲染。设计时只需按端产出对应根结构，无需改渲染器。

## 本技能规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | **数据依赖显式化** | 新建组件必须标注 `refEntity` 和 `refFields`（定义见「节点字段」章节），使一致性检查能进行字段级语义比对 |
| 2 | **层级深度上限（5级）** | 按"用户最少切换次数"计算，超过时把深层操作提前到浅层页面 |
| 3 | **状态作为基础属性** | 每个功能区和功能组件具有状态，不同状态下展示/操作/转换不同 |
| 4 | **权限控制映射（全层级）** | 每一级功能节点（Tab/页面/功能区/功能组件）必须标注 `perm_ref`（引用 business-workflow 权限点 id）。父节点权限决定整棵子树可见性。**只做映射，不定义新权限点**。详见原则六 |
| 5 | **API 覆盖度** | 每个功能组件必须有对应的 API 端点（按钮→POST/PUT、列表→GET、编辑→PUT/PATCH） |
| 6 | **CHANGELOG 必写** | 每次变更后在 `data/CHANGELOG.md` 记录 |
| 7 | **文本精确化（Text Precision）** | 每个功能组件必须定义精确的显示文本、按钮标签、占位文字、反馈提示和校验消息。所有文本标注 i18n key + 中文源文本。详见原则七 |
| 8 | **路由命名与业务含义一致**（桌面重点） | 路由路径和路由名必须反映实际业务含义，全为英文小写、连字符（kebab-case）。禁止旧项目遗留命名（如 `legacy-station`） |
| 9 | **组件文件命名与路由一致**（桌面重点） | 页面/组件代码文件名（`.vue`/`.tsx` 等）与路由/页面引用名完全一致（路由 `device-group` ↔ 视图 `DeviceGroup.vue`） |
| 10 | **i18n 键名与路由严格对应**（桌面重点） | i18n 键按路由/页面/组件层级与名称定义，保持完全一致（`routes.device-iot.device-group.title`）。改路由名须同步 i18n 键 |
| 11 | **减少非必要文本**（桌面重点） | 能用通用图标按钮的尽量不写文字（删除/确认/详情/创建），降低多语言维护成本 |

## 输入来源与依赖

> **⚠️ 本技能的输入有严格的依赖关系。调用本 skill 前，必须确认以下输入源已就绪。**

| 输入 | 路径 | 依赖的流水线步骤 | 就绪检查 |
|------|------|----------------|---------|
| **API 设计文档** | `design/04-platform-api/data/rest/{domain-slug}.js` | §8.3 | 文件存在且非空 |
| **ER 数据** | `design/03-entity-relationship/data/{domain-slug}.js` | §8.2 | 文件存在且非空 |
| **业务工作流** | `design/02-business-workflow/data/{domain-slug}.js` | §8.1 | 文件存在且非空 |
| **原始讨论记录** | `design/01-raw-input/{domain-slug}.md` | — | 如存在则读取 |
| **域注册表** | `design/domain-registry.js` | §8 前置 | 文件存在且 domains 数组非空 |

## 技能目录结构

```
client-ui-design/
├── SKILL.md                               ← 本文件（技能说明）
└── templates/                             ← 模板文件（复制到目标项目，与本 SKILL.md 同目录分发）
    ├── design-viewer.html                 ← 统一渲染器（5 标签页，自动检测 tabs/pages，无需修改）
    ├── loader.js                          ← 数据入口模板（复制后编辑 files 列表）
    ├── example-tree-mobile.js             ← 移动端功能结构树示例（tree.tabs）
    ├── example-tree-desktop.js            ← 桌面端功能结构树示例（tree.pages）
    ├── example-processes.js               ← 业务流程文档示例（2.4）
    ├── example-style.js                   ← 设计风格结论示例（2.5）
    └── example-i18n.js                    ← 多语言方案结论示例（2.6）
```

## 首次搭建（新项目）

按序执行以下步骤。

### 步骤 1：创建目录结构

```bash
mkdir -p {project}/design/{slug-of-app}/data
```

### 步骤 2：复制渲染器

```bash
cp templates/design-viewer.html \
   {project}/design/{slug-of-app}/
```

`design-viewer.html` 是纯渲染引擎（递归树状展开 + Sugiyama SVG 流程图 + 区块渲染），**自动检测 `tree.tabs`/`tree.pages`**，零项目依赖。**不要修改此文件。**

### 步骤 3：创建数据目录入口

```bash
cp templates/loader.js \
   {project}/design/{slug-of-app}/data/
```

编辑 `data/loader.js`，在 `files` 数组中列出所有数据文件（不含 `.js` 后缀）：

```javascript
var files = [
  "tree",
  "processes",
  "style",
  "i18n"
];
```

### 步骤 4：为每个产出类型创建数据文件

```bash
# 移动端：用 tabs 根示例
cp templates/example-tree-mobile.js \
   {project}/design/{slug-of-app}/data/tree.js
# 桌面端：用 pages 根示例
# cp templates/example-tree-desktop.js \
#    {project}/design/{slug-of-app}/data/tree.js

cp templates/example-processes.js \
   {project}/design/{slug-of-app}/data/processes.js
cp templates/example-style.js \
   {project}/design/{slug-of-app}/data/style.js
cp templates/example-i18n.js \
   {project}/design/{slug-of-app}/data/i18n.js
```

编辑每个文件，修改 `PS_DATA["{client-slug}"]` 下的对应属性填充实际设计内容（示例模板中的 key 为 `demo`，替换为实际 client-slug）。

## 编辑已有设计

1. 找到 `data/` 下对应模块的文件
2. 编辑对应的 PS_DATA 属性：
   - `tree.js` — 修改 `tree` 对象（移动端 `tabs` / 桌面端 `pages`，均含 `shared_pages`/`shared_components`/`flows`）
   - `processes.js` — 修改 `processes` 数组
   - `style.js` — 修改 `style` 数组
   - `i18n.js` — 修改 `i18n` 数组
3. 无需构建，浏览器打开 `design-viewer.html` 验证

## CHANGELOG 规范

每次设计变更后，必须在 `data/` 目录下创建或更新 `CHANGELOG.md` 文件，记录本次变更内容，便于审核追溯。

**CHANGELOG 格式：**

```markdown
# {端名称} 设计变更说明 v{旧版本} → v{新版本}

> {变更概要说明，如"基于 XXX 的综合同步更新"}
> 审核人：{审核人} | 日期：{YYYY-MM-DD}

---

## 变更 1：{变更标题}

**类型**：{新增功能结构|功能精简|Bug 修复|描述修正|...}
**来源**：{变更的触发原因——用户反馈、差异分析、业务逻辑变更等}

### 变更内容

| 之前 | 之后 |
|------|------|
| {修改前状态} | {修改后状态} |

### 理由
- {为什么做这个变更}

---

## 未变更部分（确认已对齐）

| 设计项 | 状态 |
|--------|------|
| {设计项名称} | ✅ 已验证无需变更 |
```

**记录要求：**

| 规则 | 说明 |
|------|------|
| **版本号** | 每次变更递增版本号（v1→v2→v3→...），与设计迭代对应 |
| **每次变更一条记录** | 同一次迭代中的多个变更点分列多个"变更 N"条目 |
| **变更类型明确** | 标注本次变更属于新增/修改/删除/Bug 修复/功能精简等 |
| **来源可追溯** | 说明变更的触发原因——用户反馈、差异分析报告、业务逻辑变更等 |
| **未变更部分确认** | 列出本次迭代中已确认无需改动的设计项，便于审核人了解全局 |
| **与差异分析对照** | 如果变更源于差异分析报告，末尾列出差异项的逐一处理情况 |

## 数据文件格式（精确 Schema）

### 文件级结构

所有数据文件共享 `PS_DATA` 命名空间。**必须使用 `window.PS_DATA` 属性访问**，而非裸变量 `PS_DATA` 查找，避免脚本加载时序导致的 ReferenceError：

```javascript
var PS_DATA = window.PS_DATA = window.PS_DATA || {};
PS_DATA["{client-slug}"] = PS_DATA["{client-slug}"] || {};
```

### loader.js 结构

```javascript
(function() {
  var files = ["tree", "processes", "style", "i18n"];
  files.forEach(function(f) {
    document.write('<script src="data/' + f + '.js"><\/script>');
  });
})();
```

### tree.js — 功能结构树（2.1~2.3）

**移动端（`client_type=mobile`）使用 `tree.tabs`** 表达 TabBar 分页结构：

```javascript
PS_DATA["{client-slug}"].tree = {
  // 2.1 业务功能结构：导航标签组 → 标签 → 页面 → 功能区 → 功能组件
  tabs: [{
    name: "标签：首页",
    desc: "内容分发首页",
    perm_ref: "public",
    children: [{
      type: "page", name: "页面：首页",
      perm_ref: "public",
      children: [
        { type: "zone", name: "功能区：推荐清单", perm_ref: "public",
          children: [
            { type: "component", name: "功能：引导到详情页", perm_ref: "public" }
          ] }
      ]
    }]
  }],
  // 2.2 公共页面（跨入口复用的独立页面）
  shared_pages: [{ ... }],
  // 2.2 公共组件
  shared_components: [],
  // 2.3 前端流程概要
  flows: [{ name: "主链路", steps: ["步骤1：描述", "步骤2：描述"] }]
};
```

**桌面端（`client_type=desktop`）使用 `tree.pages`** 表达页面集合（无固定 TabBar 层）：

```javascript
PS_DATA["{client-slug}"].tree = {
  // 2.1 业务功能结构：页面集合 → 页面 → 功能区 → 功能组件
  // ⚠️ 桌面端不使用 tabs[]，而用 pages[]；导航方式由 design-viewer.html 自动适配
  pages: [
    {
      name: "页面：仪表盘",
      desc: "数据总览与快捷操作入口",
      perm_ref: "StaffDashboardView",
      children: [
        { type: "zone", name: "功能区：数据总览", perm_ref: "StaffDashboardView",
          children: [
            { type: "component", name: "功能：显示关键指标卡片", perm_ref: "StaffDashboardView" }
          ] },
        { type: "zone", name: "功能区：快捷操作", perm_ref: "StaffDashboardView|StaffProjectCreate",
          children: [
            { type: "component", name: "功能：创建新项目", perm_ref: "StaffProjectCreate" }
          ] }
      ]
    }
  ],
  shared_pages: [{ ... }],
  shared_components: [],
  flows: [{ name: "主链路", steps: ["步骤1", "步骤2"] }]
};
```

**节点字段说明（两端一致）：**

| 字段 | 必需 | 类型 | 说明 |
|------|------|------|------|
| `type` | 是 | `"page"` / `"zone"` / `"component"` | 节点类型（Tab 层为隐式根节点，不加 type；桌面端页面集亦为隐式根）。功能组件统一为 `"component"`（早期示例中的 `"func"` 为旧写法，已废弃） |
| `name` | 是 | string | 节点名，如 `"页面：首页"`、`"进入赛事详情"` |
| `desc` | 否 | string | 功能描述标注（原则四），说明节点实际干什么。有初始输入要求的节点应描述清楚输入要求 |
| `componentType` | 否（component 节点必需） | string | 功能组件的显示样式类型，如 `"button"`、`"modal"`、`"display"`、`"input"` 等。仅 `type:"component"` 的节点设置此字段 |
| `text` | 否（`display` / `rich_text` 必需） | object | **显示文本定义**。`{key: "i18n_key", zh: "中文源文本"}`。状态相关文本使用 `variants: [{condition: "...", key: "...", zh: "..."}]` |
| `label` | 否（`button` / `link` 必需） | object | **按钮/链接标签文字**。`{key: "i18n_key", zh: "按钮文字"}` |
| `placeholder` | 否（`input` 建议设置） | object | **输入框占位提示**。`{key: "i18n_key", zh: "请输入…"}` |
| `hint` | 否（`input` 建议设置） | object | **输入框辅助说明**（显示在输入框下方）。`{key: "i18n_key", zh: "辅助说明文字"}` |
| `feedback` | 否（`button` / `link` / `input` 建议设置） | object | **操作反馈文本**。`{success: {key, zh}, error: {key, zh}}` |
| `show_when` | 否（所有 component） | string | **精确显示条件**（权限之外的业务条件）。如 `"user_status === 'pending_review'"`。不设置时默认仅受 `perm_ref` 控制 |
| `validation` | 否（`input` 建议设置） | object[] | **输入校验规则**。`[{rule: "required|maxlength|pattern|...", value: …, error: {key, zh}}]` |
| `children` | 否 | Node[] | 子节点数组，叶子节点（component）不设此字段 |
| `refs` | 否 | string[] | **引用发起方标注**：标记在触发导航的 component 上，指向目标页面路径 |
| `remark` | 否 | string | 额外标记，如 `"🆕"`、`"后置"` |
| `biz_ref` | 否 | string | 功能逻辑引用，指向 business-workflow 数据文件路径 |
| `refEntity` | 否（规则 1：新建组件必须标注） | string | 数据依赖实体引用：`"{domain-slug}:{EntityName}"`，供一致性检查做字段级语义比对 |
| `refFields` | 否（规则 1：新建组件必须标注） | string[] | 引用的实体字段列表，如 `["seat_id", "tier_id"]`，供字段一致性比对 |
| `perm_ref` | **是（所有层级必须标注）** | string | **权限点引用**：控制该节点及其整棵子树显示与操作的权限点 id（对应 business-workflow `permissions` 数组中的 `id`）。支持单个权限 id 或管道分隔的 OR 逻辑（如 `"StaffCompetitionManage\|StaffTicketManage"`）。公开节点标注 `"public"`。**Tab/页面/功能区缺少此字段时，前端无法判断该层级是否应渲染** |
| `page_input` | 否（page 节点建议设置） | object | **页面入参定义**。`{from: "page:上游页面id", params: ["param1", "param2"]}` |
| `page_output` | 否（page 节点建议设置） | object | **页面出参定义**。`{to: "page:下游页面id", params: ["param1", "param2"]}` |
| `api_ref` | 否（component 节点建议设置） | string | **API 绑定**。`"POST /orders/me"`——该组件触发时调用的 API 端点路径 |
| `sends` | 否（有 api_ref 时建议设置） | string[] | **发送数据字段**。`["seat_id", "tier_id"]`——组件向 api_ref 发送哪些字段 |

> `page_input`/`page_output`/`api_ref`/`sends` 为可选追溯字段（见 development-standard §2.6）。初始设计时可为空，复查阶段（review）必须检查：page_output.params 未出现在下游 page_input.params 中 → 🔴 data_flow_broken；api_ref 端点不存在 → 🔴 api_mismatch。**进入代码生成（§8.7）前应补齐；未补齐时 code-gen 以 ⚠️ 警告输出并标注 TODO，不阻塞生成**（见 client-code-gen）。

**层级规则：**
- **移动端：** Tab组（根）→ Tab(1) → 页面(2~5) → 功能区(任意) → 功能组件(叶子)
- **桌面端：** 页面集合（根）→ 页面(1~5) → 功能区(任意) → 功能组件(叶子)\
  （无 TabBar 层，页面可直接为第 1 层；侧边栏多级页面深度仍从最外层页面算起，上限 5 级不变）

### processes.js / style.js / i18n.js

格式与 `client-ui-design` 的其他模板文件一致，详见 `example-*.js`。Block 类型体系：`p` / `h2`/`h3`/`h4` / `ul` / `ol` / `note` / `table` / `hr`。Flowchart 节点类型：`start`(绿) / `end`(绿) / `action`(蓝) / `decision`(琥珀) / `subprocess`(紫)。

### design-viewer.html 渲染器加载机制

1. HTML 中引用 `<script src="data/loader.js">`
2. `loader.js` 使用 `document.write` 同步加载 `files` 中列出的所有子文件
3. 数据加载完毕后，底部 IIFE 从 `PS_DATA["{client-slug}"]` 读取并渲染
4. 功能结构树标签页自适应：检测到 `tree.tabs` 时以 TabBar 模式渲染，检测到 `tree.pages` 时以页面集模式渲染

## 设计方法论

本技能遵循 `design/01-raw-input/page-design-methodology.md` v2 的完整方法论。以下摘录核心概念，设计时需逐条遵守。移动端与桌面端共享同一方法论体系；提及"TabBar""Tab组""标签"处，桌面端替换为"导航""导航组"或直接以页面为根。

### 节点体系与层级规则

所有功能树节点使用统一的递归 `children[]` + `type` 格式：

| 节点类型 | 层级角色（移动端） | 层级角色（桌面端） | 子节点类型 | 说明 |
|---------|---------|---------|-----------|------|
| 导航标签组 | 根容器 | — | 标签 / 页面 | 移动端 TabBar 的整体容器 |
| 页面集合 | — | 根 | 页面 | 桌面端无固定 TabBar，页面集合构成根 |
| 标签 | 第1层 | — | 页面 | 移动端 TabBar 的每一项 |
| 页面 | 第2~5层 | 第1~5层 | 功能区、功能组件 | 独立页面，任意层级 |
| 功能区 | 任意层 | 任意层 | **功能组件（或下级功能区）** | 页面内的功能区块，**列表属于功能区**。功能区可以嵌套 |
| 功能组件 | 叶子节点 | 叶子节点 | 无（不可再分） | 功能树的最小不可分单元，**列表项才是功能组件**。需设置 `componentType` |

> **功能区嵌套规则：** 功能区可以包含下级功能区，用于对强相关的功能做进一步分组。这种嵌套不改变层级深度计算——深度按"用户最少切换次数"算，嵌套功能区不增加切换次数。

**层级深度上限（五级）：**

| 层级 | 定义（移动端） | 定义（桌面端） |
|------|---------------|---------------|
| 第1层 | TabBar 标签 | 页面直接可见（如侧边栏菜单项）、或顶级页面本身 |
| 第2层 | 切换标签后的内容 | 页面内无需导航就能看到的功能区 |
| 第3层 | 一次操作后进入的子页面/浮窗 | 点击后进入的子页面或弹窗 |
| 第4层 | 再次操作后进入的下一级 | 子页面中的下一级页面 |
| 第5层 | 最深级页面（上限） | 最深级页面（上限） |

**路径优化：** 尽可能让深度不超过5级。如果某条路径超限，考虑把深层操作提前到浅层页面中。

**节点命名规范：**

命名前缀表明节点类型，设计时必须使用统一前缀：
- 移动端：`标签：首页`、`页面：赛事详情`、`功能区：推荐清单`
- 桌面端：`页面：仪表盘`、`功能区：数据表格`
- 功能组件按 `[componentType]` 标记：`[button]：进入审核中心`、`[display]：显示状态信息`、`[modal]：验票结果`

### 功能组件详述

功能组件（component）是功能树的叶子节点，通过 `componentType` 属性指示其显示样式类型。

#### 两大基本能力

1. **信息展示能力** — 显示文本、图片、视频、富文本等内容
2. **操作能力** — 可被用户操作。两个方向：**直接操作**（即时生效）和 **功能入口**（导航到其他功能）

#### componentType 取值

| componentType | 说明 | 功能描述示例 |
|-------------|------|-------------|
| `button` | 按钮，接受点击操作 | "点击后打开赛事详情页并传递 competition_id" |
| `modal` | 浮窗/弹出框 | "验票结果显示票状态/座位信息/异常原因" |
| `link` | 超链接/导航入口 | "引导到个人资料编辑页" |
| `display` | 普通信息展示 | "显示头像/昵称/会员标识" |
| `rich_text` | 富文本展示 | "展示入场须知与禁带物品说明" |
| `image` | 图片展示 | "显示赛事主视觉海报" |
| `video` | 视频展示 | "播放赛事精彩集锦" |
| `input` | 输入框/表单输入 | "输入搜索关键词" |

> **设计规范：** 每个功能组件只对应**一个操作目标**。如果需要对同一数据做多个不同操作，使用多个独立的功能组件分别承载。

#### componentType 与文本字段映射

| componentType | `text` | `label` | `placeholder` | `hint` | `feedback` | `validation` |
|-------------|--------|---------|-------------|-------|----------|------------|
| `button` | | ✓ | | | ○ | |
| `modal` | ✓ | | | | | |
| `link` | | ✓ | | | | |
| `display` | ✓ | | | | | |
| `rich_text` | ✓ | | | | | |
| `image` | | | | | | |
| `video` | | | | | | |
| `input` | | | ○ | ○ | ○ | ○ |

> **原则：** 每个可读文本必须在设计阶段定义 i18n key 和中文源文本。`image` / `video` 无文本需求，但如有说明文字（alt/desc）仍需标注。

#### 引用规则 (refs)

- refs 标注在**引用的发起方**（触发导航的 component 上），指向目标页面路径
- 被引用的页面不需要知道自己被谁引用
- 只有**页面**和**功能区**可以作为公共节点出现

### 公共页面与公共组件

**公共页面**是可被多个入口或其他页面复用的独立页面。**公共组件**是可被多个页面复用的 UI 组件。

**处理规则：**

| 场景 | 处理方式 |
|------|---------|
| 公共页面A，内部功能区A1/A2/A3只服务于A | A1/A2/A3唯一属于A，不单独拆出 |
| 公共页面A，内部组件Alpha只在A内部使用 | Alpha属于A，不单独列出 |
| 公共组件Alpha被页面A、B、C同时引用 | Alpha**必须单独列出**，并标明被A/B/C引用 |
| 公共组件Beta被页面D引用但被页面E嵌套引用 | Beta单独列出，标明引用关系 |

**与功能树（2.1）的关系：** `tree.tabs`（移动端）/`tree.pages`（桌面端）描述导航结构，`tree.shared_pages` 描述被多个入口复用的独立页面——它们的内部结构在 shared_pages 中展开，但通过 `refs` 字段标注哪些入口引用了它们。

> 实际设计流程：先定义完整导航结构，当发现某个页面被多个入口同时指向时，将其提取到 `shared_pages` 中，并在原入口处标注引用关系。

### 七项核心设计原则

**原则一：输入完整 + 结论完整**
1. **输入完整**：设计开始前确保所有输入来源（讨论记录、business workflow、API 设计、ER 设计、交互文档、样式要求、多语言需求）已收集到位
2. **结论完整**：设计方案必须产出全部六种产出物类型（2.1~2.6），不可缺失

**原则二：层级深度上限（五级）**
按"用户最少切换次数"计算层级深度，不超过5级。详见上方层级深度表。

**原则三：节点类型归一**
所有设计节点使用统一类型体系。功能区是功能树的组织单位，功能组件是叶子节点。从页面开始逐层展开，每一层节点类型明确，不混用。

**原则四：功能描述属性（标注）**
除结构位置外，每个功能区和功能组件必须有一个**功能描述**——描述它**实际干什么**，而不是描述它在结构上是什么位置。
- 功能区标注示例：`"由推荐配置中心驱动的流式推荐内容列表，6 种内容类型各自渲染不同卡片样式"`
- 功能组件标注示例：`"按状态筛选（全部/待支付/已支付/已退款），切换时刷新列表"`

> 功能描述是对节点**行为**的描述（干什么、怎么处置自身功能），不是对节点**结构位置**的描述。

**原则五：状态作为基础属性**
每个功能区和功能组件都具有**状态**属性。内容展现方式、可操作性、被操作后的业务逻辑，均基于当前状态而不同。设计时需针对每一种可能状态，定义：该状态下的展现形态、该状态下可执行的操作、操作后向什么状态转换。

**原则六：权限控制（全层级可见性）**
所有层级节点（Tab标签/页面/功能区/功能组件）都受权限控制，简化为两个维度：
1. **显示权限** — 当前用户是否有权看到这个节点及其整棵子树
2. **操作权限** — 当前用户是否有权操作这个功能组件

**全层级标注规则：**
- **Tab 标签层（移动端）**：标注该 Tab 所需的权限集合（OR 逻辑）。若用户缺少所有相关权限，整个 Tab 隐藏
- **页面层**：标注进入该页面所需的最小权限。若用户无此权限，页面不可访问（路由守卫拦截，或菜单/Tab 中不显示入口）。公开页面标注 `"public"`
- **功能区层**：标注该功能区可见所需的权限。若用户无此权限，整个功能区不渲染。功能区权限为其子组件权限的 OR 聚合
- **功能组件层**：标注组件可见/可操作的权限。每个功能组件只对应一个操作目标，权限直接管到单个组件能否显示、能否操作

> **设计意图：** 避免出现"空页面"或"灰页面"——如果用户对某个页面的所有内容都没有权限，则页面本身应被隐藏。这要求每一级父节点都标注权限标签，前端从根到叶逐级判断：当前节点权限不足 → 整棵子树不渲染。

**权限点聚合规则（OR 逻辑）：**
- 父节点的 `perm_ref` 是其所有直接子节点权限的 OR 聚合（管道分隔）
- 如果某父节点下所有子节点共享同一权限，父节点可直接使用该权限
- 如果子节点权限各不相同，父节点使用管道列出所有权限：`"PermA|PermB|PermC"`
- 父节点中存在 `"public"` 子节点时，父节点仍可用管道列出非 public 权限（`"public"` 子节点不参与父节点的权限判断）

> **⚠️ 页面设计不定义新权限点。** 权限点的唯一定义源是 business-workflow。设计时自顶向下逐级标注（Tab/页面→功能区→功能组件），从 `permissions` 数组匹配权限点 id，逐层向上做 OR 聚合。缺失时反推 business-workflow 补充，歧义时提示用户仲裁。

**原则七：文本精确化（Text Precision）**
设计阶段的产出物必须包含每个可见文本元素的精确内容——不可将文本措辞留给实现阶段随意决定。这是设计文档从「功能地图」升级为「UI 规格说明书」的关键步骤。

**必须定义的内容：**
1. **显示文本** — 每个 `display` / `rich_text` 组件的精确文字（含 i18n key + 中文源文本）
2. **按钮/链接标签** — 每个 `button` / `link` 组件上的精确文字
3. **输入框提示** — 每个 `input` 组件的 `placeholder`（占位提示）和 `hint`（辅助说明）
4. **操作反馈** — 每个可操作组件成功/失败时用户看到的提示文字
5. **校验错误** — 每个输入校验规则对应的错误提示文字
6. **条件文本** — 若文本随状态变化，须枚举每个状态对应的文本变体

**为什么必须在设计阶段完成：**
- **i18n 依赖**：文本的 i18n key 必须在设计阶段定义，翻译表本身是设计交付物。实现阶段只做引用，不做 key 命名
- **设计审核依赖**：审核人无法从「功能描述」推断实际 UI 文案。设计不定义文本 = 审核无法进行
- **权限绑定依赖**：每个可见元素的权限控制精确到叶子。文本未定义 → 组件粒度不够 → 权限绑定随机化

**文本定义格式：**
```javascript
// display / rich_text 组件
{ type: "component", componentType: "display",
  text: { key: "login.logo_title", zh: "全赛通运营——专业拳击赛事运营管理平台" } }

// 状态相关文本
{ type: "component", componentType: "display",
  text: { key: "review.status_label",
    variants: [
      { condition: "status === 'pending_review'", zh: "⏳ 等待审核" },
      { condition: "status === 'approved'", zh: "✅ 已通过" },
      { condition: "status === 'rejected'", zh: "❌ 已驳回" }
    ] } }

// button 组件
{ type: "component", componentType: "button",
  label: { key: "login.external_login_btn", zh: "第三方登录" },
  feedback: { success: { key: "login.success", zh: "登录成功" },
              error: { key: "login.fail", zh: "登录失败，请重试" } } }

// input 组件
{ type: "component", componentType: "input",
  placeholder: { key: "auth.name_placeholder", zh: "请输入真实姓名" },
  validation: [
    { rule: "required", error: { key: "auth.name_required", zh: "姓名不能为空" } }
  ] }
```

> **边界说明：** 文本精确化要求定义「显示什么文字」，不要求定义「文字用什么颜色/字号/字体」——后者属于样式层，在实现阶段控制。

### 典型反模式（设计时避免）

| 反模式 | 问题 | 正确做法 |
|-------|------|---------|
| 层级超过5级 | 用户操作路径太长，容易迷失 | 把深层操作提前到浅层页面 |
| 一个功能组件绑多个操作 | 权限模型复杂化 | 拆成多个独立功能组件，各绑一个操作 |
| 功能描述缺失 | 其他人看不懂这个节点实际干什么 | 每个功能区和功能组件写清楚功能标注 |
| 公共组件不标注引用关系 | 改了一个公共组件，影响范围不清 | 公共组件必须列出引用它的所有页面 |
| 把列表当作功能组件 | 粒度错乱 | 列表是功能区，列表项才是功能组件 |
| 业务功能结构和前端业务流程混在一起表达 | 既看不清功能树也看不清操作序列 | 2.1和2.3分开产出，各自独立完整 |
| 功能逻辑设计在页面结构文档里写了一大堆 | 页面设计文档臃肿，同步困难 | 功能逻辑交由 business-workflow skill 管理，页面设计只做引用标注 |
| 设计风格只有要求没有结论 | 输入了"要什么风格"但没有落地的具体方案 | 基于输入要求产出配色、字体、间距等具体决策 |
| 多语言只有需求没有实现方案 | 开发不知道多语言功能在前端怎么落地 | 基于输入需求产出翻译文件结构、UI自适应、切换交互等具体方案 |
| 父节点缺少 `perm_ref` | Tile/页面/功能区未标注权限，前端无法判断是否应隐藏整棵子树 | 从 Tab/页面到组件逐级标注 `perm_ref`，父节点权限为其子节点权限的 OR 聚合 |
| `display`/`rich_text` 组件缺 `text` 字段 | 显示文本未在设计阶段定义，i18n key 缺失 | 所有 `display`/`rich_text` 组件必须设置 `text: {key, zh}` |
| `button`/`link` 组件缺 `label` 字段 | 按钮文字由开发者随机决定 | 所有 `button`/`link` 组件必须设置 `label: {key, zh}` |
| `input` 组件缺 `placeholder`/`validation` | 用户不知道输入格式要求 | 设置 `placeholder`、`hint` 和 `validation` 数组 |
| 文本在 `desc` 里混着写 | `desc` 是功能描述，不能代替 `text`/`label` | `desc` 描述行为，`text`/`label` 定义精确文本，两者分开 |

### 功能逻辑设计的引用方式

当功能树中的节点涉及业务规则、状态机、流程条件时，应在节点上标注对应的 business-workflow 数据文件引用：

```
功能区：审核详情 → 功能：审核动作（通过/打回/补正/转交）
  | biz_ref: business-workflow/data/01-user-identity.js
  |     → section "用户注册审核状态链路"
  |     → 状态：待审核 → 补正中 → 待复审 → 已通过/已驳回
```

在 `tree.js` 数据中通过 `biz_ref` 字段标注（见节点字段说明表）。

## 六种渲染视图

| 标签页 | 渲染内容 | 数据来源 |
|--------|---------|---------|
| 📁 功能结构树 | 递归树状展开，可交互折叠 | `tree.tabs`（移动端）/ `tree.pages`（桌面端） |
| 🔁 公共页面与组件 | 公共页面树 + 组件卡片 + 前端流程步骤 | `tree.shared_pages` + `shared_components` + `tree.flows` |
| 🔀 业务流程 | 区块渲染 + SVG 流程图（Sugiyama 布局） | `processes[]` |
| 🎨 设计风格 | 区块渲染（配色表、字体层级、间距规则等） | `style[]` |
| 🌐 多语言方案 | 区块渲染（语言列表、翻译结构、自适应策略） | `i18n[]` |

## 设计原则

- **JS 数据文件为唯一权威源** — 数据与渲染分离
- **模块化拆分** — tree / processes / style / i18n 各自独立
- **单一渲染器** — 所有内容由 `design-viewer.html` 统一渲染（自动检测 tabs/pages）
- **统一递归结构** — 功能树节点使用 `children[]` + `type` 格式
- **零外部依赖 + 零构建步骤**
- **功能描述（标注）必须完整**
- **层级深度不超过 5 级**

## 与相关技能的关系

| 技能/文件 | 管理内容 |
|-----------|---------|
| `domain-registry.js` | **域注册表**——所有领域定义的中心注册表。设计前先读取获取 `{domain-slug}`，`biz_ref` 中的路径以此为准 |
| `business-workflow` | 功能逻辑设计（2.4） |
| `entity-relationship` | 数据模型、实体关系 |
| `api-design` | API 端点、请求响应 |
| `client-code-gen` | 客户端代码生成（A2 合并产物：由本技能设计的 tree 生码） |

---

## 一致性检查模式

本技能提供一种特殊的执行模式——**一致性检查**，用于在上游设计（ER、工作流、API）变更后，
自动检测当前客户端页面设计是否仍与上游保持一致。

### 触发场景

| 场景 | 说明 |
|------|------|
| **ER 变更后** | 实体字段增删改、实体关系变化、枚举值变化 |
| **工作流变更后** | 新增/删除业务步骤、状态机变化、角色变化 |
| **API 变更后** | 端点增删、请求/响应字段变化 |
| **常规复查** | review skill 在执行前端一致性维度时委托调用 |

### 输入规格

| 输入 | 来源 | 说明 |
|------|------|------|
| 当前设计文件 | `design/06-{client-slug}/data/tree.js` | 待检查的页面功能结构（移动端 `tree.tabs` / 桌面端 `tree.pages`） |
| ER 数据文件 | `design/03-entity-relationship/data/*.js` | 最新实体定义，作为字段级参照 |
| 工作流数据文件 | `design/02-business-workflow/data/*.js` | 最新业务规则和流程，作为操作级参照 |
| 域注册表 | `design/domain-registry.js` | 领域定义 |

### 检查步骤

1. **实体覆盖检查**：逐领域读取 ER 数据中的核心实体，与 tree.js 中所有节点的 `refEntity` 对照，找出在 ER 中有定义但前端没有任何页面/组件引用的实体
2. **字段一致性检查**：逐节点读取 `refFields`，与对应 ER 实体的字段定义做差异对比：
   - 标记 `refFields` 中引用了已不存在的字段
   - 标记 ER 实体新增了字段但前端没有对应展示
   - 标记字段类型/枚举值不匹配
3. **工作流覆盖检查**：逐读取工作流数据中的 action 和 decision 节点，与 tree.js 中的交互组件（componentType 为 button/link 等）对照，找出工作流有定义但前端没有对应交互入口的操作
4. **描述陈旧性检查**：对于有 `refEntity` 但尚未标注 `refFields` 的组件，检查其 `desc` 中提到的字段名是否与 ER 实体的当前字段定义一致
5. **权限点覆盖检查（全层级）：** 逐节点（Tab/页面/功能区/功能组件）读取 `perm_ref`，对照 business-workflow 的 `permissions` 数组：
   - 标记任何层级缺少 `perm_ref` 标注的节点
   - 标记 `perm_ref` 中引用了不存在的权限点 id
   - 标记 business-workflow 有定义但前端无任何组件引用的权限点
   - 标记父节点 `perm_ref` 与其子节点权限聚合不一致的情况
6. **文本与 i18n 完整性检查：** 逐功能组件（`type:"component"`）检查文本字段是否满足要求：
   - 标记 `componentType:"display"|"rich_text"` 缺少 `text` 字段的组件
   - 标记 `componentType:"button"|"link"` 缺少 `label` 字段的组件
   - 标记 `componentType:"input"` 缺少 `placeholder` / `validation` 的组件
   - 标记所有 `text`/`label`/`placeholder`/`hint`/`feedback` 中缺少 `key` 或 `zh` 的组件
   - 标记 `text.variants` 中 `condition` 与工作流状态机定义不一致的文本变体
   - 标记 `validation[].error` 中缺少 `key` 或 `zh` 的校验规则
   - 标记 `show_when` 条件表达式中引用了不存在的工作流状态值

### 输出格式

> 输出格式遵循共享规范：`_shared/consistency-check-format.md`。
> 本 skill 的 `type` 枚举见共享规范注册表（`client-ui-design` 行）。
> 本 skill 的 `source` 枚举：`er-to-frontend`, `workflow-to-frontend`。

输出一份结构化的一致性检查报告：

```json
{
  "summary": {
    "end_slug": "{client-slug}",
    "total_scanned": 0,
    "total_issues": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "issues": [
    {
      "severity": "high",
      "type": "field_mismatch",
      "source": "er-to-frontend",
      "ref_path": "页面：XX / 功能区：YY / 组件：ZZ",
      "ref_entity": "domain-slug:EntityName",
      "ref_field": "EntityName.fieldName",
      "detail": "字段 Competition.old_status 在 ER 中已不存在",
      "suggestion": "更新 refFields 并同步检查 desc"
    }
  ],
  "uncovered_entities": [
    { "entity": "EntityName", "domain": "domain-slug", "suggested_page_type": "list|detail|management" }
  ],
  "uncovered_workflow_actions": [
    { "action": "节点名称", "workflow_file": "XX-workflow.js", "suggested_component_type": "button" }
  ]
}
```

### 使用方式

1. **作为独立检查**：对 Claude 说"使用 client-ui-design 检查 {端-slug} 与 ER/工作流的一致性"
2. **被 review skill 调用**：review skill 在前端一致性维度中自动委托本技能执行（详见 review skill §2）
3. **变更后快速检查**：对上游文件做局部修改后，对本端设计执行针对性检查

### 数据流完整性检查（追加步骤）

> 在标准 6 步检查之后追加，检查页面间数据传递是否完整。

7. **页面间数据流检查**：遍历所有 page 节点，对每个 page：
   - 标记缺少 `page_input` 和 `page_output` 的页面 → ⚠️ untraced_page
   - 标记 `page_output.params` 中字段未全部出现在下游 `page_input.params` 中的 → 🔴 data_flow_broken
   - 标记 `page_input.params` 中字段无法追溯到上游 `page_output.params` 或外部源的 → 🔴 missing_source
8. **组件-API 绑定检查**：遍历所有有 `api_ref` 的 component 节点：
   - 标记 `api_ref` 指向的端点不在 API 设计中的 → 🔴 api_mismatch
   - 标记 `sends` 中字段不在 API `consumes` 参数中的 → 🔴 field_mismatch
9. **全链追溯验证**：选一条核心用户旅程，从起点页面走到终点页面：
   - 检查 page_input → api_ref.sends → API consumes → API produces → page_output → 下游 page_input 全链通畅
   - 任一环节断 → 报告具体断点
