# MERGE-NOTES — mobile-code-gen（仲裁版草稿）

- 底座：`inbox/zy-ai-consult/mobile-code-gen/SKILL.md`（`58454bbc7d5b`，与 zy-iot-ai 版完全相同）
- 参照：`inbox/boxing-competition-operation/mobile-code-gen/SKILL.md`（`56f84a5fbf62`）
- 草稿：`drafts/mobile-code-gen/SKILL.md`

## 三方处置表

| # | 差异点 | boxing | zy-iot / consult | 处置 | 依据 |
|---|--------|--------|------------------|------|------|
| 1 | 技能定位 | 面向微信小程序（wx.*/rpx/safe-area） | 技术框架无关，通用原则 | 以 consult 为准 | 冲突 → consult |
| 2 | 输入规格契约 blockquote | 有 | 无 | **回灌** | 明显通用且 zy 缺失 |
| 3 | 生成前校验语义 | 缺失即 ⚠️/🔴 分级，🔴 拒绝生成 | ⚠️ 警告清单、不阻塞、review D6/D10 兜底 | 以 consult 为准 | 内容冲突 → consult |
| 4 | `data_flow_broken` 严重度 | 🔴 并拒绝生成 | ⚠️ 不阻塞 | 以 consult 为准 | 冲突 → consult |
| 5 | 一致性检查细化项 `missing_source` / `field_dropped` / `untraced_send` | 有（含分级编码） | 无 | 不并入，**记待议** | 内容通用但与 #3/#4 的非阻塞策略存在分级张力 |
| 6 | `@trace` 注释完整性检查（检查步骤） | 有（第 7 步） | 无——但完成检查清单仍要求「已标注 @trace」 | **回灌**（补齐 consult 自身缺口） | 明显通用且 zy 缺失；consult 清单条目自证需要 |
| 7 | 「布局合理化设计规范」整节 + 完成清单 6 行布局项 | 有（8 组细则，rpx/wx 措辞） | 无 | 不强行并入，**记待议** | 原则或可通用化，但按原文并入即引入 rpx/wx 实例；铁律禁止凭记忆改写泛化 |
| 8 | 输出格式 `_shared/consistency-check-format.md` 引用 | 无 | 有 | 以 consult 为准（zy 已有共享规范引用） | — |
| 9 | 使用方式措辞 | 祈使句 | 「对 Claude 说……」 | 以 consult 为准 | 冲突 → consult |
| 10 | 关系表「tdd-build/tdd-execute 协同」行 | 有（小程序 Stage 2b 措辞） | 无 | ✅已裁（R-007 定案：选其它——按通用表述并入关系表，去小程序实例措辞，2026-08-23） | 关系本身通用；并入行已去实例化，与 consult 技术栈无关口径一致 |
| 11 | 设计路径 / 输出目录命名 | `design/05-miniprogram-{client-slug}`、`src/mobile-{app}` | `design/06-{client-slug}`、`src/{client-slug}` | 以 consult 为准 | 实例差异不回灌 |
| 12 | 后端枚举命名说明 | C# enum + JsonStringEnumConverter | 项目约定序列化格式（如 snake_case） | 以 consult 为准 | 技术栈实例差异不回灌 |

## 三类清单

### 回灌清单（2 项）
1. **输入规格契约 blockquote**（§技能说明，输入源之后）——tree.js 节点字段以 mobile-app-design「节点字段说明」为唯一 schema。原文取自 boxing。
2. **检查步骤新增第 7 步「`@trace` 注释完整性检查」**，原第 7 步枚举硬编码检查顺延为第 8 步——consult 完成检查清单中保留着「生成代码已标注 @trace 注释」却无对应检查步骤，boxing 该步正好补齐此内部缺口。原文取自 boxing。

### 待议清单（3 项，其中 1 项已由 R-007 裁决关闭）
1. **「布局合理化设计规范」整节及配套 6 行完成清单项**：容器边界、按钮尺寸档位、弹窗高度稳定、间距/字号体系、三态齐全、安全区、表单统一。底层原则看似跨端通用，但全文以 rpx 单位与 wx 组件措辞书写；按「实例差异不回灌 + 禁止凭记忆重写」未并入。若枢纽决定收录，建议先做去实例化改写再入 zy 系。
2. **一致性检查细化项 `missing_source` / `field_dropped` / `untraced_send` 及 🔴 分级编码**：检测逻辑通用，但其错误级（🔴）定性与本稿采用的 consult「⚠️ 警告不阻塞生成、review 兜底」策略冲突，需先裁决分级语义再决定是否并入。
3. ~~**关系表「tdd-build/tdd-execute 协同」行**~~ ✅已裁（R-007 定案：选其它，2026-08-23）：已按通用表述并入关系表——「协同——生成完成后调用 tdd-execute 执行对应端测试」，去除「小程序 Stage 2b」实例措辞。

### 实例差异不回灌清单（留项目侧）
- 微信小程序专属声明（wx.* API、rpx、safe-area、`.wxml/.wxss` 文件类型）。
- `src/miniprogram-{customer|fighter|operation}` 项目命名实例。
- 反例中的 `<view wx:if>`、`<picker>` 等小程序组件示例（consult 本就保留，非本次改动）。

## 血缘
frontmatter 已加 `lineage:`（origin: arb-hub + 三方 sha256 前 12 位）。除处置表所列外，正文与底座逐字一致。
