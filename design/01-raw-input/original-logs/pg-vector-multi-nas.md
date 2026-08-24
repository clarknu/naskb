# NASKB 多 NAS 向量库设计（PostgreSQL + pgvector）

> 状态：设计稿 v2（2026-08 已确认，待实施）
> 依据需求：REQ-R4 全系列（`design/requirement.md`）；ADR-20260816-3
> 目标：把 NASKB 的语义向量检索从"本地 numpy 快照"升级为"PG + pgvector 多 NAS 独立向量库"，
> 同时保留现有 numpy/BM25 后端作为离线兜底。
>
> v2 变化：① NAS 身份增加**用户账号**维度（不同账号视图不同）；
> ② 新增**数据一致性体系**（哈希校验 + 三层版本对齐 + 条目增删改同步机制）。

## 1. 背景与目标

现状（已实现）：
- 内容处理：`.naskb/` 描述仓库（`index.json` 每文件一条 `FileEntry`：summary/category/tags/
  content_description/transcription/ocr_text/file_hash/original_path 等；`meta.json` 存 schema 版本）。
- 检索索引：`desc index-vectors` 用本机 bge-small-zh-v1.5 把"摘要+描述"编码为 512 维向量，
  存工作区 `db/vectors.npz + vectors.json`，检索 = numpy 全量余弦。无向量索引时降级 BM25。
- 服务：`desc serve`（Web UI + `/api/search` `/api/ask`）。

目标（本次设计）：
1. **一个工具支持多个 NAS**；每个 NAS 一个**独立向量库**；
2. NAS 身份 = **协议 + 主机 + 端口 + 用户账号**（同一 NAS 不同账号的视图可能不同，必须分开）；
3. 资源按 NAS 内**目录（分类文件夹）组织结构**保存；
4. 每条向量至少包含：① 向量数据；② 用于向量化的内容摘要；③ 完整文本内容（不含二进制原始数据）；
   ④ 指向的原始 NAS 资源。任何一条向量都可对应回 NAS 里的一个文件；
5. **哈希校验体系**：向量库条目能回答"我对应的是哪个文件版本、该版本是否已过期"；
   抽取 → 入库全链路有**增/删/改/移 的同步机制**，与 NAS 最新文件状态对齐。

约束（沿用既有决策，不推翻）：
- 向量化输入只用"摘要+描述"（用户 2026-08-11 拍板）；全文仅作 RAG 上下文/存证，不参与索引。
- 不做文档级 chunking：一个文件一条向量。
- 二进制（图片/音频/视频）不存原始字节：其"完整内容"= 已抽取的文本（描述 + 转写 + OCR 文本）。

## 2. 总体架构

```
NAS (webdav://hostA:5006)
  ├─ 账号 alice 看到的视图 ──► .naskb 仓库 A（meta 记录采集身份 alice）
  └─ 账号 bob   看到的视图 ──► .naskb 仓库 B（meta 记录采集身份 bob）
         │                              │
         ▼                              ▼
  naskb desc sync-vectors <root> --nas <alias>   （本机 bge-small-zh 编码）
         │                              │
   ┌─────▼──────────────────────────────▼──────────────────────────┐
   │  PostgreSQL 18 + pgvector 0.8.6（192.168.5.2:25432）            │
   │  database: naskb                                                │
   │  ├─ public.nas_registry                 ← NAS 注册表（全局）      │
   │  ├─ schema: nas_webdav_192_168_5_2_5006_u3f9a2b1c4d5e  ← alice 库 │
   │  │    ├─ resources（资源/目录结构/哈希/新鲜度状态）              │
   │  │    └─ vectors（vector(512) + 摘要 + 全文 + 源哈希）           │
   │  ├─ schema: nas_webdav_192_168_5_2_5006_ua7e4f0c9b2d1a  ← bob 库 │
   │  └─ …                                                           │
   └────────────────────────────────────────────────────────────────┘
         ▲
   desc search/ask/serve（--pg / serve 内选 NAS）→ 检索指定 NAS 的 schema
         ▲
   无 PG 可用时：回退现有 numpy npz（单 NAS 本地）+ BM25 —— 现状保持不变
```

