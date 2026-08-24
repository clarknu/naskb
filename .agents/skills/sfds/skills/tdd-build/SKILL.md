---
name: tdd-build
version: 3.0.0
description: |
  TDD 测试设计与编码——三阶段架构（API TDD → Page Mock TDD → Integration TDD）。
  读取 API 设计/ER/工作流/页面设计/后端架构设计 → 按阶段设计测试用例 → 编写测试代码。
  输出 TDD 设计文档 + 测试代码。三阶段分离（Stage 1/2/2b/3）+ 阶段参数分发。
triggers:
  - TDD 设计
  - 测试设计
  - 测试编码
  - 写测试
  - 测试用例设计
  - 测试代码生成
  - TDD
  - 测试覆盖
  - 架构测试
  - API 测试
  - 页面测试
  - 集成测试
  - 写 API 测试
  - 写页面测试
  - 写集成测试

lineage:
  origin: arb-hub
  sources:
    boxing:        {sha256: 7b1586e18413}
    zy-iot-ai:     {sha256: c16853e0c671}
    zy-ai-consult: {sha256: c16853e0c671}
---

# TDD Build — 测试设计与编码 Skill

> **本 skill 只负责测试的设计与编码。测试的执行、报告、失败分析与修复循环由 [`tdd-execute`](../tdd-execute/SKILL.md) 负责。**

---

## §1 阶段分发

TDD 按 **三层递进** 组织，每层有独立的启动条件、Mock 策略、测试框架和目录结构。

> **调用方传入 Arguments 字符串，按以下规则自动分发到对应阶段。**

| 参数含 | 分发到 | 说明 |
|--------|--------|------|
| `api` | **§3 API TDD** | 后端 API 测试设计与编码 |
| `page-mock` | **§4 Page Mock TDD** | Web 前端页面独立 Mock 测试设计与编码 |
| `miniprogram` | **§4b Mini Program TDD** | 小程序模拟器自动化测试设计与编码 |
| `integration` | **§5 Integration TDD** | 前后端集成测试设计与编码 |
| 为空 / `all` | **依次执行全部适用阶段** | 自动检测项目端类型：有 Web 端→§3→§4→§5；有小程序端→§3→§4b→§5。两者都有则都执行 |

> **端类型自动检测：** 当 `arguments=all` 时，读取项目的客户端列表（`design/domain-registry.js` 或 `design/` 目录下的 `06-*` 子目录），自动判定执行哪些前端测试阶段。

**阶段间关系：**

```
API 设计完成                  页面设计完成              两端代码全部完成
     ↓                            ↓                          ↓
┌──────────────┐    ┌──────────────────────┐    ┌──────────────┐
│ Stage 1      │    │ Stage 2 / 2b         │    │ Stage 3      │
│ API TDD      │    │ ┌──────────┬────────┐│    │ Integration  │
│              │    │ │ Stage 2  │Stage 2b││    │ TDD          │
├──────────────┤    │ │Page Mock │Mini Prg││    ├──────────────┤
│ 验证对象:    │    │ │(Web)     │(小程序)││    │ 验证对象:    │
│ 后端 API     │    │ ├──────────┼────────┤│    │ 端到端流程   │
│              │    │ │Vitest/   │微信开  ││    │              │
│ Mock 策略:   │    │ │Jest      │发者工具││    │ Mock 策略:   │
│ 外部服务     │    │ │组件测试  │automator│   │ 仅外部服务   │
│              │    │ ├──────────┼────────┤│    │              │
│ 测试框架:    │    │ │Mock 全部 │Mock wx ││    │ 测试框架:    │
│ 后端框架测试库│    │ │HTTP API  │API+HTTP││    │ 浏览器 E2E /│
│              │    │ │          │        ││    │ 小程序全集成│
│ 目录:        │    │ │tests/    │tests/  ││    │ 目录:        │
│ tests/api/   │    │ │page-mock/│minipro-││    │ tests/       │
│              │    │ │          │gram/   ││    │ integration/ │
└──────────────┘    │ └──────────┴────────┘│    └──────────────┘
     并行→          └──────────────────────┘     串行→
```

> **Stage 2（Web Page Mock）和 Stage 2b（Mini Program）是并行变体**——项目可能只有其一、两者皆有、或都没有。
> 两者均在"页面设计完成"后即可启动，彼此独立。Stage 3 只在其覆盖的端类型对应的前端测试全绿后才启动。
>
> **目录说明（门控按用例层级而非物理目录）：** 图中 `tests/api/` 与 `tests/integration/` 为通用分层示意。允许项目把 Stage 1（API TDD）与 Stage 3（Integration）的用例放在同一物理测试根目录下组织（如领域级用例与跨域旅程用例各占子目录）；此时「Stage 3 在 Stage 1 全绿后启动」的门控按**用例层级**理解——上一层级用例全绿后再跑下一层级——不要求两阶段物理目录分离。

**Mock 策略逐层递减**：Stage 1 只 mock 外部服务 → Stage 2/2b mock 全部 API → Stage 3 只 mock 外部服务，其余全真实。越往后越接近生产环境。

---

## §2 通用方法论（三阶段共享）

以下方法论在 Stage 1/2/3 中统一适用，各阶段特定差异在各节单独说明。

### 2.1 本技能规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | **契约先行** | 测试代码只依赖设计契约（API 路径/参数/响应，页面功能树定义），不依赖任何实现细节 |
| 2 | **输入完整** | 每个 Stage 开始前必须采集该阶段的完整输入（见各 Stage 的输入采集表） |
| 3 | **覆盖度达标** | 正常路径 100% / 参数校验全覆 / 状态转换全覆 / 错误场景 ≥80% / 边界条件 ≥80% / 权限全等级（状态转换/错误场景/边界条件/权限维度按 §2.5 复杂度分级裁剪，L1 简单 CRUD 可省略相应维度；L2+ 全量执行） |
| 4 | **独立可重复** | 每个测试用例独立运行，不依赖其他用例的执行顺序 |
| 5 | **失败回溯链清晰** | 测试失败时按"测试代码→实现→设计→业务流程"逐级回溯定位（由 tdd-execute 执行） |
| 6 | **中文输出** | 所有 TDD 报告、摘要、汇报内容必须使用中文撰写，不得输出英文报告 |

### 2.2 测试用例设计模板

