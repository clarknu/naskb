# NASKB Agent 接口设计 — Skill / Tool Calling / MCP 三形态选型与实现方案

> 版本: v0.2
> 状态: **阶段 A（MCP Server stdio）已实施（2026-08-11）**；B~D 待实施
> 最后更新: 2026-08-11
> 依赖: [requirement.md](./requirement.md), [analysis-engine-v2.md](./analysis-engine-v2.md)
> 取代: [mcp-kb-design.md](./mcp-kb-design.md), [mcp-tech-reassessment.md](./mcp-tech-reassessment.md)
> （二者基于 v1 架构：LanceDB + `.kbdes` sidecar + watchdog 文件监控；v2 已改为 `.naskb/` 目录隐藏仓库 + PG 多 NAS 向量库 + 增量幂等 analyze。本设计在 v2 公共层之上重做接口层，旧草案的 JobQueue 思想保留。）

## 实施记录（v0.2 追加）

| 项 | 状态 | 说明 |
|----|------|------|
| 能力注册表 | ✅ | `common/capabilities.py`：14 个 `kb_*`（name/description/kind/scope/job），handler = `NasKbService` 同名方法 |
| JobManager | ✅ | `common/jobs.py`：线程池（默认 1 并发）+ 进度上报 + get/list/shutdown |
| MCP Server（stdio） | ✅ | `naskb/mcp/server.py`：`NasKbService` + `build_mcp`（注册表驱动）+ `run_stdio`；入口 `python -m naskb.mcp.server` 或 `naskb desc serve-mcp` |
| A 组读工具 | ✅ | kb_search / kb_ask / kb_get_doc / kb_fetch_file（复用 KnowledgeCore，引擎自动选择） |
| B 组 job 工具 | ✅ | kb_ingest（analyze_tree 增量幂等 + 进度） / kb_sync_vectors（PG 增量） / kb_index_vectors / kb_job_status / kb_list_jobs |
| C 组整理工具 | ✅ | kb_plan_reorganize（→plan_id 持久化） / kb_preview_reorganize（dry-run 逐条判定） / kb_apply_reorganize（apply_with_housekeeping + mark_applied） |
| D 组状态工具 | ✅ | kb_status（scan + PG 差异） / kb_stats |
| 协议级验收 | ✅ | MCP 官方客户端 stdio 往返：14 工具列表 + search/get_doc/fetch/stats/ingest 全通过（tests/test_mcp_server.py 18 用例 + 冒烟） |
| 边界防护 | ✅ | root 白名单（读写路径统一校验）；Windows 8.3 短路径名展开（`_resolve_compare`）；模型缺失快速回退 BM25（`model_ready`，下载只由 index-vectors 触发） |

**实现偏差（相对 v0.1）**：① 工具实现直接落在 `NasKbService` 方法（注册表存元数据、不存 handler 引用，避免循环依赖）；② 认证/root 白名单的"白名单配置化"（`[server.roots]`）留到阶段 B（当前白名单 = 启动时 `--root` 登记）；③ `kb_fetch_file` 暂返回 base64（≤8MB），临时授权 URL 留待决策点 4。

---

## 1. 背景与目标

NASKB v2 已具备四大核心能力（全部可用、有测试）：

| # | 能力 | 现有入口 |
|---|------|---------|
| 1 | 元数据整理/分析/提取（DeepSeek 分类摘要标签、MiMo 图片音频、MinerU OCR） | `desc analyze` / `analyze-tree`（增量幂等） |
| 2 | 元数据入向量库（本地 bge-small-zh 索引 / PG 多 NAS 独立 schema） | `desc index-vectors` / `sync-vectors` |
| 3 | 检索元数据与原始文档/资源（语义向量 → BM25 降级 → PG；RAG 带来源） | `desc search` / `ask` / `serve` |
| 4 | 新文件归类整理（AI 方案 → 确认执行；移动不删除 + 级联更新 + 清空目录） | `desc plan-reorganize [--apply]` |

