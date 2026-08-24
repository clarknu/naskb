---
name: release-management
version: 1.0.0
description: 发布管理方法论——环境层级与晋升、发布门禁、版本规范（SemVer + tag）、回滚流程、线上安全红线。项目特定配置见 release/ 目录（environments.yaml / policy.md / CHANGELOG.md）。
lineage:
  origin: arb-hub
  case: CASE-005
  sources:
    zy-iot-ai:     {sha256: 28bc8805eb1b}
    zy-ai-consult: {sha256: e81304f0379e}
---

# Release Management（发布管理）

> **定位：通用发布方法论 skill。** 环境层级、发布门禁、版本规范、回滚流程为通用方法论
> （可复制到全局 `~/.agents/skills/` 复用）；**项目特定数据一律不写入本 skill**，
> 通过 `release/` 目录（`environments.yaml` 环境清单 / `policy.md` 发布规则 / `CHANGELOG.md` 版本历史）
> 与项目部署文档引用。
> 本项目部署设计：`docs/ecs-deploy-design.md`（决策 D1-D6）；部署指南：`docs/deploy-guide.md`（公共服务宿主化原则）。

## 触发条件

用户表达以下意图时调用本 Skill：
- "发布线上"、"上线"、"发版"、"部署到生产"、"发布流程"、"发线上"
- "更新到线上"、"发布规则"、"版本号"、"打 tag"、"回滚"
- 任何涉及多环境（dev/test/alpha/beta/prod）切换或发布门禁的请求

## ⛔ 线上安全红线（最高优先级，不可逾越）

> 任何发布体系改造都**不得影响线上已部署的东西**。skill 怎么做、内容怎么做、
> 测试怎么做由实施方自主决定，但以下红线不可违反：

1. **线上变更只通过发布流程发生**——发布体系的改造（密钥、迁移、部署方式）在
   本机完成并验证，不主动连接/修改线上（ECS、RDS、线上前端）。
2. **迁移闸门**：部署流程为「解压 → 迁移(fail-fast) → 配置 → 重启」。迁移不通过时，
   不写 systemd、不替换前端、不重启服务，线上运行状态完全不变。
3. **存量库拒绝自动迁移**：目标库无 `alembic_version` 表时中止并提示人工执行首次接入，
   禁止自动 stamp 掩盖「库 ≠ ORM」差异。
4. **切换必须有回退**：部署方式变更（如 systemd→docker）保留旧方式至稳定期，
   失败可一键回退。
5. **skill 只定义流程，不自动执行**：实际发布动作仍需满足发布门禁 + 人工确认，
   不引入"说一句就改线上"的隐式执行。
6. **发布必须基于已提交版本**：部署打包的是工作区代码；发布前确认代码已 commit，
   引入 tag 后以 `vX.Y.Z` 为发布基准。

## 一、环境层级标准（通用方法论）

### 1.1 四层级部署原则（2026-08-24 固化）

> **部署只有四个层级，每个项目固定下来后基本不变**：

| 层级 | 代号 | 定位 | 部署形态 |
|------|------|------|---------|
| 本地开发部署 | `local` | **日常开发 + 本地测试**（pytest/E2E 都在此层完成） | 本机进程/容器，连本地或内网库 |
| 线上开发部署 | `dev` | 云端开发验收环境（与线上同构，供联调/冒烟） | 独立部署实例 + 独立库 + 独立域名 |
| 线上预发部署 | `beta`（pre-prod） | 真实链路验收、上线演练、迁移预演 | 与生产同构、独立库、独立域名 |
| 线上正式环境 | `prod` | 正式对外 | 独立库、独立域名、独立密钥 |

- **日常开发与本地测试统一使用「本地开发部署」这一套环境**，不另设独立的
  「测试部署层」——自动化测试（pytest/E2E）是本地开发部署内的验证环节
  （测试库独立 schema/库隔离即可）。
- **四层级晋升路径**：`local → dev → beta → prod`。晋升**不是改配置**，而是按
  同一套发布流程在目标环境重跑一遍（打包→迁移→部署→健康检查→打 tag）。
  `beta → prod` 是唯一"上线"动作。
