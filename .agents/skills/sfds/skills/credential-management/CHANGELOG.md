# CREDENTIAL-MANAGEMENT · CHANGELOG

## [1.7.0-arb.1] - 2026-08-30
- **从 zy-ai-consult 回收 v1.7.0（CASE-013）**：consult `skills/credential-management` 为项目侧领先版，回收到本 bundle 并**泛化为项目中性**（去 zy-ai-consult 专名/实例，示例抽象化）。
- **模型反转（核心）**：从 `v1.0.0` 的"整个 `.credential` 目录 gitignore + 手工设 passphrase"，改为 consult 的 **"加密库入库 + master 密钥外置"**——`credential.json`/`credential.meta.json`/`config` 整体提交进代码库；**唯一不入库的是 `init` 自动生成的高熵 master 密钥**（换机/迁机凭它恢复）；仅 gitignore `.credential/unlock/`（每机 DPAPI blob）。配套给出"离线爆破→最强杠杆=主密熵/理想 Argon2id"推理。
- **机密/非密拆分（v1.7.0）**：密钥库只存机密（口令/Key/令牌/密钥材料）；非密部署配置（IP/域名/地址/端口/用户名/库名/URL/路径/模型名）进**部署配置文档**，并维护「部署步骤→密钥库 Key」对照表、用到才取。
- **命名与 scope**：`{env}_{kind}` 命名（env=local/alpha/beta/release，不强制 SSH）；scope 族通配（含 `*_PW` 真实踩坑）；`online_*` 线上共用主机。
- **安全增强**：值写入不落 argv（`--file`/OS 级 stdin、禁 `--value`）；SSH 私钥入密钥库+内存加载；设计资产（DSL/配置/MCP/协议层/拓扑）副本必须打码；开发 Key 与运行 Key 分离；Windows 边界（DPAPI+AesGcm+AMSI 规避）。
- 工具 `scripts/credentialctl.ps1` 更新为 consult 版（无项目专名，纯通用工具）。

## [1.0.0] - 2026-08-28（被 v1.7.0-arb.1 取代）
- 初始接入（arb-hub）：作为 SFDS bundle 的 L3 子技能。
- 旧模型：`vault.json`/`vault.meta.json`，passphrase 派生主密钥，整个 `.credential` gitignore；占位符 `<CREDENTIAL-MANAGEMENT:…>`、数据根 `.CREDENTIAL-MANAGEMENT`。已废弃并纠正为 `credential.json`/`credential.meta.json`、master 密钥外置、`.credential`、`<CREDENTIAL:…>`。
