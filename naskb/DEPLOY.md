# NASKB 部署指南

## 项目文件说明

```
naskb/                    # 项目根（可分发）
├── SKILL.md              # Copilot Skill 声明（Skill 形态使用）
├── MCP.md                # MCP 接口参考手册（MCP 形态使用）
├── mcp.json              # MCP 配置模板（复制到 .vscode/ 使用）
├── pyproject.toml        # Python 包声明 + 依赖 + 入口点
└── src/                  # 源代码
    └── naskb/
        ├── common/       # 共享核心（Skill + MCP 均依赖）
        ├── skill/        # Skill/CLI 实现
        └── mcp/          # MCP 服务实现

.vscode/
└── mcp.json              # VS Code 当前激活的 MCP 配置
```

---

## 部署 Skill (CLI) 形态

### 1. 安装

```bash
cd naskb/
pip install -e .                # 开发模式安装
# 或
pip install ".[directml]"       # 生产安装 + GPU 加速
```

### 2. 初始化

```bash
naskb init --work-path D:/NASKB_data
naskb source add "我的文档" "D:/Documents"
naskb index --full
```

### 3. 分发

打包为 Copilot Skill 时，只需分发以下文件：
```
naskb/
├── SKILL.md
├── pyproject.toml
└── src/naskb/
    ├── common/
    └── skill/
```

mcp/ 目录在 Skill 部署时不需要。

---

## 部署 MCP (Service) 形态

### 1. 安装（含 MCP 依赖）

```bash
cd naskb/
pip install -e ".[mcp, directml]"
```

### 2. 配置 MCP 服务器

复制 `naskb/mcp.json` 到 VS Code 配置位置：

```bash
# VS Code: 复制到 .vscode/mcp.json
cp naskb/mcp.json .vscode/mcp.json

# Claude Desktop: 编辑 ~/Library/Application Support/Claude/claude_desktop_config.json
```

### 3. 启动

```bash
# stdio 模式（IDE 集成）
python -m naskb.mcp.server

# HTTP/SSE 模式（外部网络调用）
python -m naskb.mcp.server --transport sse --port 8765 --host 0.0.0.0
```

### 4. 分发

打包 MCP 服务器时：
```
naskb/
├── MCP.md
├── mcp.json
├── pyproject.toml
└── src/naskb/
    ├── common/
    └── mcp/
```

skill/ 目录在 MCP 部署时不需要。

---

## 配置优化

### config.toml 推荐配置

```toml
[model]
name = "bge-large-zh-v1.5"   # MCP 推荐 large（精度优先）
execution_provider = "directml"
batch_size = 32
intra_op_threads = 4           # 单次推理内部并行线程数
inter_op_threads = 1           # 计算图节点并行（通常设 1）
hf_endpoint = ""               # 留空使用官方源，或填镜像如 https://hf-mirror.com

[db]
path = "db/"

[state]
path = "state.db"
```

### 模型下载加速

如果 HuggingFace 官方源下载慢，设置镜像：

```toml
[model]
hf_endpoint = "https://hf-mirror.com"
```

或设置环境变量：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### 推理并发调优

| 参数 | 作用 | 建议值 |
|------|------|--------|
| `intra_op_threads` | 单个推理操作的内部并行 | CPU 核心数 / 2 |
| `inter_op_threads` | 计算图节点间并行 | 1（通常不需要） |
| `batch_size` | 批量嵌入大小 | 16-64 |

---

## MCP 接口说明

使用者查看 **MCP.md** 即可了解全部接口：
- 16 个 Tools 的完整签名和参数
- 2 个 Resources（config / stats）
- 2 个 Prompts（search / organize）
- 典型工作流和错误处理
