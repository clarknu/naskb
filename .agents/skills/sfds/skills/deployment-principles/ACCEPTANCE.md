# DEPLOYMENT-PRINCIPLES · ACCEPTANCE

- 技能：DEPLOYMENT-PRINCIPLES（部署总原则：环境拓扑 + 中间件资源放置 + 网络访问拓扑 + 部署原则）
- 来源：**合并**两个原则/评审资产（CASE-020）+ 网络分层（CASE-021）+ **细则定稿回收**（CASE-022，consult v1.1.0 §2 同源）
- 版本：1.2.0-arb.1
- 定位：**原则/评审资产**（无步骤流程），被 `release-management`（发布门禁）与 `review`（校核维度）引用，并按触发词独立触发

## v1.2.0-arb.1 验收要点（2026-08-31）

- [x] §三 重构为「三原则 + 落地规则 8 条」；与 consult `infra-service-isolation` v1.1.0 §2 / `deployment-config-guide` §10.4b **语义等价**（取并集，以细则为准）。
- [x] 安全红线入条款：中间件**仅内网绑定、禁 `0.0.0.0` 公网**。
- [x] **服务名 `{env}-{service}` 环境前缀**（防多环境共网 DNS 冲突）入条款 + 清单。
- [x] 业务全进 Docker / 跨产品禁互访 / 访问路径判定 / 多线并存 + Tunnel 前置层定位 / 每环境宿主端口唯一，全部成文。
- [x] 评审清单网络项 3→8；正反例网络项 3→5。
- [x] 无项目专名（IP/域名/产品名均为泛化示例）。

## 接受范围

| 项 | 结论 |
|---|---|
| 是否入册（pipeline-registry.js） | ✅ 已登记（`layer: 原则`, `stage: review`, `priority: 5`），非方法论孤岛 |
| 性质 | 原则/评审资产（无步骤流程）；「环境拓扑规范 + 中间件资源放置」合一，统一总纲 |
| 一、环境拓扑规范 | 线上一致不超范围；环境非随意堆积；本地开发不出子网/Mock 绕过；预发与线上逻辑隔离/自建复用/轻量独立一套；数据库逻辑隔离元规则 |
| 二、中间件资源放置 | 宿主机原生/统一独立实例；业务 compose 不自建；compose 自带公共服务移除；host-gateway 访问；三环境同构；多系统共享独立实例（每系统一库一用户）；凭据集中管理 |
| 三、评审检查清单 | 合并去重后 11 项 |
| 四、正例/反例 | 合并后 7 行 |
| 引用关系 | 被 release-management 门禁（§二 门禁10/11）与 review 校核维度（§2.13）引用；与 credential-management（机密）/ release-management（怎么发布）互补 |

## 验收状态

- **L1 静态验收通过**：frontmatter（name/version/lineage/case=CASE-020/merge.from/triggers 兼容合并）完整；触发词为两来源并集去重；与既有技能无冲突触动词（「环境配置」等已并入，不再与 credential 撞词）。
- L2/L3 待测；`release-management`/`review` 的引用已指向本技能（见 release-management §二 门禁10/11、review §2.13、AGENTS.md 铁律表）。