分层原则：**NAS 文件是事实源；`.naskb/` 是抽取快照（唯一工作事实）；PG 是可重建的派生库**。
PG 挂了不影响 `analyze`/`desc search --no-vector` 等既有功能。

## 3. NAS 身份模型（五要素）

### 3.1 身份要素与归一化

| 要素 | 归一化规则 | 示例 |
|---|---|---|
| protocol | 小写；枚举 `webdav` / `local`（将来可扩 `smb`） | `webdav` |
| host | 小写、去尾随点；IPv6 用 `[ ]` 包裹；local 固定为 `local` | `192.168.5.2` |
| port | 整数；缺省按协议默认（webdav http=80 / https=443，local=0） | `5006` |
| user | 账号名原样保留（大小写敏感，如群晖账号区分大小写）；**不参与明文 schema 名**，只以哈希入名 | `alice` |

- **五要素相同 = 同一个 NAS 视图库**。不同账号即使看到重叠文件，也各自成库（权限视图语义）。
- URL 路径、共享目录挂载点不算身份（属于资源定位）。
- 工具内部主键 `nas_id`（UUID）；五要素是身份判定依据。

### 3.2 schema 命名

```
nas_<protocol>_<host>_<port>_u<hash12>
# host 中非 [a-z0-9] 替换为下划线；hash12 = sha1(user)[:12]（账号不进明文，避免凭据泄露面）
# 例：webdav + 192.168.5.2 + 5006 + alice → nas_webdav_192_168_5_2_5006_u<sha1(alice)[:12]>
```

总长超 63（PG 标识符上限）时整体替换为 `nas_<sha1(五要素)[:24]>` 的确定性降级。
schema 名从五要素可确定性算出，registry 丢失可自愈。

### 3.3 注册表（public.nas_registry）

```sql
CREATE TABLE nas_registry (
  nas_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  protocol    text NOT NULL,
  host        text NOT NULL,
  port        int  NOT NULL,
  username    text NOT NULL,
  schema_name text NOT NULL UNIQUE,
  label       text NOT NULL DEFAULT '',
  root_hint   text NOT NULL DEFAULT '',
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (protocol, host, port, username)
);
```

- `username` 存明文仅在 PG 内部表（PG 本身是凭据级系统，可接受）；schema 名只含其哈希。
- 后续支持 `pg-rebind`：主机迁移（IP 变更）时把旧 schema 重新绑定到新五要素（改名 + registry 更新）。

### 3.4 采集身份落盘（.naskb/meta.json）

`.naskb` 仓库是"哪个账号看到的视图"，身份必须固化在快照里，否则无法判断快照属于谁：

```json
{
  "schema": "naskb-index-v2",
  "updated_at": "…",
  "access_identity": {
    "protocol": "webdav",
    "host": "192.168.5.2",
    "port": 5006,
    "user": "alice",
    "webdav_path": "/homes/alice"
  }
}
```

- `desc analyze-tree` 时写入（从 config / 命令行连接参数推导）；
- `sync-vectors` 校验 `.naskb` 的 access_identity 与目标 NAS 五要素一致，**不一致拒绝同步**
  （防串库：同一目录换了账号访问时告警，而不是悄悄把 bob 的内容混进 alice 的库）。

## 4. 每 NAS schema 的表设计

### 4.1 `resources` — 资源表（NAS 文件 + 目录结构 + 版本指纹）

