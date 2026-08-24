---
name: backend-architecture-design
version: 1.0.0
description: |
  后端架构与服务体系设计——在 API 设计之后、代码实现之前，将架构模式、分层策略、
  模块边界、服务拓扑、缓存体系、可靠性策略、部署结构、可观测性等后端架构决策
  固化为结构化设计资产。提供创建模式（内含复杂度门控）、一致性检查模式、审计模式三种执行方式。
triggers:
  - 后端架构设计
  - 架构审计
  - 全量分析
  - 架构设计
  - 服务体系设计
  - 后端架构
  - 服务架构
  - 系统架构
  - backend architecture
  - 架构模式
  - 分层设计
  - 模块边界
  - 服务拓扑
  - 缓存策略
  - 可靠性设计
  - 部署架构
  - 无状态服务
  - 灰度发布
  - 故障转移
  - 服务治理
  - API 网关
  - 微服务架构
lineage:
  origin: arb-hub
  sources:
    boxing:        {sha256: 90fc6136590f}
    zy-iot-ai:     {sha256: ea56aba65a83}
    zy-ai-consult: {sha256: c0c1c935c367}
---

# backend-architecture-design — 后端架构与服务体系设计

## 技能说明

- **所属流水线：** `development-standard` §8.3b「后端架构设计」（新增步骤，位于 API 设计之后、TDD 设计之前）
- **定位：** 在代码实现之前，将后端架构决策固化为结构化设计资产。`api-code-gen` 以此为实现约束，`review` 以此做架构合规检查，`tdd-build` 以此设计架构承诺测试。
- **输入源：**
  - `design/02-business-workflow/data/{slug}.js`（业务工作流——提供复杂度判断依据）
  - `design/03-entity-relationship/data/{slug}.js`（ER 数据——提供数据规模和关系复杂度）
  - `design/04-platform-api/data/{slug}.js`（API 设计——提供端点清单、缓存/幂等/频控标注）
  - `design/01-raw-input/`（原始需求——提供非功能需求、部署目标）
  - `design/domain-registry.js`（域定义与编号，模块边界划分的依据）
  - 项目 `AGENTS.md`（技术栈与运行环境）
- **输出目录：** `design/05-backend-architecture/data/`
- **适用条件：** 复杂度 ≥ L2 时必须执行；L1 项目可跳过

---

## 0. 核心原则

### 0.1 架构决策必须在代码之前

复杂后端的架构决策（分层、模块边界、缓存拓扑、可靠性策略）如果留到编码时临场发挥，
必然导致不一致、遗漏和后期返工。**架构设计是 api-code-gen 的前置输入，不是可选附录。**

### 0.2 按复杂度裁剪，不过度设计

| 复杂度 | 架构设计深度 |
|--------|------------|
| L1 简单 CRUD | 跳过本 skill，直接进入 api-code-gen |
| L2 复杂单体 | 必填：分层策略、模块边界、缓存策略、幂等策略 |
| L3 模块化单体 | L2 + 服务拓扑、可靠性策略、可观测性 |
| L4 分布式服务 | L3 + 服务治理、网关、部署拓扑、灰度发布 |
| L5 大规模平台 | L4 + 多区域、SLO、容灾、运维规范 |

### 0.3 设计即约束，不是建议

架构设计资产不是"参考文档"，而是 api-code-gen 和 review 的输入约束。
api-code-gen 必须按架构设计生成代码骨架；review 必须检查代码是否遵守架构承诺。

### 0.4 域注册表同步

开工前先读 `design/domain-registry.js`；改领域边界/模块划分前必须先写注册表。

---

## 1. 复杂度门控（前置步骤）

> **铁律：** 在进入架构设计之前，必须先通过复杂度问卷确定项目等级。
> L1 项目直接跳过本 skill；L2+ 项目必须完成对应深度的架构设计。

### 1.1 复杂度问卷

对每个领域或整个项目，回答以下问题：

