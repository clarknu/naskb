---
name: naskb
description: >
  NASKB 本地向量知识库。语义检索本地文档、NAS 文件、笔记、媒体文件描述。
  支持中英文查询，代码与数据分离，自带 Python 环境，不污染系统。
  提供 Skill (CLI) 与 MCP (持续服务) 双形态。
tools:
  - naskb_search
  - naskb_status
  - naskb_index
applyTo: "*"
---

# NASKB — 本地向量知识库

## 概述

NASKB 是纯本地运行的向量知识库系统，提供两种形态：

| 形态 | 模式 | 适用 | 入口 |
|------|------|------|------|
| **Skill** | CLI | 一次性操作 | `naskb` |
| **MCP** | 持续服务 | AI 集成、实时监控 | `naskb-mcp` |

## 快速开始

```bash
# Skill / CLI
naskb init --work-path D:/NASKB_data
naskb source add "笔记" "D:/Notes"
naskb index --full
naskb search "关键词"

# MCP 服务
pip install ".[mcp]"
python -m naskb.mcp.server
```

---

## Skill 工具

### naskb_search
```python
naskb_search(query: str, top_k: int = 10, threshold: float = 0.5) -> str
```
语义检索。`threshold` 范围 0.0~1.0。

### naskb_status
```python
naskb_status() -> str
```
索引进度、已索引数、缺失描述统计。

### naskb_index
```python
naskb_index() -> str
```
增量索引，仅处理新增/变更文件。

---

## MCP 工具

> **完整接口参考手册 → [MCP.md](./MCP.md)**
> 16 个工具 + 2 个资源 + 2 个提示模板，含签名、参数、返回值示例、工作流。

| # | Tool | 说明 |
|---|------|------|
| 1 | `kb_search` | 语义检索 |
| 2 | `kb_index_full` | 全量索引 |
| 3 | `kb_index_incremental` | 增量索引 |
| 4 | `kb_index_file` | 单文件索引 |
| 5 | `kb_status` | 状态报告 |
| 6 | `kb_list_sources` | 来源列表 |
| 7 | `kb_list_missing` | 缺失描述 |
| 8 | `kb_list_jobs` | 后台任务 |
| 9 | `kb_get_job_status` | 任务详情 |
| 10 | `kb_add_source` | 添加来源 |
| 11 | `kb_remove_source` | 移除来源 |
| 12 | `kb_describe_media` | 媒体描述 (.kbdesc) |
| 13 | `kb_check_stale` | 描述过期检查 |
| 14 | `kb_start_watcher` | 启动监控 |
| 15 | `kb_stop_watcher` | 停止监控 |

---

## 配置

### MCP 部署 (mcp.json)
```json
{
  "mcpServers": {
    "naskb": {
      "command": "python",
      "args": ["-m", "naskb.mcp.server"],
      "env": { "NASKB_WORK": "D:/NASKB_data", "PYTHONPATH": "./src" }
    }
  }
}
```

### config.toml (工作路径下)
模型选择、GPU 方案、数据库路径、排除规则。

## 环境变量

| 变量 | 用途 |
|------|------|
| `NASKB_WORK` | 工作路径 |
| `NASKB_HOME` | 代码目录 |