各阶段共用的测试用例模板（API 测试和前端测试的具体示例见各 Stage 章节）：

```markdown
### TC-{编号}: {测试标题}

- **正向追溯链**: workflow:{node_id}.outputs.{field} → API:{method} {path}.consumes[].{param} → page:{page_id}.sends[].{field}
- **反向追溯链**: page:{page_id}.page_input.params[] ← page:{prev_page}.page_output.params[] ← API:{method} {path}.produces[].{field} ← ER:{entity}.{field}
- **用户旅程**: {journey-name}（来自 business-workflow start→end 路径）

> **注意**：正向/反向追溯链和用户旅程字段在初始设计阶段可选填写，在 tdd-execute 复审阶段和 review 一致性检查时强制要求。
- **类型**: 正常流程 / 异常流程 / 边界条件 / 状态转换 / 并发 / 幂等 / 缓存 / 故障恢复 / 架构承诺
- **前置条件**: {数据准备、认证状态、业务状态前提}
- **调用序列**:
  1. {操作描述} → 预期结果
  2. {操作描述} → 预期结果
- **断言清单**:
  - ✅ {断言条件}
- **边界条件**:
  - ⚠️ {边界场景 → 预期行为}
```

### 2.3 测试代码原则

| 原则 | 说明 |
|------|------|
| **一个用例一个方法** | 每个 TC-XXX 对应一个测试方法，方法名体现测试场景 |
| **测试数据工厂** | 通用的测试数据准备抽取为工厂方法，避免重复 |
| **Mock 外部依赖** | 第三方服务、消息队列等外部依赖使用 Mock |
| **数据库隔离（DI 拦截）** | 见下方 §2.4 |
| **可重复执行** | 每个测试用例独立，不依赖其他用例的执行顺序 |

### 2.4 测试数据库隔离规则 —— DI 容器拦截模式

**核心原则：测试代码通过 DI 容器替换来切换数据库，永远不通过修改配置文件或环境变量来改变数据库行为。**

生产环境的数据库连接串写在配置文件中，由应用入口读取。
测试基础设施通过框架提供的 DI 拦截机制，在容器构建后将生产注册**移除**并**替换**为测试专用实例。
配置文件和入口代码对"测试模式"零感知——没有 `if (isTest)` 分支，没有 `TestingConnectionString` 配置键。

> **为什么是 DI 拦截而不是配置文件切换？**
> - 配置文件切换意味着入口代码需要感知"当前是测试还是生产"，污染入口代码
> - 环境变量切换（如 `APP_ENV=Testing`）是间接耦合——改了变量却期望行为变化，出问题时难以追踪
> - DI 拦截是显式的、可读的、集中在测试基础设施中的——TestHarness 只需"移除生产注册 → 注册测试替身"两步就把整个依赖替换了
> - 生产代码不携带任何测试负担，测试代码不依赖任何配置文件 magic string

**适用范围：** 所有需要在测试中隔离的外部依赖（数据库、消息队列、对象存储、缓存服务、第三方 API 客户端等），统一通过 DI 容器拦截替换。

**数据库无关声明：** 本规则与数据库类型无关。无论是关系型（SQLite / PostgreSQL / MySQL / SQL Server）、文档型（MongoDB）、或其他存储系统，隔离策略完全相同。

#### 通用模式

```
生产入口（app entry）
  │
  └── 读取配置 → 注册真实依赖（DB / MQ / Storage / Cache）
      │
      └── 不感知测试/生产模式差异
          │
          ▼
测试基础设施（TestHarness / TestFactory / TestModule）
  │
  └── 继承/包装生产入口
      │
      ├── 1. 定位 DI 容器中的生产注册
      ├── 2. 移除生产注册
      ├── 3. 注册测试替身     ← 内存DB / Mock / Stub
      └── 4. 其他测试专用替换（后台服务禁用、外部服务 Stub 化）
```

#### 框架对应关系

| 框架 | 生产入口 | DI 拦截入口 | 替换 API |
|------|---------|------------|---------|
| ASP.NET Core | 入口文件 + 配置文件 | `WebApplicationFactory<TProgram>` → `ConfigureServices` | `Remove(生产注册)` → `Add(测试替身)` |
| Spring Boot | `Application.java` + `application.yml` | `@TestConfiguration` + `@Primary` Bean 覆盖 | `@Bean` 覆盖或 `@Profile("test")` |
| NestJS | `main.ts` + `AppModule` | `Test.createTestingModule()` → `overrideProvider()` | `overrideProvider().useValue()` |
| FastAPI / Starlette | `app.py` + 配置 | `TestClient(app)` + `app.dependency_overrides` | `app.dependency_overrides[原依赖] = 测试替身` |
| Express / Fastify | `app.ts` + 配置 | 测试文件直接构造 app 实例并注入 Stub | 手动替换中间件/服务实例 |
| Django | `settings.py` | `@override_settings` + `TestCase` 的 `setUp` | `override_settings(DATABASES={...})` |

> **本质就是 3 步：** (1) 定位 DI 容器中的生产注册 → (2) 移除它 → (3) 注册测试替身。生产入口文件对测试模式零感知。

#### 测试替身选择指南

| 替身类型 | 适用场景 | 优点 | 缺点 |
|---------|---------|------|------|
| **内存数据库**（SQLite :memory: / H2 / Embedded MongoDB） | 开发阶段、快速迭代、CI 轻量运行 | 零外部依赖、启动极快、隔离天然 | 方言差异可能导致生产 Bug 漏过 |
| **测试容器**（Testcontainers: PostgreSQL / MySQL / MongoDB） | 接近上线、对 SQL 方言敏感的查询 | 与生产环境完全一致 | 需要 Docker、启动较慢 |
| **Mock / Stub** | 单元测试、不涉及真实查询的 Service 层测试 | 极快、精确控制返回值 | 不验证实际查询逻辑 |

> **推荐策略：** 日常开发用内存数据库（快速迭代），CI 流水线中增加一个 Testcontainers 阶段（方言验证）。两者都通过 DI 拦截切换，不需要改任何生产代码。

### 2.5 TDD 分级策略（按复杂度决定测试深度）

> **设计意图：** 不是所有项目都需要全量测试。测试深度应与项目复杂度匹配。

**复杂度 → 测试维度映射：**

