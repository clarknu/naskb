---
name: api-code-gen
version: 3.0.0
description: |
  服务端代码生成与一致性检查——覆盖 development-standard §8.6「API 代码实现」全部子步骤。
  架构驱动：读取 backend-architecture 设计资产，动态决定生成模式（模块单体 / 事件驱动 / CQRS 等）。
  技术栈无关：从项目 AGENTS.md 读取目标框架，不内置任何框架特定代码。
triggers:
  - API 代码生成
  - API 实现
  - 服务端代码
  - 后端代码生成
  - API code generation
  - API 一致性检查
  - API 实现检查
  - ORM 代码生成
  - 实体类生成
  - 后端实现
  - 服务端实现

lineage:
  origin: arb-hub
  sources:
    boxing:        {sha256: 1664e1888d44}
    zy-iot-ai:     {sha256: 0c38958c7b5e}
    zy-ai-consult: {sha256: 0c38958c7b5e}
---

# api-code-gen — 架构驱动的服务端代码生成

## 技能说明

- **所属流水线：** `development-standard` §8.6「API 代码实现」
- **输入源：**
  - `design/05-backend-architecture/data/*.js`（**架构设计—首要输入**，决定代码生成模式）
  - `design/04-platform-api/data/rest/{slug}.js`（API 设计数据文件，协议定义见 `data/{rest,iot,internal,ai-tools}/protocol.js`）
  - `design/03-entity-relationship/data/{slug}.js`（ER 数据）
  - 项目 `AGENTS.md`（目标技术栈：框架、ORM、语言、测试命令）

> **输入规格契约：** 上游设计产物字段以对应技能为准——API 数据文件结构见 api-design §4、ER 四数组见 entity-relationship §2、页面功能树见 mobile/desktop-app-design「节点字段说明」。上游字段改名必须先同步本技能检查逻辑，禁止静默假设字段存在。

- **输出目录：** `src/server/`

> **核心理念：本 skill 不内置任何架构模式。** 它是一个纯引擎——读取架构设计资产，
> 按资产定义的规则翻译成代码。架构换了你只改架构设计，不用改本 skill。

---

## 0. 核心原则

### 0.1 架构驱动，不硬编码模式

**本 skill 的唯一职责：读取设计资产 → 翻译成代码骨架。**

| 架构设计资产 | 控制什么 |
|-------------|---------|
| `system-topology.js` | 确定架构风格（`architectureStyle.primary`），发配到对应生成器 |
| `module-boundaries.js` | 生成模块目录、Application Service 接口、事件订阅/发布注册 |
| `event-contracts.js` | 生成事件 dataclass、Command dataclass、EventStore 模型 |
| `layering-strategy.js` | 生成目录结构、`__init__.py` 依赖导入、分层约束校验 |
| `caching-strategy.js` | 生成缓存装饰器、缓存配置 |
| `resilience-policy.js` | 生成幂等中间件、重试/熔断/频控代码 |
| `data-consistency.js` | 生成 Outbox 模型 + Background Publisher |
| `observability-policy.js` | 生成健康检查端点、指标注册、审计日志 |
| `security-policy.js` | 生成 JWT 鉴权、敏感字段加密/脱敏 |

**架构风格路由：** 读取 `system-topology.js` → `architectureStyle.primary`：
- `"event-driven-modular-monolith"` → 生成 EventBus + EventStore + Outbox + IoT Gateway
- `"modular-monolith"` → 生成模块边界 + 分层，无事件层
- `"microservices"` → 生成独立服务 + API Client（将来支持）
- `"monolithic"` → 经典三层（Controller + Service + Repository），无模块目录
- 旧值映射：`"event-driven"` / `"cqrs"` 为旧词汇（组合式风格出现前的写法）→ 提示架构侧把 `architectureStyle.primary` 补齐为复合风格（如 `event-driven-modular-monolith`、`modular-monolith + cqrs` 语义需在 system-topology.js 中显式声明）后再生成
- 未匹配到已知风格 → 输出警告，回退到最小骨架生成

### 0.2 技术栈从 AGENTS.md 读取，不内置

