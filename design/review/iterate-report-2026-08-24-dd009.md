# 迭代报告：DD-009 拍板批次（匿名移除 + 端点接回 + 裁剪口径 + E2E 接入）

> 日期：2026-08-24 | 领域：cross-domain（全部 6 域）
> 模式：联调修正（批量·路径 C）| 起点：raw-input/§8.1~§8.6（多起点合并）| 问题数：10
> API 相关：是
> 决策存档：design/01-raw-input/07-user-decisions-2026-08-24.md ｜ 台账：design/review/user-decisions-pending.md

## 变更摘要

按用户拍板完成 10 项变更：匿名白名单移除（全部端点需身份，仅引导/直链例外）、report/folder 端点接回、MCP 三工具接线（14→17）、deep 关闭清理存量 chunk、直链不认证（网关 IP 边界）、权限模型保留（契约化）、健康检查/频控裁剪、行为承诺测试补齐、E2E 接入全局 Playwright MCP、发布节奏=不主动发布。

## 级联执行记录

| 步骤 | 负责 Skill | 变更摘要 | TDD 回归 | 结果 |
|------|-----------|---------|---------|------|
| 落账 | iterate | DD-009 + 决策存档/台账/gap 状态 | — | ✅ |
| §8.1 | business-workflow | 匿名角色移除（03/04/06）；deep 关闭语义；认证规则 | — | ✅ |
| §8.3 | api-design | report/folder 端点；全端点 login_required；_conventions 重写；MCP 17 工具；200 口径对齐 | — | ✅ |
| §8.3b | backend-architecture-design | security（直链边界）/observability（裁剪）/resilience（裁剪）/audit 同步 | — | ✅ |
| §8.4 | desktop-ui-design | 6 处 public→login_required；deep 确认提示；i18n | — | ✅ |
| §8.5 | tdd-build | 行为承诺套件（14 用例）+ DD-009 端点回归（4 例）+ Integration E2E 规格（TC-I001~I003） | ⚠️ 14+4 | ✅ |
| §8.6 | api-code-gen | auth.py 重写；report 装饰器恢复；folder 端点；deep 钩子；MCP 三工具（capabilities+server）；config/exts/retrieval 清扫；app.js 确认框；文档计数/文案 | ⚠️ | ✅ |
| §8.8 | tdd-execute | 全量 379 passed / 1 skipped（含回归与承诺套件）；契约退出码 0（11 规则，report/folder 自动对齐）；viewer smoke 5/5；E2E 6/6 | 含回归 | ✅ |
| Review | review | **全量复查（D0-D12）——下一步启动** | — | ⏳ |

## TDD 回归用例（摘要）

| 测试方法 | 覆盖场景 | 类型 | 状态 |
|---------|---------|------|------|
| TestDd009Endpoints（4 例） | report 接回/404、folder 需 PG、deep 钩子无 PG 跳过 | 回归 | ✅ |
| test_arch_contract_behavior.py（14 例） | 幂等提交、任务状态机、ETag 304/缩略图缓存、PG 回退/LLM 503、MCP 审计、权限绕过 | 行为承诺 | ✅ |
| TestAuth（2 例改写） | 匿名例外集合、开放模式 | 口径适配 | ✅ |
| TestSourceTools（3 例） | 三 MCP 工具结构/脱敏/URL | 回归 | ✅ |
| test_rebind_nas（隔离修复） | nas_registry 行清理 | 修复 | ✅ |

## 验证结果

- [x] tdd-execute 全绿（379/379，1 环境跳过）
- [x] 架构契约机械校验退出码 0（0 high/0 medium；2 low=债务 K-001/K-002 豁免，2026-11-24 到期）
- [x] viewer 渲染 5/5（scripts/viewer-smoke.mjs，0 error）
- [x] E2E 旅程 6/6（scripts/e2e/e2e-journeys.mjs，全局 Playwright 引擎 chromium-1234 + 全身份 token 口径）
- [x] 变更意图确认满足（10 项拍板逐项落地，gap 清单 ⚖️ 项全部标注拍板结论）
- [ ] Review 全量复查（D0-D12）——待启动（用户已选定全量范围）

## 相关文件变更（主要）

- 设计资产：design-decisions.js（DD-009）、02/04/05/06 CHANGELOG、rest/*（+2 端点/权限口径）、ai-tools/tools.js（17 工具）、_conventions、security/observability/resilience/audit-dossier、tree/i18n、07-tdd（+integration 规格）
- 代码：server/{auth,app,routes_sources,routes_content}.py、common/{pgstore,capabilities,config,exts,retrieval,analyzer/document}.py、mcp/server.py、skill/cli.py（计数）、web/public/app.js
- 测试：tests/api/test_server_api.py（适配+回归）、test_mcp_server.py（+3）、test_v2_features.py（隔离修复）、tests/api/test_arch_contract_behavior.py（新增 14 例）
- 验证工具：scripts/e2e/e2e-journeys.mjs、scripts/viewer-smoke.mjs（根目录可跑）
- 文档：README/DEPLOY/config.example.toml/AGENTS.md/release/policy.md（门禁 2/7 + §四b 网关边界）

## 遗留（转 Review）

- 全量 Review D0-D12（下一步；输入已齐：设计资产最新 + 测试报告 + 契约报告 latest.json）
- kb_ask.deep 静默回退语义（B-01 推荐项，未拍板，随 Review 确认）
- ~~K-001/K-002 债务到期清理~~ → **已于 2026-08-24 提前清零**（AC-005 违规 0）。