```sql
CREATE TABLE resources (
  resource_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rel_path     text NOT NULL,           -- 相对 NAS 视图根的路径（正斜杠）
  parent_dir   text NOT NULL,           -- 目录部分，LIKE 前缀查询目录用
  name         text NOT NULL,
  kind         text NOT NULL DEFAULT 'file',
  category     text NOT NULL DEFAULT '',
  tags         text[] NOT NULL DEFAULT '{}',
  summary      text NOT NULL DEFAULT '',
  content_description text NOT NULL DEFAULT '',
  file_type    text NOT NULL DEFAULT '',
  -- ── 版本指纹（哈希校验体系核心，ADR-20260816-4）──
  file_hash    text NOT NULL DEFAULT '',  -- .naskb 抽取时算的内容哈希（sha256，采样规则见 hash_algorithm）
  hash_algorithm text NOT NULL DEFAULT 'sha256:sample8x64k',  -- sha256:full | sha256:sample8x64k
  mtime        double precision NOT NULL DEFAULT 0,  -- 抽取时的最后修改时间（epoch 秒）
  ctime        double precision,                     -- 抽取时的创建时间；WebDAV 缺失为 NULL（NULL=不可免检）
  size_bytes   bigint NOT NULL DEFAULT 0,            -- 抽取时的文件大小
  analyzer_version text NOT NULL DEFAULT '',
  analyzed_at  timestamptz,
  -- ── 新鲜度状态 ──
  status       text NOT NULL DEFAULT 'ok',   -- ok | stale_source | stale_vector（见 §5.3）
  prev_hashes  jsonb NOT NULL DEFAULT '[]',  -- 历史指纹：[{hash, analyzed_at, replaced_at}]（审计旧版本）
  synced_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (rel_path)
);
CREATE INDEX idx_resources_parent ON resources (parent_dir);
CREATE INDEX idx_resources_status ON resources (status);
```

### 4.2 `vectors` — 向量表

```sql
CREATE TABLE vectors (
  vector_id    bigserial PRIMARY KEY,
  resource_id  uuid NOT NULL REFERENCES resources(resource_id) ON DELETE CASCADE,
  model        text NOT NULL,           -- 编码模型（bge-small-zh-v1.5）
  dim          int  NOT NULL,           -- 512
  embedding    vector(512) NOT NULL,    -- ① 向量数据
  summary_text text NOT NULL,           -- ② 用于向量化的内容摘要（=Doc.text）
  full_text    text NOT NULL DEFAULT '',-- ③ 完整文本内容（无二进制）
  source_hash  text NOT NULL DEFAULT '',-- 该向量对应的文件版本哈希（=生成时的 resources.file_hash）
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (resource_id, model)
);
CREATE INDEX idx_vectors_embedding ON vectors USING hnsw (embedding vector_cosine_ops);
```

- ④ 指向原始 NAS 资源：`resource_id → resources.rel_path`；schema 即 NAS 身份（五要素）。
- **`source_hash` 是"这条向量描述的是哪个文件版本"的直接答案**——需求"原数据知道自己对应的是老版本文件"。
  检索/问答返回时附带，与资源当前 `file_hash` 不一致即向用户提示"内容可能已过期"。

### 4.3 检索 SQL（单 NAS）

```sql
SELECT r.rel_path, r.category, r.tags, r.summary, r.status,
       r.file_hash, v.source_hash, v.summary_text, v.full_text,
       1 - (v.embedding <=> %s::vector) AS score
FROM vectors v JOIN resources r ON r.resource_id = v.resource_id
WHERE v.model = %s
ORDER BY v.embedding <=> %s::vector
LIMIT %s;
```

## 5. 数据一致性体系（哈希校验 + 同步机制）

### 5.1 三层版本对齐链

```
NAS 文件（真源：内容 + mtime + size）
   │  analyze-tree（现有增量：hash 对比）
   ▼
.naskb 条目（快照：file_hash + mtime + size + analyzed_at + analyzer_version）
   │  sync-vectors（本设计：增量同步 + 元数据预检）
   ▼
PG 行（resources 指纹 + vectors.source_hash + status）
```