当前交付形态只有两种薄封装：**CLI**（`naskb desc ...`）与 **Skill**（`naskb/SKILL.md`），外加实验性 REST（`desc serve` 的 `/api/search` `/api/ask`）。CLI 是"人/Agent 通过终端使用"；对企业级场景——公司内多个 Agent、聊天机器人、自动化流程随时向知识库**存入文档、取出答案、触发整理**——需要标准化的**程序化接口**。

目标：把上述四块能力封装成可被外部 Agent 与 AI 应用统一调用的服务，成为企业 AI 供应链中稳定的一环。

---

## 2. 三种形态不是选择题，是分层

| 维度 | ① Tool Calling（function calling） | ② MCP Server | ③ Skill |
|------|-----------------------------------|--------------|---------|
| 本质 | 函数 JSON Schema + 执行回调 | 标准协议：Tools + Resources + Prompts + 进度通知 | 指令文档（SKILL.md）+ 可选脚本 |
| 谁消费 | 任意 LLM 应用（OpenAI 兼容 API 直连） | MCP 原生客户端：Claude Desktop / Cursor / VS Code / Dify / MaxKB / Coze / LangGraph / 自研 SDK | 支持 skill 形态的 Agent：Reasonix / Copilot / Claude Code 等 |
| 部署 | 无独立服务端，随应用进程 | 常驻服务（stdio 或 streamable HTTP） | 文件分发，无服务端 |
| 结构化能力 | 仅函数 | 工具/资源/提示词/进度/采样，协议内建 | 无（纯文本指令，靠 LLM 遵循） |
| 企业接入成本 | 每个平台手写一遍适配 | **一次实现，处处可用** | 每类 Agent 单独安装，且无契约保证 |
| 擅长 | 代码级直连、自定义编排 | 标准化的共享服务接入 | 教 Agent"怎么用好 KB"（工作流/守则/示例） |

**结论：三者分层、不是互斥。**

- **MCP Server 是主执行接口**——企业共享知识库的标准接入方式，一次实现覆盖所有 MCP 原生客户端与平台；
- **Tool Calling 不单独手写**——由同一套"能力注册表"自动导出 OpenAI 兼容函数 Schema（平台只收 function schema 时用）；
- **Skill 保留并升级为"使用剧本"**——它解决的是"Agent 如何正确使用 KB"（何时检索、何时 RAG、整理前先出方案、移动不删除等守则），与执行接口互补；`SKILL.md` 里同时写明可调用 MCP 服务；
- **REST 保留为轻量兼容面**——现有 `/api/search` `/api/ask` 契约不动，供 MaxKB 等"HTTP 直连型"平台使用。

> 一句话：**一套能力，四个出口（MCP / REST / function schema / CLI+Skill），一个事实源。**

---

## 3. 推荐架构

### 3.1 分层视图

```mermaid
graph TB
    subgraph 消费端
        MC[MCP 原生客户端<br/>Claude Desktop / Cursor / VS Code<br/>Dify / MaxKB / Coze / 自研 SDK]
        FC[任意 LLM 应用<br/>OpenAI 兼容 function calling]
        SK[Skill 原生 Agent<br/>Reasonix / Copilot]
        RST[HTTP 直连平台<br/>MaxKB 扩展包等]
    end

    subgraph NASKB 服务进程（常驻）
        MCPAD[MCP 适配器<br/>stdio / streamable HTTP]
        HAD[HTTP 适配器<br/>REST :8765]
        FAD[Function Schema 适配器<br/>OpenAI tools 格式]

        subgraph 能力注册表
            CAP[common/capabilities.py<br/>Capability 注册表<br/>单一事实源]
        end

        subgraph 公共核心（复用现有 common/）
            CORE[Common Core 服务对象<br/>检索 / RAG / 入库 / 向量同步 / 整理]
            JOB[JobManager<br/>长任务队列 + 进度]
            AUTH[认证与审计<br/>Bearer token + 白名单 + 审计日志]
        end
    end

    subgraph 存储
        NAS[(NAS / 本地目录<br/>.naskb 仓库)]
        PG[(PostgreSQL + pgvector<br/>多 NAS 独立 schema)]
    end

    MC --> MCPAD
    FC --> FAD
    SK -->|直接调用 CLI| CORE
    RST --> HAD
    MCPAD --> CAP
    HAD --> CAP
    FAD --> CAP
    CAP --> CORE
    CORE --> JOB
    CORE --> AUTH
    CORE --> NAS
    CORE --> PG
```

