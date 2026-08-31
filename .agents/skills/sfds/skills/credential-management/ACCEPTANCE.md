# CREDENTIAL-MANAGEMENT · ACCEPTANCE

- 技能：CREDENTIAL-MANAGEMENT（项目机密与部署配置的唯一去向）
- 来源：**从 zy-ai-consult 回收 v1.7.0（CASE-013）**，泛化为项目中性
- 版本：1.7.0-arb.1
- 定位：L3 工具胶水（驱动 credentialctl + 贯彻配置纪律），常驻旁路（stage=bypass）

## 接受范围

| 项 | 结论 |
|---|---|
| 是否入册（pipeline-registry.js） | ✅ 已登记，非方法论孤岛 |
| 工具来源 | Windows 本地加密库 CLI `credentialctl.ps1`（consult 版，与技能同捆 `scripts/`；纯通用、无项目专名） |
| 主密钥模型 | `init` **自动生成高熵 master 密钥**（唯一恢复钥匙）→ 每次机 DPAPI(CurrentUser, KEK) 自动解锁；迁机重输一次重绑 |
| 库文件与入库 | `credential.json`/`credential.meta.json`/`config` **整体提交进代码库**；仅 `.credential/unlock/` gitignore |
| 机密/非密 | 库只存机密；非密部署配置进部署配置文档 + 「部署步骤→密钥库 Key」对照表 |
| 默认输出 | `<CREDENTIAL:proj/key>` 占位符；仅 `--env`/`--reveal` 在部署时取真值 |
| 访问控制 | 项目 scope + token 认证；越权/错 token 拒绝；每次读取进审计 |
| 数据位置 | `<项目根>\.credential\`（数据随项目，不散落用户主目录） |

## 已知边界 / 需后续完善

- Windows 专用（依赖 DPAPI + AesGcm）；跨平台后端（age/SOPS）未实现，仅预留抽象。
- master 密钥与所有机器 blob 都丢 → 无恢复手段（master 密钥须外存密码管理器）。
- 改 scope 无 CLI（需编辑 `credential.json` 或重建）；KDF 为 PBKDF2-SHA256×600k（抗离线偏弱，理想 Argon2id）。
- 无远端/多人/RBAC；`--config --plain` 非敏感配置为明文（已按 v1.7.0 不再用于入库，非密配置转部署文档）。

## 验收状态

- L1 自检通过：frontmatter 结构/lineage（CASE-013 + reclaim）/assets 清单/触发词齐全；工具端到端路径（init/project init/add/get 占位符/--env/reveal/list/越权/错 token/跨机重绑）由 consult 侧实测，本版为泛化（未改功能）。
- L2/L3（加载与沙盒推演）待本 bundle 在 `*-arb` 实例 + sandbox 语境复测。