任何一层与上游不一致，都能被检出并传播为"过期"标记。

### 5.2 指纹四元组与三级判定链（ADR-20260816-4）

**指纹四元组**（判定"原数据与文件是否一致"的全部依据）：

| 要素 | 获取成本（WebDAV） | 作用 |
|---|---|---|
| `size` | PROPFIND，零下载 | 快速否决 |
| `mtime` | PROPFIND，零下载 | 快速否决 |
| `ctime` | PROPFIND（creationdate，可能缺失） | **免检必要条件**：缺失则不得免检 |
| 内容采样 hash | 8 个 Range 请求（≤512KB） | 最终裁决 |

**内容 hash 采样规则**（防"头相同、后不同"的伪装文件）：
- 文件 ≤512KB：全量 sha256 → `hash_algorithm = sha256:full`
- 文件 >512KB：8 段 × 64KB 均匀分布，第 i 段（i=0..7）起始偏移
  `start_i = i * (S - 65536) // 7`（整数运算；i=0 即文件头，i=7 即文件尾；
  位置仅由 size 决定，同大小文件永远同位置）；按序喂入 sha256 → `sha256:sample8x64k`
- 段间允许轻微重叠（S 略大于 512KB 时），无害；规则简单优先
- WebDAV 用 HTTP Range 请求取段（不支持 Range 的文件报错重试，不静默降级）

**三级判定链**（analyze-tree 对每个已有条目）：

```
L1 免检：path+name+size+mtime 一致 且 ctime 两侧均可取且一致 → 跳过一切（零下载）
        （ctime 任一侧缺失/不一致 → 不得免检）
L2 hash 复核：算采样 hash 对比 .naskb →
        一致 → 回写 stat 字段（补记 ctime），跳过重析；不一致 → L3
L3 重析：内容真的变了 → 走完整 analyze（摘要/OCR/转写/向量化全部重做），更新全部字段
```

- 旧数据迁移：历史条目无 ctime → 首次升级后全部走一次 L2（WebDAV 每文件 8 个 Range 请求，
  一次性成本），补记 ctime 后进入 L1 常态。
- 深度兜底：`--verify-hash` 全量 hash 校对（本地用全文件 sha256；WebDAV 全量下载，
  贵，仅定期/手动）——覆盖"同秒修改+同大小"等采样盲区。
- 免检的残余风险声明：mtime 秒级粒度下"同秒修改且 size 不变"理论上可漏检；
  由 L2 的采样 hash 与 `--verify-hash` 兜底，不作为默认路径的完整保证。

### 5.3 状态机（resources.status）

| 状态 | 含义 | 触发 | 处理 |
|---|---|---|---|
| `ok` | 三层一致：PG = .naskb = NAS 现状 | 正常同步完成 | — |
| `stale_vector` | NAS 未变，但 .naskb 已重析（hash 变）PG 未更新 | sync 发现 .naskb hash ≠ PG hash | 重嵌向量，状态回 ok |
| `stale_source` | NAS 文件 mtime/size 与 .naskb 不一致（源已变，快照落后） | sync 预检发现 | 不入库/保留旧行但标 stale；提示先跑 analyze-tree |

检索/问答输出带 `status`；`stale_source` 的条目在 ask 上下文头部附加
"⚠️ 该内容对应的源文件可能已更新，以下为旧版本内容"。

### 5.4 同步机制（增/删/改/移 四操作）

`naskb desc sync-vectors <root> [--nas <alias>] [--rebuild] [--verify-hash]`

预检（每 NAS 视图根目录）：PROPFIND 遍历取 mtime/size/creationdate → 与 .naskb 对比，产出"疑似变化清单"；
若有变化且未加 `--force` → 只把对应条目标 `stale_source`，其余正常同步。

以 schema 内 `rel_path` 为键对比 `.naskb`：