### 3.2 能力注册表（单一事实源）

新增 `naskb/common/capabilities.py`：每个能力只定义一次（名字/描述/参数 Schema/处理函数/语义属性），四个适配器从注册表自动生成各自的出口，**不维护四份实现**。

```python
# naskb/common/capabilities.py（新增，示意）
from enum import Enum

class CapKind(str, Enum):
    READ  = "read"    # 只读、毫秒级、同步返回
    WRITE = "write"   # 写操作（入库/同步），秒~分钟级，走 job 模式
    PLAN  = "plan"    # 出方案不执行（plan-reorganize 无 --apply）
    APPLY = "apply"   # 执行整理/移动，需显式确认
    ADMIN = "admin"   # 来源/配置管理

@dataclass
class Capability:
    name: str            # 规范名，如 "kb_search"
    description: str     # 给 LLM 看的行为描述（含前置条件/副作用）
    params: dict         # JSON Schema（参数定义一次，四处复用）
    handler: Callable    # 直接复用 common/ 现有实现（retrieval/pgstore/reorganizer/analyzer...）
    kind: CapKind
    timeout: int | None  # 秒；None → 必须走 job 模式（WRITE/APPLY 类）
    scope: str           # 所需最小权限角色（read / write / admin）
```

适配器职责：

| 适配器 | 位置 | 说明 |
|--------|------|------|
| MCP | `naskb/mcp/adapter.py` | 注册表 → MCP Tools；另注册 Resources（只读视图）与 Prompts（工作流模板） |
| HTTP | `naskb/common/serve.py` 扩展 | 注册表 → REST 端点；**保持 `/api/search` `/api/ask` 现有契约不变** |
| Function | `naskb/common/functions.py` | 注册表 → OpenAI tools JSON（`{type:function, function:{name,description,parameters}}`），供平台 Agent 直接注入 |
| CLI | `naskb/skill/cli.py` | 维持现状（命令行语义已与能力一一对应，后续可选改为注册表驱动） |

### 3.3 与现有 `desc serve` 的关系

不另起炉灶：把 `serve.py` 的 `KnowledgeCore` 升级为 **Common Core 服务对象**（进程内单例，持有检索内核、PG 引擎、JobManager、配置），同一进程可同时开两个端口——REST（默认 8765，兼容现有前端）与 MCP（streamable HTTP，默认 8866）。`desc serve` 命令增加 `--mcp` 开关，或提供独立命令 `desc serve-mcp`。

---

## 4. 工具面设计（MCP Tools / function schema / REST 同源）

统一前缀 `kb_`（避免与客户端内其他 MCP server 冲突）。按使用频度分四组：

### A. 检索与问答（READ，同步、毫秒级，最高频）

| Tool | 参数 | 语义 |
|------|------|------|
| `kb_search` | `query, top_k=10, nas=None, threshold=None` | 语义检索（本地向量 → BM25 自动降级；`nas` 指定时走 PG 对应 schema）。返回 `[{path, score, summary, tags, category, nas, engine}]` |
| `kb_ask` | `question, top_k=5, nas=None` | RAG 问答：召回 top-k → DeepSeek 生成，**带来源路径**。返回 `{answer, sources, engine}` |
| `kb_get_doc` | `path, nas=None, include_fulltext=false` | 取单文件完整元数据（摘要/标签/分类/EXIF/转录/ocr_text；`include_fulltext` 才带全文，控制 token 成本） |
| `kb_fetch_file` | `path, nas=None` | 取**原始资源**：返回内容字节，或授权下载引用（本地 `file://` / WebDAV 临时 URL）。企业场景建议走临时 URL + 时效 |