| 测试维度 | L1 简单CRUD | L2 复杂单体 | L3 模块化单体 | L4 分布式 |
|---------|:----------:|:----------:|:----------:|:--------:|
| **正常路径** | ✅ | ✅ | ✅ | ✅ |
| **参数校验** | ✅ | ✅ | ✅ | ✅ |
| **错误场景** | 🟡 关键端点 | ✅ | ✅ | ✅ |
| **状态转换** | — | ✅ | ✅ | ✅ |
| **业务规则** | — | ✅ | ✅ | ✅ |
| **边界条件** | 🟡 | ✅ | ✅ | ✅ |
| **权限** | 🟡 | ✅ | ✅ | ✅ |
| **幂等性** | — | ✅ | ✅ | ✅ |
| **并发冲突** | — | 🟡 | ✅ | ✅ |
| **缓存命中/失效** | — | 🟡 | ✅ | ✅ |
| **外部依赖失败/熔断** | — | — | ✅ | ✅ |
| **事务回滚** | — | 🟡 | ✅ | ✅ |
| **事件发布/Outbox** | — | — | ✅ | ✅ |
| **超时/降级** | — | — | ✅ | ✅ |
| **健康检查** | 🟡 | ✅ | ✅ | ✅ |
| **审计日志** | — | 🟡 | ✅ | ✅ |
| **HTTP 服务间契约** | — | — | — | ✅ |
| **消息 Schema** | — | — | — | ✅ |
| **gRPC/WebSocket** | — | — | — | 🟡 |
| **前端组件测试（Page Mock / Mini Program）** | ✅ | ✅ | ✅ | ✅ |
| **前端交互测试（Page Mock / Mini Program）** | — | ✅ 导航+表单+权限 | ✅ + 缓存 | ✅ + 缓存 |
| **集成 E2E 测试** | — | ✅ 关键旅程 | ✅ | ✅ |

> **图例：** ✅ = 必做，至少 1 个用例 / 🟡 = 建议做，可按需裁剪 / — = 不适用，跳过
>
> **判定规则：** 复杂度等级从 `backend-architecture-design` 的 `system-topology.js` 读取。

### 2.6 架构承诺测试覆盖（L2+ 项目）

> 如果项目复杂度 ≥ L2 且存在后端架构设计资产，以下维度必须在 Stage 1（API TDD）中覆盖。
> 这些测试验证的不是业务功能是否正确，而是**架构承诺是否兑现**。

| 覆盖维度 | 最低要求 | 来源资产 |
|---------|---------|---------|
| **幂等性** | `idempotency.requiredEndpoints` 中的每个端点至少 1 个重复请求用例 | `resilience-policy.js` |
| **并发冲突** | 涉及状态变更的端点至少 1 个并发用例 | `resilience-policy.js` |
| **缓存命中** | 标注缓存的 GET 端点至少 1 个缓存命中用例 | `caching-strategy.js` |
| **缓存失效** | 标注失效条件的缓存至少 1 个失效后重新获取用例 | `caching-strategy.js` |
| **外部依赖失败** | `circuitBreaker.targets` 中的每个外部依赖至少 1 个失败用例 | `resilience-policy.js` |
| **事务回滚** | 涉及多表写入的端点至少 1 个部分失败回滚用例 | `data-consistency.js` |
| **事件发布** | 有副作用的端点至少 1 个事件发布验证用例 | `data-consistency.js` |
| **健康检查** | 1 个健康检查端点用例 | `observability-policy.js` |
| **审计日志** | `auditLog.events` 中的每个事件至少 1 个审计记录验证用例 | `observability-policy.js` |
| **权限绕过** | 每个权限等级至少 1 个越权访问用例 | `security-policy.js` |
| **超时/降级** | 标注超时配置的端点至少 1 个超时用例 | `resilience-policy.js` |

### 2.7 微服务间契约测试覆盖（L4+ 项目）

> 当项目复杂度 ≥ L4（分布式服务），服务间通信链路的契约必须独立验证。

| 覆盖维度 | 最低要求 | 来源资产 | 测试方法 |
|---------|---------|---------|---------|
| **HTTP 服务间契约（Consumer 端）** | `module-boundaries.js` 中每个跨服务 HTTP 调用 ≥ 1 个 Consumer 契约用例 | `module-boundaries.js` | CDC：Mock Provider，验证 Consumer 请求格式正确 |
| **HTTP 服务间契约（Provider 端）** | 每个暴露 HTTP 接口的服务 ≥ 1 个 Provider 验证用例 | `module-boundaries.js` | Provider 端加载所有 Consumer 契约 → 验证实际响应匹配 |
| **消息队列 Schema** | `event-contracts.js` 中每个事件类型 ≥ 1 个 Schema 验证用例 | `event-contracts.js` | Schema Registry 校验 + 序列化/反序列化兼容性测试 |
| **消息队列行为** | 每个事件类型 ≥ 1 个端到端消息用例 | `event-contracts.js` | 嵌入式 MQ broker 或 Mock |
| **gRPC 契约兼容性** | 每个 Proto service ≥ 1 个向后兼容用例 | `deployment-profile.js` | Proto lint（buf breaking） |
| **WebSocket 生命周期** | 每个 WebSocket 端点 ≥ 1 个连接生命周期用例 | `deployment-profile.js` | 测试用 WebSocket 客户端 + 超时/断线模拟 |

---

## §3 Stage 1 — API TDD 设计与编码

> **对应前端触发词：** `写 API 测试`、`API TDD`、`API 测试设计`
> **Arguments 匹配：** 含 `api` 时执行本阶段。

### 3.1 启动条件

| 条件 | 状态 |
|------|:---:|
| API 设计（§8.3）完成 | ✅ 必须 |
| ER 数据存在 | ✅ 必须 |
| 业务工作流存在 | ✅ 必须 |
| 后端架构设计（L2+） | 🟡 架构承诺测试需要 |
| API 实现代码 | ❌ **不需要**——TDD 本质是在实现之前写测试 |

### 3.2 输入采集

