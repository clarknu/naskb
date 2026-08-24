# 业务工作流设计变更说明 v0 → v1

> 存量项目 SFDS 方法论接入：按真实业务行为反向建立 6 域业务工作流（含权限点/角色/RBAC 授权规范）。
> 日期：2026-08-24

---

## 变更 1：建立 6 域工作流资产

**类型**：新增流程（存量接入）
**来源**：SFDS 方法论补全（design/01-raw-input/ 整合需求文档 + 代码事实基线）

### 变更内容

| 之前 | 之后 |
|------|------|
| 无结构化工作流资产（平铺 md） | 6 域 WF 数据文件 + 权限点/角色定义 |

- `01-source-management.js`：来源全生命周期 + 变更确认清单（11 权限点）
- `02-ingestion-analysis.js`：扫描→三级判定→多模态分析→入库（4 权限点）
- `03-retrieval-qa.js`：检索/问答引擎链（3 权限点）
- `04-deep-analysis.js`：条款级入库→问答（2 权限点）
- `05-knowledge-reorganize.js`：生成→预览→确认→apply 三重校验（3 权限点）
- `06-platform-console.js`：任务生命周期 + 下载/预览子流程（5 权限点）

### 理由

- 业务工作流是权限点唯一定义源（business-workflow §3.4）；下游 API/页面设计以本资产做权限映射。
- 数据协议字段（inputs/outputs/consumers）初始已按关键链路填写，复查阶段（review）强制核验。

---

## 涉及的 Section / Flowchart

- 每域 `overview` / `main-flow` / `rules` / `permissions-table`；05 域追加 `apply-flow`（子流程）；06 域追加 `download-flow` / `preview-flow`（子流程）。

---

## 变更 2：认证口径与 deep 语义（DD-009 拍板批次）

**类型**：规则调整｜**来源**：用户拍板（2026-08-24，iterate 路径 C）

| 之前 | 之后 |
|------|------|
| 匿名只读角色存在（AnonymousReader：KbSearch/KbAsk/ChunkAsk/下载预览） | 全部移除——全部端点需身份（仅 /api/config/public、/api/docs、/api/openapi.json 匿名引导） |
| deep 开关语义：只影响后续，不清理存量 | 关闭即清理该来源存量条款级 chunk 行（UI 确认提示） |

涉及：01/03/04/06 域 roles 与规则；权限点保留为正式契约（多用户/角色走 R7-15）。

---

## 变更 3：条款级回退显式提示（P-003 A' 拍板）

**类型**：规则调整（诚实性）｜**来源**：用户拍板（2026-08-24，复查 P-003）

| 之前 | 之后 |
|------|------|
| 无 PG/无默认 schema 时静默回退文档级（R005） | 回退必须显式提示：level=summary + note（显式要求条款级时）——R005 更新 |

涉及 04-deep-analysis.js 规则 R005；API 契约 rest/04、ai-tools/tools.js 同步。

---