| # | 问题 | 判断阈值 |
|---|------|---------|
| Q1 | 峰值 QPS 预估？ | > 100 → L3+ |
| Q2 | 数据量级（核心表行数）？ | > 1000 万 → L3+ |
| Q3 | 并发用户数？ | > 500 → L3+ |
| Q4 | 是否需要水平扩展？ | 是 → L4+ |
| Q5 | 是否需要多服务独立部署？ | 是 → L4+ |
| Q6 | 是否有支付/票务/财务/库存等强一致场景？ | 是 → L3+ |
| Q7 | 是否需要灰度发布、回滚？ | 是 → L4+ |
| Q8 | 是否有多租户、跨区域部署？ | 是 → L5 |
| Q9 | 是否有合规审计要求（如金融级日志）？ | 是 → L4+ |
| Q10 | 是否存在外部系统依赖（支付网关、消息推送）？ | 是 → L3+ |
| Q11 | 是否需要异步任务、消息队列、事件流？ | 是 → L3+ |
| Q12 | 业务状态机数量？ | > 5 个独立状态机 → L2+ |
| Q13 | 领域数量（来自 domain-registry）？ | > 3 个领域 → L2+ |
| Q14 | 权限角色数量？ | > 5 个角色 → L2+ |

### 1.2 等级判定与影响

| 等级 | 触发条件 | 典型场景 |
|------|---------|---------|
| **L1 简单 CRUD** | Q12-Q14 全否，Q1-Q11 全否 | 内部工具、简单配置管理、单表查询录入 |
| **L2 复杂单体** | Q12 或 Q13 或 Q14 为真 | 多状态机+多角色+多领域，如拳击赛事平台 |
| **L3 模块化单体** | Q1/Q2/Q3/Q6/Q10/Q11 任一为真 | 电商平台、预约系统、有支付/库存/外部服务 |
| **L4 分布式服务** | Q4/Q5/Q7/Q9 任一为真 | 金融平台、大型 SaaS、需独立扩缩容和灰度 |
| **L5 大规模平台** | Q8 为真 | 多租户企业级 SaaS、跨区域部署、99.9%+ SLA |

> **判定规则：** 取满足条件的最高等级。L1 项目不执行本 skill。

**复杂度等级对实际执行的影响：**

| 影响维度 | L1 | L2 | L3 | L4 | L5 |
|---------|----|----|----|----|-----|
| **架构设计步骤** | 跳过 | 执行 §8.3b | 执行 §8.3b | 执行 §8.3b | 执行 §8.3b |
| **必填架构资产** | 0 个 | 5 个（topology/boundaries/layering/caching/security） | 9 个（L2 + resilience/data-consistency/observability/event-contracts） | 10 个（L3 + deployment-profile） | 10 个（全部） |
| **分层约束** | 约定俗成 | 写入 `layering-strategy.js`，api-code-gen 生成时检查 | 同 L2 + 架构合规检查主动拦截违规 | 同 L3 + 跨服务分层规则 | 同 L4 |
| **缓存设计** | 无要求 | Redis/HTTP 缓存拓扑必须定义 | L2 + 防击穿/穿透策略必填 | L3 + 分布式缓存一致性 | L4 + 跨区域缓存 |
| **可靠性** | 无要求 | 仅幂等性必填 | 完整：超时/重试/熔断/降级/限流 | L3 + 服务网格集成 | L4 + SLO 驱动 |
| **数据一致性** | 本地事务 | 本地事务 | Outbox 模式必填 | Saga + 补偿事务 | L4 + 跨区域 |
| **可观测性** | 基础日志 | 结构化日志 + 健康检查 | L2 + 指标 + 追踪 | L3 + 审计日志 | L4 + SLO Dashboard |
| **安全** | 基础认证 | 权限模型 + 敏感数据脱敏 | L2 + 加密 | L3 + API 网关鉴权 | L4 + 租户隔离 |
| **部署** | 单实例 | 单实例 | 单实例（模块化单体） | 多服务拓扑 + 网关 + 服务注册 + 灰度 | 多区域 |
| **TDD 范围** | 对外 API 测试 | 对外 API + 架构承诺测试 | 同 L2 | L3 + 服务间契约测试 | L4 + 混沌工程 |
| **Review** | 跳过 D11（架构合规） | 全 13 维度 | 全 13 维度 | 全 13 维度 | 全 13 维度 |
| **代码生成规则** | 基础 CRUD | 强制分层架构 | L2 + 模块边界强制 | L3 + 服务客户端生成 | L4 + 多租户 |

---

## 2. 完整执行流程（创建模式）

```
复杂度判定（§1）
    │
    ├── L1 → 终止，提示"当前复杂度不需要后端架构设计"
    │
    └── L2+ → 继续
            │
            ├── 步骤 1：输入采集
            ├── 步骤 2：架构模式选择
            ├── 步骤 3：横向分层设计
            ├── 步骤 4：纵向分域与模块边界
            ├── 步骤 5：横切关注点设计（缓存/可靠性/可观测性/安全）
            ├── 步骤 6：部署与运维设计（L4+）
            └── 步骤 7：输出结构化数据
```