| 输入 | 来源 | 提供什么 |
|------|------|---------|
| **API 设计文档** | `design/04-platform-api/data/rest/{domain-slug}.js` | 端点列表、请求参数、响应格式、错误场景、状态机 |
| **ER 数据** | `design/03-entity-relationship/data/{domain-slug}.js` | 实体字段约束、关系定义、枚举值 |
| **业务工作流** | `design/02-business-workflow/data/{domain-slug}.js` | 操作步骤顺序、状态转换条件、业务规则约束 |
| **后端架构设计（L2+）** | `design/05-backend-architecture/data/*.js` | 架构承诺：幂等/缓存/可靠性策略等 |
| **域注册表** | `design/domain-registry.js` | 领域 slug、跨域引用 |

### 3.3 测试框架与 Mock 策略

| 维度 | 详情 |
|------|------|
| **测试类型** | 后端 HTTP 集成测试（通过测试客户端发请求，走完整请求-响应周期） |
| **测试框架** | 项目后端技术栈的测试框架（pytest + httpx / JUnit / Jest + supertest / xUnit 等） |
| **Mock 什么** | 外部服务（LLM/ASR/TTS/MQTT broker/第三方 API） |
| **真实什么** | 数据库（内存/项目测试库，通过 DI 拦截）、内部业务逻辑、中间件 |
| **数据库** | 测试专用数据库，通过 DI 拦截切换（见 §2.4），不动生产配置 |

### 3.4 设计输出

输出到 `design/07-tdd/api/{domain-slug}-tdd-design.md`：

```markdown
# TDD 设计（API）：{领域名}

> 基于 API 设计 v{version} | 工作流 v{version} | 后端架构 v{version}（L2+）
> 日期：{YYYY-MM-DD} | Stage: API TDD

## 测试范围

| API 端点 | 方法 | 涉及工作流 | 涉及实体 |
|----------|------|-----------|---------|
| /api/xxx | POST | section-3.1 | entity-xxx |
| ... | ... | ... | ... |

## 追溯矩阵

| 测试用例 | 正向链（workflow→API→ER） | 反向链（API←ER←workflow） | 用户旅程 |
|---------|--------------------------|--------------------------|---------|

## 用户旅程覆盖矩阵

| 旅程 | 涉及 API | 覆盖测试用例 | 状态 |
|------|---------|-------------|------|

## 测试用例

### TC-001: {标题}
...

### TC-002: {标题}
...
```

### 3.5 测试代码输出

代码目录：`tests/api/{domain-slug}/`

```
tests/api/
├── conftest.py              ← 共享 fixtures（DI 拦截、测试 DB 初始化、全局 Mock）
├── {domain-slug}/
│   ├── test_{feature1}.py
│   ├── test_{feature2}.py
│   └── conftest.py          ← 域级 fixtures
└── ...
```

**测试代码原则**（Stage 1 特化）：
- 测试代码完全独立于 API 实现——只依赖 API 设计文档中的接口契约（路径、方法、参数名、参数类型、响应结构、状态码、错误格式）
- 不 import/reference 任何 API 实现类（Controller 类名、Service 方法名等）

### 3.6 运行命令

Stage 1 的执行命令（由 `tdd-execute(api)` 执行）——**以 `tdd-execute` §3.2 命令表为准**，此处不再维护命令，避免双源不一致：

| 后端技术栈 | 示例命令（详见 tdd-execute §3.2） |
|-----------|----------------------------------|
| Python + FastAPI | `PYTHONPATH=src python -m pytest tests/api/ -v` |
| .NET | `dotnet test tests/api/ --verbosity normal` |
| Node.js | `npx jest tests/api/` |
| Spring Boot | `./gradlew test --tests "*ApiTest*"` |

---

## §4 Stage 2 — Page Mock TDD 设计与编码

> **对应前端触发词：** `写页面测试`、`页面 TDD`、`页面 mock 测试`、`前端测试`
> **Arguments 匹配：** 含 `page-mock` 时执行本阶段。

### 4.1 启动条件

| 条件 | 状态 |
|------|:---:|
| 页面功能设计（§8.4）完成 | ✅ 必须 |
| API 设计（§8.3）完成 | ✅ 需要（用于构造 Mock 数据形状） |
| 页面实现代码 | ❌ **不需要**——TDD 本质是在实现之前写测试 |
| 后端 API 实现 | ❌ 完全不需要——本阶段全部 API Mock |

### 4.2 输入采集

| 输入 | 来源 | 提供什么 |
|------|------|---------|
| **页面功能树** | `design/06-{client-slug}/data/tree.js` | 功能组件列表、表单字段、操作按钮、权限引用 |
| **页面流程定义** | `design/06-{client-slug}/data/processes.js` | 页面跳转路径、数据传递定义 |
| **API 设计文档** | `design/04-platform-api/data/rest/{domain-slug}.js` | 端点签名——用于构造精确的 Mock 响应（形状、状态码、错误格式） |
| **域注册表** | `design/domain-registry.js` | 领域 slug、跨域引用 |

### 4.3 测试框架与 Mock 策略

| 维度 | 详情 |
|------|------|
| **测试类型** | 前端组件/路由/交互测试——模拟用户在浏览器中的操作 |
| **测试框架** | 前端技术栈的组件测试框架（Vitest + @vue/test-utils / Jest + React Testing Library 等） |
| **Mock 什么** | **全部 API 调用**——使用 MSW（Mock Service Worker）或框架内置 mock 拦截所有 HTTP 请求 |
| **真实什么** | Vue/React 组件、路由跳转、状态管理、表单校验、UI 渲染 |
| **后端依赖** | **零**——不需要启动任何后端服务 |

> **为什么 Stage 2 要 mock 全部 API？**
> 因为 Stage 2 的目标是验证**前端自身的行为**——路由跳转是否正确、表单校验是否生效、
> 按钮状态是否按预期切换、Loading/Error 状态是否正确渲染。
> 这些行为**不需要真实后端**也能完全验证，而且 mock 可以精确控制边界场景
> （比如 mock 一个 500 错误来验证错误提示是否正确展示），这在真实后端上反而很难触发。

### 4.4 设计输出

输出到 `design/07-tdd/page-mock/{client-slug}-tdd-design.md`：

