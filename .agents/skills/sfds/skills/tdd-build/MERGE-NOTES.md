# MERGE-NOTES — tdd-build（仲裁版草稿）

- 底座：`inbox/zy-ai-consult/tdd-build/SKILL.md`（`c16853e0c671`，与 zy-iot-ai 版完全相同）
- 参照：`inbox/boxing-competition-operation/tdd-build/SKILL.md`（`7b1586e18413`）
- 草稿：`drafts/tdd-build/SKILL.md`

## 三方处置表

| # | 差异点 | boxing | zy-iot / consult | 处置 | 依据 |
|---|--------|--------|------------------|------|------|
| 1 | fixture 一致性检查（§6 设计-代码一致性核对步骤） | 第 4 步，后续步骤顺延 | 无此步 | **回灌** | 明显通用且 zy 缺失 |
| 2 | 问题类型枚举 `fixture_mismatch` | 有 | 无 | **回灌**（随 #1 配套） | 与 #1 同源配套，缺它则该类问题无处归类 |
| 3 | 规则 #3 覆盖度裁剪条款 | 括注「按 §2.5 复杂度分级裁剪…L1 可省略；L2+ 全量」 | 无括注 | **回灌** | 通用；已核实 consult 底座存在 §2.5「TDD 分级策略」，交叉引用成立 |
| 4 | 「目录说明（.NET 实例）」blockquote ×3 | 有（Stage1/3 共用目录、按用例层级门控、DomainXX/CrossDomainFlows 组织） | 无 | ✅已裁（R-007 保留回灌，2026-08-23，已泛化）：理念并入草稿 §1 目录说明 blockquote；.NET/xUnit/DomainXX 等实例措辞留项目侧 | 「门控按用例层级而非物理目录」理念或可通用，但全文以 .NET/tests-api-autotest 实例措辞书写 |
| 5 | Stage 2b 完成清单 MCG-L1~L6 布局检查行 | 有 | 无 | 不并入，**记待议** | 依赖 mobile-code-gen 布局规范（该规范本身已挂待议），一并挂起 |
| 6 | wechatide harness 本地扩展（harness up/down、wechatide-setup 引用） | 多处 | 无；命令为 `-t` 风格 + `automation_viewport_action` 截图 | 不回灌 | boxing 自我标注「[本地扩展]」「详见项目 wechatide-setup skill」，属项目侧扩展；zy 侧 wechatide 命令族不同 |
| 7 | 截图命令 | `simulator_screenshot --path` | `automation_viewport_action --action screenshot` | 以 consult 为准 | 冲突 → consult |
| 8 | TDD 文档路径 | `design/06-tdd/` | `design/07-tdd/` | 以 consult 为准 | 实例差异（目录编号）不回灌 |
| 9 | 测试代码目录示例 | `tests/api-autotest/integration/DomainXX_*/`、`.csproj` 组织 | `tests/api/{domain}/` conftest.py 结构、`tests/integration/{client-slug}/` Playwright 结构 | 以 consult 为准 | 技术栈实例差异不回灌 |
| 10 | 示例业务域 | 赛事/报名/票务 | 设备/IoT | 以 consult 为准 | 实例差异不回灌 |
| 11 | Mock/真实边界举例 | 支付网关/短信/微信 API | LLM/ASR/TTS/MQTT broker | 以 consult 为准 | 实例差异不回灌 |
| 12 | Stage 1 测试框架表述 | xUnit + WebApplicationFactory（当前项目）、SQLite :memory: | pytest/httpx/Jest/xUnit 等、内存库经 DI 拦截 | 以 consult 为准 | 冲突 → consult（更技术栈无关） |

## 三类清单

### 回灌清单（3 项）
1. **§6 一致性核对新增第 4 步「fixture 一致性检查」**，原第 4/5 步（编译/语法、追溯完整性）顺延为第 5/6 步。原文取自 boxing。
2. **JSON 问题类型枚举增加 `fixture_mismatch`**（`assertion_mismatch` 之后），与上一条同源配套。
3. **§2.1 规则 #3 覆盖度括注**：「状态转换/错误场景/边界条件/权限维度按 §2.5 复杂度分级裁剪，L1 简单 CRUD 可省略相应维度；L2+ 全量执行」。原文取自 boxing；§2.5 标题在底座中逐字存在（第 190 行），引用有效。

### 待议清单（原 2 项；第 1 项已裁，剩 1 项）
1. **「目录说明（.NET 实例）」blockquote 组**（Stage 架构图后、Stage1 代码目录后、Stage3 代码目录后）：其可通用化内核是「当 Stage 1 与 Stage 3 物理共用测试根目录时，『Stage 3 在 Stage 1 全绿后启动』的门控按用例层级理解，不按物理目录分离」。→ ✅已裁（R-007 保留回灌，2026-08-23，已泛化）：已在草稿 §1 架构图后增补技术栈无关的「目录说明（门控按用例层级而非物理目录）」blockquote；.NET/xUnit/DomainXX/CrossDomainFlows 等实例措辞不并入、留项目侧。
2. **Stage 2b 完成清单的 MCG-L1~L6 布局检查行**：与 mobile-code-gen 待议项 1（布局合理化设计规范）联动，若该规范入枢纽体系，本组行随之恢复。

### 实例差异不回灌清单（留项目侧）
- .NET/xUnit/WebApplicationFactory/SQLite :memory: 及 `tests/api-autotest/BoxingPlatform.Tests.slnx` 解决方案组织。
- wechatide harness 本地扩展全套（harness up/down、免扫码登录态、wechatide-setup skill）。
- 赛事域示例文案与 `design/06-tdd` 目录编号。

## 血缘
frontmatter 已加 `lineage:`（origin: arb-hub + 三方 sha256 前 12 位）。除处置表所列外，正文与底座逐字一致。

## R-007 回灌记录（2026-08-23）
- P-09「按用例层级门控」理念泛化并入：草稿 §1 架构图后新增 1 段目录说明 blockquote（无 .NET/xUnit/CLAUDE.md/小程序/rpx 实例措辞）。
- 对应待议清单第 1 项 / 处置表 #4 关闭。
