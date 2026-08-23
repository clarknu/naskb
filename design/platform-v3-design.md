# NASKB v3 平台化重定位总体设计（功能设计·整合方案）

> 版本: v0.2（决策已确认）
> 创建: 2026-08-18（v0.2 同日拍板修订）
> 定位变更依据: 用户 2026-08-18 重定位指示（对话记录）
> 依赖: [requirement.md](./requirement.md), [analysis-engine-v2.md](./analysis-engine-v2.md),
>       [pg-vector-multi-nas.md](./pg-vector-multi-nas.md), [agent-interface-design.md](./agent-interface-design.md),
>       [reorganize-refactor-plan.md](./reorganize-refactor-plan.md)
> 状态: **已获用户批准并逐项拍板 8 项决策（2026-08-18，见 §9）**；附录 A 已落入 requirement.md（R7 需求组 + ADR-20260818-1）

---

## 0. 一句话重定位

**从「附着在 NAS 上的本地工具」升级为「自持知识的知识库系统」**：
系统自己拥有知识（元数据/摘要/全文/索引/预览产物的权威存储），对外提供操作界面（Web UI）、
用户可见功能与开放 API；NAS 及各类可挂载文件系统退化为**知识源**（原始数据的存放地，
可写源同时保留 `.naskb` 提取数据作为缓存）。系统在知识源之上提供：检索罗列、RAG 问答、
下载代理（流式转发）、内容预览、整理规划（可写源）五大用户能力。

### 0.1 新旧定位对比

| 维度 | 旧定位（v2，工具） | 新定位（v3，系统） |
|---|---|---|
| 形态 | CLI/Skill/MCP 工具集，无常驻界面 | 常驻服务：Web UI + REST API + MCP |
| 知识归属 | 附着在源端 `.naskb/`，工具是过客 | **系统内部自持**（PG 主库 + 内部 blob 仓）；`.naskb` 降为缓存 |
| 知识源 | 本地目录 / WebDAV 二选一连接 | 多源注册制：local / WebDAV / SMB / NFS / iSCSI（挂载式集成） |
| 源的读写假设 | 默认可写（要建 `.naskb`） | **支持只读源**：抽取后自行存储，源一个字节都不写 |
| 内容触达 | 只有描述与全文文本 | 增加**下载代理**（流式）与**在线预览**（图片/视频/音频/PDF/文本） |
| 用户 | 开发者/AI Agent | 最终用户（浏览器操作）+ AI Agent（API/MCP）双受众 |
| 安全边界 | `--root` 启动参数白名单 | 来源注册表即边界：一切资源凭 `resource_id` 寻址，不接受裸路径 |
| 不变的部分 | 确定性层/AI 编排层分离；事实源唯一原则；摘要索引；无 chunking | 原则全部保留，只是"派生层"从源端搬到系统内 |

### 0.2 架构不变量（继承自 requirement.md §4，重申）

1. 事实源唯一：源文件仍是事实源；系统内存储是**可重建的派生快照**（方向反转：v2 里 PG 是派生、
   `.naskb` 是准事实；v3 里系统内存储是"知识的家"，但原始文件仍以源为准）。
2. 索引只用摘要+描述（ADR-20260811-1）；Doc.text/context 分层；不做 chunking。
3. 确定性层与 AI 编排层分离。
4. 轻量起步、按需升级；每步升级有明确触发条件。

---

## 1. 总体架构

