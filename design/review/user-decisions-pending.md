# 待拍板事项台账（User Decisions Pending）

> 维护：SM 接入迭代。状态：**已全部拍板（2026-08-24）**，剩余= iterate 执行。
> 原始决策存档：design/01-raw-input/07-user-decisions-2026-08-24.md
> 逐条状态在本文件「拍板结果」列更新，执行状态见 iterate 迭代报告。

## A. 待仲裁（接口行为类 · 6 项）

| # | 情况 | 拍板结果 | 执行状态 |
|---|------|---------|---------|
| D-01 | `GET /api/sources/{sid}/report` 死代码 | **要做**（接回，定义一致性报告语义） | ✅ 已执行（装饰器恢复+端点回归，见 iterate-report-dd009） |
| D-02 | `/api/folder` 孤儿匿名前缀 | **要做**（目录级描述端点） | ✅ 已执行 |
| D-03 | `POST /api/ask` `/api/kb/ask` 匿名口径 | **干掉匿名**——全部需身份（/api/config/public、/api/docs 保留作引导，待确认） | ✅ 已执行（横切） |
| D-04 | 多 token 仅 tokens[0] 生效 | 未单独拍板——随 D-03 处置：**声明单 token**（单管理员模型），实现不变，文档修正 | ✅ 已随 D-03 落地（单 token 文档声明） |
| D-05 | 深度分析关闭后存量 chunk | **清理掉**（UI 加确认提示） | ✅ 已执行 |
| D-06 | WebDAV 密码明文 | 未拍板——**登记长期债**（security-policy 已注明；V2 加密计划），本次不动 | ⏳ 随设计巡检落账 |

## B. 需确认语义（差异基线其余项）

| # | 情况 | 拍板结果 | 执行状态 |
|---|------|---------|---------|
| B-01 | kb_ask.deep 静默回退文档级 | 未单独拍板——按推荐：保持回退，响应带 engine/level 提示 | 随 review 细节作业 |
| B-02 | kb_fetch_file 直链无 token | **不要 Token**；安全边界=外围网关 IP 约束（网络层），API 层不认证 | ✅ 已固化（security-policy directLinkBoundary + release 四b） |
| B-03 | MCP 三工具未注册 | **要接**（kb_list_sources/kb_list_tree/kb_get_file_url） | ✅ 已执行 |
| B-04 | pg_vector_table/pg_vector_dim 假配置 | 未单独拍板——按推荐：**删除配置**（代码硬编码为准） | ✅ 已清扫 |
| B-05 | DOC_EXTS/TEXT_EXTS 双集合 | 未单独拍板——按推荐：统一登记 | ✅ 已清扫 |
| B-06 | collect_docs 路径语义差异 | 未单独拍板——按推荐：统一源内相对路径 | ✅ 已清扫 |
| B-07 | CLI 命令数 24 vs 28 | 未单独拍板——按推荐：28 为准修文档 | ✅ 已修订 |
| B-08 | web/dist vs web/public 文案 | 未单独拍板——按推荐：修正 | ✅ 已修订 |

## C. 裁剪口径（方法论张力）

| # | 张力点 | 拍板结果 | 落账位置 |
|---|--------|---------|---------|
| T-1 | 权限模型（RBAC 多角色 vs 单管理员） | **保留**（企业非加密资料管理有用）——当前单管理员实现不变，权限点=正式契约，多用户/角色走 R7-15 演进 | design-decisions.js + WF/UI 标注保持 |
| T-2 | 健康检查/频控/指标（L3 必产 vs 个人场景） | **裁剪** | observability/resilience 资产裁剪声明；release 门禁 7 用 config+stats |
| T-3 | TDD 架构承诺测试（行为承诺矩阵） | **补齐完整**（除健康检查维度随 T-2 裁剪） | tests/api 新增行为承诺套件 |
| T-4 | E2E 门禁（浏览器 E2E vs 无工具链） | **保留**——用全局 Playwright MCP server（本机 C:\Soft；他机各用其配置） | integration 旅程规格 + release 门禁 2 |

## D. 信息与节奏

- D 组环境事实（dev/prod 主机、PG 形态、密钥偏好）：暂不需要，发布指令时再确认。
- 发布节奏：**不主动发布**；收到明确指令 → 全做完 → 发布到指定环境。
- Git 提交：待执行批次整合后按「批次 commit」提交（待用户确认提交策略）。

## E. 远期

- ~~架构债务 K-001/K-002~~ → **已于 2026-08-24 清零**（用户指令；AC-005 违规 0、债务 0/0）。
- R5-06 剩余阶段（真实文档验证、分级检索等）。
- 方法论问题报告：**已移交**（2026-08-24 用户完成搬运；仓库 bundle 已含配套修复：verify-fixed.mjs/raw-input-to-*/wechatide 改名/arch-contract 模板等）。
- **P-002 延期实现项**（复查确认）：page-mock 执行层（Vitest+MSW）——后续独立迭代。**✅ 已实现（2026-08-24）：已接入 vitest + @vue/test-utils + jsdom + fetch mock（等价 MSW），用例 tests/page-mock/web-console/*.spec.js 全绿；未实现明细（TC-M003/M006/M007/M010）见 design/07-tdd/page-mock/web-console-tdd-design.md**。
- **P-004 对齐**（复查确认）：ER 派生 VO 已补（source_stats / folder_entry_view）。