```markdown
# TDD 设计（Page Mock）：{客户端名}

> 基于页面设计 v{version} | API 设计 v{version}
> 日期：{YYYY-MM-DD} | Stage: Page Mock TDD

## 测试范围

| 页面/组件 | 涉及交互 | Mock API | 权限 |
|----------|---------|---------|------|
| 设备列表页 | 列表渲染、筛选、分页 | GET /api/v1/devices | admin |
| 设备详情页 | 详情展示、操作按钮 | GET /api/v1/devices/{id} | admin |
| ... | ... | ... | ... |

## 测试用例

### TC-M001: 设备列表加载成功
- **类型**: 正常流程
- **前置条件**: Mock GET /api/v1/devices 返回 3 条设备数据
- **操作序列**:
  1. 渲染设备列表页面组件
  2. 等待异步数据加载完成
- **断言清单**:
  - ✅ 列表中渲染 3 行设备数据
  - ✅ 每条数据显示设备名称、状态标签
  - ✅ 分页组件显示正确的总条数

### TC-M002: 设备列表加载失败展示错误提示
- **类型**: 异常流程
- **前置条件**: Mock GET /api/v1/devices 返回 500
- **操作序列**:
  1. 渲染设备列表页面组件
  2. 等待请求完成
- **断言清单**:
  - ✅ 页面显示错误提示信息
  - ✅ 不显示空列表（区别于无数据的空状态）

### TC-M003: ...
```

### 4.5 测试代码输出

代码目录：`tests/page-mock/{client-slug}/`

```
tests/page-mock/
└── {client-slug}/
    ├── setup.ts               ← MSW server + handlers、全局 mock 数据
    ├── pages/
    │   ├── test_device_list.spec.ts
    │   ├── test_device_detail.spec.ts
    │   └── ...
    ├── components/
    │   ├── test_status_badge.spec.ts
    │   └── ...
    └── navigation/
        └── test_routing.spec.ts
```

### 4.6 运行命令

Stage 2 的执行命令（由 `tdd-execute(page-mock)` 执行）——**以 `tdd-execute` §4.2 命令表为准**：

| 前端技术栈 | 示例命令（详见 tdd-execute §4.2） |
|-----------|----------------------------------|
| Vue 3 + Vitest | `cd src/{client-slug} && npx vitest run tests/page-mock/` |
| React + Jest | `npx jest tests/page-mock/` |
| Angular + Jasmine | `ng test --include='**/page-mock/*.spec.ts'` |

---

## §4b Stage 2b — Mini Program Simulator TDD 设计与编码

> **对应触发词：** `写小程序测试`、`小程序 TDD`、`Mini Program 测试`、`模拟器测试`
> **Arguments 匹配：** 含 `miniprogram` 时执行本阶段。
>
> **本阶段仅在项目中存在小程序端（client slug 含 `miniprogram`）时适用。**
> 当 `arguments=all` 时，自动检测项目端类型：有 Web 端→执行 §4，有小程序端→执行 §4b，两者都有→都执行。

### 4b.1 启动条件

| 条件 | 状态 |
|------|:---:|
| 页面功能设计（§8.4）完成 | ✅ 必须 |
| API 设计（§8.3）完成 | ✅ 需要（用于构造 Mock 数据形状） |
| 小程序项目文件存在（`project.config.json`） | ✅ 必须 |
| 微信开发者工具已安装且 `wechatide` 命令可用 | ✅ 必须 |
| 页面实现代码 | ❌ **不需要**——TDD 本质是在实现之前写测试 |
| 后端 API 实现 | ❌ 不需要——本阶段可 Mock 全部 wx API + HTTP API |

### 4b.2 输入采集

| 输入 | 来源 | 提供什么 |
|------|------|---------|
| **页面功能树** | `design/06-{client-slug}/data/tree.js` | 功能组件列表、表单字段、操作按钮、权限引用 |
| **页面流程定义** | `design/06-{client-slug}/data/processes.js` | 页面跳转路径、数据传递定义 |
| **API 设计文档** | `design/04-platform-api/data/rest/{domain-slug}.js` | 端点签名——用于构造精确的 Mock 响应 |
| **域注册表** | `design/domain-registry.js` | 领域 slug、跨域引用 |
| **小程序项目配置** | `<project>/project.config.json` | appid、项目根路径 |

### 4b.3 测试框架与 Mock 策略

| 维度 | 详情 |
|------|------|
| **测试类型** | 小程序模拟器自动化测试——在微信开发者工具模拟器中操作真实小程序页面 |
| **测试框架** | 微信开发者工具 automator（通过 `wechatide` CLI 调用，参见 `wechatide-skill/skills/automator/SKILL.md`） |
| **Mock 什么** | **wx API**（通过 `automation_wx_api` mock）+ HTTP API（按需 Stub 服务） |
| **真实什么** | 小程序页面渲染、路由跳转、组件交互、数据绑定 |
| **后端依赖** | **零**——纯 Mock 模式下不需要启动后端服务 |
| **工具依赖** | 微信开发者工具 + `wechatide` CLI + 已登录态（`openid` 有效） |

> **为什么使用模拟器而非单元测试框架？**
> 微信小程序页面由 WXML + WXSS + JS/TS 三部分组成，前端组件测试框架（Vitest/Jest）无法渲染
> WXML 模板，因此无法验证 UI 行为。微信开发者工具内置的 automator 可以直接在模拟器中
> 导航页面、点击元素、读取数据、截图验证——是当前小程序 UI 自动化的可行方案。

> **Mock 层级选择：**
> - **纯 Mock 模式（Stage 2b 推荐）**：Mock 全部 wx API + HTTP API，验证前端自身行为
> - **半集成模式**：Mock wx API，HTTP API 走真实后端（需启动后端服务）
> - **全集成模式**：不 Mock，全部走真实服务（等价于 Stage 3 的小程序版）

### 4b.4 测试工具速查

Stage 2b 的所有原子操作通过 `wechatide` CLI 的 automator 工具完成。关键工具速查：

