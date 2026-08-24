# NASKB 知识库系统（v0.1 平台版 · 由 v2 工具形态重定位而来）

> 需求基线：`design/01-raw-input/`（整合需求文档，REQ-R1~R7 锚点；原始逐版设计文档归档于
> `design/01-raw-input/original-logs/`）
> 重定位方案：original-logs/`platform-v3-design.md`（2026-08-18 拍板：工具 → 自持知识的知识库系统；
> 2026-08-23 V1 系统底座实施完成）

**v0.1 平台版**：知识真正存放在系统内部（PG 主库），本地目录 / WebDAV / SMB·NFS·iSCSI 挂载
均作为**知识源**接入（支持只读知识库，源一个字节不写）。提供 Web 操作界面、开放 REST API、
下载代理（Range 流式）、在线预览（图片/PDF/音视频/文本）、RAG 问答与知识整理。
工具形态命令（`naskb desc …`）全部保留。

## 结构

```
naskb/                      ← Skill/系统根
├── SKILL.md                ← AI 入口（playbook）
├── DEPLOY.md               ← 部署指南
├── web/dist/               ← Web UI 静态包（Vue3，运行时零 Node）
└── scripts/naskb/          ← 代码
    ├── common/             ← 确定性层：.naskb 仓库、fs(local/webdav)、检索、PG 向量库、
    │                          来源注册表、扫描对账(inventory)、AI 富化(enrich)、
    │                          条款级分段(chunker, REQ-R5-06)、干净导出(clean_export, REQ-R5-02)
    ├── server/             ← 平台服务（FastAPI）：REST API + 认证 + 调度 + 下载代理/预览
    ├── analyzer/           ← AI 编排层：文档/图片/音频/视频/MinerU/目录/重组
    ├── mcp/                ← MCP Server（17 个 kb_* 工具，stdio）
    └── skill/cli.py        ← desc 命令组（28 命令）
NASKB_data/                 ← 工作区：config.toml、sources.json（无 PG 时来源表）
tests/                      ← 测试（按 SFDS 方法论重组：api/ unit/ integration/ + 架构契约门禁 test_arch_contract.py；
                              基线 356 passed / 1 skipped，见 tests/test-reports/）
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
| `sync-chunks <root> [--nas]` | 深析目录 MinerU md 分段成条款级 chunk 向量行（需 `[deep].enabled`，REQ-R5-06） |
| `export-clean <out> [--zip]` | .naskb 分析产物 → 干净 Markdown/ZIP（供外部引擎，REQ-R5-02） |
| `termbase-add <词>…` / `termbase-list` | NAS 术语表读写（jieba 自定义词典，关键词通道二期用） |
| `sync-status <root> [--nas]` / `pg-status` | 只读一致性报告 / PG 已注册 NAS 向量库清单 |
| `index-vectors <root>` | 构建语义向量索引（首次自动下载 ~24MB 模型到工作区） |
| `plan-reorganize <root> [--apply]` | AI 生成整理方案并执行（整仓跟随/级联更新/空目录清理）；方案持久化 plan_id，apply 凭 id 复校验执行 |
| `migrate` | v1 `.sidecar.json` → v2 `.naskb` 迁移 |
| `serve-mcp [--root X] [--pg]` | **MCP Server（stdio）**：17 个 `kb_*` 工具（检索/问答/入库/整理）供外部 Agent 调用，长任务返回 job_id；`mcp.json` 模板见仓库根 |

| `serve-mcp [--root X] [--pg]` | **MCP Server（stdio）**：17 个 `kb_*` 工具（检索/问答/入库/整理）供外部 Agent 调用，长任务返回 job_id；`mcp.json` 模板见仓库根 |
| `serve-platform [--host --port]` | **平台服务（v0.1 主入口）**：Web UI + 开放 API——来源注册（local/WebDAV，rw\|ro 只读知识库）、扫描对账/AI 富化入库、目录浏览罗列、`/api/kb/search` 检索、下载代理（Range 断点/ETag/stale 提示）、在线预览（图片/PDF/音视频/文本）、任务中心、Bearer 认证（`[server] tokens`）；API 文档 `/api/docs` |

NAS 场景：`naskb desc --webdav-url <url> analyze-tree /path`（config.toml 配好 [webdav] 后可省略）。

### 快速开始（零安装）

```bat
python run.py                # 就这么跑；自动借用 .venv 解释器、自动定位工作区
python run.py --host 0.0.0.0 --open   # 局域网可访问 + 自动打开浏览器
```

首次使用：
1. 浏览器打开「来源」页 → 注册一个本地目录或 WebDAV（选 ro 只读或 rw 双写）→ 扫描 → AI 分析
2. 「检索问答」搜索/提问；点结果直接预览或流式下载
3. 认证（可选）：config.toml `[server] tokens = ["你的令牌"]` 后重启

> `pip install '.[server,pg]'` 仅用于**换新机器部署**时安装依赖；日常在本仓库运行不需要。

## 模型分工与部署

- DeepSeek（文本分类/摘要/方案）可并发 4-6；MiMo（图片/音频）严格串行；MinerU（扫描件 OCR）严格串行（本机 CPU，`.venv-mineru` 独立环境，模型首次运行自动下载）。
- **检索**：语义向量（bge-small-zh ONNX，~24MB 本地模型，`desc index-vectors` 构建索引）为主，BM25 关键词为自动降级；无 LanceDB 等重型向量库（numpy 余弦，毫秒级）。
- 部署：拷贝 `naskb/` + `NASKB_data/config.toml` + Python 环境即可（向量模型首次运行自动下载）。

## 深度分析（条款级，REQ-R5-06）

标准/规范/研发类文档需要**条款级精细问答**（"6.3.2 条怎么规定""表 4 耐压要求"）时启用：

- 摘要级检索（一文件一向量）不变；`[deep].roots` 圈定目录叠加**条款级第二层**——MinerU 结构化
  Markdown 按标题层级分段成 chunk 向量行（`vectors.level='chunk'`），问答引用到「文件 + 章节」两级。
- 启用：config.toml 设 `[deep] enabled=true` + `roots`；先 `desc sync-vectors` 再 `desc sync-chunks`；
  平台 `POST /api/kb/ask` 提供条款级问答（两级引用 + 保真直返 + 无命中诚实兜底）。
- **系统级**：平台「来源」页给来源开「深度分析」（`SourceRecord.deep`）后，扫描/分析/定时自动建
  条款级 chunk 行（只读源用暂存 md，不留存）；来源页可查看「变更」确认清单
  （`/api/sources/{id}/changes`）、勾选后「确认同步并分析」（`/confirm`）。
- 法律纪律：设计学习自开源项目（只读源码），实现零拷贝（REQ-R6-07 / ADR-20260823-1）。
  详见 original-logs/`deep-analysis-roadmap.md`、original-logs/`chunk-retrieval-design.md`。

## 整理原则（AI 执行时自动保证）

1. 移动不删除；`.naskb` 整仓跟随（artifacts/folder/meta 随迁）
2. 移动/增删后源、目标、上层 folder.json 自动级联更新
3. 搬空的源目录自动删除（只删空目录树）
4. 子路径先移（防"先移整目录后抽子目录"失败）
