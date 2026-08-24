# 后端架构设计变更说明 v0 → v1

> 存量项目 SFDS 方法论接入：复杂度判定 L3，建立 11 文件架构资产 + 架构契约（机械通道）+ 探针 + pytest 门禁。
> 日期：2026-08-24

---

## 变更 1：建立 L3 架构资产

**类型**：新增架构设计（存量接入）
**来源**：SFDS 方法论补全（backend-architecture-design §1 问卷 + 代码事实基线）

### 变更内容

| 之前 | 之后 |
|------|------|
| 无架构资产（平铺 md） | 10 数据文件 + arch-contract + design-decisions + audit-dossier 骨架 |

- `system-topology.js`：L3 模块化单体（问卷 Q10/Q11/Q12/Q13=yes；Q1-Q9/Q14=no）
- `module-boundaries.js`：11 模块（域切片 + 协议层 + 平台核心 + 数据访问），跨组调用白名单=存量基线
- `layering-strategy.js`：4 层（HTTP/MCP/CLI 协议层 + common 核心层）
- `caching-strategy.js` / `security-policy.js` / `resilience-policy.js` / `data-consistency.js` / `observability-policy.js` / `event-contracts.js`
- `arch-contract.js`：11 条规则（4 dependency-direction / ownership / value-domain / set-relation×5 / reference-whitelist；4 条 reviewLedger；2 条 knownDebts K-001/K-002 宽限至 2026-11-24）
- `design-decisions.js`：架构域决策视图（DD-005/DD-A001~005）
- `audit-dossier.js`：审计档案初始骨架（审计模式运行后整体再生成）
- 探针：`scripts/probes/probe_naskb.py`（AST 静态；51 units / 304 依赖边 / 55 表引用 / 5 值域字面量 / 52 路由）
- 门禁：`tests/test_arch_contract.py`（pytest 包装运行器，断言退出码 0）

### 理由

- 架构契约模型真实跑通：首轮运行退出码 0（11 规则全过、债务 2/2 生效、未分组单元 0）。
- 白名单/表归属按存量基线声明（探针事实反推）——机械校验从"今天起"守卫新增漂移。

---

## 涉及的 Section / Flowchart

- 无 flowchart；架构资产供 architecture-viewer.html 渲染与契约运行器消费。

---

## 变更 2：裁剪口径与安全边界（DD-009 拍板批次）

**类型**：策略调整｜**来源**：用户拍板（2026-08-24）

- security-policy：认证=全部需身份（匿名仅三引导端点）；新增 directLinkBoundary（MCP 直链不认证，边界=网关 IP 约束）
- observability-policy：健康端点/指标 → **裁剪**（门禁 7 以 /api/config/public + /api/stats 代替）
- 
esilience-policy：频控 G1-G5 → **裁剪**（结构性限流承担）
- udit-dossier：coverage 同步（caching/observability 裁剪注记）

---

## 变更 3：架构债务清零（K-001/K-002，2026-08-24）

**类型**：债务清理｜**来源**：用户指令（"赶紧清掉"）

- `server/routes_sources.py`：SourceIn.access_mode 默认值 `"rw"` → `ACCESS_MODES[0]`（引用 source_registry 权威常量）
- `skill/cli.py`：adopt 构造 `access_mode="rw"` → `ACCESS_MODES[0]`（同上）
- `arch-contract.js` knownDebts：条目移除（留占位）；audit-dossier debts 清空
- 验证：探针 literal 5→3（仅权威定义处）；契约 0 违规 / 0 债务 / 退出码 0