| 操作 | 工具 | 关键参数 |
|------|------|---------|
| 环境检查 | `check_wechatide_status` | `--skill-version` |
| 打开项目 | `open_project_window` | `--project <path>` |
| 页面导航 | `automation_navigate` | `--action navigateTo` / `redirectTo` / `switchTab` / `navigateBack`，`--url <pagePath>` |
| 元素点击 | `automation_element_action` | `--selector <css>` `--action tap` |
| 文本输入 | `automation_element_action` | `--selector <css>` `--action input` `--value <text>` |
| 读取文本 | `automation_element_action` | `--selector <css>` `--action text` |
| 读取属性 | `automation_element_action` | `--selector <css>` `--action attribute` `--name <attrName>` |
| 读取数据 | `automation_page_action` | `--action getData` `--path <dataPath>` |
| 查询元素 | `automation_page_action` | `--action querySelectorAll` `--selector <css>` |
| 等待条件 | `automation_page_action` | `--action waitFor` `--condition <expr>` |
| 截图 | `automation_viewport_action` | `--action screenshot` `--wait-for-selector <css>` `--path <localPath>` |
| Call wx API | `automation_wx_api` | `--action call` `--method <apiName>` |
| Mock wx API | `automation_wx_api` | `--action mock` `--method <apiName>` `--result-file <jsonPath>` |
| 执行 JS | `automation_evaluate` | `--fn-source <function>` |
| 运行时信息 | `automation_runtime_info` | `--action currentPage` / `pageStack` / `systemInfo` |

> **完整工具列表与参数说明**：参见 `wechatide-skill/wechatide-tools/references/tools.yaml`。
> **调用示例与最佳实践**：参见 `wechatide-skill/skills/automator/SKILL.md`。

### 4b.5 设计输出

输出到 `design/07-tdd/miniprogram/{client-slug}-tdd-design.md`：

```markdown
# TDD 设计（Mini Program）：{客户端名}

> 基于页面设计 v{version} | API 设计 v{version}
> 日期：{YYYY-MM-DD} | Stage: Mini Program Simulator TDD

## 测试范围

| 页面路径 | 涉及交互 | Mock wx API | Mock HTTP API | 权限 |
|---------|---------|------------|--------------|------|
| pages/device/list | 列表渲染、筛选、分页 | wx.getSystemInfo | GET /api/v1/devices | — |
| pages/device/detail | 详情展示、操作按钮 | wx.showModal | GET /api/v1/devices/{id} | admin |
| ... | ... | ... | ... | ... |

## 测试用例

### TC-MP001: 设备列表加载成功
- **类型**: 正常流程
- **前置条件**: Mock GET /api/v1/devices 返回 3 条设备数据；Mock wx.getSystemInfo 返回标准屏幕信息
- **操作序列**:
  1. navigateTo pages/device/list
  2. waitFor .device-item
  3. querySelectorAll .device-item → 验证 count >= 1
- **断言清单**:
  - ✅ 页面至少渲染 1 个 device-item 元素
  - ✅ 每个 device-item 包含设备名称文本
  - ✅ 不出现 error 或 empty 状态
- **证据**: screenshot → tests/miniprogram/{slug}/evidence/tc-mp001.png

### TC-MP002: 设备列表加载失败展示错误提示
- **类型**: 异常流程
- **前置条件**: Mock GET /api/v1/devices 返回 500
- **操作序列**:
  1. navigateTo pages/device/list
  2. waitFor .error-toast
- **断言清单**:
  - ✅ 页面显示错误提示
  - ✅ 不显示空列表（区别于无数据的空状态）
```

### 4b.6 测试脚本与证据输出

目录结构：`tests/miniprogram/{client-slug}/`

```
tests/miniprogram/
└── {client-slug}/
    ├── test-plan.md           ← 测试用例列表 + 执行顺序 + wechatide 命令序列
    ├── mock/
    │   ├── wx-api-mocks.json   ← wx API mock 配置（method → result 映射）
    │   └── http-mocks.json     ← HTTP API mock 响应数据
    ├── scripts/                ← 可重放脚本（通过 automation_generate_script 生成）
    │   └── tc-mp001.js
    └── evidence/               ← 截图证据
        ├── tc-mp001.png
        └── tc-mp002.png
```

> **与 Web Page Mock 的关键区别：**
> 小程序测试没有传统的"测试代码文件"（`*.spec.ts`）。测试用例通过 `wechatide` CLI
> 实时执行：设计文档定义用例规格 → 执行时将规格翻译为 `wechatide` 命令序列 →
> 截图和状态读取作为证据留存。`automation_generate_script` 工具可将已执行的调用
> 序列生成为可重放的 `.js` 脚本，放入 `scripts/` 目录供回归使用。

### 4b.7 执行命令

Stage 2b 的执行命令（由 `tdd-execute(miniprogram)` 执行）——详见 `tdd-execute` §4b。

核心执行模式（示意）：

```bash
# 1. 环境检查
wechatide -c <clientName> -t check_wechatide_status --skill-version <version>

# 2. 打开项目窗口
wechatide -c <clientName> -t open_project_window --project <projectPath>

# 3. 按 test-plan.md 逐条执行用例
wechatide -c <clientName> -t automation_navigate --project <p> --action navigateTo --url pages/x/x
wechatide -c <clientName> -t automation_page_action --project <p> --action waitFor --condition ".loaded"
wechatide -c <clientName> -t automation_viewport_action --project <p> --action screenshot --wait-for-selector .content --path evidence/tc-xxx.png
```

---

## §5 Stage 3 — Integration TDD 设计与编码

> **对应前端触发词：** `写集成测试`、`集成 TDD`、`E2E 测试`、`端到端测试`
> **Arguments 匹配：** 含 `integration` 时执行本阶段。

### 5.1 启动条件

| 条件 | 状态 |
|------|:---:|
| Stage 1（API TDD）全部通过 | ✅ 必须——API 行为和契约已由 Stage 1 验证 |
| Stage 2（Page Mock TDD）全部通过 | ✅ 必须——前端行为已由 Stage 2 验证 |
| Stage 2b（Mini Program TDD）全部通过（如有小程序端） | ✅ 必须——对应端类型的前端行为已由 Stage 2b 验证 |
| API 实现代码完成 | ✅ 必须 |
| 页面实现代码完成 | ✅ 必须 |
| 后端可独立启动 | ✅ 必须 |

> **Stage 3 是最终的串联验证——所有组件独立验证通过后才拼在一起测试。**

### 5.2 输入采集

| 输入 | 来源 | 提供什么 |
|------|------|---------|
| **API TDD 设计文档** | `design/07-tdd/api/{domain-slug}-tdd-design.md` | Stage 1 已覆盖的场景——Stage 3 只补端到端旅程 |
| **Page Mock TDD 设计文档** | `design/07-tdd/page-mock/{client-slug}-tdd-design.md` | Stage 2 已覆盖的交互——Stage 3 只补跨页面串联 |
| **业务工作流** | `design/02-business-workflow/data/{domain-slug}.js` | 完整的用户旅程（start→end） |
| **页面流程定义** | `design/06-{client-slug}/data/processes.js` | 跨页面跳转路径和数据传递链 |
| **域注册表** | `design/domain-registry.js` | 领域 slug、跨域引用 |