> 设计要点：`kb_get_doc` 与 `kb_fetch_file` 分离——Agent 先看智能描述判断相关性，需要原文时再取资源，避免每轮检索都拉大文件。

### B. 入库与索引（WRITE，秒~分钟级，异步 job + 进度通知）

| Tool | 参数 | 语义 |
|------|------|------|
| `kb_ingest` | `root, nas=None, workers=4` | scan + analyze-tree **增量幂等**（hash 对比，一致跳过/变更重分析/删除清孤儿），可反复调用 |
| `kb_analyze_file` | `path, nas=None, force=false` | 单文件分析（文档 DeepSeek / 图片音频 MiMo / 扫描件 MinerU 自动路由） |
| `kb_sync_vectors` | `root, nas=None, rebuild=false` | `.naskb` → PG 多 NAS 向量库（增/改/删/移增量） |
| `kb_index_vectors` | `root` | 构建本地语义向量索引（bge-small-zh） |
| `kb_job_status` | `job_id` | 查询长任务进度（阶段/进度 0~1/结果/错误） |
| `kb_list_jobs` | `status=None` | 任务列表（pending/running/completed/failed） |

> 长任务模式：analyze-tree / sync-vectors / MinerU OCR 是分钟级操作，**同步返回 job_id + 立即返回**；支持 MCP 的客户端自动收进度通知（`notifications/progress`），其余轮询 `kb_job_status`。旧草案的 JobQueue 思想原样继承。

### C. 整理与重组（PLAN → APPLY，两步走，有副作用）

| Tool | 参数 | 语义 |
|------|------|------|
| `kb_plan_reorganize` | `root, nas=None, max_items=None` | AI 生成整理方案（目标路径/依据/涉及文件），**只输出不动**。返回 `plan_id` |
| `kb_apply_reorganize` | `plan_id, confirm=true` | 执行方案。服务端校验：`confirm=true` 必填、plan 未被篡改（方案生成后文件集比对）、目标路径在 root 白名单内。遵守"移动不删除/级联更新/清空目录/子路径先移"四条原则 |

> 设计要点：**绝不提供"一步到位的整理"工具**。执行入口强制要求先 plan 后 apply，与 CLI 的 `plan-reorganize [--apply]` 语义一致；`confirm` 参数要求调用方显式传 true，防止 Agent 误触发批量移动。

### D. 管理与状态（ADMIN / READ）

| Tool | 参数 | 语义 |
|------|------|------|
| `kb_status` | `root, nas=None` | 一致性报告：valid/stale/missing + PG 同步差异（对应 `desc scan` + `sync-status`） |
| `kb_stats` | — | 引擎/文档数/向量索引状态/PG 注册 NAS 清单（对应 `desc pg-status`） |
| `kb_list_sources` | — | 已注册知识库来源 |
| `kb_add_source` / `kb_remove_source` | `name, root, nas=None` | 注册/注销来源（写 `[pg]` 配置或 root 白名单） |

### 资源（MCP Resources，只读视图，Agent 直接"读"不用"调"）

```
kb://stats                  → 全局状态快照
kb://sources                → 来源清单
kb://status/{root}          → 指定库一致性报告
kb://doc/{path}             → 单文件元数据视图（与 kb_get_doc 同数据）
kb://plan/{plan_id}         → 已生成未执行的方案
```

### 提示词（MCP Prompts，工作流模板）

