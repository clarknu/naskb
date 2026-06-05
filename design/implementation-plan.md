# NASKB 实现计划

> 版本: v0.2  
> 创建: 2026-06-04  
> 依赖: [requirement.md](./requirement.md)

---

## 总览

本计划将 NASKB 分为 **6 个阶段**，按依赖关系递进。

```
Phase 0: 模型选型测试    (1-2 天)   ← 新增：实测 bge-large vs bge-base + DirectML
Phase 1: 项目骨架        (1-2 天)
Phase 2: 核心引擎        (3-5 天)
Phase 3: 文件系统层      (2-3 天)
Phase 4: CLI & Skill     (2-3 天)
Phase 5: 测试 & 文档     (2-3 天)
────────────────────────────────
合计预估: 11-18 天
```

---

## Phase 0: 模型选型与 GPU 验证 🔬

### 目标
在目标机器上实测 `bge-large-zh-v1.5` 与 `bge-base-zh-v1.5` 的 ONNX + DirectML 推理性能，决定最终选型。验证 ONNX Runtime DirectML EP 在老旧 GPU 上的可用性。

### 任务清单

| # | 任务 | 详细 |
|---|------|------|
| 0.1 | 环境准备 | 安装 `onnxruntime-directml`，确认 GPU 出现在可用设备列表中 |
| 0.2 | 模型导出 (bge-base) | 下载 `BAAI/bge-base-zh-v1.5` → Optimum 导出 ONNX |
| 0.3 | 模型导出 (bge-large) | 下载 `BAAI/bge-large-zh-v1.5` → Optimum 导出 ONNX |
| 0.4 | 单条推理基准 | 两个模型分别在 CPU / DirectML 下编码 10 条中文文本，记录耗时 |
| 0.5 | 批量推理基准 | batch_size=1/8/16/32 对比吞吐 |
| 0.6 | 语义质量抽检 | 构建 50 条中文查询 + 200 篇文档的 mini 测试集，对比检索 Precision@5 |
| 0.7 | DirectML 兼容性确认 | 若 DirectML 不可用，验证 CPU 回退路径，评估是否接受纯 CPU 性能 |
| 0.8 | 备选方案评估 | 若 DirectML 失败，尝试 ncnn Vulkan 后端可行性 |

### 产出
- `docs/model-benchmark.md` — 包含两个模型的性能数据与最终选型结论
- 确定最终使用的模型名称、维度、单条/批量耗时

### 验收标准
- [ ] ONNX Runtime DirectML EP 在目标 GPU 上成功加载并推理
- [ ] 两个模型的推理耗时数据完整
- [ ] 明确选定最终模型（large 或 base），记录在 `config.toml` 模板中
- [ ] 如 DirectML 完全不可用，有明确的 CPU 回退方案

---

## Phase 1: 自包含项目骨架搭建

### 目标
建立 Skill 代码目录结构，实现自包含 Python 环境的自动创建与激活。

### 任务清单

| # | 任务 | 详细 | 产出 |
|---|------|------|------|
| 1.1 | Skill 目录初始化 | 创建 `naskb/` 包目录、`pyproject.toml`、`SKILL.md` 骨架 | 目录结构 |
| 1.2 | 依赖声明 | `pyproject.toml` 中声明核心依赖：`lancedb`, `onnxruntime-directml`, `fsspec`, `click`；**不含** `torch`, `sentence-transformers` | `pyproject.toml` |
| 1.3 | 环境引导脚本 | `bootstrap.py`：检测/创建工作路径 → 创建 `.venv` → `uv pip install` 依赖 → 下载 ONNX 模型 | `naskb/bootstrap.py` |
| 1.4 | 入口包装脚本 | `naskb.cmd` (Windows) / `naskb` (Unix)：定位工作路径 → 激活 venv → 执行 CLI | 可执行入口 |
| 1.5 | 模型管理模块 | `naskb/model_manager.py`：下载 HF 模型 → 缓存到工作路径 `models/` | `naskb/model_manager.py` |
| 1.6 | 配置模块 | `naskb/config.py`：读取工作路径下的 `config.toml`，支持嵌套结构 | `naskb/config.py` |

### 关键设计：环境隔离

```
首次运行:
  > naskb init --work-path D:/NASKB_data
  1. 创建 D:/NASKB_data/
  2. 创建 config.toml 模板
  3. 创建 .venv (Python 3.10+)
  4. uv pip install -r requirements.txt  →  安装到 .venv，系统 Python 不受影响
  5. 下载 ONNX 模型到 models/
  6. 完成！

后续运行:
  > naskb --work-path D:/NASKB_data search "关键词"
  → 自动激活 .venv → 执行搜索
```