- `alpha` 内测等扩展层级**按需保留为概念**，不构成默认部署层级。
- 各项目固定四层级后基本不变；新增/删除环境必须走本 skill 评审，禁止随手加层。

**环境隔离原则**：库物理隔离、密钥隔离、域名隔离、数据单向（低层种子不进 prod、
prod 数据不下放低层）。

> 本项目实际落地：`local`（本机）+ `dev`（5.2 研发联调，内网 `192.168.5.2`）+
> `prod`（线上 ECS 三子域 + RDS，见 `release/environments.yaml`）；
> `beta` 预发层级按四层级原则预留、暂未落地。

## 二、发布门禁（不满足不发）

> 下表为通用发布门禁并集。凡标注「示例（项目侧适配）」的命令/路径仅为实例形态，
> 真实命令与脚本留在各项目 `release/` 目录（`policy.md` 等），本 skill 不硬编码项目数据。

| # | 门禁 | 说明 |
|---|------|------|
| 1 | 全量测试绿 | 发布前执行项目全量测试，0 失败。示例（项目侧适配）：`pytest`（真实命令见各项目 `release/policy.md`，如 `PYTHONPATH=src python -m pytest tests/ -v`） |
| 2 | e2e 绿 | 浏览器端到端测试通过。示例（项目侧适配）：项目自有 e2e 脚本，如 `scripts/e2e_full.py` / `e2e_ai.py` |
| 3 | ORM-DB 无差异 | 迁移到位、ORM 与库结构无 schema 漂移。示例（项目侧适配）：独立 diff 脚本核对 dev 库，或以 `alembic upgrade head` 校验 |
| 4 | 迁移预演 | 目标环境的上一级（或同构环境）`alembic upgrade head` 成功 |
| 5 | 密钥齐全 | 目标环境密钥文件存在且含强随机密钥、不入库。示例（项目侧适配）：远程 `deploy/.env` chmod 600，由部署脚本生成 |
| 6 | CHANGELOG 更新 | 本版本条目已写入 `release/CHANGELOG.md` |
| 7 | 健康检查 | 部署后 API 健康端点 200 + 前端首页 200。示例（项目侧适配）：`GET /health` 返回 `{"status":"ok"}` |
| 8 | **目标环境全量回归** | 发布后对目标环境执行：API 全端点回归（认证 → 只读端点断言 200 + 带参种子补测）+ 协议层冒烟（如 WS——按项目技术栈取舍）+ 关键旅程冒烟（旅程清单项目侧定义，如对话/任务导入/提醒）+ 环境对比（发预发布时线上仍 200）。示例（项目侧适配）：回归脚本与旅程清单见各项目 `release/policy.md` |
| 9 | **架构契约校验（L2+ 项目）** | 架构约束机械校验退出码 0（探针 + 运行器，见 `_shared/arch-contract-spec.md` §10；通常已含于门禁 1 的测试套件，独立列出便于门禁清点与豁免审计） |

> **时间安排（测试先行）**：全量回归在发布前本地/CI 跑完；发布后的回归是快速部署
> 验证 + 目标环境冒烟，不重跑全量。

## 三、标准发布流程

```
1. 门禁预检（§二 第 1~3 项）
2. bump 版本 + 更新 release/CHANGELOG.md
3. alembic revision（如有 schema 变更）——本地生成 + 人工 review + dev 库验证
4. 构建部署产物（本项目：scripts/deploy.py（dev 5.2）/ scripts/deploy_prod.py（prod ECS）
   ——上传代码 + 生成远程 .env + docker compose 启动）
5. 远程执行：迁移（fail-fast 闸门）→ 部署 → 健康检查
6. 公网验证（前端域名 + API 域名 200）
7. 目标环境全量回归（门禁 8：API 端点回归 + 关键旅程冒烟 + 环境对比）
8. git tag vX.Y.Z + push --tags
9. 记录回滚点（tag + alembic revision）
```

### 部署后启动与重启策略（通用原则，2026-08-21 固化）

1. **部署即启动**：发布动作（`docker compose up -d` / 启动服务）后，被部署的环境必须处于运行状态
   并通过健康检查（门禁 7）——「部署了但没起来」视为发布失败。