### 步骤 1：输入采集

读取以下输入并理解：

| 输入 | 提取内容 |
|------|---------|
| domain-registry.js | 域定义与编号（前置读取，见 §0.4） |
| 业务工作流 | 状态机数量、业务规则复杂度、角色数量、异步操作需求 |
| ER 数据 | 实体数量、跨域关系、数据规模预估、强一致场景 |
| API 设计 | 端点总数、写操作比例、已有幂等/缓存/频控标注、外部回调端点 |
| 原始需求 | 非功能需求（性能/可用性/安全）、部署目标、合规要求 |
| AGENTS.md | 技术栈约束、运行环境 |

> ⚠️ **追溯前置检查：** 在开始架构设计之前，验证上游资产是否具备追溯字段：
> - **API 设计：** 端点是否标注 `consumes` / `produces` 字段
> - **ER 数据：** 实体字段是否标注 `source` / `consumers` 字段
> - **工作流：** 步骤是否标注 `inputs` / `outputs` / `consumers` 字段
> 存在未标注追溯字段的资产时，先标记为 ⚠️（缺失追溯）并在架构设计决策中记录，不阻塞设计流程但需明确风险。
> （R-007 定案：上述追溯字段均已在 development-standard §2.6「正向定义」数据协议表中定义——API 端点 `consumes`/`produces`、ER 字段 `source`/`consumers`、工作流节点 `inputs`/`outputs`/`consumers`，引用成立，2026-08-23）

### 步骤 2：架构模式选择

根据复杂度等级和业务特征，选择架构模式：

| 模式 | 适用等级 | 特征 |
|------|---------|------|
| **单体** | L1-L2 | 单一部署单元，进程内分层 |
| **模块化单体** | L2-L3 | 单一部署单元，模块边界清晰，依赖方向约束 |
| **微服务** | L4-L5 | 独立部署单元，服务间通过 API/消息通信 |
| **事件驱动** | L3-L5 | 服务间通过事件总线解耦，适用于异步流程多的场景 |
| **CQRS** | L3-L5 | 读写分离，适用于读写负载差异大的场景 |

**决策输出到 `system-topology.js`：**

```js
{
  architectureStyle: "modular-monolith",  // monolithic | modular-monolith | microservices | event-driven-modular-monolith
  // event-driven / cqrs 是修饰维度，与主风格组合（如 event-driven-modular-monolith、microservices + cqrs）；
  // 组合语义需在 system-topology.js 中显式声明，避免旧词汇（event-driven / cqrs 单独出现）导致生成器无法路由
  rationale: "多领域复杂业务规则但团队单人开发，模块化单体平衡复杂性与运维成本"
}
```

### 步骤 3：横向分层设计

定义代码分层及每层的职责边界：

| 层 | 职责 | 依赖方向 |
|----|------|---------|
| **Controller / API Layer** | HTTP 协议适配：参数绑定、响应序列化、路由注册。**不写业务逻辑** | → Application Service |
| **Application Service** | 用例编排：调度 Domain Service + Infrastructure，管理事务边界 | → Domain Service / Infrastructure 接口 |
| **Domain Service** | 核心业务规则：状态机转换、业务校验、领域计算 | → 无外部依赖（纯函数） |
| **Repository / Data Access** | 数据持久化：实现 Domain 定义的接口，封装 EF Core / ORM 细节 | 实现 Domain 接口 |
| **Infrastructure** | 技术能力：缓存、消息队列、文件存储、外部 API 客户端、后台任务 | 实现 Domain/Application 定义的接口 |
| **Background Job** | 异步任务：Outbox 重试、定时任务、事件处理 | → Application Service / Infrastructure |

**分层约束（硬规则，写入 `module-boundaries.js`）：**

- Controller 禁止直接调用 Repository
- Controller 禁止包含业务逻辑（if/switch 判断业务状态）
- Domain Service 禁止依赖 Infrastructure 具体实现
- Repository 禁止跨域直接查表（必须通过所属域的 Application Service）
- Infrastructure 只通过接口被上层调用

### 步骤 4：纵向分域与模块边界

对每个业务域，定义模块边界：