### 验收标准
- [ ] 在一个全新的 Windows 机器上（无预装 Python 包的），执行 `naskb init --work-path ./test_work` 成功
- [ ] `test_work/.venv/` 包含所有依赖
- [ ] 系统 `pip list` 不受任何影响
- [ ] `naskb --help` 正常输出命令列表

---

## Phase 2: 核心引擎

### 目标
实现向量化、存储、检索三大核心能力。

### 2.1 Embedding 模块

| # | 任务 | 详细 |
|---|------|------|
| 2.1.1 | `Embedder` 类 | 封装 ONNX Runtime 推理会话；支持 DirectML EP 和 CPU EP 切换 |
| 2.1.2 | Tokenizer | 加载模型对应的 tokenizer（使用 `transformers` 仅加载 tokenizer，不加载模型权重） |
| 2.1.3 | 长文本处理 | 分段策略：按句号/换行切分，每段 ≤ 510 tokens；均值池化合为单向量 |
| 2.1.4 | 批量编码 | `encode_batch(texts: list[str], batch_size: int) -> np.ndarray`；返回 (N, 768) 或 (N, 1024) |
| 2.1.5 | GPU 回退 | DirectML 初始化失败 → 自动降级 CPU + 日志警告 |

**关键文件**: `naskb/embedder.py`

### 2.2 向量存储模块

| # | 任务 | 详细 |
|---|------|------|
| 2.2.1 | `VectorStore` 类 | 封装 LanceDB 连接；`db_path` 从配置读取，不硬编码 |
| 2.2.2 | 表管理 | `files` 表 + `folders` 表；自动创建 schema；维度自适应模型 |
| 2.2.3 | CRUD | `add()`, `upsert()`, `delete()`, `get_by_id()` |
| 2.2.4 | 检索 | `search(vector, top_k, threshold, source_filter)` → 返回带 metadata 的结果 |
| 2.2.5 | IVF-PQ 索引 | 数据量 > 10,000 时自动构建加速索引 |

**关键文件**: `naskb/vector_store.py`

### 2.3 状态管理模块

| # | 任务 | 详细 |
|---|------|------|
| 2.3.1 | SQLite 状态库 | 建表 `indexed_files(source_id, path, mtime, size_bytes, content_hash, indexed_at)` |
| 2.3.2 | 变更检测 | `has_changed(source_id, path, mtime, size_bytes) -> bool` — 三元组比对 |
| 2.3.3 | 状态查询 | `get_stats()` → 各来源的 indexed/outdated/missing_desc/skipped 计数 |
| 2.3.4 | 文件哈希 | 对文本文件计算内容 MD5（仅在前 64KB），辅助变更检测 |

**关键文件**: `naskb/state.py`

### 2.4 索引编排器

| # | 任务 | 详细 |
|---|------|------|
| 2.4.1 | `Indexer` 类 | 接收 `Config` + `Embedder` + `VectorStore` + `StateManager` |
| 2.4.2 | 全量索引 | `index_full(source_ids=None)` — 扫描 → 分类(text/binary) → 嵌入 → 批量写入 |
| 2.4.3 | 增量索引 | `index_incremental()` — 仅处理 state 中标记变更的文件 |
| 2.4.4 | 粒度控制 | `index_file(path)`, `index_folder(path)`, `index_source(source_id)` |
| 2.4.5 | 文件夹摘要 | 自动生成文件夹聚合文本并向量化 |
| 2.4.6 | 缺失记录 | 二进制文件无 `.md` 描述 → 写入 `missing_desc` 表 |

**关键文件**: `naskb/indexer.py`

### 验收标准
- [ ] 对一个含 20 个 .md 文件 + 5 个二进制文件（含描述）的目录全量索引
- [ ] 中文查询 "数据库" 返回 SQLite 相关文档，且得分 > 0.5
- [ ] 修改 1 个文件后增量索引仅更新该文件（其他 19 个跳过）
- [ ] 描述文件缺失的二进制文件出现在 `naskb missing` 列表中
- [ ] DirectML GPU 推理比纯 CPU 快 3-5 倍（若有 GPU）

---

## Phase 3: 文件系统抽象层

### 目标
基于 fsspec 封装统一文件系统接口，支持多来源独立连接。

### 任务清单

