# MERGE-NOTES — tdd-execute（仲裁版草稿）

- 底座：`inbox/zy-ai-consult/tdd-execute/SKILL.md`（`4c24a69e1b2d`，与 zy-iot-ai 版完全相同）
- 参照：`inbox/boxing-competition-operation/tdd-execute/SKILL.md`（`28b165989b71`）
- 草稿：`drafts/tdd-execute/SKILL.md`

## 三方处置表

| # | 差异点 | boxing | zy-iot / consult | 处置 | 依据 |
|---|--------|--------|------------------|------|------|
| 1 | §5 集成测试「小程序端分支」说明 | 有 | 无 | **回灌** | 明显通用且 zy 缺失（consult 本身保留 §4b 小程序阶段，语义自洽） |
| 2 | Stage 1 前置条件「API TDD 设计文档存在且为最新」 | 有（Page Mock / Integration 同类行亦有） | 无（仅小程序阶段保留设计文档行） | ✅已裁（R-007 维持删除，2026-08-23）：不回灌，草稿 §2 末已加注记 | 检查意图通用，但 consult 系统性删除三个阶段该行疑似有意裁剪，路径又含实例编号（06-tdd vs 07-tdd），拿不准 |
| 3 | Stage 1 执行命令 .NET 行 | `.NET + xUnit（当前项目）`+ `--filter FullyQualifiedName~DomainXX` 分层执行策略 | `.NET` + 朴素 `dotnet test tests/api/` | 以 consult 为准；策略 ✅已裁（R-007 保留回灌，2026-08-23，已泛化）入 §3.2 | 冲突 → consult；「先跑领域级用例」策略或可泛化但措辞绑定 .NET/xUnit |
| 4 | 测试数据库就绪表述 | SQLite :memory: 模式确认 | 按 tdd-build §2.4 DI 拦截 + 内存库/项目测试库 | 以 consult 为准 | 冲突 → consult（更技术栈无关） |
| 5 | wechatide 环境检查/登录命令族 | harness up 自动拉起、loginExpired/versionRelation、polling_task_result | `-t` 参数风格、openid 判定、scan_login | 以 consult 为准 | 工具版本实例差异；harness 属 boxing 项目本地扩展 |
| 6 | 截图命令 | `simulator_screenshot --path` | `automation_viewport_action --action screenshot` | 以 consult 为准 | 冲突 → consult |
| 7 | 服务启动治理原则 | 「启动命令一律从 CLAUDE.md/launchSettings/package.json 读取，禁止硬编码」 | 直接给出 uvicorn/vite 具体命令 | 以 consult 命令为底；原则 ✅已裁（R-007 保留回灌，2026-08-23，已泛化）入 §5.1/§5.2，具体命令改标「示例（从配置读）」 | 冲突 → consult；boxing 的防硬编码原则本身是通用改进，并入需改写 consult 命令段，超出演示例替换的最小修改边界 |
| 8 | 集成阶段前后端启动示例 | dotnet run / npm run dev（含端口 5164 等） | uvicorn :8000 / vite --port 5173 | 以 consult 为准 | 实例差异不回灌 |
| 9 | 报告路径 | `tests/test-reports/*-execute-report-*.md` | `test-reports/tdd-execute-report-*.md` | 以 consult 为准 | 实例差异不回灌 |

## 三类清单

### 回灌清单（1 项）
1. **§5.2 执行步骤第 6/7 步之间新增「小程序端分支」blockquote**：小程序端不用 Playwright/Cypress，改用 wechatide automator 全集成模式（见 wechatide-skill）。原文取自 boxing；consult 触发表仍含 §4b miniprogram 阶段，该说明补齐集成阶段对小程序端的分支语义。

### 待议清单（3 项，均已随 R-007 定案关闭）
1. **API / Page Mock / Integration 阶段的「TDD 设计文档存在且为最新版本」前置行**：boxing 有、consult 删（小程序阶段保留）。→ ✅已裁（R-007/P-10，2026-08-23）：维持 consult 的删除、不回灌；草稿 §2 末已加「注记（已裁）」防回流。
2. **服务启动命令治理原则**：「一律从项目配置读取、禁止硬编码」（boxing）vs 固化 uvicorn/vite 命令（consult）。→ ✅已裁（R-007 保留回灌，2026-08-23，已泛化）：原则并入 §5.2 引导 blockquote + §5.1 两行改写，uvicorn/vite 具体命令降级为「示例（从配置读）」，健康检查地址/端口改为按项目配置。
3. **Stage 1 领域级用例先行策略**（boxing 的 `--filter ~DomainXX` 先跑 + 全量回归含 CrossDomainFlows 属预期的分层执行说明）：→ ✅已裁（R-007 保留回灌，2026-08-23，已泛化）：泛化为「先领域级用例层后全量回归」分层执行策略并入 §3.2，去除 .NET/xUnit/DomainXX/CrossDomainFlows 实例措辞。

### 实例差异不回灌清单（留项目侧）
- wechatide harness 本地扩展全套及新旧命令族差异。
- SQLite :memory:、端口 5164/5173、`src/server-api/BoxingPlatform.Api` 启动方式等 boxing 项目参数。
- `tests/api-autotest/` 与 `design/06-tdd` 目录命名。

## 血缘
frontmatter 已加 `lineage:`（origin: arb-hub + 三方 sha256 前 12 位）。除处置表所列外，正文与底座逐字一致。

## R-007 回灌记录（2026-08-23）
- P-12 服务启动禁硬编码原则：§5.2 顶部新增「服务启动原则」blockquote；§5.1 前置两行、§5.2 步骤 2/4 的 uvicorn/vite 命令改标「示例（从配置读）」；步骤 3/5 轮询地址改为按项目配置。
- P-11 分层执行策略：§3.2 命令表后新增「先领域级后全量」泛化 blockquote（去 .NET/xUnit 实例措辞）。
- P-10 前置设计文档行：维持 consult 删除，§2 末加「注记（已裁）」，不回灌。