```js
{
  module: "Ticketing",
  ownsEntities: ["TicketOrder", "AdmissionPass", "RefundRequest"],
  exposes: ["ITicketingApplicationService"],
  forbiddenDependencies: ["Finance.Infrastructure", "Competition.DomainService"],
  crossDomainCalls: [
    { target: "Competition", via: "ICompetitionApplicationService", reason: "验证赛程状态" }
  ],
  databaseOwnership: "ticketing",  // 数据库名 / schema 名
  independentDeployable: false     // L4+ 时为 true
}
```

**模块边界规则：**
- 每个域拥有自己的实体和数据库表
- 跨域访问只能通过 Application Service 接口
- 禁止跨域共享数据库（微服务模式下）
- 禁止循环依赖

### 步骤 5：横切关注点设计

#### 5.1 缓存体系

```js
caching: [
  {
    resource: "competition-public-list",
    layer: "redis+http",           // redis | memory | http | cdn
    ttl: "5m",
    key: "cache:competition:list:{query_hash}",
    invalidation: "competition-published-or-updated",
    antiBreakdown: "mutex-lock",   // 防击穿策略
    antiPenetration: "bloom-filter" // 防穿透策略
  }
]
```

#### 5.2 可靠性策略

```js
resilience: {
  timeout: { default: "30s", external: "5s" },
  retry: {
    strategy: "external-only",     // none | external-only | all
    maxAttempts: 3,
    backoff: "exponential"
  },
  circuitBreaker: {
    targets: ["payment-provider", "sms-gateway"],
    threshold: "5-failures-in-60s",
    recoveryTime: "30s"
  },
  idempotency: {
    requiredEndpoints: ["POST /orders", "POST /payments", "POST /refunds"],
    keyHeader: "Idempotency-Key",
    cacheSuccess: "24h",
    cacheFailure: "5min"
  },
  fallback: {
    "payment-provider": "return-pending-status-retry-later",
    "sms-gateway": "queue-failed-notification"
  },
  rateLimit: {
    global: { perIp: "1000/min" },
    auth: { perIp: "10/min" },
    write: { perUser: "60/min" },
    sensitive: { perUser: "5/min" }
  }
}
```

#### 5.3 数据一致性

```js
dataConsistency: {
  strategy: "outbox",              // local-transaction | outbox | saga | eventual
  outbox: {
    storage: "database-table",
    publisher: "background-service",
    retryLimit: 5,
    deadLetterQueue: "outbox-failed"
  },
  compensation: {
    enabled: true,
    strategy: "saga-compensating-transactions"
  }
}
```

#### 5.4 可观测性

```js
observability: {
  logging: {
    level: "Information",
    structured: true,
    correlationId: "X-Correlation-Id header → Serilog Enrich",
    sensitiveFieldMasking: ["password", "idNumber", "phone"]
  },
  metrics: {
    provider: "built-in",          // built-in | prometheus | app-insights
    endpoints: ["/metrics"],
    customMetrics: ["order-created-count", "payment-latency-ms"]
  },
  tracing: {
    enabled: true,
    header: "X-Trace-Id",
    sampling: "10%"
  },
  healthCheck: {
    endpoint: "/api/v1/health",
    checks: ["database", "redis", "external-services"],
    readinessProbe: "/api/v1/health/ready"
  },
  auditLog: {
    enabled: true,
    events: ["order-created", "payment-initiated", "refund-approved", "user-suspended"],
    retention: "365d"
  }
}
```

#### 5.5 安全边界

```js
security: {
  auth: {
    scheme: "JWT Bearer",
    tokenLifetime: "2h",
    refreshToken: "30d rotating"
  },
  authorization: {
    model: "permission-based",     // role-based | permission-based
    enforcement: "attribute-on-controller"
  },
  tenantIsolation: {
    enabled: false,                // L5 多租户场景
    strategy: "discriminator-column"
  },
  sensitiveData: {
    encryption: ["idNumber", "bankAccount"],
    hashing: ["password"],
    masking: ["phone", "email"]
  },
  exposure: {
    internalOnlyEndpoints: ["/api/v1/admin/*"],
    publicEndpoints: ["/api/v1/competitions", "/api/v1/health"]
  }
}
```

### 步骤 6：部署与运维设计（L4+）