| # | 任务 | 详细 |
|---|------|------|
| 3.1 | `SourceManager` | 管理多个 `KnowledgeSource` 实例的生命周期（连接/断开/重连） |
| 3.2 | `FileSystemAdapter` 工厂 | 根据 `fs_type` 创建对应的 fsspec 文件系统实例 |
| 3.3 | `LocalAdapter` | 本地文件系统（`file://`），已是 fsspec 内置 |
| 3.4 | `WebDAVAdapter` | WebDAV（需 `webdav4` 或 fsspec webdav 实现），含 basic auth |
| 3.5 | `Scanner` | 接收 `KnowledgeSource` → 递归遍历 → 应用排除规则 → 产出 `ScannedFile` 列表 |
| 3.6 | 排除规则引擎 | 解析 `.kbignore`（来源级）+ `config.toml [exclusions]`（全局级）；支持 ext/folder/folder_summary |
| 3.7 | 描述文件匹配 | `find_desc_file(fs, binary_path) -> Optional[str]` — 同目录查找 `filename.ext.md` |

**关键文件**: `naskb/sources.py`, `naskb/scanner.py`, `naskb/fs/`

### 验收标准
- [ ] 本地文件系统扫描正确，`.kbignore` 规则生效
- [ ] 多来源分别扫描，结果带正确的 `source_id`
- [ ] `folder_summary` 规则下文件夹不深入内部，不报告缺失
- [ ] 二进制文件正确关联同名 `.md` 描述文件

---

## Phase 4: CLI 与 Skill 封装

### 目标
提供完整的命令行界面，并封装为 Copilot Skill。

### 4.1 CLI 实现

| # | 命令 | 说明 |
|---|------|------|
| 4.1.1 | `naskb init --work-path <path>` | 创建工作路径 + .venv + 配置模板 + 下载模型 |
| 4.1.2 | `naskb source add <name> <url>` | 添加知识库来源 |
| 4.1.3 | `naskb source list/remove` | 来源管理 |
| 4.1.4 | `naskb index --full/--update` | 全量/增量索引 |
| 4.1.5 | `naskb index --source <id>` | 指定来源索引 |
| 4.1.6 | `naskb index --file/--folder <path>` | 单文件/文件夹索引 |
| 4.1.7 | `naskb search <query> [--top-k] [--threshold] [--source]` | 语义检索 |
| 4.1.8 | `naskb status` | 索引进度总览 |
| 4.1.9 | `naskb missing` | 缺失描述文件列表 |
| 4.1.10 | `naskb remove <path>` | 删除索引记录 |
| 4.1.11 | `naskb config [set]` | 配置管理 |

**关键文件**: `naskb/cli.py`

### 4.2 Skill 封装

| # | 任务 | 详细 |
|---|------|------|
| 4.2.1 | `SKILL.md` | 按 Copilot Skill 规范声明；设置 `NASKB_WORK` 环境变量 |
| 4.2.2 | 工具: `naskb_search` | 接收查询字符串 → 调用 `naskb search` → 格式化返回 |
| 4.2.3 | 工具: `naskb_status` | 返回索引进度摘要 |
| 4.2.4 | 工具: `naskb_index` | 触发 `naskb index --update` |

**关键文件**: `SKILL.md`, `naskb/skill_tools.py`

### 验收标准
- [ ] 所有 CLI 命令可正常运行并输出预期结果
- [ ] `--work-path` 参数和 `NASKB_WORK` 环境变量均可正确识别工作路径
- [ ] 搜索结果包含：文件路径 + 来源名称 + 相关性得分 + 内容摘要
- [ ] Skill 在 Copilot 对话中可被正确触发

---

## Phase 5: 测试、文档与发布

### 目标
保证代码质量，编写使用文档。

### 任务清单

| # | 任务 | 详细 |
|---|------|------|
| 5.1 | 单元测试 | `config`, `embedder`, `vector_store`, `state`, `scanner`, `indexer`, `sources` |
| 5.2 | 集成测试 | 端到端：init → 添加来源 → full index → search → 增量 update |
| 5.3 | 多来源测试 | 同时索引本地 + mock 远程来源 |
| 5.4 | 环境隔离测试 | 验证系统 Python 不受污染 |
| 5.5 | 性能测试 | 1000 文件索引耗时；10 万条向量检索耗时 |
| 5.6 | README | 安装指南、配置说明、CLI 参考、常见问题 |
| 5.7 | CHANGELOG | 首版变更记录 |

### 验收标准
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试全通过（含多来源场景）
- [ ] 10 万条向量检索 < 100ms
- [ ] README 中有从零开始的完整快速开始示例
- [ ] 在新机器上仅需 `naskb init --work-path ...` 即可运行

---

## 技术决策速查