| 情况 | 判定 | 操作 |
|---|---|---|
| .naskb 有、PG 无 | **增** | 编码 → 插 resources + vectors |
| 双方有、hash 同 | 一致 | 跳过 |
| 双方有、hash 不同 | **改** | 旧 hash 追加进 prev_hashes → 重嵌 → 更新两行 |
| .naskb 无、PG 有 | 疑似**删** | 按 hash 在全 schema 找匹配行：找到 → 判为**移**（保留 resource_id 与向量，更新 rel_path）；找不到 → **删**（级联删向量） |
| `--rebuild` | — | 清空 schema 全量重建（模型更换/结构升级用） |
| `--verify-hash` | — | 对疑似变化文件下载内容重算 sha256 确认（贵，按需） |

- **移动跟随**：利用 hash 匹配区分"移动"与"删除+新增"，引用（resource_id）稳定，
  与现有 `.naskb` moved_from/original_path 溯源机制呼应。
- 批量提交（200 条/批）；单条失败记日志不中断；结束打印 added/updated/moved/deleted/stale 统计。
- `desc sync-status <root>`：只读一致性报告——三层 hash 对比清单，不写任何数据。

### 5.5 版本历史（"老版本"可回答）

- `resources.prev_hashes` 审计链：每次内容变更把旧指纹 + 时间入列（保留最近 N 版，如 20）；
- `vectors.source_hash` 让每条向量自证版本；
- 满足"原数据知道自己对应的是老版本文件，而新文件已经被更新了"的语义：
  PG 里能查到"当前向量基于 hash X，资源最新 hash 是 Y（X≠Y，且 Y 已重新抽取/未重新抽取）"。

## 6. 检索接入（命令与 serve）

| 入口 | 行为 |
|---|---|
| `desc search <q> --pg [--nas <alias>]` | 走 PG；`--nas` 缺省 = 当前 root 对应 NAS；`--nas all` = 每库取 top-k 合并（分数不跨库比较） |
| `desc ask <q> --pg` | PG top-k → summary_text+full_text 组上下文（附 status 过期提示）→ DeepSeek 生成；来源显示 `别名 + rel_path` |
| `desc serve` | NAS 下拉（registry + config 别名）；引擎徽章 `pg-<schema>`；`/api/search` `/api/ask` 增加可选 `nas` 字段；结果带 status 徽章 |
| 无 PG / 连接失败 | 回退 numpy 向量 → BM25（现状保留） |

## 7. 配置与代码改动点

```toml
[pg]
host = "192.168.5.2"
port = 25432
user = "naskb"                # 专用账号（最小权限），不用 postgres
password = ""
database = "naskb"

[[nas]]
alias = "home"
protocol = "webdav"
host = "192.168.5.2"
port = 5006
username = "alice"            # ← 身份第五要素
root_path = "/homes/alice"

[[nas]]
alias = "local"
protocol = "local"
host = "local"
port = 0
username = ""
root_path = "C:/NAS_local"
```

代码结构：

```
naskb/scripts/naskb/common/
├── pgstore.py        ← 新增：连接、registry、schema/DDL、sync（预检/四操作）、pg_search、sync-status
├── serve.py          ← 修改：后端选择链 pg → numpy → bm25；nas 参数；status 徽章
├── desc_store.py     ← 修改：meta.json 增 access_identity 读写
├── vector_index.py   ← 不动（离线兜底）
└── config.py         ← 修改：[pg] 与 [[nas]] 解析
naskb/scripts/naskb/skill/cli.py
└── 新增 sync-vectors / sync-status / pg-status；search/ask 加 --pg/--nas；serve 加 --nas-default
```

依赖：`psycopg[binary]` 入 pyproject（已验证 3.3.4 连 PG 18）。密码明文存 config（与现有 key 同策略），
代码/日志绝不打印连接串与密码。

## 8. 其他可琢磨/优化的点（按性价比排序）