```js
deployment: {
  serviceTopology: [
    {
      service: "BoxingPlatform.Api",
      type: "stateless-api",
      instances: 2,
      databaseOwnership: ["ticketing", "competition"],
      dependencies: ["Redis", "ObjectStorage"],
      healthCheck: "/api/v1/health"
    }
  ],
  apiGateway: {
    enabled: true,
    routing: "path-based",
    auth: "jwt-validation-at-gateway",
    rateLimit: "gateway-level"
  },
  serviceRegistry: {
    enabled: true,
    provider: "consul",             // consul | k8s-service | eureka
    healthCheckInterval: "10s"
  },
  grayRelease: {
    enabled: true,
    strategy: "header-based",      // header-based | cookie-based | weight-based
    header: "X-Release-Version",
    rollback: "manual-trigger"
  },
  configManagement: {
    strategy: "environment-variables",
    secrets: "external-secrets-manager"
  },
  statelessness: {
    sessionStorage: "redis",
    noLocalFileState: true,
    noInMemorySession: true
  }
}
```

### 步骤 7：输出结构化数据

输出到 `design/05-backend-architecture/data/`：

| 文件 | 内容 | 适用等级 |
|------|------|---------|
| `system-topology.js` | 架构模式、复杂度等级 | L2+ |
| `module-boundaries.js` | 模块边界、依赖方向、跨域调用 | L2+ |
| `layering-strategy.js` | 分层定义、层间约束 | L2+ |
| `caching-strategy.js` | 缓存拓扑、TTL、失效、防击穿/穿透 | L2+ |
| `resilience-policy.js` | 超时、重试、熔断、降级、幂等、频控 | L3+ |
| `data-consistency.js` | 一致性策略、Outbox、Saga、补偿 | L3+ |
| `observability-policy.js` | 日志、指标、追踪、健康检查、审计 | L3+ |
| `security-policy.js` | 认证、授权、租户隔离、敏感数据 | L2+ |
| `deployment-profile.js` | 服务拓扑、网关、注册、灰度、配置 | L4+ |
| `event-contracts.js` | 跨服务/跨模块事件定义（事件名、携带字段、发布者、订阅者） | L3+ |
| `design-decisions.js` | 决策账本——每次调整（含会话中自然语言调整）先记账后改资产（§4.2）；"有意决策"查证与审计对账的唯一依据 | L2+ |
| `arch-contract.js` | 架构契约谓词——机械执行层的声明源，格式见 `_shared/arch-contract-spec.md` | L2+ |
| `audit-dossier.js` | 审计档案——派生数据，由审计模式（§3b）整体再生成，禁止手编 | L2+（审计时生成） |

**_trace 追溯块（每个架构数据文件顶部必须包含）：_**

```js
_trace: {
  consumes: [
    "workflow:boxing-tournament-workflow",   // 消费的工作流资产
    "er:boxing-competition-er",              // 消费的 ER 资产
    "api:boxing-platform-api"                // 消费的 API 设计资产
  ],
  produces: [
    "constraint:layering",                   // 产出的分层约束
    "constraint:caching",                    // 产出的缓存策略约束
    "constraint:resilience",                 // 产出的可靠性约束
    "constraint:data-consistency",           // 产出的数据一致性约束
    "constraint:observability",              // 产出的可观测性约束
    "constraint:security",                   // 产出的安全约束
    "constraint:module-boundary",            // 产出的模块边界约束
    "constraint:deployment"                  // 产出的部署约束（L4+）
  ]
}
```

> `consumes` 声明本架构设计消费了哪些上游资产（用于追溯链上游验证）；`produces` 声明本架构设计产出了哪些约束类型（用于下游资产反向追溯）。`produces` 枚举值必须来自本 skill 已定义的约束类别。

**基础设施（随 skill 首次使用自动就绪）：**

| 文件 | 职责 |
|------|------|
| `design/05-backend-architecture/architecture-viewer.html` | HTML 查看器——工具栏 + 左侧导航 + 右侧详情，双击打开即可查看（file:// 协议） |
| `design/05-backend-architecture/data/loader.js` | 数据加载器——加载所有架构数据 JS 文件 |

> **模板文件位于：** `templates/`（与本 SKILL.md 同目录分发）。
> 首次使用时，从 templates 复制 `architecture-viewer.html` 和 `data/loader.js` 到项目 `design/05-backend-architecture/` 目录。
> `data/system-topology.js`（以及 `data/deployment-profile.js` 等）在模板目录 `templates/data/` 提供最小示例，供新项目参考。

**数据文件格式：** 挂载到 `window.ARCH_DATA` 命名空间（如 `window.ARCH_DATA["system-topology"] = {...}`），由 `architecture-viewer.html` 加载渲染。与 `workflow-viewer.html` / `er-viewer.html` / `api-viewer.html` 遵循相同模式。双击打开即可，无需 HTTP 服务器。