### 5.3 测试框架与 Mock 策略

| 维度 | 详情 |
|------|------|
| **测试类型** | 浏览器端到端测试——启动真实后端 + 真实前端页面 |
| **测试框架** | 浏览器自动化框架（Playwright / Cypress / Selenium） |
| **Mock 什么** | 仅外部服务（LLM/ASR/TTS/MQTT broker），其余全部真实 |
| **真实什么** | 真实后端服务 + 真实前端页面 + 真实数据库 + 真实中间件 |
| **后端依赖** | 需要——测试前必须启动后端服务 |
| **前端依赖** | 需要——测试前必须启动前端开发服务器或构建产物 |

> **Stage 3 的测试粒度是用户旅程级别**，不是单个 API 或单个页面。
> 单个 API 和单个页面的边界场景已在 Stage 1 和 Stage 2 覆盖。
> Stage 3 应该聚焦在"用户从登录到完成一个完整业务流程"的串联验证。

### 5.4 设计输出

输出到 `design/07-tdd/integration/{client-slug}-tdd-design.md`：

```markdown
# TDD 设计（Integration）：{客户端名}

> 基于 API TDD v{version} | Page Mock TDD v{version} | 业务工作流 v{version}
> 日期：{YYYY-MM-DD} | Stage: Integration TDD

## 测试范围

| 用户旅程 | 涉及页面 | 涉及 API | 关键验证点 |
|---------|---------|---------|-----------|
| 设备注册→上线→控制 | 设备列表→详情→控制台 | POST register→POST connect→POST control | 设备状态流转、操作反馈 |
| 用户登录→权限页面访问 | 登录→仪表盘→管理页 | POST login→GET /me→GET devices | 权限拦截、数据隔离 |
| ... | ... | ... | ... |

## 端到端测试用例

### TC-I001: 设备全生命周期旅程
- **类型**: 用户旅程
- **涉及 Stage 1 测试**: TC-001, TC-005, TC-012
- **涉及 Stage 2 测试**: TC-M001, TC-M005
- **操作序列**:
  1. 打开设备列表页 → 验证列表加载成功
  2. 点击"新增设备"→ 填写表单 → 提交 → 验证设备出现在列表
  3. 点击设备进入详情 → 验证详情数据与创建时一致
  4. 执行控制操作 → 验证设备状态更新
- **断言清单**:
  - ✅ 列表中新增设备可见
  - ✅ 详情页数据完整
  - ✅ 控制操作后状态正确更新

### TC-I002: ...
```

### 5.5 测试代码输出

代码目录：`tests/integration/{client-slug}/`

```
tests/integration/
├── conftest.py               ← 后端启动 fixture、数据库准备
├── {client-slug}/
│   ├── setup.ts               ← Playwright config、base URL
│   ├── journeys/
│   │   ├── test_device_lifecycle.spec.ts
│   │   ├── test_user_auth_flow.spec.ts
│   │   └── ...
│   └── helpers/
│       ├── api-helpers.ts      ← 辅助请求（如 setup 数据）
│       └── page-objects/       ← Page Object 模式（可选）
```

### 5.6 运行命令

Stage 3 的执行命令（由 `tdd-execute(integration)` 执行）——**以 `tdd-execute` §5.2 命令表为准**：

| 工具 | 示例命令（详见 tdd-execute §5.2） |
|------|----------------------------------|
| Playwright | `npx playwright test tests/integration/{client-slug}/ --config=playwright.config.ts` |
| Cypress | `npx cypress run --spec 'tests/integration/{client-slug}/**/*'` |

**前置步骤**（tdd-execute 自动处理）：
1. 启动后端服务（如 `PYTHONPATH=src python -m uvicorn server.main:app --port 8000 &`）
2. 启动前端服务（如 `cd src/{client-slug} && npx vite --port 5173 &`）
3. 等待两者就绪
4. 运行集成测试
5. 清理：停止后端和前端

---

## §6 一致性检查模式

本模式检查 TDD 测试是否完整覆盖了设计文档中定义的端点/页面/旅程，以及测试代码是否与 TDD 设计文档一致。
根据阶段不同，检查的输入和维度有差异。

### 6.1 触发场景

| 场景 | 说明 |
|------|------|
| **设计变更后** | API 设计 / 页面设计变更后，检查 TDD 测试是否同步更新 |
| **代码实现后** | 实现完成后，检查测试是否覆盖了所有必要场景 |
| **常规复查** | review skill 在 TDD 闭环一致性维度中委托调用 |

### 6.2 按阶段的输入规格

| 阶段 | 设计文档来源 | TDD 设计文档 | 测试代码 |
|------|------------|-------------|---------|
| API TDD | `design/04-platform-api/data/rest/{slug}.js` | `design/07-tdd/api/{slug}-tdd-design.md` | `tests/api/{slug}/` |
| Page Mock | `design/06-{client-slug}/data/tree.js` | `design/07-tdd/page-mock/{client-slug}-tdd-design.md` | `tests/page-mock/{client-slug}/` |
| Mini Program | `design/06-{client-slug}/data/tree.js` | `design/07-tdd/miniprogram/{client-slug}-tdd-design.md` | `tests/miniprogram/{client-slug}/` |
| Integration | `design/02-business-workflow/data/{slug}.js` | `design/07-tdd/integration/{client-slug}-tdd-design.md` | `tests/integration/{client-slug}/` |

### 6.3 检查步骤

1. **设计→代码用例覆盖检查**：TDD 设计文档中的每个 TC-XXX，对照测试代码中的测试方法，标记设计有但代码缺失的用例
2. **端点/页面覆盖检查**（按阶段不同）：
   - API TDD：API 设计文档中的每个端点，对照测试代码中测试的方法和路径
   - Page Mock：tree.js 中的每个功能组件，对照测试代码中有无覆盖
   - Mini Program：tree.js 中的每个功能组件，对照测试设计中的用例覆盖（通过 test-plan.md）
   - Integration：工作流中的每个关键旅程，对照测试代码中有无覆盖
