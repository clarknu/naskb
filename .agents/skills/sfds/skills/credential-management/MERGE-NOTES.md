# CREDENTIAL-MANAGEMENT · MERGE-NOTES

- 技能：CREDENTIAL-MANAGEMENT（项目机密与部署配置的唯一去向）
- 案件：**CASE-013**（2026-08-30 需求方确认回收 consult v1.7.0）
- 地位：从项目侧领先版回收进本 bundle 并泛化；无三方冲突分叉。

## 来源与方向

- consult `skills/credential-management`（v1.7.0，项目侧领先）→ 本 bundle（v1.7.0-arb.1）。consult 是事实上的最新主线，其 v1.7.0 是对本枢纽 v1.0.0 的**模型反转 + 增强**，方向为**回收**（项目→枢纽）。
- 初始版 v1.0.0 由本枢纽新生（无分叉），下发至项目后由 consult 演化；本次回收闭环。

## 与 v1.0.0 的取舍（diff 级）

| 项 | v1.0.0（旧） | v1.7.0-arb.1（回收） | 定案 |
|---|---|---|---|
| 库模型 | `.CREDENTIAL-MANAGEMENT` 整个 gitignore；passphrase 手工设 | `.credential` 加密库整体入库；`init` 自动生成 master 密钥外置 | 选 consult（模型反转） |
| 库文件 | `vault.json`/`vault.meta.json` | `credential.json`/`credential.meta.json`/`config` | 选 consult |
| 占位符 | `<CREDENTIAL-MANAGEMENT:…>` | `<CREDENTIAL:proj/key>` | 选 consult（并修正旧元数据不一致） |
| 机密/非密 | `--config --plain` 存库 | 非密配置进部署文档，库只存机密 | 选 consult（v1.7.0 拆分） |
| 命名 | 无 | `{env}_{kind}` + scope 族通配 + `online_*` | 采纳 |
| 安全 | — | 值不落 argv、SSH 私钥入库内存加载、设计资产副本打码、开发/运行 Key 分离 | 采纳 |
| Windows | — | DPAPI+AesGcm+AMSI 规避 | 保留 |

## 泛化（去项目专名）

- 删除 zy-ai-consult 专名/实例：`mimo_api_key`/`deepseek_api_key`/`aliyun_access_key_id`/`dify_db_password`/`wecom_*`/`dify_base_url`/`beta_dify_*` 等 → 抽象为 `{service}_api_key`/`{provider}_access_key_id`/`{service}_db_password`/`{service}_base_url`/`{env}_{service}_*`。保留 `{env}_{kind}`/`online_*`/`db_*`/`local_*` 等**通用模式名**。
- 项目侧"部署配置文档"路径（consult `docs/deployment-config-guide.md`）→ 泛化为"项目侧部署配置文档（release 域过程资产，见 `release-management`）"，不再硬编码项目路径。
- 版本历史的 consult IP（`121.237.183.231` 等）不写入泛化正文，见本 bundle CHANGELOG（仅作来源说明）。

## 附带的修正

- 旧元数据（v1.0.0 的 CHANGELOG/ACCEPTANCE/MERGE-NOTES）使用 `<CREDENTIAL-MANAGEMENT:…>`、`.CREDENTIAL-MANAGEMENT`，与 SKILL.md/脚本不一致；本次统一为 `.credential` + `<CREDENTIAL:…>`。

## 待议（后续）

- L2/L3 复测（`*-arb` 实例 + sandbox）；是否纳入 `deployment-principles`（Phase B）的"部署原则/引用"关系；触发词是否需与其它技能收敛。