| 需要的信息 | AGENTS.md 字段 | 用途 |
|-----------|---------------|------|
| 编程语言 | `runtime`（如 `Python 3.12+`） | 文件扩展名、语法 |
| Web 框架 | `framework`（如 `FastAPI`） | 路由装饰器、依赖注入 |
| ORM | `orm`（如 `SQLAlchemy 2.0 async`） | 实体基类、查询语法 |
| 测试命令 | 测试命令（如 `python -m pytest`） | 测试验证 |
| 迁移命令 | 从 ORM 推导（如 `alembic`） | 数据库迁移 |

**类型映射：** 从 `AGENTS.md` 的 techStack 动态构建，不内置任何框架的类型表。

### 0.3 设计即代码，零兼容冗余

| 场景 | 做法 |
|------|------|
| 设计有变更 | 旧字段/表/路由直接删除替换，不保留过时代码 |
| 设计删除实体/字段/端点 | 代码中对应删除，不保留死代码 |
| 数据迁移 | 通过框架迁移工具解决，不在代码层做兼容 |

### 0.4 枚举强制

所有离散值域的业务概念必须定义为语言级枚举（Python `Enum`、TypeScript `enum` 等），严禁 `string` 替代。具体语法遵循 `AGENTS.md` 中的框架惯例。

---

## 1. 执行流程

### 步骤 0：读取架构设计（所有步骤的前置条件）

**在生成任何代码之前，必须完整读取以下文件：**

1. `design/05-backend-architecture/data/system-topology.js` → 提取 `architectureStyle.primary`、`complexityLevel`
2. `design/05-backend-architecture/data/module-boundaries.js` → 提取所有模块的 `applicationService`、`events`、`crossModuleCalls`
3. `design/05-backend-architecture/data/event-contracts.js` → 提取所有事件的字段定义
4. `design/05-backend-architecture/data/layering-strategy.js` → 提取 `directoryTemplate`、`layers`、`constraints`
5. `AGENTS.md` → 提取 `techStack`

**L1 项目：** 如果 `complexityLevel == "L1"` 或架构设计资产不存在，跳过架构驱动的生成步骤，使用经典三层模式。

### 步骤 1：前置 Gap 分析

#### 1.1 ER → ORM Gap

逐实体、逐字段对照 ER 数据与现有代码，标记缺失/多余/类型不匹配。

#### 1.2 API → 代码 Gap

逐端点对照 API 设计文档与现有路由，标记缺失/签名不一致。

#### 1.3 架构 → 代码 Gap（L2+）

| 检查维度 | 对照资产 |
|---------|---------|
| 模块目录是否存在 | `module-boundaries.js` → `src/server/modules/{module}/` |
| 事件类是否定义 | `event-contracts.js` → `src/server/events/` |
| 分层约束是否遵守 | `layering-strategy.js` → 代码目录结构和 import |
| 缓存/幂等/健康检查 | `caching-strategy.js` / `resilience-policy.js` / `observability-policy.js` |

### 步骤 2：代码生成（一次性全量，按架构风格路由）

```
读取 system-topology.js → architectureStyle.primary
    │
    ├── "event-driven-modular-monolith"
    │     ├── 2.1 生成事件系统（EventBus + EventStore + dataclass）
    │     ├── 2.2 生成模块骨架（按 module-boundaries.js）
    │     ├── 2.3 生成分层目录（按 layering-strategy.js）
    │     ├── 2.4 生成 ORM 模型（按 ER 数据）
    │     ├── 2.5 生成 API 路由（按 API 设计）
    │     ├── 2.6 生成横切关注点（缓存/幂等/健康检查/安全）
    │     └── 2.7 生成 IoT Gateway（如果 module-boundaries 中有 IoT 类模块）
    │
    ├── "modular-monolith"
    │     └── 同以上，但跳过 2.1 事件系统 + 2.7 IoT Gateway
    │
    └── 未知风格
          └── 输出警告，生成最小骨架（Controller + Service + Repository）
```

#### 2.1 生成事件系统（EventBus + EventStore + 事件类）

**触发条件：** `architectureStyle.primary` 为 `"event-driven-modular-monolith"` 或架构中包含 EventBus 定义。

**从 `event-contracts.js` 生成：**

