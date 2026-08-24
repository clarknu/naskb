---
name: entity-relationship
version: 3.0.0
description: |
  实体关系图（ER 图）设计技能——使用 er-viewer.html + data/*.js 模式
  进行实体定义、关系设计、字段约束设定，通过 D3 力导向布局自动生成交互式 SVG。
  采用 entities/value_objects/services/enums 四数组结构、事件层级模板、跨域 ghost 实体、
  枚举限高、字段类型彩色渲染、hash 路由。
triggers:
  - ER 图
  - 实体关系
  - 实体设计
  - 关系设计
  - 数据建模
  - 领域建模
  - entity relationship
lineage:
  origin: arb-hub
  sources:
    boxing:        {sha256: 853c2e828381}
    zy-iot-ai:     {sha256: 284168bb484a}
    zy-ai-consult: {sha256: 284168bb484a}
---

# Entity Relationship (ER) Design

本技能封装了 `er-viewer.html` + `data/*.js` 的完整工具链。
**当前渲染器为 D3.js v7 力导向布局版本。**

## 本技能规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | **不重复定义** | 每个实体只在归属域定义一次，其他域通过 `cross_domain` 引用。`core-er.js` 汇总所有跨域关系 |
| 2 | **结构化数据优先** | ER 数据以 JS 文件为唯一权威源，`er-viewer.html` 只是渲染层 |
| 3 | **单一渲染器** | 所有领域共用 `er-viewer.html`（hash `#XX` 单域 / `#all` 全景），零外部依赖（D3 本地化） |
| 4 | **域注册表同步** | 开工前先读取 `design/domain-registry.js`，改领域边界时必须先写注册表 |
| 5 | **决策可追溯** | 每次设计操作前，将原始输入原文追加到 `design/01-raw-input/{domain-slug}.md` |
| 6 | **四数组结构** | 每个域数据文件包含 `entities[]`、`value_objects[]`、`services[]`、`enums[]` 四个独立数组 |
| 7 | **CHANGELOG 必写** | 每次变更后在 `design/03-entity-relationship/data/CHANGELOG.md` 记录 |

> （R-007 定案：一致性检查上收 review 成立——工作流→ER 等跨资产校验由 review 统一调度，本技能不设独立一致性检查模式，2026-08-23）

---

## 1. 设计流程

```
输入源 → 实体提取 → 关系识别 → 输出生成 → 迭代验证
```

**每次被调用时，skill 必须先输出执行计划与用户确认，然后再开始执行。**

---

## 2. 数据文件结构

### 2.1 顶层结构

```javascript
window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["XX-domain-slug"] = {
  "domain":      "XX",         // 领域编号
  "title":       "领域中文名",
  "slug":        "domain-slug",
  "description": "...",
  "enums":           Enum[],       // 枚举定义（含 EventType 等共享枚举）
  "entities":        Entity[],     // 实体列表（含 abstract: true 基类）
  "value_objects":   ValueObject[],// 值对象列表（不可变消息/事件子类）
  "services":        Service[],    // 服务列表（含 methods[]）
  "relations":       Relation[]    // 关系列表
};
```

### 2.2 Entity 结构

```jsonc
{
  "id":          "snake_case_id",    // 实体唯一标识
  "name":        "中文名",           // 如需标注抽象："中文名（抽象）" 或 "中文名（抽象基类）"
  "table":       "table_name"|null,  // 表名，抽象类可为 null
  "abstract":    true|false,         // 是否抽象基类（渲染为灰色虚线卡片）
  "extends":     "parent_id",        // 继承链（可选）
  "description": "...",
  "fields":       Field[]             // 字段列表
}
```

### 2.3 ValueObject 结构

与 Entity 相同，但有 `"type": "vo"` 标记。抽象 VO 可设 `abstract: true`。

### 2.4 Service 结构

```jsonc
{
  "id":          "service_id",
  "name":        "中文名",
  "description": "...",
  "methods":     [ {"name":"methodName", "sig":"(params) → return", "desc":"..."} ]
}
```

### 2.5 Enum 结构

```jsonc
{
  "id":          "EnumName",
  "name":        "枚举中文名",
  "description": "...",
  "values":      [ {"code":"CODE", "zh":"中文值", "desc":"..."} ]
}
```

### 2.6 Field 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 字段名（snake_case） |
| `type` | string | 是 | 数据类型（`UUID`, `varchar(64)`, `integer`, `datetime`, `text`, `boolean`, `json`, `decimal(5,2)`, `EnumName`） |
| `pk` | bool | 否 | 是否主键 |
| `nn` | bool | 否 | 是否 NOT NULL |
| `uq` | bool | 否 | 是否 UNIQUE |
| `fk` | string | 否 | 外键引用 `"实体.字段"` |
| `desc` | string | 是 | 字段说明 |
| `comment` | string | 否 | 详细注释 |
| `default` | string | 否 | 默认值 |

### 2.7 Relation 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `from` | string | 是 | 源端 `"实体.字段"` |
| `to` | string | 是 | 目标端 `"实体.字段"` |
| `type` | string | 是 | 基数：`"1:1"`, `"1:N"`, `"N:1"`, `"1:0..1"` |
| `desc` | string | 是 | 关系描述 |
| `cross_domain` | string | 否 | 跨域时指定目标域编号 |

### 2.8 跨域引用

- 每个实体只在归属域定义，其他域通过 `cross_domain` 引用
- 跨域实体会自动在目标域渲染为 **外部引用 (ghost)** 卡片：
  - 第 1 行：中文名（从源域 data 查找）
  - 第 2 行：英文表名
  - 第 3 行：`← 域 XX`（橙色斜体标签）
  - 样式：浅蓝底 `#eff6ff` + 深橙虚线 `#ea580c` + 粗线 2.5px
- `core-er.js` 汇总全部跨域关系供全景图渲染

---

## 3. 事件层级模板

域 07 事件基础设施使用以下继承结构：

```
event（抽象基类）
├── platform_event（抽象）── platform_command（抽象）+ platform_message（抽象）
├── device_event（抽象）── device_command（抽象）+ device_message（抽象 VO 基类）
└── domain_event（抽象）── domain_command（占位）+ domain_message（占位）
```

- 抽象基类：`entities[]`, `abstract: true`, `extends` 指向父类
- 设备消息子类：`value_objects[]`, `extends` 指向 `device_message`
- 具体指令子类：`entities[]`, `extends` 指向 `platform_command` 或 `device_command`

---

## 4. 渲染器特性（D3 v7）

| 特性 | 说明 |
|------|------|
| **D3-force 布局** | d3.forceSimulation 自动排布节点，碰撞检测避免重叠 |
| **四类型卡片** | 实体（蓝）、值对象（紫虚线）、服务（黄虚线）、枚举（琥珀） |
| **抽象实体** | 灰色虚线卡片 + 小标签 "Abstract"，字段区独立 |
| **外部引用 (ghost)** | 浅蓝底 + 深橙虚线 + 三行信息（中文/英文/域标签） |
| **枚举限高** | 超过 9 项的枚举卡片只显示前 9 项 + "+N more" 标记 |
| **字段类型显示** | 字段行用彩色 tspan：字段名黑粗、类型灰色、PK 蓝、FK 紫、NN 红 |
| **数量标记** | 连线两端标记基数（1 / 0..N 等），沿连线方向外推 20px |
| **连线类型区分** | 实体↔实体蓝实线、↔VO 紫虚线、↔枚举琥珀、↔抽象灰虚线、跨域橙 |
| **hash 路由** | `#03` → 域 03，`#07` → 域 07，默认 `#all` 全景 |
| **wheel zoom** | viewBox 缩放（滚轮），无动画 |
| **click detail** | 点击卡片弹出右侧详情面板，点击空白关闭 |
| **图例** | 固定在左下角，包含实体/VO/服务/枚举/抽象/外部引用六种 |

---

## 5. 编辑约束（铁律）

| # | 约束 | 说明 |
|---|------|------|
| 1 | **read→edit 循环** | 每次 `edit_file` 前必须用 `read_file(path)`（无 offset/limit）完整读取 |
| 2 | **禁止批处理脚本** | 禁止用 Python/PowerShell/JS 脚本批量替换代码或文档——它们会因 CRLF 换行符失败 |
| 3 | **write_file 整写** | 大文件重构（如新增 6+ 实体）直接用 `write_file` 写入完整文件 |
| 4 | **浏览器验证** | Viewer 改动后必须用 Playwright `browser_run_code_unsafe`（或等价浏览器工具）file:// 逐域验证 0 errors |
| 5 | **浏览器生命周期** | 验证完成后必须 `browser_close` |

---

## 6. 设计原则

- **四数组结构**：entities / value_objects / services / enums 独立维护
- **中文优先**：卡片标题纯中文，副标题英文/表名
- **抽象类标注**：名称含 `（抽象）` 或 `（抽象基类）`，由 viewer 自动 strip
- **枚举用原名**：不要加 `enum:` 前缀，直接写枚举 ID
- **零外部依赖**：HTML + D3 本地化 + CSS，无 CDN
- **文件命名**：`{domain-slug}.js`，如 `07-event-infrastructure.js`
- **entity ID**：snake_case，如 `device_command`、`sleep_score`

---

## 7. CHANGELOG 规范

存放位置：`design/03-entity-relationship/data/CHANGELOG.md`

每次设计变更后记录版本号、变更类型、来源、涉及实体。