---

## 3. 一致性检查模式

校验架构设计资产与 API 设计、ER 数据、代码实现之间的一致性。

### 3.1 触发场景

| 场景 | 说明 |
|------|------|
| **架构设计变更后** | 修改架构设计后，检查下游资产是否同步 |
| **API 设计变更后** | API 新增端点后，检查架构策略是否覆盖 |
| **代码实现后** | 检查代码是否遵守架构约束 |
| **常规复查** | review skill 在 D11 维度委托调用 |

### 3.2 检查步骤

1. **架构 → API 一致性：** 架构中的幂等端点列表 ↔ API 中的幂等标注；架构中的限流策略 ↔ API 中的频控标注；架构中的缓存策略 ↔ API 中的缓存标注
2. **架构 → ER 一致性：** 模块数据归属 ↔ ER 跨域关系；一致性策略 ↔ ER 中的强一致实体
3. **架构 → 代码一致性：** 分层约束是否在代码中遵守；模块边界是否被突破；缓存实现是否匹配策略；幂等实现是否覆盖全部指定端点；健康检查端点是否存在；审计日志是否接入
4. **架构 → API 追溯一致性：** 架构策略覆盖的端点是否在 API 设计中真实存在，且对应端点的 `produces` 字段已标注（确保架构约束可追溯到 API 设计源头）
5. **架构 → ER 追溯一致性：** 缓存策略、一致性策略引用的实体字段在 ER 数据中是否有 `source` / `consumers` 标注（确保架构决策可追溯到数据模型源头）

### 3.3 输出格式

> 输出格式遵循共享规范：`_shared/consistency-check-format.md`（与本 skill 同目录分发的 `_shared/` 子目录）。
> 本 skill 的 `type` 枚举见共享规范的注册表（`backend-architecture-design` 行）。
> 本 skill 的 `source` 枚举：`architecture-to-api`, `architecture-to-code`。

```json
{
  "summary": {
    "total_issues": 0,
    "architecture_api_issues": 0,
    "architecture_code_issues": 0,
    "complexity_level": "L3"
  },
  "issues": [
    {
      "severity": "high",
      "type": "layer_violation",
      "source": "architecture-to-code",
      "detail": "...",
      "suggestion": "..."
    }
  ]
}
```

---

## 3b. 审计模式（人的全量分析入口）

> **定位：** 架构保障的双通道之一。机器通道 = 架构契约（`_shared/arch-contract-spec.md`，
> 机械、无情、跑门禁）；**人审通道 = 本模式**——把全部分层/分域/横切/决策/债务整合成
> 一份可在 architecture-viewer 中通读的审计视图，供人做全量分析。两条通道读**同一份
> 数据资产**，人审内容与机器执行内容永不脱节。
>
> **形态铁律：** 审计产物遵循 `_shared/document-asset-format.md`——审计档案是**派生数据
> 文件**（`data/audit-dossier.js`）+ architecture-viewer 新增视图（「审计总览」「决策账本」），
> **不是独立 Markdown 长文**。机器运行记录（契约运行报告）保持 JSON 快照（`design/review/arch-contract/`），
> 由审计视图内嵌摘要。

### 3b.1 触发方式

- "使用 backend-architecture-design 审计 {domain-slug} / 全项目架构"
- "架构全量分析" / "给我整合一份架构全景"
- 大版本里程碑前、review 全量复查时联动

### 3b.2 审计流程（五步）

```
① 采集 —— 读取全部架构资产（topology/boundaries/layering/横切策略）
          + design-decisions.js（决策账本）+ arch-contract.js 及最近运行报告
② 派生 —— 机械可算部分由数据直接计算：分层×分域矩阵、横切覆盖表、追溯地图（_trace
          正向/反向 + 断链清单）、债务清单、对账结果（§3b.4）、契约运行摘要
③ 叙述补充 —— AI 生成最小叙述：执行摘要、人审检查单（analystChecklist，按架构理念
          逐条生成引导性问题并链接到数据锚点）；analystNotes 显式标注 author: "AI"
④ 渲染 —— 写入 data/audit-dossier.js（带 generatedFrom 版本戳）→ viewer 审计视图
⑤ 人审 —— 用户在 viewer 内做全量分析；批注/结论回流 data/audit-annotations.js
          （第一手输入，手写合法，再生成不吞并）；必要时触发 §4 同步螺旋
```