```python
# src/server/events/base.py — 自动生成
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

class EventCategory(Enum):
    DOMAIN = "domain"
    COMMAND = "command"

@dataclass
class BaseEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""  # 模块 slug

# 每个 Domain Event 生成一个 dataclass
@dataclass
class EntityStateChanged(BaseEvent):
    """{source-module}/{EventIdentifier} → {subscriber-modules}（示例：模块间事件订阅关系）"""
    entity_id: str = ""
    prev_state: str = ""
    new_state: str = ""
    reason: str = ""

# 每个 Command 生成一个 dataclass
@dataclass
class ExecuteActionCommand(BaseEvent):
    """{source-module}/{CommandService} → {target-module}/{Gateway}（示例：跨模块命令路由）"""
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target_id: str = ""
    action: str = ""
    priority: str = "normal"
```

**从 `module-boundaries.js` 的 `events` 生成 EventBus 注册：**

```python
# src/server/events/event_bus.py — 自动生成
class EventBus:
    def __init__(self): ...
    async def publish(self, event: BaseEvent): ...
    def subscribe(self, event_type: type, handler: Callable): ...

# 全局实例
event_bus = EventBus()
```

**从 `data-consistency.js` 的 outbox 生成 EventStore + Outbox：**

```python
# src/server/events/event_store.py
class EventStore:
    async def append(self, event: BaseEvent) -> str: ...
    async def replay(self, device_id: str, since: datetime) -> list[BaseEvent]: ...

# src/server/events/outbox.py（如果 data-consistency.strategy.crossModule == "outbox"）
class OutboxPublisher:
    async def run(self): ...  # 后台 asyncio 任务，每 1s 扫描 pending 行
```

#### 2.2 生成模块骨架（按 module-boundaries.js）

**对每个模块，生成目录结构：**

```
src/server/modules/{module_slug}/
├── __init__.py
├── application/
│   ├── __init__.py
│   └── {service_name}.py          ← I*Service 接口 + 实现骨架
├── domain/
│   ├── __init__.py
│   └── {policy_name}.py           ← 纯函数业务规则
├── events/
│   ├── __init__.py
│   ├── handlers.py                ← 订阅注册 + Handler 骨架
│   └── publisher.py               ← 发布封装
└── infrastructure/
    ├── __init__.py
    └── {repo_name}.py             ← Repository 实现
```

**handlers.py 骨架（从 `events.subscribes` 生成）：**

```python
# src/server/modules/device_iot/events/handlers.py
from src.server.events.event_bus import event_bus
from src.server.events.base import AdjustAngleCommand, StartOTACommand, ...

@event_bus.subscribe(AdjustAngleCommand)
async def on_adjust_angle(event: AdjustAngleCommand):
    """将角度指令下发到指定设备的 MQTT/WS 通道"""
    # TODO: 实现 — 通过 IoT Gateway 下发
    raise NotImplementedError

@event_bus.subscribe(StartOTACommand)
async def on_start_ota(event: StartOTACommand):
    """触发 OTA 任务下发"""
    raise NotImplementedError
```

#### 2.3 生成分层目录（按 layering-strategy.js）

按 `directoryTemplate` 生成完整目录树，每层 `__init__.py` 中包含 import 约束注释（标记允许和禁止的依赖方向）。

#### 2.4 生成 ORM 模型（按 ER 数据）

从 `AGENTS.md` 读取 ORM 框架，动态构建类型映射表，按 ER 数据生成实体类。
**不内置任何框架映射**——每种框架的类型映射在生成时动态构建。

#### 2.5 生成 API 路由（按 API 设计 + security-policy.js）

- 生成 FastAPI/Flask/Express 路由（按 AGENTS.md 的 framework）
- 异常处理覆盖设计文档中的所有错误场景
- Controller 只做协议适配，不写业务逻辑

#### 2.6 生成横切关注点

| 资产 | 生成内容 |
|------|---------|
| `caching-strategy.js` | 缓存装饰器 + 缓存配置（`@cached(ttl=...)`) |
| `resilience-policy.js` | 幂等中间件 + 重试/熔断/频控装饰器 |
| `observability-policy.js` | `/api/v1/health` 端点 + 指标注册 + 审计日志 + Correlation ID |
| `security-policy.js` | JWT 鉴权依赖注入 + 敏感字段加密/脱敏中间件 |

#### 2.7 生成 IoT Gateway（如果 module-boundaries 中有 device-iot 模块）

```python
# src/server/gateway/iot_gateway.py
class IoTGateway:
    """订阅所有 Command 事件，通过 MQTT/WS 下发到设备"""
    async def start(self): ...
    async def _publish_to_device(self, device_id: str, command: dict): ...
```

### 步骤 3：数据库迁移

