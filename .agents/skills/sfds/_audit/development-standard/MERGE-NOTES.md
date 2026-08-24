# MERGE-NOTES · development-standard 三方合并记录

> CASE-002 · 依据 R-002（boxing 保持活跃、双向回灌）+ 需求方裁决"内容冲突时以 zy-ai-consult 为准"
> 基座：inbox/zy-ai-consult@2026-08-23（v3.0.0，1229 行）→ 仲裁版 v3.1.0（1250 行）
> 对照方：inbox/zy-iot-ai@2026-08-23（1166 行）、inbox/boxing-competition-operation@2026-08-23（1183 行，含未提交改动）

## 一、zy 系内部差异（consult vs iot，70+/7- 行）——全部采纳 consult

| 差异 | 判定 | 理由 |
|---|---|---|
| 第一部分新增 §4 调度模式（4.1 数据源/4.2 判定流程/4.3 输出格式/4.4 铁律） | ✅ 采纳 | SFDS-C 机制的载体；管线状态机唯一裁判 |
| triggers 新增 6 个调度类触发词（下一步/继续/当前进度…） | ✅ 采纳 | 随调度模式 |
| §1.2 目录树 + pipeline-state.js；§1.5 改为生成域注册表**与管线状态** | ✅ 采纳 | 调度模式数据源 |
| §1.3 + "生成后必执行 generate-trigger-table.mjs --write" | ✅ 采纳 | 派生物禁手编铁律的落地 |
| Part2 §2 新增 ⛔产物准入边界 callout（指向 _shared/document-asset-format.md） | ✅ 采纳 | 准入规则非风格建议 |

zy 系内部差异全部为通用层内容、无项目私货——**基座整体取 consult 无需取舍**。

## 二、boxing ↔ zy 系章节对照与处置

| 章节 | boxing（SFDS v1） | zy 系（v3） | 处置 |
|---|---|---|---|
| 第一部分 §1.3 | 生成 CLAUDE.md | 生成 AGENTS.md | 取 AGENTS.md（通用 agent 标准，zy-iot 8/14 迁移决策） |
| 第一部分 §4 | 本 skill 的迭代说明 | consult：+§4 调度模式（迭代说明顺延为 §5） | 取 consult |
| 第二部分标题 | 单人全栈开发标准 **v1** | **v3** | 取 v3（代际演进：11 章→12 章、§8 加 8.0 强制约束） |
| §2 核心理念 | 基础版 | +2.x 正向数据协议/反向验证等 | 取 consult |
| §4 技能体系 | 全生态表 + 4.1 设计约束 + 4.2 新 Skill 创建规范 + 4.3 生命周期管理 | 全生态表（含 arch-contract 生态）+ 4.1 设计约束 | 见回灌判定表第 3 行 |
| §5 通用约定 | 5.0 执行契约 + 5.1~（CLAUDE.md 表述） | 5.1~（AGENTS.md 表述） | **回灌 5.0**，其余取 consult |
| §6 设计资产组织 | 基础版 | +产物准入边界 | 取 consult |
| §8 流水线 | "流水线"（无 8.0） | "七步流水线"+8.0 执行顺序强制约束 | 取 consult；**回灌覆盖率口径**入 8.5 |
| §9 复查门控 | 9.2 触发点 A/B/C + 风险等级 | 9.2 仅触发点 C（附下沉理由） | **不回灌 A/B**（见判定表第 1 行）；9.3 两方逐字相同 |
| §10/§11 | 基础版 | 含同步螺旋、决策日志、sync-status 等 | 取 consult |

## 三、回灌判定表（原清单五项 → 逐项裁决）

| # | boxing 独有内容 | 判定 | 理由 |
|---|---|---|---|
| 1 | 复查触发点 A/B（§8.6/§8.7 后轻量复查） | ❌ 不回灌 | **consult 有意删除且理由成立**：代码-设计对齐已下沉至 api-code-gen/mobile/desktop-code-gen 的后置一致性检查，Review 保持唯一外部全量入口，避免重复检查。符合"以 consult 为准"裁决。已留待 CASE-001 打包时核验各 code-gen 后置检查确实覆盖对齐项 |
| 2 | §5.0 Skill 通用执行契约（出计划→确认→执行→汇报） | ✅ 已回灌 | 通用行为铁律，zy 系缺失；与 iterate 两阶段停等铁律同源互补 |
| 3 | `_shared/consistency-check-format.md` 格式共享规范引用 | ✅ 已回灌 | 家族级共享约定雏形，与 pipeline-registry 并列的 _shared 资产；插入 §4.1 末尾 |
| 4 | 覆盖率口径唯一权威（行覆盖 60%/80% 标记线、错误边界 ≥80%） | ✅ 已回灌 | 消除 tdd-build/tdd-execute/review 各自另立阈值的漂移风险；插入 §8.5 |
| 5 | §4.2/4.3 新 Skill 创建规范与生命周期管理 | 🔀 部分被取代 → ✅已裁（R-007 保留回灌，2026-08-23，已泛化）：弃用/下线三条规则已泛化并入草稿新增 §4.2「Skill 生命周期管理（弃用/下线纪律）」 | 注册清单职责已由 pipeline-registry 准入契约（C 机制，未登记=孤岛）更强地承担；弃用/下线三条规则暂无对应物，**挂起待议**：随 capability-map 建立时决定归宿 |

## 四、外部耦合登记（assets 清单依据）

本 skill 运行依赖以下 `_shared` 家族资产（位于 `.agents/skills/_shared/`，不在本目录内）：
`pipeline-registry.js`、`gen/generate-trigger-table.mjs`、`document-asset-format.md`、`consistency-check-format.md`（本次回灌新增引用）、模板 `templates/pipeline-state.js`。

## 五、遗留事项

1. boxing 未提交快照中的 tdd/wechatide 改动与本 skill 无关，不影响本次合并基线；
2. boxing 版 L148 方法论查询表提及"触发点 A/B/C"——若后续 boxing 采纳仲裁版，该表行需同步改为"触发点 C"；
3. ~~挂起项 5 待 capability-map 设计时一并裁决~~ → ✅已裁（R-007/P-20，2026-08-23）：弃用/下线三条纪律已泛化并入草稿 §4.2（创建规范部分仍由 pipeline-registry 准入契约承担）。

## 六、R-007 回灌记录（2026-08-23）

- P-20 Skill 弃用/下线纪律：草稿 §4 技能体系新增「#### 4.2 Skill 生命周期管理（弃用 / 下线纪律）」三条——弃用标注（description 标 ⚠️ 已弃用 + 触发词移除）、删除前三处同步下线（项目技能注册表 AGENTS.md/pipeline-registry + 本文件 §4 全生态表 + 全局技能目录 `~/.agents/skills/`，涉及派生物重跑生成脚本）、历史保留在 Git。
- 泛化处理：boxing 原文的项目专属注册表述措辞统一为"项目技能注册表（AGENTS.md 可用技能表 / pipeline-registry）"，与 consult v3 底座的派生物铁律衔接；无 .NET/xUnit/CLAUDE.md 实例措辞。