| Prompt | 作用 |
|--------|------|
| `kb-find` | 检索+问答模板："先 kb_search 定位 → 必要时 kb_get_doc 看细节 → kb_ask 总结带来源" |
| `kb-ingest` | 入库模板："新增文档先 kb_ingest → kb_status 核对覆盖 → kb_sync_vectors 入 PG" |
| `kb-reorganize` | 整理模板：**强制两段式**——先 kb_plan_reorganize，向用户展示方案并取得确认后才 kb_apply_reorganize |

Prompt 的价值：把"正确使用 KB 的守则"固化进协议层，即使消费方是零配置的通用 Agent 也能安全操作。

---

## 5. 传输、部署与认证

### 5.1 传输形态

| 传输 | 适用 | 说明 |
|------|------|------|
| **stdio** | 桌面本地 Agent（Claude Desktop / Cursor 本机） | `mcpServers.naskb = {command: "naskb", args: ["serve-mcp", "--stdio"]}`；零配置，进程随客户端起停 |
| **streamable HTTP**（主推企业） | 常驻服务，多客户端远程接入 | MCP 2025 标准传输；同一 server 实现双传输，进程常驻 NAS 或内网服务器 |

### 5.2 认证与授权（企业必需）

- HTTP 形态强制 **Bearer token**（配置 `[server.auth]`，支持多 key）；stdio 形态走本机信任（进程即用户身份）；
- 角色最小化：`read`（检索/问答/读元数据）→ `write`（入库/索引/同步）→ `admin`（来源管理/整理执行）。每个 Capability 的 `scope` 字段声明所需角色；
- **root 白名单** `[server.roots]`：服务端只允许对白名单内目录执行写/整理/移动；检索读取不受限（或同样可收敛）。这是企业数据安全底线——Agent 无论如何误用，物理上动不了白名单之外的文件。

### 5.3 部署形态（三选一，按企业条件）

1. **Windows 常驻**（现状环境）：`desc serve-mcp --host 0.0.0.0 --port 8866`，计划任务/开机自启，与 `desc serve` 并存；
2. **NAS 本机**（群晖等支持 Docker/任务）：容器内跑服务，NAS 卷直挂为 root；
3. **内网服务器**：多 NAS 通过 WebDAV 挂载，PG 向量库集中，服务端一个进程管所有 NAS（`--nas` 参数天然支持）。

### 5.4 接入 Dify（已定为首个落地客户端）

Dify 1.0+ 通过官方 MCP 插件原生支持远程 MCP server（SSE / streamable HTTP 传输），接入步骤：

1. Dify 市场安装 **MCP 插件** → 添加服务器，类型选 streamable HTTP，URL 填 `http://<NASKB主机>:8866/mcp`；
2. 认证：插件配置里填 Bearer token（对应 `[server.auth]` 中生成的 key）；
3. 连接成功后，14 个 `kb_*` 工具**自动注册**进 Dify 工具列表，在 Agent 节点 / 工作流工具节点直接勾选使用；
4. **超时对策（必须）**：Dify 工具节点有调用超时上限，分钟级操作绝不能同步等——设计已强制 B/C 组走 job 模式（工具立即返回 `job_id`，Agent 在流程里轮询 `kb_job_status`，或用"工具→条件分支"实现等待）；
5. 工具描述即 LLM 使用依据：Dify 里工具对模型是黑盒，每个 `kb_*` 的 description 必须写清"做什么/什么时候用/有什么副作用"，设计已按此标准写；
6. 多 MCP server 共存时工具名以 `kb_` 前缀隔离，不与其他插件冲突。

> 备选路径：若某环境装不了 MCP 插件，Dify 也支持 OpenAPI 自定义工具——直接复用现有 `desc serve` 的 REST 契约（`/api/search` `/api/ask`）。但每加一个能力都要在 Dify 手工维护 schema，长期维护税高，仅作兜底。

---

## 6. 安全与治理

