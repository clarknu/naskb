# API 测试执行报告（tdd-execute Phase 3）

> 日期：2026-08-24 | 执行：`python -m pytest tests/ -q`（全量，含 api/ unit/ integration/ + 架构契约门禁）| 耗时 126.45s
> 结果：**381 passed, 1 skipped, 0 failed**（exit code 0；1 skipped = 环境门控——真实 PG/外部服务不可达时跳过，非缺陷）
> 执行者：verify 阶段正式执行（DD-009 迭代 + P-003 A'/P-004 对齐 + K-001/K-002 债务清理后基线）；门禁判定：✅ 达标

## 整体结果

| 指标 | 数值 |
|------|------|
| 全量通过 | 381 |
| 跳过 | 1（环境门控） |
| 失败 | 0 |
| 架构契约门禁（tests/test_arch_contract.py） | exit 0（11 规则；**0 违规 / 0 债务**——K-001/K-002 债务已清零） |
| 行为承诺套件（tests/api/test_arch_contract_behavior.py） | 通过（幂等重复提交 / 任务状态机合法性 / ETag 304·缩略图缓存 / 无 PG 回退·无 LLM 明确 503 / MCP 写审计与读不审计 / 权限绕过与匿名例外——全身份口径） |
| DD-009 端点回归（report/folder/MCP 三工具接线） | 通过 |
| TestAuth 口径适配（匿名例外缩减为引导/直链） | 通过 |

## 覆盖口径（对应 tdd-build §2.5 复杂度裁剪，L2+ 全量）

- 六域 TC 规格（design/07-tdd/api/*-tdd-design.md）：正常/校验/错误/状态/边界/权限全覆盖（既有套件 + 本迭代补充）
- 架构承诺：机械 11 规则 + 行为承诺套件（T-3 拍板补齐）
- 契约（Arch-Contract）：探针 51 units / 56 路由自动对齐 report/folder/MCP 工具；报告 design/review/arch-contract/latest.json
- 缺口登记（不阻塞，见 remaining-issues）：G-08 CLI 28 命令无独立套件（主链路间接覆盖）；G-05 真实标准文档深析（R5-06 后续阶段）

## 失败分类与修复记录

- 本轮全量：**0 失败**，无需溯源/修复循环。
- 回放（本轮之前已闭环）：DD-009 迭代批次修复 TestAuth 匿名口径（7 项）、rebind 隔离（stale nas_registry 清理策略）、探针贪婪匹配（sources/resources 前缀）、AsyncFunctionDef 路由扫描；P-003 A'（kb_ask.deep 显式回退语义）契约/测试同步；P-004（source_stats/folder_entry_view 派生 VO 对齐）。
- 债务清理：AC-005 字面量全部改为 `ACCESS_MODES[0]`（K-001/K-002 清零）。

## 门禁判定（verify exitGate：全量测试 0 失败）

| 判据 | 结果 |
|------|------|
| pytest 全量 0 失败 | ✅ 381 passed / 1 skipped / 0 failed |
| 架构契约退出码 0 | ✅ 0 违规 / 0 债务 |
| viewer 回归门禁（官方 verify-fixed.mjs，bundle 模板） | ✅ 5/5（0 console error / 0 pageerror / emptyTexts 空） |
| viewer smoke（项目设计资产） | ✅ 5/5（scripts/viewer-smoke.mjs，全局 Playwright 引擎） |
| E2E 旅程（TC-I001~I003） | ✅ 6/6（scripts/e2e/e2e-journeys.mjs，全局引擎 chromium-1234，全身份 token 口径；证据 tests/integration/evidence/） |
| 关联阶段报告 | page-mock-execute-report-2026-08-24.md（23 用例全绿） |

## 引用

- 基线前史：tests/test-reports/baseline-2026-08-24.md（356 → 379 更新节）；本报告为 verify 阶段正式执行记录
- 复查收敛：design/review/_archived/naskb-review-v1.md（381 全量引用 + 6 问题处置）
- 迭代记录：design/review/iterate-report-2026-08-24-dd009.md