| 决策点 | 选择 | 备选 |
|--------|------|------|
| Embedding 模型 | **bge-large / bge-base** (Phase 0 实测决定) | — |
| 模型格式 | ONNX（Optimum 导出） | ncnn |
| GPU 运行时 | **ONNX Runtime + DirectML** | ncnn Vulkan / CPU only |
| 向量数据库 | **LanceDB**（路径可配） | FAISS + SQLite |
| 文件系统抽象 | **fsspec**（每个来源独立连接） | 自行封装 |
| Python 环境 | **uv 创建隔离 venv**（工作路径下） | venv + pip |
| CLI 框架 | **click** | typer |
| 状态存储 | **SQLite**（路径可配） | JSON |
| 配置格式 | **TOML** (`config.toml`) | YAML |
| 代码分发 | Skill 只含源码 + pyproject.toml | 打包 .whl |

---

## 目标目录结构

```
# === Skill 代码目录 (只读，分发) ===
~/.agents/skills/naskb/
├── SKILL.md                          # Copilot Skill 声明
├── README.md
├── pyproject.toml                    # 仅含依赖声明，不含 torch
├── naskb/
│   ├── __init__.py
│   ├── bootstrap.py                  # 环境引导（创建 venv + 安装依赖 + 下载模型）
│   ├── model_manager.py              # ONNX 模型下载/缓存
│   ├── config.py                     # 配置管理（读取 config.toml）
│   ├── embedder.py                   # ONNX Runtime 封装 (DirectML/CPU)
│   ├── vector_store.py               # LanceDB 封装
│   ├── state.py                      # SQLite 状态管理
│   ├── indexer.py                    # 索引编排器
│   ├── scanner.py                    # 文件扫描 + 排除规则
│   ├── sources.py                    # 多来源管理
│   ├── fs/
│   │   ├── __init__.py
│   │   ├── base.py                   # FileSystemAdapter 工厂
│   │   ├── local.py                  # 本地文件系统
│   │   └── webdav.py                 # WebDAV 文件系统
│   ├── cli.py                        # Click CLI 入口
│   └── skill_tools.py                # Skill 工具函数
├── scripts/
│   └── export_onnx.py                # Phase 0: 模型导出（开发机用）
└── tests/
    ├── test_embedder.py
    ├── test_vector_store.py
    ├── test_indexer.py
    ├── test_scanner.py
    ├── test_sources.py
    └── fixtures/                     # 测试用文件

# === 工作路径 (运行时生成，用户管理) ===
D:/NASKB_data/                        # 用户指定的工作路径
├── .venv/                            # 隔离的 Python 虚拟环境 (自动创建)
├── config.toml                       # 主配置文件 (用户编辑)
├── models/                           # ONNX 模型文件 (自动下载)
│   ├── bge-large-zh-v1.5/
│   │   ├── model.onnx
│   │   └── tokenizer/
│   └── bge-base-zh-v1.5/
├── db/                               # LanceDB 向量数据库 (路径可配)
│   ├── files.lance/
│   └── folders.lance/
└── state.db                          # SQLite 索引状态库 (路径可配)
```

---

## 风险与缓解

| 风险 | 概率 | 缓解措施 |
|------|------|----------|
| DirectML 在老 GPU 上不可用 | 中 | Phase 0 优先验证；回退 CPU，bge-base 单条 ~30ms 可接受 |
| ONNX 导出 bge-large 失败 | 低 | Optimum 已支持 BGE 系列；备选直接用 sentence-transformers + torch（仅开发环境） |
| uv 在 Windows 上行为异常 | 低 | 备选标准库 `venv` + `pip`，仅速度差异 |
| LanceDB Windows 兼容性 | 低 | 官方支持 Windows + Python 3.10+ |
| fsspec WebDAV 认证问题 | 中 | 先支持本地文件系统；WebDAV 标记为实验性 |
| 自包含环境首次安装慢（需下载包） | 中 | 使用 uv 加速（比 pip 快 10-100x）；给用户明确进度条 |
| 百万级数据 + 1024 维向量内存占用 | 低 | LanceDB 列存 + 内存映射；粗估 100 万 × 1024 × 4B ≈ 4GB，可接受 |

---

> **下一步**: 请校对以上修改，重点确认：
> 1. GPU 方案 (DirectML) 是否符合预期？
> 2. 自包含 Python 环境的方案是否满足"不与系统重合"的要求？
> 3. 三大路径（代码/工作/来源）的分离设计是否清晰？
>
> 确认后进入 Phase 0：在目标机器上实测模型性能。