```mermaid
graph TB
    subgraph 消费端
        U[浏览器用户<br/>Web UI]
        AG[AI Agent<br/>MCP / function schema / REST]
    end

    subgraph NASKB 服务进程（常驻，单机部署）
        WEB[Web UI（静态前端）]
        API[REST API 层<br/>旧 /api/search /api/ask 契约不动]
        MCPAD[MCP Server（stdio/HTTP）]
        AUTH[认证与审计<br/>Bearer token]

        subgraph 核心服务
            SRC[来源注册表服务<br/>多协议接入/连通性/调度]
            ING[摄取与分析管线<br/>analyze-tree 增量幂等（现有）]
            RET[检索与问答内核<br/>向量/BM25/PG 引擎链（现有）]
            FILE[内容访问服务<br/>下载代理/预览/缩略图（新增）]
            ORG[整理服务（可写源）<br/>plan/apply（现有）]
            JOB[JobManager + 调度器<br/>jobs.py（现有）+ 定时扫描（新增）]
        end
    end

    subgraph 系统内部存储（知识的家）
        PG[(PostgreSQL + pgvector<br/>独立实例 192.168.5.2:25432<br/>sources/resources/vectors)]
        TMP[(临时暂存区 store/tmp<br/>分析期临时文件<br/>任务结束即清·不留中间产物)]
        NPZ[(numpy 向量快照<br/>离线兜底，保留)]
    end

    subgraph 知识源（原始数据）
        L[本地磁盘]
        W[WebDAV]
        S[SMB/NFS/iSCSI<br/>挂载或直连]
    end

    U --> WEB --> API
    AG --> MCPAD
    AG --> API
    API --> SRC & RET & FILE & ORG
    MCPAD --> RET & FILE & ORG
    SRC & RET & FILE & ORG --> JOB
    ING --> PG & TMP
    RET --> PG & NPZ
    SRC -->|读流/PROPFIND/stat| L & W & S
    ORG -->|仅可写源| L & W & S
```

分层说明：