### 3b.3 审计档案数据骨架（audit-dossier.js）

```js
window.ARCH_DATA["audit-dossier"] = (function () {
  var _trace = { consumes: ["architecture:*", "decisions:design-decisions", "contract:arch-contract"],
                 produces: ["report:audit-dossier"] };
  return {
    _trace: _trace,
    generatedFrom: { assets: [{ file: "data/layering-strategy.js", version: "v1" }, /*...*/ ],
                     command: "backend-architecture-design 审计模式", generatedAt: "ISO-8601" },
    summary: { architectureStyle, complexityLevel, layerCount, moduleCount,
               decisionCount, activeDebts,
               contractLastRun: { report: "design/review/arch-contract/*.json",
                                  exitCode: 0, violations: 0, warns: 2 } },
    layerXDomain: [ { layer: "…", module: "…", contact: "接触面描述", note: "…" } ],
    crossCuttingCoverage: [ { concern: "caching", covered: ["…"], missing: ["…"] } ],
    traceMap: { forward: ["decision → assets → code/tests"], broken: [ { from: "…", to: "…", reason: "…" } ] },
    reconciliation: { unsyncedDecisions: ["DD-017"], orphanChanges: [ { asset: "…", changelogEntry: "…", guessedReason: "…" } ] },
    debts: [ /* knownDebts + 存量 violations 合并视图 */ ],
    analystChecklist: [ { id: "Q-01", dimension: "渠道中立", question: "新增渠道是否零修改核心层？",
                          whereToLook: "data/module-boundaries.js#channel-access.note" } ],
    analystNotes: [ { id: "N-01", date: "…", author: "AI | human", note: "…" } ]
  };
})();
```

### 3b.4 对账（增量过程的收口）

双向核验决策账本与资产变更：

| 方向 | 检查 | 暴露的问题 |
|------|------|-----------|
| 账本 → 资产 | `synced=false` 的决策清单 | 口头/会话调整已记账但未落盘 |
| 资产 → 账本 | CHANGELOG 条目无对应决策 id（AI 辅助比对，标注 heuristic） | 资产被改过但无决策来源 |

对账结果置顶于审计视图；`unsyncedDecisions` 非空时列入人审检查单第一条。

### 3b.5 人审检查单生成规则

来源三路，逐条生成并链接数据锚点（不复述数据内容，避免双写）：
1. **架构理念**——本项目架构的核心不变量（如"核心层零渠道感知"→ "Q: 新增渠道是否零修改核心层？"）；
2. **reviewLedger**——契约规范 §4.1 登记的语义约束逐条转为人审问题；
3. **谓词盲区**——enforcement 为 heuristic/review 的规则，逐条转为"此约束机器不拦截，需人确认"。

---

## 4. 同步螺旋更新工作流

> **适用场景：** 不创建新架构，而是对已有架构设计进行增量更新。
> 触发源不限于上游变更——代码实现反馈、API 设计调整、原始需求澄清、review 发现问题均可触发。

### 4.1 触发方式

- "使用 backend-architecture-design 更新 {domain-slug} 的架构设计"
- "同步 {domain-slug} 的架构设计与最新代码/API"
- 被 review 或 api-code-gen 发现架构不一致时自动触发

### 4.2 更新流程（遵循同步螺旋 §10.3b）

```
触发更新（任意来源）
    │
    ├── 1. 确定真相源
    │      · 代码实现比架构设计更优 → 代码是真相源
    │      · API 设计新增了端点 → API 设计是真相源
    │      · 用户明确了新的非功能需求 → 原始需求是真相源
    │      写入 design-decisions.js
    │
    ├── 2. 影响分析
    │      真相源的变更影响哪些架构资产？
    │      · API 新增支付端点 → resilience-policy.js 的幂等列表
    │      · ER 新增跨域关系 → module-boundaries.js 的跨域调用路径
    │      · 原始需求补充合规要求 → observability-policy.js 的审计事件
    │
    ├── 3. 增量修改
    │      只改动受影响的架构资产，不动无关资产。
    │      更新受影响资产的版本号。
    │
    ├── 4. 上溯检查
    │      架构的修改是否揭示了上游 API/ER/工作流/原始需求的缺失或过时？
    │      → 如果是，反推上游更新
    │
    ├── 5. 下传检查
    │      架构的修改是否破坏了下游 TDD/代码？
    │      → 如果是，标记受影响的下游资产为 dirty
    │
    └── 6. 收敛与记录
    │      更新 sync-status.js，受影响资产 dirty=false
    │      CHANGELOG 记录本次更新
```

