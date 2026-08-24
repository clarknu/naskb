# NASKB — 本地知识库 Skill 系统设计规格

> 版本: v0.2  
> 状态: 草稿  
> 最后更新: 2026-06-04

---

## 1. 项目概述

### 1.1 项目名称

**NASKB** — NAS Knowledge Base，一个面向个人/团队知识管理的本地向量知识库系统，封装为 VS Code Copilot Skill，通过 CLI 即可完成全部操作。

### 1.2 核心目标

构建一个**纯本地运行、零外部服务依赖、中文友好**的向量知识库。以文件系统为数据源，自动索引文本文件与媒体文件的描述信息，支持灵活检索与增量更新。

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **零服务依赖** | 不启动任何守护进程/服务，全部通过 CLI 命令完成 |
| **本地优先** | Embedding 模型与向量数据库均本地运行 |
| **自包含运行** | Skill 自带完整 Python 运行环境，不依赖系统 Python 包 |
| **代码与数据分离** | 代码只读，所有数据（数据库、配置、模型）存储在用户指定路径 |
| **中文友好** | 模型选型以中文语义理解为首要指标 |
| **广泛 GPU 兼容** | 优先支持 Vulkan / DirectML 等通用 GPU 加速 API，兼容老旧显卡 |
| **文件即数据** | 以文件系统为唯一数据源，保持"所见即所得" |

---

## 2. 技术选型

### 2.1 向量化模型 (Embedding)

#### 2.1.1 模型选择

**最终模型在 `bge-large-zh-v1.5` 与 `bge-base-zh-v1.5` 之间以实测结果为准。**

| 候选模型 | 维度 | 中文支持 | Token 上限 | 模型大小 | 推荐用途 |
|----------|------|----------|------------|----------|----------|
| `bge-large-zh-v1.5` | **1024** | ★★★★★ | 512 | ~326 MB | 精度优先，GPU 推理 |
| `bge-base-zh-v1.5` | **768** | ★★★★★ | 512 | ~102 MB | 速度优先，CPU/GPU 均可 |

- 两个模型均转为 ONNX 格式运行，方便在多种 GPU 后端间切换。
- 维度更高（768 / 1024）意味着更丰富的语义表达，对中文检索更有利。
- 长文本策略：超过 512 token 的内容采用**分段嵌入 + 均值池化**，使单文件始终对应一个向量。

#### 2.1.2 GPU 推理运行时

核心约束：需兼容**不支持最新 CUDA Compute Capability** 的老旧 GPU，优先走 Vulkan / DirectML / OpenGL 等通用 3D/GPU 计算 API。

**方案：ONNX Runtime + 多 Execution Provider 自适应**

```
优先级: DirectML → CPU (最终保底)
```

| Execution Provider | 底层 API | 适用场景 | 兼容性 |
|--------------------|----------|----------|--------|
| **DirectML** | DirectX 12 | Windows，几乎所有 DX12 显卡 | ★★★★★ 最广泛 |
| **OpenVINO** | OpenCL / Vulkan | Intel 集显 + 部分独显 | ★★★☆ |
| **CPU (默认)** | — | 无 GPU 或 GPU 不支持时 | ★★★★★ 始终可用 |

- **DirectML** 是 Windows 上兼容性最好的 GPU 加速方案，从 2015 年后的几乎所有显卡都支持 DX12。
- ONNX Runtime 的 DirectML EP 已成熟稳定，无需额外安装驱动 SDK。
- 模型导出为 ONNX 格式后，同一份模型文件可在不同 EP 间无缝切换。
- 仅在模型导出阶段使用 PyTorch + HuggingFace Optimum；**运行时零 PyTorch 依赖**。