| 层 | 职责 | 现状 |
|---|---|---|
| 接入层 | 多协议知识源接入、注册、连通性、读写属性 | fs/base.py 已抽象 local/webdav(+smb 桩)；缺注册制运行时管理 |
| 摄取层 | 扫描→AI 分析→入库 | **已完成**（batch.py/analyzer/*，增量幂等三级判定） |
| 存储层 | 系统内知识的权威存放 | PG resources/vectors 已具备核心字段；缺 sources/folders 表与"主库地位"切换 |
| 检索层 | 向量/BM25/RAG/状态徽章 | **基本完成**；缺跨源合并（--nas all） |
| 内容访问层 | 下载代理、预览、缩略图 | **全新** |
| 交互层 | Web UI、REST、MCP | serve 有雏形页面与稳定契约；需平台化 |
| 治理层 | 认证、审计、任务、调度、备份 | jobs.py 有任务框架；其余待建 |

---

## 2. 知识源接入层（挂载式集成）

### 2.1 来源类型矩阵

| 协议 | 接入方式 | 读写 | 实现策略 | 阶段 |
|---|---|---|---|---|
| **local** | 直接登记本机路径 | 可写/只读均可 | `fs/local.py` 现成 | V1 |
| **WebDAV** | HTTP 直连（五要素身份 + basic auth） | 通常可写；也可只读 | `fs/webdav.py` 现成；补 ctime 缺失兜底（已有） | V1 |
| **SMB** | 直连：fsspec smb（`fs/base.py:128` 已有分支）起步，后续换 `smbprotocol` 原生实现（流式读更稳） | 先只读 | V1 验证桩可用性；V2 原生化 | V2 |
| **NFS** | **OS 挂载**为盘符/目录 → 注册为 local 源（Windows NFS 客户端 / Linux mount） | 随挂载 | 接入指南 + 连通性探测，不写 NFS 客户端 | V2 |
| **iSCSI** | 块设备挂载成本地磁盘 → 注册为 local 源 | 随挂载 | 运维指南（initiator 配置），代码零改动 | V2 |

> 设计立场：**能用 OS 挂载解决的协议（NFS/iSCSI）不在应用层重复造客户端**；
> 应用层只为 WebDAV/SMB 这类"网络文件协议"维护直连适配器。挂载型来源与 local 同权。

### 2.2 来源注册表（运行时管理，取代 config-only）

数据模型（PG `public.sources`，新建；与 `nas_registry` 外键关联）：

```
sources(
  source_id   uuid PK,
  nas_id      uuid → nas_registry,        -- 连接身份（五要素，REQ-R4-01 语义不变）
  alias       text UNIQUE,
  root_path   text,                        -- 该知识库的根（NAS 视图内路径或本机路径）
  access_mode text DEFAULT 'rw',           -- rw | ro          ← 只读知识库的关键字段
  label       text DEFAULT '',
  scan_policy jsonb DEFAULT '{}',          -- {auto: bool, interval_min: int}
  enabled     bool DEFAULT true,
  created_at / updated_at timestamptz
)
```

- 一个 NAS（五要素）可登记多个来源（不同共享目录 = 不同知识库）。
  `resources` 表增加 `source_id` 列，schema 仍按 NAS 身份组织（沿用 ADR-20260816-3），
  检索按 `source_id` 过滤即可支持"单库/跨库"两种范围。
- 管理入口：REST `/api/sources` + Web UI 来源管理页；config.toml `[[nas]]` 作为引导导入
  （首启自动迁入注册表），此后以库为准。
- **安全边界换位**：现行 `--root` 白名单（agent-interface 阶段 A 实现）升级为
  "注册表即白名单"——所有读写操作必须引用 `source_id`/`resource_id`，
  API 层不再接受任意文件系统路径。

### 2.3 可写源 vs 只读源（本次重定位的核心差异）

| 行为 | rw（可写） | ro（只读） |
|---|---|---|
| `.naskb/` 写入源端 | ✅ 继续双写（便携缓存，符合"NAS 保留知识提取数据"） | ❌ 绝不写 |
| MinerU/缩略图等产物落点 | 源端 `.naskb/artifacts/`（原始仲裁端，唯一保留处） | 不保留（临时暂存区用完即清） |
| 整理 plan/apply | ✅（现有 reorganizer 全套安全机制） | ❌ 功能上隐藏/禁用 |
| 删除检测 | 分析时孤儿清理 | 只标记 `missing_in_source`，不清内部知识（防误删知识） |
| 新鲜度 | analyze-tree 增量幂等（L1/L2/L3 现有） | 周期预检（§4.3）+ 访问时轻校验 |

---

## 3. 知识存储层（系统内部自持）

### 3.1 职责划分

| 存储 | 内容 | 说明 |
|---|---|---|
| **PG（独立实例，沿用 192.168.5.2:25432）** | sources / nas_registry / **resources**（每文件的元数据+指纹+full_text）/ **vectors**（向量+summary_text+full_text） | **知识的权威存放地**。v2 设计的表结构几乎原样复用——当时按"向量库"设计，实际字段已覆盖知识主库所需（rel_path/parent_dir/category/tags/summary/content_description/full_text/file_hash/hash_algorithm/mtime/ctime/status/prev_hashes） |
| **临时暂存区**（工作区 `store/tmp/`，任务级生命周期） | 分析过程中的下载缓存与中间文件（MinerU 输入输出、抽帧等） | **不持久保留任何中间产物：入库即清**（用户拍板 2026-08-18——产物体量不可控，避免无限膨胀）。文档拆出物的标准解析/存储与再组织属"二级知识库体系"（REQ-R7-15），另行专项设计 |
| **源端 `.naskb/`** | 可写源的提取数据缓存 | 语义降级为"边缘缓存"：丢了可从系统重建（反向恢复命令 `desc export-repo`，V2） |
| **numpy 快照**（db/vectors.npz） | 离线检索兜底 | 保留，REQ-R4-13 回退链不变 |

> 双写语义（用户拍板 2026-08-18）：可写源端 `.naskb` 是提取数据的**原始仲裁端**（权威记录）；
> 系统内 PG 维护其**副本 + 后续处理衍生的知识产物**。只读源没有 `.naskb`，系统副本即唯一存放地；
> 原始文件永远以源为准（事实源唯一原则不变）。
>
> 中间件纪律（全局部署规则）：PG 使用宿主/统一管理的独立实例，NASKB 业务进程**不内嵌任何数据库、
> 不自带 Redis/队列容器**；后台任务用进程内线程池（jobs.py 现状），调度用进程内循环（§6.4）。
> 将来容器化时 compose 只声明自身服务，PG 走内网地址。

### 3.2 只读源的摄取模式（pull-mode ingestion）

现状管线默认"写到源端 `.naskb`"。v3 引入 **ArtifactSink 抽象**：

```
ArtifactSink
├── SourceRepoSink      # 现行为：写 .naskb（rw 源，原始仲裁端）
└── InternalSink        # 新增：元数据/全文直接入 PG（ro 源；中间产物只过临时区，不落盘保留）
```

- 分析输入侧不受影响：WebDAV/SMB 本来就是"下载到临时区再分析"（cli.py `_download_to_tmp` 现成），
  local 直接读；MinerU 等重产物的中间文件同样只在 `store/tmp/` 存在，任务结束清理。
- `FileEntry` 数据类与 PG resources 字段一一对应，InternalSink 直接入库，跳过 JSON 落盘。
- folder.json 目录级描述：ro 源同样入内部库——**已拍板用独立 `folders` 表**
  （原 §9-6 决策点），浏览页的"目录智能描述卡片"靠它。

### 3.3 文件精确定位与更新校验（只读源的可靠性保障）

复用已实现的指纹体系（ADR-20260816-4，batch.py/hashing.py/pgstore.py 均已落地）：

1. **精确定位**：`resource_id → (source_id, rel_path)` + 按协议生成 `canonical_uri`
   （webdav: 拼 GET URL；local/smb/nfs: 适配器路径）。API/UI 全程凭 id，源端改名/移动
   由移动检测（hash 匹配，pgstore.sync_vectors 已实现）跟随更新。
2. **三层版本对齐**：源文件 ↔ 系统内 resources/vectors（v2 时代的 NAS↔.naskb↔PG 三层，
   在 ro 场景收敛为两层，指纹四元组 size/mtime/ctime/采样 hash 原样适用）。
3. **新鲜度状态机**：ok / stale_vector / stale_source（pgstore 已有 DDL 与统计），
   ro 源新增第四态 `missing_source`（源端消失，知识保留可搜，下载/预览时明确告知）。
4. **校验时机**：
   - 周期预检：调度器按 scan_policy 做 PROPFIND/readdir 零下载比对（**这正是旧计划 REQ-R4-10，
     在 v3 从"优化项"升格为只读知识库的正确性根基**）；
   - 访问时轻校验：下载/预览前 stat 比对，不一致当场标 stale 并提示"先重新扫描"；
   - 深度校验：手动 `--verify-hash`（旧计划条目，随 V2 落地）。

### 3.4 存量迁移与兼容

- **adopt 命令**（V1）：对现存可写源的 `.naskb` 仓库执行一次"收编导入"——collect_docs 读
  条目直接灌 PG（sync-vectors 已能做，补 folder.json 与 artifacts 入 blob 仓），
  之后该源在 UI/API 里与其他来源无异。
- CLI（`naskb desc ...`）与 Skill 全部保留，作为高级用户/无人值守通道；
  MCP 14 工具改指向新服务对象（方法签名不变，内部从"root 路径"改为"source 别名"）。
- `/api/search` `/api/ask` 契约不动（ADR-20260816-2），前端与外部集成零迁移成本。

---

## 4. 内容访问层（新增：下载代理 + 预览）

### 4.1 下载代理（流式转发）

```
GET /api/files/{resource_id}/download
  ?disposition=inline|attachment
Headers: Range（透传）, If-None-Match
响应: 200/206 流式分块转发; ETag = file_hash; Content-Disposition: filename*=UTF-8''…
失败: 503 {error:"source_unreachable", hint:"稍后重试或检查来源连接"} + stale 徽章信息
```

- 实现要点：local 用 seek 读；WebDAV 转发 Range 头到源站；SMB 偏移读。**全程不在服务端
  落盘整文件**（大文件友好）；NAS 国内服务器 NO_PROXY 纪律沿用（REQ-R6-04）。
- 访问前轻校验（stat 四元组）→ 不一致返回 409 + stale 提示，附"重新扫描"链接。
- 不做产物级缓存：系统内无持久 blob 仓（用户拍板），源不可达即 503 明确告知；
  将来如需离线可读，另立"快照缓存策略"专项评估。

### 4.2 在线预览矩阵（先简单版，复杂后置）

| 类型 | V1 行为 | V2+ 增强 |
|---|---|---|
| 图片 jpg/png/webp/gif/bmp | `<img>` 直接流式预览 + 元数据面板（EXIF/摘要/标签） | heic/tiff 转码；缩略瀑布流 |
| 视频 mp4/webm（H.264/VP9） | `<video>` Range 流播（下载代理天然支持拖进度条） | 其他编码/容器：提示"无法在线播放"+下载；**关键帧图集预览**（analyzer/video.py 抽帧能力已有；rw 源用源端产物，ro 源按需现抽或不提供） |
| 音频 mp3/wav/m4a/flac/ogg | `<audio>` 播放 + **转写全文侧栏**（transcription 已在知识库里） | 说话人分离展示 |
| PDF | 内嵌 viewer 流式加载 | 大文件懒加载页 |
| 文本 txt/md/json/code | 文本视图；md 渲染 | 语法高亮 |
| Office docx/xlsx/pptx | **提示"暂不支持在线查看"+ 下载按钮**（用户拍板的简单版策略） | docx→HTML（mammoth/docx-preview）；xlsx 表格预览；pptx 图页 |
| 已分析文档（rw 源，MinerU 产物在源端 `.naskb/artifacts/`） | **"解析视图"**：经代理流式展示源端 MinerU HTML——零新代码就让大量 PDF/扫描件获得高质量预览（复用现有产物）；**ro 源不留产物，此档不适用**，回退原生预览/下载 | middle.json 版面结构还原（rw 源） |
| 其他/未知二进制 | 无法查看 + 下载 | 按需扩展 |

预览端点族：`GET /api/files/{id}/preview`（按类型分流）、`GET /api/files/{id}/thumbnail`。

---

## 5. 用户可见功能（检索 · 罗列 · 问答 · 整理）

1. **全局搜索/罗列检索**：关键词+语义混合搜索结果列表（引擎徽章/新鲜度徽章照旧）；
   **目录树浏览**：来源 → 目录树 → 文件清单（面包屑导航），目录节点带 folder 描述卡片，
   支持按目录范围过滤检索（parent_dir 索引已在 PG 设计中）。
2. **RAG 问答**：现有 `ask` 能力（带来源、过期内容显式标注——REQ-R4-07 的 UI 化）。
3. **文件详情页**：预览器 + 智能元数据（摘要/标签/分类/OCR/转写）+ 操作
   （下载 / 重新分析 / 查看指纹与版本历史 prev_hashes / 在源中定位）。
4. **整理（仅可写源）**：plan → 人工确认 → apply 两段式（P0+P1 安全机制全继承），
   UI 上呈现方案 diff、冲突三档处理结果、失败分类清单。
5. **来源管理**：注册/编辑/停用来源、连通性测试、手动扫描/同步、一致性报告
   （sync-status 的图形化）、扫描策略（自动周期开关）。
6. **任务中心**：JobManager 任务列表/进度/结果（analyze-tree/sync 等长任务的可见性）。

---

## 6. 平台技术形态

### 6.1 服务进程与框架（吸收 agent-interface-design 阶段 B 的欠账）

- 单进程常驻服务：`naskb serve-platform`（或升级版 `desc serve`），承载 REST + Web UI +
  MCP-over-HTTP（streamable）三个出口；stdio MCP 继续可用（桌面 Agent）。
- 后端框架引入 **FastAPI**（已拍板）：自动生成 OpenAPI 文档正好喂"开放 API"目标，
  StreamingResponse 天然支撑下载代理，pydantic 校验收紧 API 面。现 stdlib `_Handler`
  的 5 个端点原样平移，旧契约不变。
- 前端采用 Vue3 + Vite 构建**静态包**由服务进程托管（已拍板）——运行时不引 Node、
  不加服务；开发期才需要构建步骤。

### 6.2 开放 API 面（REST，全部 Bearer 保护，匿名只读可配置）

```
# 兼容保留（契约冻结，ADR-20260816-2）
GET  /api/search        POST /api/ask       GET /api/stats       POST /api/reload
# 来源与浏览
GET/POST/PATCH/DELETE /api/sources[/{id}]   POST /api/sources/{id}/test|scan|sync
GET  /api/tree?source=&dir=                  GET  /api/folder?source=&path=
# 内容访问
GET  /api/files/{rid}                        GET  /api/files/{rid}/download
GET  /api/files/{rid}/preview                GET  /api/files/{rid}/thumbnail
# 整理（rw 源）与任务
POST /api/reorganize/plan|preview|apply        GET  /api/jobs[/{job_id}]
GET  /api/openapi.json（FastAPI 自动产出 → function-calling 平台直接消费）
```

### 6.3 出口矩阵（一套核心，四个出口——agent-interface §2 结论原样生效）

| 出口 | 状态 |
|---|---|
| REST | V1 平台化（上述清单） |
| MCP stdio | 已有 14 工具；V2 增 `kb_list_tree` / `kb_file_url`(下载链接) / `kb_list_sources`，并补 Resources/Prompts（阶段 C 欠账） |
| OpenAI function schema | 由 OpenAPI 自动导出（阶段 C 的 functions.py 欠账，被 FastAPI 方案顺带解决） |
| CLI/Skill | 保留现状 |

### 6.4 认证、任务与调度

- **认证**（serve 访问口令欠账的正式解法）：`[server.auth] tokens=[...]` Bearer；
  v1 单管理员令牌 + "局域网匿名只读"开关；多用户/角色留 V3（与 MaxKB 多用户诉求一起看）。
- **任务**：jobs.py 线程池（MiMo/MinerU 串行纪律不变）承接 analyze/sync/整理。
- **调度**：进程内轻量循环（无新中间件）——周期 scan/sync 预检、stale 复查。
  **旧计划"阶段 3 定时同步"欠账在此清偿。**
- **审计**：WRITE/APPLY/ADMIN 操作追加式审计日志（blob 仓 `audit/`，V2）。

---

## 7. 现状映射总表（已有/欠账 → v3 归属）

### 7.1 已实现，直接成为 v3 地基

| 资产 | v3 角色 |
|---|---|
| batch.py 三级判定链 + hashing.py 采样 hash | 只读源更新校验的根基（§3.3） |
| pgstore.py resources/vectors DDL、sync 四操作、hash 移动识别 | 知识主库与同步内核（§3.1） |
| pgsearch.py + retrieval.py 引擎链 + 回退 | 检索层原样 |
| analyzer/*（MinerU/MiMo/DeepSeek/视频分级/docx 图文流） | 摄取管线原样，输出改接 ArtifactSink |
| reorganizer P0+P1 全套安全机制 | 可写源整理服务 |
| mcp/server.py 14 工具 + capabilities/jobs | MCP 出口与任务框架 |
| serve.py /api/search /api/ask 契约 | REST 兼容面 |
| fs/base.py local/webdav(+smb 桩) | 接入层适配器 |

### 7.2 旧计划欠账 → v3 吸收安排

| 欠账（出处） | v3 安排 |
|---|---|
| REQ-R4-10 sync PROPFIND 预检 + `--verify-hash` | **V1 核心**（升格为只读正确性根基，§3.3） |
| REQ-R4-11 access_identity 防串库 | V1，演化为"来源绑定校验"（source ↔ 五要素 ↔ 实际连接三方核对） |
| REQ-R4-14 pg-rebind | V2（来源管理页的"主机迁移"操作） |
| `--nas all` 跨库合并 | V2（跨源检索，分数不跨库比较原则不变） |
| 阶段 3 定时同步 | V1 调度器（§6.4） |
| agent-interface 阶段 B（HTTP 传输/Bearer/root 白名单配置化） | V1 被"平台服务 + 注册表边界"整体吸收 |
| 阶段 C（Resources/Prompts/审计/functions.py） | V2（functions.py 由 OpenAPI 导出替代） |
| 阶段 D（部署/健康检查） | V3 |
| serve 访问口令未排期 | V1 认证（§6.4） |
| REQ-R5 MaxKB 系列 / RRF 混合检索 | V3 不变 |
| middle.json 版面框解析（analysis-engine-v2 §8.4） | V3 backlog |
| 整理 B4 taxonomy 可配置 / B7 scope 分批 / approval 策略 | V2（UI 整理页顺手做 taxonomy 编辑） |
| 文档债：README 测试数 164→253、cli.py 头注释、requirement.md §7 与 R1-14/15 缺号 | **立即**（V0.1 固化时一并清） |

### 7.3 v3 净新增工作量（旧计划完全没有的部分）

净新增 = ArtifactSink 双模式摄取（internal 模式不留产物）、sources 注册表及管理 UI/API、
resource_id 寻址改造、下载代理（Range 流式）、预览子系统（矩阵 V1 档）、
Web UI（浏览/详情/管理/任务四组页面）、认证、调度器。

---

## 8. 实施路线图

| 阶段 | 内容 | 验收 |
|---|---|---|
| **V0.1 固化（立即，~半天）** | 提交当前未入库成果（mcp/capabilities/jobs/plan_store/两设计文档/mcp.json）；requirement.md 落附录 A 修订；README/CLI 注释修正 | git 干净；基线与实现一致 |
| **V1 系统底座（1~2 周）** | FastAPI 服务化（旧契约平移）；sources 注册表 + 管理 API/UI 骨架；ArtifactSink（internal 模式）；adopt 收编命令；下载代理（Range/ETag/stale 校验）；预览 V1 档（图片/PDF/音视频原生格式/文本/MinerU 解析视图/兜底下载）；Web UI 四组页面骨架（搜索问答/浏览/详情/来源管理）；Bearer 认证 + 匿名只读开关；调度器（周期预检）；R4 收尾三项（precheck/access_identity→来源绑定/定时同步） | 浏览器完成"注册 WebDAV 只读源 → 扫描 → 搜到文件 → 预览图片/PDF → 流式播放 mp4 → 下载大文件（Range 断点）"；停源后检索仍可用且带 missing/stale 徽章；旧 /api/search /api/ask 回归通过 |
| **V2 体验补全** | Office 预览（docx/xlsx/pptx 尽力档）；缩略图/关键帧图集；跨源合并检索（--nas all 语义入 API）；SMB 原生适配；NFS/iSCSI 接入指南；pg-rebind；MCP 扩展三工具 + Resources/Prompts + 审计日志；备份说明与 export-repo 反向重建 | Word/PDF 扫描件"解析视图"可用（rw 源）；两个来源合并搜索正常；断电重启后 `pg_dump` + 可写源源端 `.naskb` 可完整恢复（系统内无持久产物依赖） |
| **V3 深度能力** | 多用户/角色；MaxKB 扩展包（REQ-R5 系列）；RRF 混合检索；middle.json 版面框；Word 级在线编辑评估（用户已定后置） | 按届时需求再定 |

---

## 9. 决策记录（用户 2026-08-18 逐项确认，全部生效）

| # | 决策点 | 结论 |
|---|---|---|
| 1 | 后端框架 | ✅ 引入 **FastAPI**（OpenAPI 自动文档 + 流式响应 + pydantic 契约收紧） |
| 2 | 前端形态 | ✅ **Vue3 + Vite 静态包**，由服务进程托管，运行时无 Node |
| 3 | 内部产物存储 | ✅ **降格为临时暂存区 `store/tmp/`**：分析中间产物一律不持久保留，入库即清；文档拆出物的标准解析/存储与再组织立项为"二级知识库体系"（REQ-R7-15），本次不做 |
| 4 | 认证起点 | ✅ 单管理员 Bearer token（+匿名只读开关）；多用户后续扩展 |
| 5 | 可写源双写 | ✅ 维持。语义澄清：源端 `.naskb` 是**原始仲裁端**（权威记录），系统内维护**副本 + 后续处理衍生产物** |
| 6 | folder 描述入库 | ✅ 独立 `folders` 表 |
| 7 | 多来源 schema 组织 | ✅ schema 按 NAS 五要素组织，`resources.source_id` 列区分同 NAS 多来源 |
| 8 | 产品命名/版本 | ✅ 全新系统形态，以「NASKB 知识库系统」**v0.1 重新起版** |

> 以上 8 项连同重定位本身记入 requirement.md **ADR-20260818-1**。

---

## 附录 A：需求基线修订（已于 2026-08-18 写入 requirement.md）

### A.1 新增需求组 R7「平台系统化」（v3 重定位）

| 编号 | 需求 | 初始状态 |
|---|---|---|
| REQ-R7-01 | 系统形态：常驻服务，提供 Web UI、REST API、MCP 三出口；CLI/Skill 保留 | 规划中 |
| REQ-R7-02 | 知识自持：PG 为知识权威库（元数据+全文+向量）；分析中间产物不持久保留（临时暂存区用完即清）；源端 .naskb 为可写源的原始仲裁端，系统内为副本+衍生产物 | 规划中 |
| REQ-R7-03 | 来源注册表：sources 表 + 管理 API/UI；注册表即安全边界，资源凭 resource_id 寻址 | 规划中 |
| REQ-R7-04 | 挂载式多协议接入：local/WebDAV（V1）、SMB 直连（V2）、NFS/iSCSI 以 OS 挂载注册为 local（V2） | 规划中 |
| REQ-R7-05 | 只读知识库：access_mode=ro 不写源端；中间产物不留存；删除仅标记 missing_source 不清知识 | 规划中 |
| REQ-R7-06 | 更新校验体系：周期预检（PROPFIND/readdir 零下载）+ 访问时 stat 轻校验 + 手动 verify-hash；状态机 ok/stale_vector/stale_source/missing_source | 规划中 |
| REQ-R7-07 | 下载代理：流式分块转发、Range 断点、ETag=file_hash、filename* 编码；源离线 503+指引 | 规划中 |
| REQ-R7-08 | 在线预览：V1 档矩阵（图片/PDF/音视频原生/文本/MinerU 解析视图/无法查看+下载兜底）；Office 后置 | 规划中 |
| REQ-R7-09 | Web UI：搜索问答、目录树浏览（罗列检索）、文件详情、来源管理、任务中心 | 规划中 |
| REQ-R7-10 | 开放 API：/api/sources /tree /files 族 + 旧 search/ask 契约冻结；OpenAPI 自动文档导出 function schema | 规划中 |
| REQ-R7-11 | 认证：Bearer token（[server.auth]）+ 匿名只读开关；多用户留 V3 | 规划中 |
| REQ-R7-12 | 调度：进程内定时扫描/同步预检/stale 复查（清偿旧"阶段 3 定时同步"） | 规划中 |
| REQ-R7-13 | adopt 收编：存量 .naskb 仓库一键导入系统库；export-repo 反向重建 | 规划中 |
| REQ-R7-14 | 部署纪律：PG 用统一独立实例（192.168.5.2:25432），业务进程不自建数据库/Redis/队列；凭据集中不入镜像 | 现行（全局规则引用） |
| REQ-R7-15 | 二级知识库体系：文档拆出物（图表/段落/实体等）的标准解析、存储与再组织——另行专项设计 | 规划中（本次不做） |

### A.2 状态修正（对现行 requirement.md）

1. §7「已知问题与待办」重写：删除"R4 全部条目待实施"（阶段 0-2 已完成的既成事实）；
2. REQ-R4-01~09、REQ-R4-11~13 状态改为"已实现/部分实现"并注明剩余子项
   （R4-10 预检、R4-11 access_identity、R4-14 rebind 未实现，转入 R7-06/R7-13 承接或保留原号跟踪）；
3. 补录 REQ-R1-14（整理安全）/REQ-R1-15（整理闭环）——reorganize-refactor-plan §6.2 承诺未兑现项；
4. REQ-R1-10 备注"L1/L2 待升级"清除（已按 REQ-R1-13 落地）；
5. 变更历史追加：2026-08-18 v3 重定位（本文档获批后记录）。
