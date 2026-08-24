# API 实现计划（04-platform-api）

> 状态：存量补全（实现先于设计）——本计划为「设计资产 ↔ 代码事实」的对账记录与后续实现路线。
> 日期：2026-08-24 ｜ 依据：design/04-platform-api/data/rest/* + server/*.py 代码基线

## 一、已实现端点清单（代码基线 → 资产文件）

| 端点 | 资产文件 | 状态 |
|------|---------|------|
| GET/POST /api/sources、PATCH/DELETE /api/sources/{sid}、POST {sid}/test|scan|analyze|adopt|confirm、GET {sid}/changes | rest/01-source-management.js | ✅ 已实现（10 端点） |
| GET /api/kb/search、POST /api/ask、GET /api/search、POST /api/reload、GET /api/stats、POST /api/pg/rebind | rest/03-retrieval-qa.js | ✅ 已实现（6 端点） |
| POST /api/kb/ask | rest/04-deep-analysis.js | ✅ 已实现（1 端点） |
| GET /api/tree、/api/files/{rid}(|/download|/preview|/parsed|/thumbnail)、GET /api/jobs、/api/jobs/{job_id}、GET /api/config/public | rest/06-platform-console.js | ✅ 已实现（9 端点） |
| 无独立 REST（任务驱动/MCP） | rest/02-ingestion-analysis.js、rest/05-knowledge-reorganize.js | — 设计决策：不建重复端点 |
| MCP 14 工具 | ai-tools/tools.js + protocol.js | ✅ 已实现（mcp/server.py） |

## 二、已知差异（代码 ↔ 声明，待 review 仲裁）

1. `GET /api/sources/{sid}/report` 装饰器未生效（死代码，调用 404）——已从设计资产中剔除，标记待决。
2. `/api/folder` 孤儿匿名前缀（auth.py 含但无路由）——待清理或接线。
3. 匿名口径：/api/jobs 需 token 而 {id} 匿名；/api/ask、/api/kb/ask 被列入匿名前缀但实际需 token。→ 设计资产按「实际需 token」标注，差异基线见 _conventions.js §auth。
4. 多 token 仅 tokens[0] 有效。
5. 兜底静态路径提示 web/dist 实为 web/public。
6. kb_ask.deep 无 nas/默认 schema 时静默回退文档级。
7. kb_fetch_file 直链不带 token（server_base_url getattr 兜底）。

全部差异清单：design/review/design-code-gap.md。

## 三、后续实现路线（未实现/演进）

| 项 | 说明 | 对应 REQ |
|----|------|---------|
| 服务端频控（G1-G5） | 当前未实现；演进项 | R6 |
| Idempotency-Key 头部 | 当前以指纹链幂等替代；是否需要头部待 review | — |
| 匿名口径统一 | 消除 /api/jobs、/api/ask 口径差异 | R7-02 |
| report 端点修复/移除 | 死代码处置 | — |
| ai-tools 渲染视图 | bundle api-viewer 为 REST-only，工具协议视图待扩展（方法论点） | — |

## 四、验证方式

- viewer 验证：`file://` 打开 api-viewer.html，0 console error（Phase10 执行）。
- 契约一致性：review 委托 api-design（工作流→API 覆盖、权限点覆盖）与 api-code-gen（设计→代码）。