| 风险 | 对策 |
|------|------|
| Agent 误触发批量移动 | APPLY 类工具强制 plan→apply 两步 + `confirm` 显式确认 + 执行前文件集复检 |
| 越权访问/写入 | Bearer token + 角色 scope + root 白名单（服务端强制，不依赖 Agent 自觉） |
| 敏感文档经 RAG 泄漏 | `kb_ask` 支持 `nas`/目录级过滤；审计日志记录问答来源（可选脱敏） |
| MiMo/MinerU 并发风控 | 服务端保留"MiMo 严格串行、MinerU 严格串行"规则；并发请求进队列，暴露为 job 状态 |
| 长任务堆积 | JobManager 限流（默认 1 个 WRITE 任务并发），超时/失败可重试 |
| 审计缺失 | 所有 WRITE/APPLY/ADMIN 操作写审计日志（时间/调用方/参数摘要/结果），落本地或 PG |

---

## 7. 与旧草案的关系

- `design/mcp-kb-design.md`（v0.1）、`design/mcp-tech-reassessment.md`（v0.3）基于 v1 架构，其中 **JobQueue 异步任务、Tool/Resource 划分思路、common 层与部署形态解耦原则** 沿用；
- 已过时需放弃：LanceDB 选型、`.kbdes` 描述文件、watchdog 实时监控（v2 的 analyze-tree 增量幂等取代了"文件变更监控"，无需常驻 watcher）；
- v2 差异对齐：工具参数中的 `root`/`nas` 对应 v2 的 `.naskb` 仓库路径与 PG schema；检索引擎枚举为 `vector|bm25|pg`。

---

## 8. 实施路线图

| 阶段 | 内容 | 验收 |
|------|------|------|
| **A. 能力注册表 + MCP stdio** | `capabilities.py` 落地；`naskb/mcp/`（adapter + server）；先实现 A 组 4 个读工具 + B 组 job 模式（kb_ingest/job_status）；`mcp.json` 模板 | 本机 Agent（Claude Desktop / Cursor）完成"检索→问答→取原文→入库→查状态"全流程 |
| **B. HTTP 常驻 + 认证** | streamable HTTP 传输；Bearer token + 角色 scope；root 白名单；`serve-mcp` 命令与 `desc serve` 同进程双端口 | 内网另一台机器上的 Agent 经 HTTP 接入，白名单外写操作被拒 |
| **C. Resources/Prompts + 治理** | 5 个资源 + 3 个提示词模板；审计日志；`functions.py` 导出 OpenAI schema（供平台型 Agent）；C 组 plan/apply 工具 | 无 MCP 的平台拿到 schema 直接注入可用；整理必须两段式 |
| **D. 部署与文档** | 服务化部署（Windows 任务/NAS 容器/Docker）；健康检查 + 启动脚本；更新 `SKILL.md`（指向 MCP）、`DEPLOY.md`；集成测试（MCP 客户端模拟） | 服务 7×24 稳定；三形态消费端各一条端到端用例 |

依赖新增仅一个：官方 `mcp` Python SDK（其余全部复用现有 `common/` 与 `pg` 依赖）。

---

## 9. 决策点（需企业侧确认）

1. **传输**：内网 HTTP 常驻为主，stdio 是否也需要？（决定 `serve-mcp` 是否双传输）
2. **认证粒度**：Bearer token 单层够用，还是需要多租户（每 NAS/每团队独立 key）？
3. **接入优先级**：**Dify 已定为首个落地客户端**（见 §5.4）；Phase A 先跑通 Dify 端到端用例（MCP 插件 → `kb_search`/`kb_ask` → Agent 节点），Claude Desktop/Cursor 本机验证作为次优先。
4. **`kb_fetch_file` 的返回形态**：直接返回字节（简单，大文件吃内存）还是临时授权 URL（需额外生成签名 URL 的能力）？
5. **RAG 权限**：是否需要按目录/来源限制 `kb_ask` 的召回范围（企业数据隔离要求）？

---

> **下一步**：确认第 9 节决策点后，从 Phase A 开始实施。