**关键原则：**
- **先记账后改资产**——任何来源的更新（含会话中的自然语言调整）必须先在 `design-decisions.js` 落一条记录（id / 真相源 / 理由 / 影响资产 / synced），再动数据文件。账本 schema：`{id: "DD-NNN", date, trigger, decision, rationale, alternatives, impactAssets[], truthSource, status: draft|applied|superseded, synced}`。对账在审计模式（§3b.4）执行
- **不重做全量设计**——已有架构决策保留，只做增量
- **设计决策日志优先**——不一致可能是过去的**有意决策**，先查 `design-decisions.js` 再判断
- **传播到稳定**——修改可能触发上下游连锁反应，迭代直到无新变更

---

## 5. 与相关技能的关系

| 技能 | 关系 |
|------|------|
| `business-workflow` | 上游——提供状态机和业务规则复杂度判断 |
| `entity-relationship` | 上游——提供数据规模和跨域关系 |
| `api-design` | 上游——提供端点清单和已有策略标注；架构设计完成后，API 设计中的缓存/幂等/频控标注应以架构设计为准 |
| `tdd-build` | 下游——架构承诺（幂等、缓存、熔断、审计）转化为测试用例 |
| `api-code-gen` | 下游——架构设计是代码生成的前置约束，Controller/Service/Infrastructure 骨架必须遵守分层和模块边界 |
| `review` | 调度——review 委托本技能做 D11「后端架构合规」检查 |

---

## 6. 完成检查清单

| 检查项 | 要求 |
|--------|------|
| 复杂度问卷已完成 | 等级已判定，`system-topology.js` 中有 `complexityLevel` |
| 架构模式已选择 | `system-topology.js` 中有 `architectureStyle` + `rationale` |
| 横向分层已定义 | `layering-strategy.js` 中有完整的层定义和约束 |
| 模块边界已定义 | `module-boundaries.js` 中有所有域的模块边界 |
| 缓存策略已完成 | `caching-strategy.js` 中有完整的缓存拓扑 |
| 可靠性策略已完成（L3+） | `resilience-policy.js` 中有超时/重试/熔断/降级/幂等/频控 |
| 数据一致性已定义（L3+） | `data-consistency.js` 中有 Outbox/Saga 策略 |
| 可观测性已定义（L3+） | `observability-policy.js` 中有日志/指标/追踪/健康检查/审计 |
| 安全策略已完成 | `security-policy.js` 中有认证/授权/敏感数据策略 |
| 部署拓扑已完成（L4+） | `deployment-profile.js` 中有服务拓扑/网关/灰度/配置 |
| 上游追溯字段已验证 | API 设计端点有 `consumes`/`produces`，ER 字段有 `source`/`consumers`，工作流步骤有 `inputs`/`outputs`/`consumers` |
| 架构产出已标注 `_trace` 块 | 每个架构数据文件顶部包含 `_trace: { consumes: [...], produces: [...] }` |
| CHANGELOG 已更新 | 架构设计变更已记录 |
| 决策账本已就位（L2+） | `design-decisions.js` 存在，最近变更均有记录，无 `synced=false` 积压 |
| 架构契约已派生（L2+） | `arch-contract.js` 按共享规范生成，规则全部标注 enforcement，语义残留进 reviewLedger |
| 审计档案可再生（L2+） | `audit-dossier.js` 为派生产物，`generatedFrom` 版本戳与当前资产一致 |

---

## 7. 使用方式

1. **完整创建**：对 Claude 说"使用 backend-architecture-design 设计 {project} 的后端架构"
2. **单域架构**：对 Claude 说"使用 backend-architecture-design 设计 {domain-slug} 的后端架构"
3. **一致性检查**：对 Claude 说"使用 backend-architecture-design 检查架构与代码一致性"
4. **复杂度判定**：对 Claude 说"使用 backend-architecture-design 判定 {domain-slug} 的复杂度等级"
5. **架构更新**：对 Claude 说"使用 backend-architecture-design 更新 {domain-slug} 的架构设计"（同步螺旋入口）
6. **被 review 调用**：review skill 在 D11 维度中自动委托本技能执行架构合规检查
7. **架构审计**：对 Claude 说"使用 backend-architecture-design 审计 {domain-slug} / 全项目架构"——再生成审计档案并渲染审计视图（§3b）