**备选路线**（若 DirectML 不可用）：[ncnn](https://github.com/Tencent/ncnn) 的 Vulkan 后端，腾讯开源，对老旧 GPU 兼容性极好，但需将模型转为 ncnn 格式。

#### 2.1.3 推理性能预估

| 模型 | 维度 | CPU 单条 | GPU(DirectML) 单条 | 批量(32) |
|------|------|----------|---------------------|----------|
| bge-base-zh-v1.5 | 768 | ~30ms | ~5ms | ~80ms |
| bge-large-zh-v1.5 | 1024 | ~60ms | ~8ms | ~150ms |

---

### 2.2 向量数据库

**选型方向**：嵌入式数据库，无需启动服务，通过文件直接读写。

| 候选方案 | 嵌入模式 | 百万级 | 备注 |
|----------|----------|--------|------|
| **LanceDB** | ✅ 原生嵌入 | ✅ | 基于 Lance 列存格式，零服务 |
| ChromaDB | ⚠️ 支持 | ✅ | 默认需服务，嵌入模式功能受限 |
| FAISS | ✅ 纯库 | ✅ | 需自行管理索引持久化 |
| Qdrant | ⚠️ 支持 | ✅ | 嵌入模式实验性 |

**推荐选型**: **LanceDB**
- 理由：原生嵌入设计，无需任何服务进程；基于 Apache Arrow / Lance 列式存储，读写高效；支持百万级数据；Python API 简洁；支持元数据过滤；存储位置可通过路径参数自由指定。

---

### 2.3 文件系统抽象层

使用 **[fsspec](https://filesystem-spec.readthedocs.io/)** 作为统一文件系统接口。**每个知识库来源可指定独立的连接目标（文件系统类型 + 路径 + 认证）。**

| 后端 | 协议 | 用途 |
|------|------|------|
| `local` | `file://` | 本地文件系统 |
| `webdav` | `webdav://` | WebDAV 远程存储（NAS 常见） |
| `sftp` | `sftp://` | SFTP / SSH |
| `smb` | `smb://` | SMB / NAS 网络共享 |
| `s3` | `s3://` | 对象存储 |

---

### 2.4 自包含 Python 运行环境

**Skill 代码目录自身不包含任何运行时数据。** 首次启动时自动在用户指定的工作路径下创建隔离的 Python 虚拟环境。

```
启动流程:
  1. 检查工作路径是否存在 Python venv
  2. 不存在 → 自动创建 venv + 安装依赖（首次约 2-5 分钟）
  3. 存在 → 直接激活使用
```

实现方式：

| 方案 | 说明 |
|------|------|
| **uv** (推荐) | Rust 写的极速 Python 包管理器，创建 venv 毫秒级，安装依赖秒级 |
| venv + pip | Python 标准库自带，兼容性最好，速度较慢 |

- Skill 分发时附带 `requirements.txt` / `pyproject.toml`（约 2KB），不含任何 .whl 或预编译包。
- 运行时所有依赖安装在工作路径下的 `.venv/` 中，系统 Python 环境完全不受影响。
- 卸载 Skill  =  删除 Skill 目录 + 删除工作路径，系统不留残留。

---

### 2.5 语言与工具链

| 层级 | 选型 | 理由 |
|------|------|------|
| 核心引擎 | Python 3.10+ | ONNX Runtime、LanceDB、fsspec 生态 |
| 依赖安装 | `uv` | 极速创建隔离环境 |
| CLI 框架 | `click` | 轻量、成熟 |
| 模型导出 | PyTorch + Optimum | 仅开发/构建时使用，运行时不依赖 |

---

## 3. 路径与存储架构

### 3.1 三大路径概念

```
┌─────────────────────────────────────────────────────┐
│  Skill 代码目录 (只读，分发用)                        │
│  ~/.agents/skills/naskb/                            │
│  ├── SKILL.md                                       │
│  ├── pyproject.toml                                 │
│  └── naskb/          ← Python 源码                  │
└─────────────────────────────────────────────────────┘
         │
         │  naskb init --work-path D:/NASKB_data
         ▼
┌─────────────────────────────────────────────────────┐
│  工作路径 (用户指定，所有运行时数据)                   │
│  D:/NASKB_data/                                     │
│  ├── .venv/              ← 隔离的 Python 环境        │
│  ├── config.toml         ← 主配置文件                │
│  ├── models/             ← ONNX 模型文件             │
│  ├── db/                 ← LanceDB 向量数据库        │
│  │   ├── files.lance/                               │
│  │   └── folders.lance/                             │
│  └── state.db            ← SQLite 索引状态           │
└─────────────────────────────────────────────────────┘
         │
         │  知识库来源 (可多个，各自独立连接)
         ▼
┌──────────────────┐  ┌──────────────────┐
│ 来源 1: 本地笔记   │  │ 来源 2: NAS WebDAV │
│ file://D:/Notes  │  │ webdav://nas/lan  │
│ .kbignore        │  │ .kbignore        │
│ docs/            │  │ media/           │
│   note.md        │  │   photo.jpg      │
│                  │  │   photo.jpg.md   │
└──────────────────┘  └──────────────────┘
```

### 3.2 路径职责

| 路径 | 环境变量 | 说明 | 示例 |
|------|----------|------|------|
| **Skill 代码目录** | `NASKB_HOME` | 只读，Python 源码所在位置 | `~/.agents/skills/naskb/` |
| **工作路径** | `NASKB_WORK` | 运行时环境、模型、数据库、状态 | `D:/NASKB_data/` |
| **来源路径** | (配置项 `sources[]`) | 被索引的知识库内容，可多个 | `D:/Notes`, `webdav://nas/doc` |

### 3.3 设计要点

- **代码与数据彻底分离**：Skill 目录可随时替换/升级，不影响数据库和索引。
- **数据库可备份**：用户只需复制工作路径下的 `db/` 和 `state.db` 即可完整备份。
- **模型独立存放**：ONNX 模型放在工作路径下，多知识库可共享同一份模型。
- **来源灵活组合**：一个知识库可同时索引本地文件夹和远程 WebDAV 目录。

---

## 4. 数据模型

### 4.1 文件索引记录 (FileRecord)

```
FileRecord {
    id:          str        # 唯一 ID (来源标识 + 相对路径的 hash)
    source_id:   str        # 所属来源标识
    path:        str        # 文件完整路径 (含协议前缀)
    rel_path:    str        # 相对来源根目录的路径
    name:        str        # 文件名
    ext:         str        # 扩展名 (含 .)
    type:        enum       # text | binary
    size_bytes:  int        # 文件大小
    mtime:       float      # 修改时间 (Unix timestamp)
    vector:      float[]    # 向量 (768 或 1024 维)
    indexed_at:  float      # 入库时间戳
    status:      enum       # indexed | outdated | missing_desc | skipped
    orig_file:   str|null   # 若为描述文件，指向原始文件路径
}
```

### 4.2 文件夹索引记录 (FolderRecord)

```
FolderRecord {
    id:          str        # 唯一 ID
    source_id:   str        # 所属来源标识
    path:        str        # 文件夹路径
    name:        str        # 文件夹名
    summary:     str        # 聚合描述文本
    source:      enum       # auto_generated | manual_description_md
    vector:      float[]    # 描述文本的向量
    file_count:  int        # 文件夹内文件总数
    indexed_at:  float      # 入库时间戳
}
```

### 4.3 知识库来源 (KnowledgeSource)

```
KnowledgeSource {
    id:          str        # 来源唯一标识
    name:        str        # 人类可读名称 (如 "本地笔记", "NAS 媒体库")
    fs_type:     enum       # local | webdav | sftp | smb | s3
    root_url:    str        # 连接 URL (如 "file://D:/Notes", "webdav://192.168.1.1/doc")
    auth:        dict|null  # 认证信息 (用户名/密码/token)
    enabled:     bool       # 是否启用
}
```

### 4.4 排除规则 (ExclusionRule)

```
ExclusionRule {
    id:          str
    source_id:   str        # 适用的来源 (空 = 全局)
    rule_type:   enum       # ext | folder | folder_summary
    pattern:     str        # 匹配模式 (如 ".pdf", "node_modules/")
    note:        str        # 备注说明
}
```

---

## 5. 功能规格

### 5.1 索引策略

#### 5.1.1 纯文本文件 (.md / .txt / .rst / .org 等)

- 直接读取文件内容 → 向量化 → 入库。
- 一个文件对应**一条**向量记录。
- 长文本（超过模型 token 上限）分段嵌入后均值池化为单向量。

#### 5.1.2 非纯文本文件（媒体、二进制、PDF、Office 等）

- 不直接向量化原始文件。
- 查找**同目录下同名 `.md` 描述文件**（如 `photo.jpg` → `photo.jpg.md`）。
  - 若存在：读取描述文件内容 → 向量化 → 入库，`orig_file` 指向原始文件。
  - 若不存在：标记为 `missing_desc`，不参与检索，但记录到"缺失列表"中。
- 检索命中时，同时返回描述文件和原始文件路径。

#### 5.1.3 文件夹描述

- 每个文件夹在索引时生成一条聚合向量：
  - 若存在 `description.md`：使用该文件内容（人工撰写）。
  - 否则：自动拼接文件夹下所有已索引文件的文件名 + 首行摘要，生成聚合文本。
- 用途：支持"这个文件夹是干什么的"这类语义查询。

### 5.2 索引生命周期管理

| 操作 | CLI 命令 | 说明 |
|------|----------|------|
| 初始化工作路径 | `naskb init --work-path <path>` | 创建 venv + 目录结构 + 配置模板 |
| 添加来源 | `naskb source add <name> <url>` | 添加知识库来源 |
| 全量构建 | `naskb index --full` | 扫描所有来源，全量重建 |
| 增量更新 | `naskb index --update` | 仅处理变更（mtime/size/新增） |
| 单来源更新 | `naskb index --source <id>` | 仅更新指定来源 |
| 单文件更新 | `naskb index --file <path>` | 手动更新指定文件 |
| 文件夹更新 | `naskb index --folder <path>` | 更新某文件夹下所有文件 |
| 检索 | `naskb search "<query>"` | 语义检索，返回 top-k 结果 |
| 状态查看 | `naskb status` | 索引进度、各来源统计 |
| 缺失列表 | `naskb missing` | 列出缺少描述文件的条目 |
| 删除索引 | `naskb index --remove <path>` | 移除指定文件索引 |
| 配置管理 | `naskb config` | 查看/修改配置 |

### 5.3 变更检测

增量更新时，通过以下三元组判断文件是否变更：

1. **mtime** — 文件修改时间是否晚于上次索引时间
2. **size_bytes** — 文件大小是否变化
3. **existence** — 文件是否仍然存在

若三者均未变化 → 跳过。任一项变化 → 重新索引。

### 5.4 排除规则

支持三种粒度的排除，规则按来源独立配置：

| 类型 | 示例 | 行为 |
|------|------|------|
| 扩展名排除 | `ext:.pdf,.mp4,.png` | 跳过该类型文件的索引 |
| 文件夹排除 | `folder:node_modules,.git` | 跳过整个文件夹，不递归进入 |
| 文件夹摘要模式 | `folder_summary:vendor` | 该文件夹仅索引 `description.md`（若有），不深入内部文件，不报告缺失 |

排除规则存放在**来源根目录**的 `.kbignore` 文件中。全局规则放在工作路径的 `config.toml` 中。

### 5.5 Skill 封装

作为 VS Code Copilot Skill（`SKILL.md`），对外暴露以下能力：

- **知识检索**：接收自然语言查询 → 返回相关文件路径 + 内容摘要
- **索引管理**：通过对话触发索引更新 / 重建
- **状态查询**：回答"哪些文件还没索引"等问题

---

## 6. 接口设计

### 6.1 CLI 接口

```
naskb
├── naskb init --work-path <path>              # 初始化工作路径
│
├── naskb source
│   ├── add <name> <url>                       # 添加知识库来源
│   ├── remove <id>                            # 移除来源
│   ├── list                                   # 列出所有来源
│   └── update <id>                            # 更新来源配置
│
├── naskb index
│   ├── --full                                 # 全量索引 (所有来源)
│   ├── --update                               # 增量更新 (所有来源)
│   ├── --source <id> [--full|--update]        # 指定来源
│   ├── --file <path>                          # 单文件
│   └── --folder <path>                        # 文件夹
│
├── naskb search <query>
│   ├── --top-k <n>                            # 返回数量 (默认 10)
│   ├── --threshold <float>                    # 相似度阈值 (默认 0.5)
│   └── --source <id>                          # 限定来源
│
├── naskb status                               # 索引进度概览
├── naskb missing [--source <id>]              # 缺失描述文件列表
├── naskb remove <path>                        # 删除索引记录
└── naskb config [set <key> <value>]           # 查看/修改配置
```

所有命令通过 `--work-path` 或环境变量 `NASKB_WORK` 定位工作路径。

### 6.2 配置文件 (config.toml)

```toml
# 工作路径下的 config.toml

[model]
name = "bge-large-zh-v1.5"       # 或 "bge-base-zh-v1.5"
onnx_path = "models/"             # ONNX 模型存放子目录
execution_provider = "directml"   # directml | cpu
batch_size = 32

[db]
path = "db/"                      # LanceDB 数据目录 (相对工作路径)
# 或绝对路径: path = "E:/Backup/naskb_db/"

[state]
path = "state.db"                 # SQLite 状态库路径

[[sources]]
id = "local-notes"
name = "本地笔记"
fs_type = "local"
root_url = "file://D:/Documents/Notes"
enabled = true

[[sources]]
id = "nas-media"
name = "NAS 媒体库"
fs_type = "webdav"
root_url = "webdav://192.168.1.100:5005/media"
auth = { username = "user", password = "pass" }
enabled = true

[exclusions]
# 全局排除规则 (对所有来源生效)
ext = [".exe", ".dll", ".bin", ".iso"]
folder = [".git", ".svn", "__pycache__"]
```

### 6.3 Python API

```python
from naskb import KnowledgeBase

# 根据工作路径初始化（自动读取 config.toml）
kb = KnowledgeBase(work_path="D:/NASKB_data")

# 全量索引所有来源
kb.index_full()

# 增量更新
kb.index_incremental()

# 搜索
results = kb.search("如何配置 WebDAV", top_k=10, threshold=0.6)
for r in results:
    print(f"[{r.score:.3f}] {r.path}")
    print(f"  {r.snippet}")

# 状态
status = kb.get_status()
print(f"已索引: {status.indexed_count}, 待更新: {status.outdated_count}")
```

### 6.4 Skill 声明 (SKILL.md 概要)

```yaml
name: naskb
description: >
  本地向量知识库。语义检索本地文档、NAS 文件、笔记。
  代码与数据分离，自带 Python 环境，不污染系统。
tools:
  - naskb_search    # 语义检索
  - naskb_status    # 索引进度
  - naskb_index     # 触发增量索引
```

---

## 7. 约束与风险

| 约束 | 应对策略 |
|------|----------|
| 老旧 GPU 无 CUDA 支持 | ONNX Runtime + DirectML（DX12），几乎覆盖所有 2015+ 显卡 |
| GPU 完全不支持 DX12 | 自动回退 CPU 推理；bge-base 单条 ~30ms 可接受 |
| 百万级数据检索性能 | LanceDB IVF-PQ 索引；bge-large 1024 维可接受 |
| 长文本超 token 上限 | 分段嵌入 + 均值池化 |
| 自包含环境首次初始化慢 | 使用 uv 加速安装；给用户明确进度提示 |
| fsspec 远端认证失败 | 优雅降级，跳过该来源并报告，不阻塞其他来源 |
| 模型与数据库路径硬编码 | 全部通过 config.toml 指定，无默认隐藏路径 |

---

## 8. 后续扩展（非首期）

- 多模态 Embedding（CLIP 等）支持直接索引图片
- 自动 OCR 提取图片中文字生成描述（连接外部 OCR Skill）
- 定时自动增量索引（watch 模式）
- Web UI 浏览与管理界面
- 多知识库联合检索
- PDF / Office 文档自动提取文本生成描述
