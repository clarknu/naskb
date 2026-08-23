# NASKB — 智能 NAS 知识库（v2 工具形态 → v3 平台化演进中）

> 需求基线：`design/requirement.md`（功能/架构设计的来源与出发点，持续更新）
> 重定位方案：`design/platform-v3-design.md`（2026-08-18 拍板：工具 → 自持知识的知识库系统，
> Web UI + 开放 API + 下载代理 + 在线预览；产品以 v0.1 重新起版）

对本地目录或 NAS（WebDAV）建立 `.naskb/` 描述仓库：AI 分类/摘要/标签、图片音频识别、
PDF/DOCX 扫描件 OCR、目录整理规划与检索。以 **Reasonix Skill** 形态交付：
AI 通过 `naskb/SKILL.md` 了解能力，调用 `naskb desc` 命令完成"扫描-分析-检索-整理-更新"闭环。

## 结构

```
naskb/                      ← Skill 根
├── SKILL.md                ← AI 入口（playbook）
├── DEPLOY.md               ← 部署指南
└── scripts/naskb/          ← 代码
    ├── common/             ← 确定性层：.naskb 仓库、fs(local/webdav)、llm 客户端、检索、PG 向量库
    ├── analyzer/           ← AI 编排层：文档/图片/音频/视频/MinerU/目录/重组
    ├── mcp/                ← MCP Server（14 个 kb_* 工具，stdio）
    └── skill/cli.py        ← desc 命令组（18 命令）
NASKB_data/                 ← 工作区：config.toml（DeepSeek/MiMo key、WebDAV、MinerU）
tests/                      ← 测试（253 用例）
```

## 核心能力（`naskb desc ...`）

| 命令 | 作用 |
|---|---|
| `scan <root>` | 扫描报告（valid/stale/missing/ignored） |
| `analyze <file>` | 单文件分析（文档 DeepSeek 摘要、图片/音频 MiMo、docx 图文流） |
| `analyze-tree <root> --llm` | 批量分析（增量幂等：hash 对比，一致跳过/变更重分析/删除清孤儿） |
| `analyze-folder <root> --recursive` | 目录级描述 folder.json |
| `search <query>` / `ask <question>` | 语义向量检索（bge-small-zh 本地嵌入）/ RAG 问答（DeepSeek 生成，带来源）；无向量索引自动降级 BM25；`--pg` 走 PG 多 NAS 向量库（失败自动回退） |
| `serve [--host --port --root --open --pg]` | 内置问答服务：Web UI + `/api/search` `/api/ask`（向量/BM25 自动选择，`/api/reload` 热刷新）；`--pg` 启用 PG 多 NAS 下拉 |
| `sync-vectors <root> [--nas --rebuild]` | 同步 .naskb → PG 多 NAS 向量库（五要素身份/独立 schema/增改删移增量） |
| `sync-status <root> [--nas]` / `pg-status` | 只读一致性报告 / PG 已注册 NAS 向量库清单 |
| `index-vectors <root>` | 构建语义向量索引（首次自动下载 ~24MB 模型到工作区） |
| `plan-reorganize <root> [--apply]` | AI 生成整理方案并执行（整仓跟随/级联更新/空目录清理）；方案持久化 plan_id，apply 凭 id 复校验执行 |
| `migrate` | v1 `.sidecar.json` → v2 `.naskb` 迁移 |
| `serve-mcp [--root X] [--pg]` | **MCP Server（stdio）**：14 个 `kb_*` 工具（检索/问答/入库/整理）供外部 Agent 调用，长任务返回 job_id；`mcp.json` 模板见仓库根 |

NAS 场景：`naskb desc --webdav-url <url> analyze-tree /path`（config.toml 配好 [webdav] 后可省略）。

## 模型分工与部署

- DeepSeek（文本分类/摘要/方案）可并发 4-6；MiMo（图片/音频）严格串行；MinerU（扫描件 OCR）严格串行（本机 CPU，`.venv-mineru` 独立环境，模型首次运行自动下载）。
- **检索**：语义向量（bge-small-zh ONNX，~24MB 本地模型，`desc index-vectors` 构建索引）为主，BM25 关键词为自动降级；无 LanceDB 等重型向量库（numpy 余弦，毫秒级）。
- 部署：拷贝 `naskb/` + `NASKB_data/config.toml` + Python 环境即可（向量模型首次运行自动下载）。

## 整理原则（AI 执行时自动保证）

1. 移动不删除；`.naskb` 整仓跟随（artifacts/folder/meta 随迁）
2. 移动/增删后源、目标、上层 folder.json 自动级联更新
3. 搬空的源目录自动删除（只删空目录树）
4. 子路径先移（防"先移整目录后抽子目录"失败）