从 `AGENTS.md` 的 `orm` 字段推断迁移命令：
- `SQLAlchemy` → `alembic revision --autogenerate && alembic upgrade head`
- `EF Core` → `dotnet ef migrations add ... && dotnet ef database update`
- 其他 → 查找项目中的迁移脚本

### 步骤 4：业务逻辑填充

逐个 Handler 和 Service 方法填充 TODO，对照 API 设计文档和工作流数据实现业务逻辑。

### 步骤 5：测试验证

从 `AGENTS.md` 读取测试命令并执行。失败处理链：
- 测试问题 → 修正测试 | 实现问题 → 修正实现
- 设计问题 → 回溯 `api-design` | 流程问题 → 回溯 `business-workflow`

> **全量回归统一由 §8.8 tdd-execute 执行**，本步骤的「全绿」指冒烟级通过，最终验收以 tdd-execute 报告为准。

### 步骤 6：后置一致性检查

#### 6.1 ER → ORM

与步骤 1.1 同样维度，生成后应零差异。

#### 6.2 API → 代码

路由/参数/响应/错误码/权限一致性。

#### 6.3 架构 → 代码（L2+）

| 检查维度 | 零差异标准 |
|---------|-----------|
| 分层合规 | Controller 无业务逻辑、Domain Service 无 Infrastructure 依赖 |
| 模块边界 | 无跨域直接查表、无禁止依赖被突破 |
| 事件契约 | 所有 handler 正确注册、事件字段与契约一致 |
| 缓存 | 实现匹配策略、TTL 一致 |
| 幂等 | `requiredEndpoints` 全部实现 |
| 健康检查 | 端点存在、覆盖项完整 |
| 审计/安全 | 审计事件接入、敏感字段脱敏 |

### 步骤 7：修复循环

后置检查发现差异 → 回到步骤 2 修复 → 重测 → 重检，直到全绿 + 零差异。

---

## 2. 一致性检查模式（独立调用）

- "使用 api-code-gen 检查 {domain} 的 API 代码与设计一致性"
- "使用 api-code-gen 检查 ER 与 ORM 模型的一致性"
- "使用 api-code-gen 检查代码与后端架构一致性"

被 `review` skill 委托：API→代码 / ER→ORM / TDD→API 三维度（与 review 草稿 §2.11 口径统一——「架构→代码」合规由 review 委托 `backend-architecture-design` 执行，不在本 skill 受托范围）。

---

## 3. 使用方式

1. **完整执行：** "使用 api-code-gen 实现全部域的 API 代码"
2. **单模块：** "使用 api-code-gen 实现 {domain-slug} 模块的代码"
3. **前置检查：** "使用 api-code-gen 检查代码与设计 gap"
4. **仅事件系统：** "使用 api-code-gen 生成事件系统骨架"

---

## 4. 完成检查清单

| 检查项 | 触发条件 |
|--------|---------|
| 架构设计资产已完整读取 | 所有项目 |
| 事件 dataclass 已生成 | 事件驱动架构 |
| EventBus + EventStore 已生成 | 事件驱动架构 |
| Outbox Publisher 已生成 | data-consistency.strategy == "outbox" |
| 模块骨架已生成 | 所有项目 |
| Application Service 接口已生成 | 所有项目 |
| Event Handler 骨架已注册 | 事件驱动架构 |
| IoT Gateway 已生成 | module-boundaries 中存在 IoT 类模块 |
| ORM 模型已生成 | 所有项目 |
| API 路由已生成 | 所有项目 |
| 横切关注点已生成 | L2+ |
| 数据库迁移已执行 | 所有项目 |
| 后置一致性检查零差异 | 所有项目 |
| 测试全绿 | 所有项目 |

---

## 5. 与相关技能的关系

| 技能 | 关系 |
|------|------|
| `backend-architecture-design` | **首要上游** — 提供架构风格、模块边界、事件契约、分层/缓存/可靠性/安全策略。代码生成的全部模式由架构资产决定 |
| `api-design` | 上游 — 提供 API 端点定义 |
| `entity-relationship` | 上游 — 提供 ER 数据，生成 ORM 模型 |
| `tdd-build` | 协同 — 生成的代码需通过其测试 |
| `tdd-execute` | 验收 — 执行全量测试 |
| `review` | 调度 — 委托本 skill 做代码一致性检查 |
