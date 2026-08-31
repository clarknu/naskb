# MERGE-NOTES — release-management（CASE-005 门禁并集）

## 〇、CASE-014：教训回流 + 过程资产（2026-08-30，v1.1.0-arb.1）

> 本次为**回收**方向（consult 领先 → bundle），非三方分叉仲裁；裁决见 `audits/2026-08-30-c014-lessons-review.md`。

- **回收 v1.1.0 教训（§八）**：consult 在 CASE-007 4 条之后于 2026-08-29 上线再增补 14 条至 18 条；按项目中性审核：A（#1-11、15-17，14 条）直接回收；B（#12/13/18）收原则句、实例入适配层；C（#14 Dify 控制台 API）不收、留项目侧；**#18 更正**——Tunnel 非默认、默认直接域名映射、Tunnel 只在云边界拦入站（ICP 前置）时兜底。
- **过程资产收敛**：发布配置权威由「`release/`(environments.yaml/policy.md/CHANGELOG) + `docs/ecs-deploy-design.md`/`deploy-guide.md`/`environment-checklist.md`」收敛为**唯一** `deployment-config-guide.md`（consult 已如此合并、原文件归档 `docs/_archive-2026-08-29/`）；§六 重写为「过程资产与引用定义」（必记 ①-⑦ + 引用次序 + 文档 vs 密钥库边界）。
- **泛化**：删除 zy-ai-consult 专名/IP（`192.168.5.2`、`121.237.183.231`、`zy-ai-<组件>-beta.<主域名>`、Dify/OpenProject/paramiko 等），改为「示例」；真实值入项目过程资产。
- **交叉引用**：§八 #11 ↔ `credential-management`（设计资产打码）+ `deployment-principles`（配置单一真相源+留痕）；§六 引用 `deployment-principles`（门禁10/11 判定）+ `credential-management`。

---

- 日期：2026-08-23 ｜ 底座：`inbox/zy-ai-consult/release-management/SKILL.md`（e81304f0379e）
- 三方关系：仅 zy 两家；通用部分（红线、四层级原则表、重启策略原则、SemVer、回滚、迁移要求）逐字相同，差异集中在门禁命令实例与项目侧引用。

## 一、门禁清单对照（consult 9 条 vs zy-iot 8 条）

**consult 独有：G9 架构契约校验（L2+）。**
**zy-iot 独有成分：G8 内的「WS 冒烟」组件。**
其余 G1-G8 为同一门禁的两地实例（其中 G4、G6 逐字相同）。

## 二、并集推导表

| 并集# | 门禁 | zy-ai-consult 实例 | zy-iot-ai 实例 | 推导 |
|-------|------|--------------------|----------------|------|
| G1 | 全量测试绿 | `pytest`，见 `scripts/README.md` | `PYTHONPATH=src python -m pytest tests/ -v` | 同一门禁两地实例 → 通用要求 + 「示例（项目侧适配）」 |
| G2 | e2e 绿 | `scripts/e2e_full.py` / `e2e_ai.py` | 泛述「浏览器端到端测试通过」 | 同一 → 通用 + 示例取 consult 脚本形态 |
| G3 | ORM-DB 无差异 | `alembic upgrade head` 校验（暂无独立 diff 脚本） | `scripts/diff_orm_pg.py`（dev 库） | 同一门禁两种实现 → 两种实现均以示例形式保留 |
| G4 | 迁移预演 | 目标环境上一级（或同构环境）`alembic upgrade head` 成功 | 同文 | **逐字相同** → 直接保留 consult 文本 |
| G5 | 密钥齐全 | 强随机密钥；远程 `deploy/.env` chmod 600 由部署脚本生成、不入库 | 固定 JWT_SECRET；`.credentials/deploy/prod.env` | 同一门禁两地实例；**要求口径取 consult（强随机、不入库）**，zy-iot 固定密钥口径仅存本表备查 |
| G6 | CHANGELOG 更新 | 本版本条目写入 `release/CHANGELOG.md` | 同文 | **逐字相同** → 直接保留 |
| G7 | 健康检查 | API 健康端点 200 + 前端首页 200（`/health` 返回 ok） | API 健康端点 200 + 前端首页 200（泛述） | 同一 → 通用 + 示例 |
| G8 | 目标环境全量回归 | API 全端点回归（认证→只读端点 200 抽查+带参种子补测）+ 关键旅程冒烟（对话/任务导入/提醒）+ 环境对比 | API 全端点回归（登录→枚举无参 GET 断言+带参种子补测）+ **WS 冒烟** + 关键旅程冒烟 + 环境对比 | 同一门禁组成有差 → 并集保留四组件框架；WS 冒烟泛化为「协议层冒烟（如 WS——按项目技术栈取舍）」，具体旅程清单降为示例 |
| G9 | 架构契约校验（L2+ 项目） | 探针 + 运行器退出码 0（`_shared/arch-contract-spec.md` §10）；通常已含于门禁 1 测试套件 | ✗ 无 | consult 独有 → 直接并入 |

统计：重叠 8 项（逐字相同 2、同门禁异地实例 6）；独有 consult 1 项（G9）；独有 zy-iot 成分 1 项（G8 的 WS 冒烟组件，技术栈实例，并入集为可选协议层冒烟）。**门禁并集共 9 条。**

## 三、SKILL.md 改动范围

1. frontmatter 新增 lineage + `case: CASE-005`。
2. §二 发布门禁：表前新增适配说明引言（标注「示例（项目侧适配）」格式约定，真实命令留在各项目 `release/` 目录）；门禁表改写为上表并集的通用化版本（7 处「示例（项目侧适配）」标注）。
3. 其余全部保留 consult 文本（冲突规则）。特别说明：
   - 头注/§六的项目文档引用（ecs-deploy-design 等）与 zy-iot 的（release-management-plan/database-migration）互为项目实例，按「冲突以 consult 为准」保留 consult 版；
   - 流程步骤 7 未追加 WS 冒烟字样——避免新造条款，WS 由门禁 8 示例层承载，是否适用由各项目 policy 决定；
   - 时间安排注取 consult 版（zy-iot 的分钟数估计属项目实例）。

## 四、三类清单

- **已回灌**：0 项（boxing 无此技能；zy-iot 差异均为命令实例，按规则不互换）
- **待议**：0 项（G5 密钥口径差已按「冲突以 consult 为准」裁定为强随机口径，如 zy-iot 项目需豁免另行走发布评审）
- **挂起**：0 项
