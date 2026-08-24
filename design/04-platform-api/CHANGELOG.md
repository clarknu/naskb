# API 设计变更说明 v0 → v1

> 存量项目 SFDS 方法论接入：按代码事实基线反向建立 REST 契约资产 + AI Tools（MCP）协议资产。
> 日期：2026-08-24

---

## 变更 1：建立 6 域 REST 资产 + 协议定义

**类型**：新增契约（存量接入）
**来源**：SFDS 方法论补全（server/*.py 实际注册为准；差异显式标注）

### 变更内容

| 之前 | 之后 |
|------|------|
| 无结构化 API 契约（平铺 md） | 6 域端点文件（26+ 端点六维度）+ 协议定义 |

- `rest/01-source-management.js`：10 端点（注册/测试/扫描/分析/收编/变更/确认/启停/删除/列表）
- `rest/03-retrieval-qa.js`：6 端点（kb/search、ask、legacy search/reload、stats、pg/rebind）
- `rest/04-deep-analysis.js`：1 端点（kb/ask 条款级）
- `rest/06-platform-console.js`：9 端点（tree/files/download/preview/parsed/thumbnail/jobs×2/config）
- `rest/02-ingestion-analysis.js`、`rest/05-knowledge-reorganize.js`：endpoints=[]（任务驱动/MCP，防双源）
- `rest/protocol.js`（REST 协议定义）+ `_conventions.js`（公共约定附录，含认证口径差异基线）
- `ai-tools/protocol.js` + `ai-tools/tools.js`（MCP 14 工具，LLM 消费者铁律 6 条过检）

### 理由

- 契约先行：后续 tdd-build/页面设计/代码复查以本资产为对照基线。
- AI Tools 协议按 api-design §10.5/§10.6 落地（与 REST 消费者（确定性程序）区分设计）。

---

## 涉及的 Section / Flowchart

- 每域 overview_blocks/design_decisions/endpoints；差异见 IMPLEMENTATION-PLAN.md §二。

---

## 变更 2：端点补充 + 认证口径 + MCP 三工具（DD-009 拍板批次）

**类型**：新增/调整｜**来源**：用户拍板（2026-08-24）

- 
est/01：新增 GET /api/sources/{sid}/report（一致性报告：source+backend+knowledge，PG 不可达内嵌 error）
- 
est/06：新增 GET /api/folder（目录条目：folders 表 → folder.json 兜底 → 现场生成）
- 全端点 permission public → login_required（仅 /api/config/public 保留 public 例外）；_conventions §auth/§rate-limit 重写
- i-tools/tools.js：新增 kb_list_sources / kb_list_tree / kb_get_file_url（A 读组）；kb_fetch_file 直链边界（网关 IP 约束）记录
- _conventions：多 token 单 token 声明随文档修正

---

## 变更 3：条款级回退显式提示（P-003 A'）

- `rest/04-deep-analysis.js`：body 增 deep 参数；响应增 level（chunk|summary）/note 字段；design_decisions 记 A'
- `ai-tools/tools.js`：kb_ask returns 增 level 说明（A' 契约自洽）

---
