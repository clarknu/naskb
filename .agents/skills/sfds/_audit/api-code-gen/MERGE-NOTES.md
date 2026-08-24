# MERGE-NOTES — api-code-gen（仲裁版草稿）

- 底座：`inbox/zy-ai-consult/api-code-gen/SKILL.md`（sha256 前12位 `0c38958c7b5e`，与 zy-iot-ai 版完全相同）
- 参照：`inbox/boxing-competition-operation/api-code-gen/SKILL.md`（`1664e1888d44`）
- 草稿：`drafts/api-code-gen/SKILL.md`

## 三方处置表

| # | 差异点 | boxing | zy-iot / consult | 处置 | 依据 |
|---|--------|--------|------------------|------|------|
| 1 | 项目配置文件名 | `CLAUDE.md` | `AGENTS.md` | 以 consult 为准 | 内容冲突 → consult |
| 2 | 架构设计资产路径 | `design/04-platform-api/backend-architecture/` | `design/05-backend-architecture/` | 以 consult 为准 | 技术栈实例差异不回灌 |
| 3 | API 设计数据路径 | `data/{slug}.js` | `data/rest/{slug}.js` + 协议 protocol.js | 以 consult 为准 | 实例差异（多协议布局） |
| 4 | 输出目录 | `src/server-api/`（ASP.NET Core） | `src/server/` | 以 consult 为准 | 冲突 → consult；路径实例留项目侧 |
| 5 | 输入规格契约 blockquote | 有 | 无 | **回灌** | 明显通用且 zy 缺失 |
| 6 | 全量回归归口说明（§8.8 tdd-execute） | 有 | 无 | **回灌** | 明显通用且 zy 缺失 |
| 7 | 代码示例语言 | C#（EventBus/EventStore 等） | Python dataclass | 以 consult 为准 | 技术栈实例差异不回灌 |
| 8 | 架构风格路由 | 3 风种 | 增加 `monolithic`、旧值映射、IoT Gateway 分支 | 以 consult 为准 | zy 侧演进，boxing 无对应缺失 |
| 9 | 步骤 5 定位 | 「冒烟测试」+ 回归归口注记 | 「测试验证」 | consult 为准 + 回灌注记（见 #6） | 冲突部分以 consult，注记单独回灌 |
| 10 | review 委托口径 | API→代码/ER→ORM/TDD→API；架构→代码归 backend-architecture-design | API→代码/ER→ORM/架构→代码 三维度 | ✅已裁（R-007 定案：选其它——§2 受托三维度改为 API→代码/ER→ORM/TDD→API，2026-08-23） | 与 review 草稿 §2.11 口径统一：「架构→代码」合规由 review 委托 backend-architecture-design |
| 11 | ASP.NET 示例免责声明 | 有（「boxing 实例…按 CLAUDE.md 替换」） | 无 | 不并入，✅已裁（R-007 定案：不回灌，2026-08-23） | 措辞绑定 boxing 实例；consult 正文已是技术栈无关表述 |

## 三类清单

### 回灌清单（2 项）
1. **输入规格契约 blockquote**（§技能说明，输入源列表之后）——原文取自 boxing 同位段落，未改写。
2. **「全量回归统一由 §8.8 tdd-execute 执行」注记**（步骤 5 之后）——原文取自 boxing 同位段落，未改写。

### 待议清单（2 项，均已由 R-007 裁决关闭）
1. ~~**ASP.NET 示例免责声明**~~ ✅已裁（R-007 定案：不回灌，2026-08-23）：boxing 免责段措辞绑定 boxing 实例，consult 正文已是技术栈无关表述，不并入。
2. ~~**「架构→代码」委托归属口径**~~ ✅已裁（R-007 定案：选其它，2026-08-23）：受托三维度统一为 API→代码/ER→ORM/TDD→API（review §2.11 口径），「架构→代码」合规由 review 委托 backend-architecture-design；本技能自身的架构后置检查（步骤 1.3/6.3）保留不变。

### 实例差异不回灌清单（留项目侧）
- C# ↔ Python 代码示例（事件类/EventBus/EventStore/Handler/目录树）。
- `src/server-api/BoxingPlatform.Api/` 目录结构与 `DomainXX` 组织。
- `design/04-platform-api/backend-architecture/` 路径编号。
- `CLAUDE.md` 字段示例值（C# 12 / .NET 8 / EF Core / dotnet test）。

## 血缘
frontmatter 已加 `lineage:`（origin: arb-hub + 三方 sha256 前 12 位）。除上表处置外，正文与底座逐字一致。
