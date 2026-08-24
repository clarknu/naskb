# MERGE-NOTES — backend-architecture-design（仲裁版草稿）

- 底座：inbox\zy-ai-consult\backend-architecture-design\SKILL.md（sha256 前 12 位：c0c1c935c367）
- 三方关系：**三方各异**（boxing 90fc6136590f / zy-iot ea56aba65a83 / consult c0c1c935c367）。consult 较 zy-iot 新增 §3b 审计模式、决策账本（design-decisions.js）、架构契约（arch-contract.js）、审计档案（audit-dossier.js）与「先记账后改资产」原则；boxing 相对多出 §0.4 域注册表同步等
- 仲裁方向：内容冲突以 zy-ai-consult 为准；boxing §0.4 为本轮重点评估对象

## 三方处置表

| 章节/内容 | boxing | zy-iot | zy-ai-consult | 处置 | 理由 |
|-----------|--------|--------|---------------|------|------|
| **§0.4 域注册表同步** | 有 | 无 | 无 | **已回灌** | 见下方专项判定 |
| 输入源清单含 `design/domain-registry.js` + 步骤 1 提取内容表含 domain-registry 行 | 有 | 无 | 无 | 已回灌（与 §0.4 同一单元的配套声明） | 保持回灌后文内自洽 |
| §3b 审计模式 / 决策账本 / arch-contract / audit-dossier / 「先记账后改资产」 / 检查清单 L2+ 三项 / 使用方式第 7 条 | 无 | 无 | 有 | 基座保留（底座已含） | consult 独有演进，非冲突 |
| 技术栈配置文件 | `CLAUDE.md` | `AGENTS.md` | `AGENTS.md` | 以 consult 为准；CLAUDE.md **留项目侧** | Agent 工具链实例差异（Claude Code vs 通用 agents 约定） |
| 输出目录 | `design/04-platform-api/backend-architecture/data/` | `design/05-backend-architecture/data/` | 同 zy-iot | 以 consult 为准 | 目录拓扑实例差异，不属方法论改进 |
| L2 幂等落点细化（接口级幂等键落 security-policy.js 或独立小节；L2 不生成 resilience-policy.js） | 有（§0.2 表与 §1.2 表两处括注） | 无 | 无 | **待议** | 是对 L2 门控歧义的真实澄清且引用的资产文件双方 schema 均存在，但无法确认 zy 系删除是否有意，不满足无争议门槛 |
| architectureStyle 枚举语义 | 含独立 `event-driven`/`cqrs` 取值 | 组合语义（如 `event-driven-modular-monolith`）+ 显式组合声明规则 | 同 zy-iot | 以 consult 为准 | consult 附带明确理由（避免生成器无法路由），为有意识演进 |
| 一致性检查 issue type | `arch_rule_violation` | `layer_violation` | `layer_violation` | 以 consult 为准 | 枚举命名冲突，consult 为准 |
| Review 维度数 | 全 13 维度（D0-D12） | 全 12 维度 | 全 12 维度 | ✅已裁（R-007 定案：选其它——以 review 自身为准改为「全 13 维度」，2026-08-23） | review 草稿实际 D0–D12 共 13 维且全文一致；本技能 §1.2 影响表已同步为「全 13 维度」 |
| 步骤 1 追溯前置检查 & 完成检查清单中工作流追溯字段名 | `inputs`/`outputs`/`consumers` | `source`/`target` | `source`/`target` | **lineage 内一致性修复**（两处改回 `inputs`/`outputs`/`consumers`） | 本 lineage business-workflow §4.5（P-17 重排后编号，原 §5.5）定义的节点协议字段即为 inputs/outputs/consumers（草稿集内可直接验证）；`source`/`target` 在整个 lineage 无任何 schema 支撑，属悬空引用。此修改是把描述对齐到 lineage 权威 schema，非引入 boxing 方法论 |
| `_trace` 兼容性说明（boxing 存量 10 文件不强制回填） | 有 | 无 | 无 | 不回灌 · 留项目侧 | 措辞即明示为 boxing-competition-operation 项目存量说明 |
| 同步螺旋步骤 6 与检查清单中 CHANGELOG 具体路径+格式行 | 详细路径与格式 | 泛化为「CHANGELOG 记录本次更新」 | 同 zy-iot | 以 consult 为准 | 路径细节随输出目录拓扑属项目实例 |

## §0.4 回灌专项判定

**判定：回灌（通用治理原则）。**

理由：
1. **纯治理性、零业务语义**——原文仅两句：「开工前先读 `design/domain-registry.js`；改领域边界/模块划分前必须先写注册表」，不含任何拳击赛事领域词汇；
2. **基础设施三系共有**——`design/domain-registry.js` 并非 boxing 私有：本 lineage（consult=基座）的 business-workflow（规则 3、步骤 1/步骤 5-2、§4.1）、api-design（规则 3）、entity-relationship（规则 4）均载有同一「域注册表同步」原则；本技能复杂度问卷 Q13 也已读取 domain-registry；
3. **缺失造成同族不对称**——四个设计技能中唯独 backend 直接执行「改领域边界/模块划分」（步骤 4）却无注册表先行原则，而这是最容易破坏跨域一致性的操作；
4. **与基座零冲突**——consult 文中不存在与之抵触的条款，插入 §0.4 恰好补全 §0.1–0.3 序列；
5. **配套同步**——输入源 bullet 与步骤 1 提取表行一并回灌，避免「原则要求先读但输入清单不列」的自相矛盾。

## 清单

### 已回灌
1. §0.4 域注册表同步（正文 1 节）
2. 输入源清单 domain-registry.js 行
3. 步骤 1 提取内容表 domain-registry 行

（以上 3 处为同一回灌单元：域注册表同步原则及其配套输入声明）

### 不回灌 · 留项目侧
1. CLAUDE.md 配置文件名（boxing 工具链实例）
2. 输出目录 `04-platform-api/backend-architecture`（boxing 目录拓扑实例）
3. `_trace` 存量兼容性说明（boxing 项目存量注释）
4. CHANGELOG 具体路径与格式行（随目录拓扑的项目实例）

### 待议
1. L2 幂等落点细化是否并入（见处置表）。
2. ~~Review 维度数 12 vs 13（D0-D12）需与 review skill 对账。~~ ✅已裁（R-007 定案：以 review 自身为准＝13 维，2026-08-23）：§1.2 影响表四处「全 12 维度」已改为「全 13 维度」。
3. （备注，非 boxing 来源）consult 版工作流追溯字段悬空引用已在本次以「lineage 内一致性修复」方式处理；若枢纽认定 `source`/`target` 为 development-standard §2.6 的新代次字段名，应反向修订 business-workflow schema 并回退本次修复。✅已裁（R-007 定案：注明成立，2026-08-23）：经核 development-standard §2.6 数据协议表——API 端点定义 `consumes`/`produces`、ER 字段定义 `source`/`consumers`、工作流节点定义 `inputs`/`outputs`/`consumers`，本技能全部追溯字段引用成立（步骤 1 前置检查、§3.2 检查 4/5、完成检查清单），已在正文前置检查处加注；`source`/`target` 组合仍无 schema 支撑，原「lineage 内一致性修复」维持不回退。

## L1 相关事实
- 草稿对底座的修改共 6 处：frontmatter lineage 头 ×1、§0.4 新节 ×1、输入源行 ×1、提取表行 ×1、追溯字段名修复 ×2。无其他改动。
