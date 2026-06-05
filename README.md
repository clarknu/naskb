# NASKB — NAS Knowledge Base

本地向量知识库系统，支持 **Skill/CLI** 与 **MCP/Service** 双形态。

## 功能

- **语义检索**: 基于 BGE 嵌入模型 + LanceDB 向量数据库，支持中英文语义搜索
- **双形态部署**: CLI 命令行工具 + MCP 持续服务，按需选择
- **文件监控**: watchdog 实时监控文件变更，自动触发索引更新
- **自描述存储**: `.kbdes/` 隐藏文件夹管理媒体文件描述，支持过期检测
- **GPU 加速**: ONNX Runtime + DirectML，兼容老旧 GPU
- **异步并行**: asyncio + ThreadPoolExecutor，支持高并发索引和检索

## 快速开始

### 安装

```bash
cd naskb/
pip install -e .                # 基础安装
pip install -e ".[directml]"    # + GPU 加速
pip install -e ".[mcp]"         # + MCP 服务
```

### Skill / CLI 模式

```bash
naskb init --work-path D:/NASKB_data
naskb source add "我的笔记" "D:/Documents/Notes"
naskb index --full
naskb search "如何配置数据库"
```

### MCP 服务模式

```bash
python -m naskb.mcp.server                                  # stdio 模式 (IDE)
python -m naskb.mcp.server --transport sse --port 8765      # HTTP 模式
```

## 项目结构

```
naskb/
├── SKILL.md            # Copilot Skill 声明 (3 个工具)
├── MCP.md              # MCP 接口参考手册 (16 个工具)
├── DEPLOY.md           # 部署指南
├── mcp.json            # MCP 配置模板
├── pyproject.toml      # Python 包声明
├── design/             # 设计文档
├── src/naskb/
│   ├── common/         # 共享核心 (embedder, vector_store, config, ...)
│   ├── skill/          # Skill/CLI 实现
│   └── mcp/            # MCP 服务实现
└── tests/              # 34 个测试 (单元 + 端到端)
```

## MCP 工具一览

| # | Tool | 说明 |
|---|------|------|
| 1 | `kb_search` | 语义检索 |
| 2 | `kb_index_full` | 全量索引 |
| 3 | `kb_index_incremental` | 增量索引 |
| 4 | `kb_index_file` | 单文件索引 |
| 5 | `kb_status` | 状态报告 |
| 6 | `kb_list_sources` | 来源列表 |
| 7 | `kb_list_missing` | 缺失描述 |
| 8 | `kb_add_source` | 添加来源 |
| 9 | `kb_remove_source` | 移除来源 |
| 10 | `kb_describe_media` | 媒体描述 (.kbdesc) |
| 11 | `kb_check_stale` | 过期检查 |
| 12 | `kb_start_watcher` | 启动监控 |
| 13 | `kb_stop_watcher` | 停止监控 |
| 14 | `kb_list_jobs` | 任务列表 |
| 15 | `kb_get_job_status` | 任务详情 |

完整接口文档见 → [naskb/MCP.md](naskb/MCP.md)

## 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 嵌入模型 | BGE-base/large-zh-v1.5 | ONNX 格式，768/1024 维 |
| 向量数据库 | LanceDB | 嵌入式，Arrow 列存 |
| 状态管理 | SQLite | WAL 模式，3 元组变更检测 |
| 文件系统 | fsspec | 统一接口，支持 local/webdav/smb |
| GPU 加速 | ONNX Runtime + DirectML | 广泛兼容 DirectX 12 显卡 |
| MCP 框架 | FastMCP | 标准 MCP 协议，stdio/HTTP 传输 |

## 测试

```bash
pip install -e ".[test]"
pytest tests/ -v
```

## License

MIT