1. **混合检索（RRF）**：PG 18 自带全文检索——给 `summary_text` 建 tsvector 列（仍只含摘要文本，
   遵守"全文不进索引"决策），向量 top-k 与关键词 top-k 做 Reciprocal Rank Fusion 融合排序。
   成本低、检索质量提升明显，可作为阶段 2 的可选增强。
2. **模型版本管理**：`vectors.model` 已是版本键；补充规则——模型配置（量化/归一化）编入 model 名；
   换模型 = 新 model 行共存 → 全量重嵌后台跑 → 切换 `当前模型` 配置 → 删除旧模型行。
   `analyzer_version` 同理会触发重析重嵌。
3. **账号视图重叠去重（观察点）**：同一 NAS 两个账号的库，同 rel_path+hash 的文件会出现两份向量
   ——语义正确（视图隔离），但存储有冗余；暂不做跨 schema 去重，先记录观察，量大再议。
4. **serve 访问控制**：serve 无登录体系；NAS 下拉只展示 config 里配置的别名（当前事实上的控制）。
   若将来 serve 对局域网多人开放，需要加访问口令（`[serve] token`）——列为后续项。
5. **安全面变化**：full_text 全文集中进 PG = 新的敏感信息面。缓解：PG 专用账号最小权限、
   `[exclusions]` 沿用（敏感目录不进分析即不进库）、PG 不暴露公网。
6. **备份策略**：PG 是派生库（可重建），备份重点仍是 `.naskb` 快照 + config；PG 用 `pg_dump`
   定期导出可选。灾难恢复顺序：恢复 .naskb → 全量 `sync-vectors --rebuild`。
7. **性能预留**：HNSW 默认参数（m=16, ef_construction=64）起步；条数上万后按需调 ef_search；
   同步端批量编码复用现有 Embedder（本机 CPU），PG 端用 executemany 批量写。
8. **hash 边界记录**：采样 hash 规则（sha256:full / sha256:sample8x64k）记录于 `hash_algorithm`；
   规则变化必须升版本并全量重析，否则全库指纹不可比——sync 预检校验 algorithm 一致性并告警。

## 9. 实施阶段

| 阶段 | 内容 | 验收 |
|---|---|---|
| 0 PG 初始化 | CREATE EXTENSION vector；建 naskb 库 + 专用账号；512 维冒烟（建临时表测完删） | 余弦 top-1 正确 |
| 1 存储层 | pgstore.py：registry、schema/DDL、sync（预检+四操作+状态机）、sync-status | 集成测试（真实 PG，无 PG 跳过）；全量同步 + 二次同步 0 变化 + 模拟改/删/移各自正确 |
| 2 检索接入 | search/ask/serve PG 后端 + 多 NAS + status 徽章 + 回退链 | 端到端：serve 选 NAS 检索/问答命中；停 PG 回退 numpy 正常 |
| 3 收尾 | 定时同步、SKILL/README 更新、备份说明 | 文档齐全 |

## 10. 待确认的决策点

1. **五要素身份**：账号（user）并入 NAS 身份 → 同一 NAS 不同账号各自独立向量库。确认？
2. **folder 条目**：`.naskb/folder.json` 目录级描述本轮不进向量库（严格"向量↔文件"一一对应），
   需要"搜目录"时再扩展 `kind='folder'`。确认？
3. **删除策略**：PG 端物理删除（级联）+ prev_hashes 审计链保留历史指纹。确认？
4. **stale 预检默认开启**：sync 每次做 PROPFIND mtime/size 预检（NAS 遍历成本）；
   疑似变化的条目只标记不重析（重析是 analyze-tree 的事）。确认？
5. **跨 NAS 检索**：`--nas all` 每库 top-k 合并，不做跨库分数比较。确认？
6. **专用账号**：授权我在 PG 上创建 `naskb` 库 + 专用账号（最小权限）？
7. 25432 的 PG 是容器还是裸装？（影响备份建议）
