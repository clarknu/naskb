# NASKB 部署指南（v2）

NASKB v2 是**独立命令行工具**：`naskb` 命令自己调用 AI（DeepSeek/MiMo/MinerU），
不需要任何外部 AI 编排。所有识别原数据写入被分析目录的隐藏仓库 `.naskb/`。

## 项目结构

```
naskb/                    # Skill/MCP 声明（Reasonix/Copilot 形态使用）
├── SKILL.md              # Copilot Skill 声明
├── MCP.md                # MCP 接口参考
├── mcp.json              # MCP 配置模板
├── DEPLOY.md             # 本文档
└── ...
pyproject.toml            # Python 包声明 + 依赖 + naskb 命令入口（仓库根）
src/naskb/                # 源代码
├── common/               # 核心：fs(WebDAV/本地) / desc_store(.naskb 仓库) /
│                         #      analyzer(文档/图片/音频/视频/MinerU) / llm / retrieval
├── skill/cli.py          # CLI 入口（naskb 命令）
└── mcp/                  # MCP 服务模式（可选）
config.example.toml       # 配置模板（复制为工作区 config.toml）
```

## 独立部署（CLI 形态）

### 1. 安装

```bash
pip install .                    # 从仓库根目录；生成 naskb 命令
pip install ".[analyze]"        # + 文档分析依赖（PDF/Word/Excel 提取，推荐）
pip install ".[llm]"            # + LLM 调用（httpx）
pip install ".[media]"          # + 图片/音频/视频分析（需系统 ffmpeg）
```

### 2. 配置（API Key）

```bash
mkdir NASKB_data
cp config.example.toml NASKB_data/config.toml
# 编辑 NASKB_data/config.toml 填入 DeepSeek / 小米 MiMo 的 api_key
# （或设环境变量 DEEPSEEK_API_KEY / MIMO_API_KEY）
```

### 3. 使用（工具调 AI，全自动）

```bash
naskb desc analyze "D:/NAS/合同.pdf" --llm     # 文档：提取全文 → DeepSeek 摘要/标签/分类
                                                #   扫描件自动走 MinerU OCR
naskb desc analyze "D:/NAS/照片.jpg" --llm      # 图片：EXIF + MiMo 视觉描述
naskb desc analyze "D:/NAS/录音.mp3" --llm      # 音频：ffmpeg 分段 + MiMo 转写
naskb desc analyze "D:/NAS/录像.mp4" --llm      # 视频：ffprobe + 分级（影视仅元数据/教学抽帧/个人全量）
naskb desc analyze-folder "D:/NAS/项目" -r      # 目录级描述（每个子目录生成 folder.json）
naskb desc split "D:/NAS"                       # 旧格式 index.json → 每文件独立原数据文件
naskb desc search "房租多少" --root "D:/NAS"     # BM25 模糊搜索（基于 .naskb 完整原数据）
naskb desc ask "月租金是多少？和谁签的？" --root "D:/NAS"   # RAG 问答（DeepSeek 带来源）
```

### 4. 产物（全部在 NAS 本地，工具失效不丢失）

```
被分析目录/
├── 合同.pdf
└── .naskb/                    ← 隐藏描述仓库（与源文件同目录）
    ├── meta.json              ← 仓库元数据
    ├── index.json             ← 轻量索引（摘要/分类/标签/hash，保持小体积）
    ├── folder.json            ← 目录级描述
    ├── files/                 ← ★ 每源文件一个独立原数据文件（全文/转写/描述/EXIF）
    │   └── 合同.pdf.json
    └── artifacts/             ← MinerU 解析产物（md/html/middle.json/images）
```

### 5. WebDAV（NAS 远程模式）

```bash
naskb -w NASKB_data desc scan webdav://主机:5006/HomeBuilding  # 本地模式为默认
# 或编程方式：FileSystemAdapter.create("webdav", url, auth)
```

## 依赖清单

| 依赖 | 用途 | 安装 |
|------|------|------|
| click / httpx | CLI / LLM 调用 | 基础 |
| pymupdf / python-docx / openpyxl / chardet | PDF/Word/Excel/编码 | `[analyze]` |
| webdav4 | WebDAV 访问 | `[webdav]` |
| MinerU（独立 venv，Python<3.14） | 扫描件 OCR / 复杂版面 | `[mineru]` |
| ffmpeg（系统） | 音频/视频处理 | 系统包 |

## 常见问题

- **`naskb init` 卡住**：init 是 v1 向量库模式（下载 embedding 模型）。v2 的 desc 体系不需要 init——直接 `naskb desc analyze` 即可，仓库自动创建。
- **扫描件 PDF 识别**：需安装 MinerU（Python<3.14 独立环境），并在 config.toml 的 `[analyzer.mineru] bin` 填可执行文件路径。
- **中文文件名乱码**：Windows 下临时文件已用 ASCII 安全命名，无影响。

## V1 平台服务部署（serve-platform / run.py）

- 启动：`python run.py --host 0.0.0.0 --open`（零安装；自动借用仓库 .venv）
- 前置：工作区 `NASKB_data/config.toml` 配好 `[pg]`（知识主库）与 `[llm.text]`（问答）
- 认证：`[server] tokens = ["..."]` 启用单管理员 Bearer；`anonymous_read` 控制匿名只读
- 依赖：`pip install '.[server]'`（仅换新机器时需要）

## 备份与恢复（V2）

系统内持久数据 = PG 主库（知识权威）+ 工作区（config.toml / sources.json：
无 PG 时来源表 / store/thumbs 缩略图缓存 / store/audit 审计）。
源端 `.naskb`（可写源）为提取数据仲裁端，属备份重点之一。

- **推荐备份**：`pg_dump`（naskb 库）+ 工作区 `NASKB_data` + 可写源源端 `.naskb`。
- **灾难恢复**：恢复 `.naskb`（或重建源）→ 重新注册来源 → `desc export-repo`/`adopt`
  可选 → 若 PG 为空则 `sync-vectors --rebuild` 全量重建向量库。
- PG 是派生库（可重建）：重点仍是源端 `.naskb` + config；PG 用 `pg_dump` 定期导出为可选。