3. **断言一致性检查**：TDD 设计文档中每个 TC 的断言清单，对照测试代码中的断言语句
4. **fixture 一致性检查**：TDD 设计文档中声明的测试数据/fixture（初始化数据、mock 返回、前置状态），对照测试代码中实际构造的 fixture——标记设计声明了但代码未构造、或代码构造了但设计未声明的数据
5. **编译/语法通过检查**：确认测试代码可编译/可解析
6. **追溯完整性检查**：每个测试用例是否有正向/反向追溯链标注

### 6.4 输出格式

> 输出格式遵循共享规范 `_shared/consistency-check-format.md`：`summary` 字段按 §1，`type` 必须来自 §2 注册表（本 skill 的枚举已在 §2 登记），`source` 用 §3 的 `tdd-to-code`。

```json
{
  "summary": {
    "end_slug": "{domain|client-slug}",
    "total_scanned": 0,
    "total_issues": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "issues": [
    {
      "severity": "high | medium | low",
      "type": "missing_endpoint_test | missing_component_test | missing_journey_test | assertion_mismatch | fixture_mismatch | compile_error | architecture_contract_missing | untraced_tc | trace_chain_broken | orphan_tc",
      "source": "tdd-to-code",
      "ref_path": "{上游 TDD 设计资产定位：文件 + 节点/行}",
      "detail": "...",
      "suggestion": "..."
    }
  ]
}
```

---

## §7 与流水线其他步骤的关系

| 步骤 | Stage 1 (API) | Stage 2 (Page Mock) | Stage 2b (Mini Program) | Stage 3 (Integration) |
|------|:---:|:---:|:---:|:---:|
| §8.1 业务工作流 | 辅助输入 | — | — | 主要输入 |
| §8.2 ER 设计 | 主要输入 | — | — | — |
| §8.3 API 设计 | **主要输入** | 辅助输入（Mock 形状） | 辅助输入（Mock 形状） | — |
| §8.3b 后端架构设计 | 架构承诺输入（L2+） | — | — | — |
| §8.4 页面设计 | — | **主要输入** | **主要输入** | 辅助输入 |
| §8.6 API 实现 | 验证对象 | — | — | 验证对象 |
| §8.7 前端实现 | — | 验证对象 | 验证对象 | 验证对象 |
| §8.8 tdd-execute | **执行 Stage 1** | **执行 Stage 2** | **执行 Stage 2b** | **执行 Stage 3** |
| §9 复查门控 | 引用执行报告 | 引用执行报告 | 引用执行报告 | 引用执行报告 |

> **关键关系：**
> - Stage 1 和 Stage 2/2b **可并行**——各自只需各自的设计完成，不相互阻塞
> - Stage 2（Web）和 Stage 2b（Mini Program）**彼此独立可并行**——依据项目端类型按需执行
> - Stage 3 **必须串行**——只在 Stage 1 +（Stage 2 或 Stage 2b，视端类型）全部通过且两端代码实现后才启动
> - tdd-build 是设计文档的**可执行翻译**——把设计契约转化为可运行的验证代码
> - 测试代码编译通过 ≠ 测试全部通过。测试的**实际执行**由 tdd-execute 负责

---

## §8 完成检查清单

### 通用检查（所有阶段）

| 检查项 | 要求 |
|--------|------|
| TDD 设计文档已输出 | 在对应 `design/07-tdd/{stage}/` 目录下 |
| 测试代码已编写 | 在对应 `tests/{stage}/` 目录下 |
| 测试代码纯契约依赖 | 不依赖实现细节 |
| 数据库隔离（DI 拦截） | 生产入口无测试分支；测试基础设施通过 DI 容器替换 |
| 反向追溯验证 | 抽 1 条用户旅程从终点反推，确认链不断裂 |
| 正向追溯验证 | 抽 1 条用户旅程从原始需求正推，确认无遗漏 |

### Stage 1 专项（API TDD）

| 检查项 | 要求 |
|--------|------|
| API 端点覆盖 | 每个端点至少 1 个用例 |
| 参数校验覆盖 | 每个必填参数有缺失/非法值用例 |
| 状态转换覆盖 | 工作流中每个状态转换有对应用例 |
| 错误场景覆盖 | API 文档中每个错误码有对应用例 |
| 权限覆盖 | 每个权限等级有越权访问用例 |
| 架构承诺覆盖（L2+） | 幂等/并发/缓存命中失效/外部依赖失败/事务回滚/事件发布/健康检查/审计日志/超时降级 |

### Stage 2 专项（Page Mock TDD）

| 检查项 | 要求 |
|--------|------|
| 页面组件覆盖 | tree.js 中的每个功能组件有至少 1 个用例 |
| 路由跳转覆盖 | processes.js 中的每个跳转路径有至少 1 个用例 |
| 表单覆盖率 | 每个表单的提交/校验/错误反馈有覆盖 |
| 权限 UI 覆盖 | 权限控制点的可见/隐藏/禁用状态有覆盖 |
| Mock 数据真实性 | Mock 响应结构与 API 设计文档一致（字段名、类型、状态码） |

### Stage 2b 专项（Mini Program TDD）

| 检查项 | 要求 |
|--------|------|
| 页面组件覆盖 | tree.js 中的每个功能组件有至少 1 个用例 |
| 路由跳转覆盖 | processes.js 中的每个跳转路径有至少 1 个用例 |
| wx API Mock 覆盖 | 页面涉及的 wx API 有对应的 Mock 配置 |
| 截图证据 | 每个用例有截图证据留存（`tests/miniprogram/{slug}/evidence/`） |
| wechatide 环境可用 | `check_wechatide_status` 返回 `openid` |
| 项目可打开 | `open_project_window` 成功 |

### Stage 3 专项（Integration TDD）

| 检查项 | 要求 |
|--------|------|
| 关键旅程覆盖 | 域注册表中的每个域至少 1 条核心旅程有 E2E 用例 |
| 跨页面数据链验证 | 每条旅程的页面间数据传递完整 |
| 外部服务隔离 | 仅外部服务 Mock，内部服务全部真实 |
| Stage 1/2 追溯 | 每个 E2E 用例标注下游覆盖的 Stage 1 和 Stage 2 测试编号 |