2. **默认不开机自启**：服务重启策略不得设为 `always`/`unless-stopped` 类开机自启——
   部署环境常与测试环境共享服务器，应允许手动停用以释放资源。
   推荐 `restart: on-failure:N`：ECS/守护进程重启后**不自动拉起**，手动 `docker stop` 后不拉起
   （可长期关闭省资源），仅容器崩溃（非零退出）自动重试 N 次兜底。
3. **手动管理透明化**：手动停用/恢复命令（`docker stop|start <容器>`）写入环境指南，供随时关闭/恢复。
4. **权衡说明**：不开机自启意味着整机重启后需手动 `docker start`（或下次发布自动拉起）——如业务要求
   「平时全跑、仅测试时手关」，可回退 `unless-stopped`（手动 stop 同样不被拉起）。
   > 本项目现状：平台/OpenProject 已选 `unless-stopped`（生产常跑型，依据本条权衡；Dify 各容器
   > `always` 沿用官方 compose）——见 `docs/ecs-deploy-design.md` §9，调整重启策略须走发布评审。

## 四、版本规范（SemVer + tag + 分支）

- 版本号：SemVer `X.Y.Z`（X=不兼容/破坏性，Y=功能，Z=修复）。
- tag：发布到 prod 后打 `vX.Y.Z`；预发布 `vX.Y.Z-beta.N` / `vX.Y.Z-alpha.N`。
- 分支：单人项目 **main 直发 + tag**；大版本（X 变更）开 `release/vX.Y` 收敛；
  **禁止在 tag 上改代码**。
- 发布动作：tag + CHANGELOG 追加 + 记录回滚点。

## 五、回滚流程

| 场景 | 动作 |
|------|------|
| 代码问题 | 切回上一个 tag → 重走发布流程 |
| 仅迁移问题 | `alembic downgrade -1`（或指定版本）→ 修迁移 → 重新 upgrade |
| 容器/部署故障 | 回退旧部署方式（docker 回退 systemd 等，见红线 4） |

## 六、执行入口（本项目）

调用本 skill 后，按以下顺序读取项目配置，禁止在 skill 内硬编码项目数据：

1. `release/environments.yaml` —— 环境清单（域名/地址/数据库/部署方式/密钥引用）
2. `release/policy.md` —— 本项目发布规则（门禁命令、发布步骤、回滚命令）
3. `release/CHANGELOG.md` —— 版本历史（发布后追加）
4. `docs/ecs-deploy-design.md` —— 线上 ECS 部署设计（组件矩阵/网络拓扑/决策 D1-D6）
5. `docs/deploy-guide.md` —— 部署指南（5.2 经验 + 公共服务宿主化原则）
6. `docs/environment-checklist.md` —— 环境配置核对清单（E1-E18）
7. `scripts/deploy.py` / `scripts/deploy_prod.py` —— 实际部署执行脚本（dev 5.2 / prod ECS）
8. `deploy/docker-compose.yml` —— 平台服务 compose（线上版）

## 七、数据库迁移要求

- schema 变更一律走 alembic（`alembic revision --autogenerate` → 人工 review → 验证 → 应用），
  禁止直接用 `create_all` 或手写 SQL 改生产结构。
- 迁移先于服务启动执行（容器 entrypoint / 部署脚本闸门）。
- 迁移脚本必须可 downgrade（数据回填类迁移同时实现回滚）。

## 八、教训固化（CASE-007，2026-08-23 新增）

以下四条来自 zy-ai-consult 8/22~8/23 真实发布故障，已固化为通用发布纪律：

1. **部署脚本 stdout 强制 UTF-8**——Windows 控制台默认 GBK，打印中文/emoji 会导致 stdout 解析崩溃；部署类脚本必须在入口显式设置 UTF-8 编码。
2. **镜像依赖清单必须完整**——缺少运行期依赖（如 paramiko）会在上线后 import 即抛错（fail-fast 502）；Dockerfile 依赖清单作为发布门禁的一项核对。
3. **敏感值传递防特殊字符截断**——经 compose `env_file` 传入的机密若含 `#` 等特殊字符会被截断；改为 base64 或显式转义传递。
4. **发布脚本对机密操作必须幂等**——密钥/证书的生成与注入重复执行不得重新生成或导致前后不一致；发布脚本用幂等写（探测已存在则跳过）。
