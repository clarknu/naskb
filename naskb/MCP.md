# NASKB MCP Server — 接口参考手册

> 版本: v0.3 | 日期: 2026-06-05 | 工具总数: 16

---

## 1. 概述

NASKB MCP Server 是一个基于 [Model Context Protocol](https://modelcontextprotocol.io/) 的本地向量知识库服务。它提供持续运行的 HTTP/stdio 服务，供 AI 客户端（VS Code Copilot、Claude Desktop 等）通过标准化协议调用。

### 1.1 与 Skill 形态的区别

| | Skill (CLI) | MCP (Service) |
|--|------------|---------------|
| 运行模式 | 命令行，用完即退 | 常驻服务，持续响应 |
| 通信协议 | 标准输入/输出 | JSON-RPC (stdio / HTTP+SSE) |
| 并发能力 | 单进程串行 | 多协程并发 |
| 文件监控 | 需手动触发 | 实时 watchdog 监控 |
| 媒体描述 | 同名 `.md` 文件 | `.kbdes/` 隐藏文件夹 + 自描述 `.kbdesc` |
| 任务管理 | 无 | 异步队列 + 状态查询 |

---

## 2. 部署配置

### 2.1 安装

```bash
cd naskb/
pip install ".[mcp]"       # 包含 mcp + watchdog
```

### 2.2 VS Code 配置

在 VS Code 中创建 `.vscode/mcp.json`：

```json
{
  "mcpServers": {
    "naskb": {
      "command": "python",
      "args": ["-m", "naskb.mcp.server"],
      "env": {
        "NASKB_WORK": "D:/NASKB_data",
        "PYTHONPATH": "./src"
      }
    }
  }
}
```

### 2.3 Claude Desktop 配置

```json
{
  "mcpServers": {
    "naskb": {
      "command": "python",
      "args": ["-m", "naskb.mcp.server"],
      "env": {
        "NASKB_WORK": "D:/NASKB_data",
        "PYTHONPATH": "./src"
      }
    }
  }
}
```

### 2.4 HTTP/SSE 模式（外部网络调用）

```bash
python -m naskb.mcp.server --transport sse --port 8765 --host 0.0.0.0
```

### 2.5 环境变量

| 变量 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `NASKB_WORK` | 是 | 知识库工作路径 | `D:/NASKB_data` |
| `PYTHONPATH` | 推荐 | Python 包搜索路径 | `./src` |

---

## 3. Tools（工具）

### 3.1 工具总览

| # | 工具名 | 用途 | 分类 |
|---|--------|------|------|
| 1 | `kb_search` | 语义检索知识库 | 检索 |
| 2 | `kb_index_full` | 全量重建索引 | 索引 |
| 3 | `kb_index_incremental` | 增量更新索引 | 索引 |
| 4 | `kb_index_file` | 索引单个文件 | 索引 |
| 5 | `kb_status` | 知识库状态报告 | 状态 |
| 6 | `kb_list_sources` | 列出所有知识来源 | 状态 |
| 7 | `kb_list_missing` | 列出缺失描述的文件 | 状态 |
| 8 | `kb_list_jobs` | 列出所有后台任务 | 状态 |
| 9 | `kb_get_job_status` | 查询单个任务详情 | 状态 |
| 10 | `kb_add_source` | 添加知识来源 | 来源管理 |
| 11 | `kb_remove_source` | 移除知识来源 | 来源管理 |
| 12 | `kb_describe_media` | 为媒体文件创建/更新描述 | 媒体管理 |
| 13 | `kb_check_stale` | 检查描述文件过期状态 | 媒体管理 |
| 14 | `kb_start_watcher` | 启动文件实时监控 | 监控 |
| 15 | `kb_stop_watcher` | 停止文件监控 | 监控 |
| 16 | `kb_get_job_status` | 查询后台任务状态 | 任务 |

---

### 3.2 检索

#### `kb_search` — 语义检索

```python
kb_search(
    query: str,              # 必填。自然语言查询，支持中文/英文
    top_k: int = 10,         # 返回结果条数 (1-100)
    threshold: float = 0.5,  # 相似度阈值 (0.0-1.0)
    source_id: str = None    # 限定来源ID，None=全部
) -> str
```

**返回值示例**：
```
找到 3 条相关结果：

1. [0.87] **向量数据库选型.md**
   路径: `D:/Notes/向量数据库选型.md`
   摘要: 对比了 FAISS、ChromaDB、LanceDB 三种向量数据库...

2. [0.72] **database-comparison.md**
   路径: `D:/Notes/database-comparison.md`
   摘要: PostgreSQL vs MySQL vs SQLite for knowledge base...
```

**使用建议**：
- 先用简短查询，无结果时降低 `threshold` 到 `0.3`
- 需要更多结果时调大 `top_k`
- 只想搜特定文件夹时指定 `source_id`

---

### 3.3 索引

#### `kb_index_full` — 全量索引

```python
kb_index_full(
    source_ids: list[str] = None,  # 限定来源列表，None=全部
    force: bool = False            # 是否清除旧索引后重建
) -> str
```

**适用场景**：
- 首次建立知识库
- 索引结构变更后完全重建
- 模型更换后的重新嵌入

**返回值示例**：
```
**全量索引完成**
- 处理来源数: 2
- 扫描文件总数: 1420
- 成功索引: 1385
```

---

#### `kb_index_incremental` — 增量索引

```python
kb_index_incremental(
    source_ids: list[str] = None  # 限定来源列表
) -> str
```

**适用场景**：
- 日常维护，快速同步新增文件
- 修改了少量文件后刷新索引

**原理**：对比文件 `mtime`/`size` 与 `state.db` 中的记录，仅处理变更文件。

---

#### `kb_index_file` — 单文件索引

```python
kb_index_file(
    source_id: str,    # 必填。来源ID
    file_path: str     # 必填。文件绝对路径
) -> str
```

**注意**：
- 文本文件（.md/.txt/.py 等）直接索引内容
- 媒体文件（.jpg/.mp4 等）需要先有 `.kbdesc` 描述文件
- 无描述文件的媒体文件会返回 `missing_desc` 错误，提示使用 `kb_describe_media`

---

### 3.4 状态查询

#### `kb_status` — 状态总览

```python
kb_status(source_id: str = None) -> str
```

**返回值包含**：
- 模型名称与维度
- 推理后端（DirectML/CPU）
- 已索引文件数 / 文件夹数
- 各来源状态统计（已索引 / 待更新 / 缺失描述）
- 后台任务队列状态

---

#### `kb_list_sources` — 来源列表

```python
kb_list_sources() -> str
```

列出所有已配置的知识来源，包括 ID、名称、类型、路径和启用状态。

---

#### `kb_list_missing` — 缺失描述

```python
kb_list_missing(source_id: str = None) -> str
```

列出所有无关联描述文件的媒体文件（二进制文件），按来源分组。

---

### 3.5 来源管理

#### `kb_add_source` — 添加来源

```python
kb_add_source(
    name: str,               # 必填。来源名称（显示用）
    url: str,                # 必填。路径 (D:/Notes 或 webdav://...)
    fs_type: str = "local"   # 文件系统类型: local / webdav
) -> str
```

---

#### `kb_remove_source` — 移除来源

```python
kb_remove_source(source_id: str) -> str
```

仅从配置中移除，不删除实际文件。

---

### 3.6 媒体描述管理

#### `kb_describe_media` — 创建/更新媒体描述

```python
kb_describe_media(
    source_id: str,       # 必填。来源ID
    media_path: str,      # 必填。媒体文件绝对路径
    description: str,     # 必填。Markdown 描述内容
    tags: str = ""        # 逗号分隔的标签
) -> str
```

**描述文件存储位置**：
```
媒体文件夹/
├── photo.jpg              # 媒体文件
└── .kbdes/                # 隐藏描述文件夹
    └── photo.jpg.kbdesc   # 自描述描述文件
```

**`.kbdesc` 文件格式**：包含 YAML 元数据头（生成时间、文件哈希、mime 类型）+ Markdown 内容体。支持自动过期检测。

---

#### `kb_check_stale` — 检查过期描述

```python
kb_check_stale() -> str
```

检查所有 `.kbdesc` 描述文件是否过期（媒体文件已更新但描述未同步），列出需要重新描述的文件。

---

### 3.7 文件监控

#### `kb_start_watcher` — 启动监控

```python
kb_start_watcher(source_ids: list[str] = None) -> str
```

启动实时文件监控。文件变更自动触发增量索引任务。要求安装 `watchdog`。

---

#### `kb_stop_watcher` — 停止监控

```python
kb_stop_watcher(source_ids: list[str] = None) -> str
```

---

### 3.8 任务管理

#### `kb_list_jobs` — 任务列表

```python
kb_list_jobs(
    status_filter: str = "all"
    # "all" | "active" | "pending" | "completed" | "failed"
) -> str
```

每行显示：状态图标 + 任务ID(前8位) + 类型 + 状态 + 目标路径。

**状态图标**：⏳待处理 🔄运行中 ✅已完成 ❌失败 ⛔已取消

---

#### `kb_get_job_status` — 任务详情

```python
kb_get_job_status(job_id: str) -> str
```

**返回值包含**：类型、状态、来源、目标路径、进度百分比、耗时、预估剩余时间、错误信息。

---

## 4. Resources（资源）

MCP Resources 是服务器暴露的只读数据端点，客户端可以主动拉取。

### `naskb://config`

获取 NASKB 当前配置摘要（模型名称、向量维度、推理后端、数据库路径等）。

### `naskb://stats`

获取 NASKB 运行时统计（已索引文件数、待更新数、活跃任务数等）。

---

## 5. Prompts（提示模板）

MCP Prompts 是预定义的提示词模板，帮助 AI 客户端更好地使用知识库。

### `search_prompt`

输入查询词，生成结构化的搜索提示。

```
请在 NASKB 知识库中搜索关于「{query}」的相关内容。
使用 kb_search 工具进行语义检索，返回最相关的结果。
```

### `organize_knowledge_prompt`

生成知识库整理检查清单。

```
请帮我整理 NASKB 知识库：
1. 使用 kb_check_stale 检查过期的描述文件
2. 使用 kb_list_missing 查看缺失描述的媒体文件
3. 使用 kb_index_incremental 更新索引
4. 使用 kb_status 确认最终的索引状态
```

---

## 6. 典型工作流

### 6.1 新建知识库

```
1. kb_add_source "我的文档" "D:/Documents"      → 添加来源
2. kb_index_full                                   → 全量索引
3. kb_status                                       → 确认状态
4. kb_start_watcher                                → 开启监控
```

### 6.2 日常使用

```
1. kb_search "如何配置数据库连接池"                  → 搜索
2. kb_list_missing                                 → 检查缺失描述
3. kb_index_incremental                            → 增量同步
4. kb_list_jobs "active"                           → 查看后台任务
```

### 6.3 管理媒体文件

```
1. kb_list_missing                                  → 找出无描述的媒体文件
2. kb_describe_media "photos" "D:/photo.jpg"        → 为照片添加描述
   "桂林漓江的日落风景照片，前景有竹筏和渔民"
3. kb_index_file "photos" "D:/photo.jpg"            → 手动触发单文件索引
4. kb_check_stale                                   → 定期检查描述是否过期
```

---

## 7. 错误处理

| 错误信息 | 原因 | 解决 |
|----------|------|------|
| `Source not found: xxx` | 来源ID不存在 | 用 `kb_list_sources` 查看正确ID |
| `File not found: xxx` | 文件路径错误 | 确认使用绝对路径 |
| `missing_desc` | 媒体文件无 .kbdesc 描述 | 用 `kb_describe_media` 创建描述 |
| `描述文件已过期` | 媒体文件已更新但描述未同步 | 重新执行 `kb_describe_media` |
| `watchdog not installed` | 未安装文件监控依赖 | `pip install watchdog` |
| `config.toml not found` | 工作路径未初始化 | 先运行 `naskb init --work-path ...` |

---

## 8. 架构说明

```
┌──────────────────────────────────────────────────┐
│ AI 客户端 (VS Code / Claude Desktop / Cursor)     │
│                    │ JSON-RPC                     │
├────────────────────┼──────────────────────────────┤
│ NASKB MCP Server   │                              │
│   ├─ 16 Tools      │  kb_search / kb_index / ... │
│   ├─ 2 Resources   │  config / stats              │
│   └─ 2 Prompts     │  search / organize           │
│                    │                              │
│   ┌────────────────┴──────────────────┐           │
│   │  AsyncIndexer                     │           │
│   │  (异步批量嵌入 + .kbdesc 集成)    │           │
│   └────────────────┬──────────────────┘           │
│   ┌────────────────┼──────────────────┐           │
│   │  JobQueue ◄────┤                  │           │
│   │  (任务队列)     │  FileWatcher     │           │
│   │                │  (watchdog)      │           │
│   └────────────────┴──────────────────┘           │
├──────────────────────────────────────────────────┤
│ Common Layer                                      │
│   Embedder(ONNX)  VectorStore(LanceDB)            │
│   StateManager(SQLite)  Scanner  Config           │
└──────────────────────────────────────────────────┘
```
