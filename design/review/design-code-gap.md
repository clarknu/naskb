# 设计-代码差距清单（Design ↔ Code Gap）

> 定位：development-standard §10.5。设计变更确认后应尽快推送到代码；未推送的变更在此登记。
> 反向含义：本清单也是「代码行为 vs 设计声明」的差异基线（DD-006：存量实现为 API 事实源，差异显式暴露待仲裁）。
> 维护规则：- [ ] {日期}: {变更摘要} — 暂未实现 / ⚖️ {差异} — 待仲裁
> 日期：2026-08-24 ｜ 状态：存量接入初始基线

## ⚖️ 待仲裁（代码行为 vs 设计声明/README 声明）

- [x] 2026-08-24: ⚖️ `GET /api/sources/{sid}/report` 死代码 → **拍板：接回实现**（一致性报告总览；iterate 执行中 — DD-009）
- [x] 2026-08-24: ⚖️ `/api/folder` 孤儿前缀 → **拍板：补实现**（目录级描述端点；iterate 执行中 — DD-009）
- [x] 2026-08-24: ⚖️ 匿名口径 → **拍板：匿名全移除**（全部端点需身份；例外= /、静态、/api/config/public、/api/docs、/api/openapi.json、/api/files/{rid}/download；iterate 执行中 — DD-009）
- [x] 2026-08-24: ⚖️ 多 token 仅首个有效 → **拍板：声明单 token**（单管理员模型，文档修正 — iterate 执行中）（2026-08-24 拍板：见 user-decisions-pending.md / iterating 执行中）
- [x] 2026-08-24: ⚖️ app.py dist/public 文案 → **拍板：修正**（iterate 执行中 — DD-009）
- [x] 2026-08-24: ⚖️ `kb_ask.deep` 静默回退 → **已裁决并修复**（P-003 方案 A'：显式要求条款级回退 → level=summary+note；成功 → level=chunk）
- [x] 2026-08-24: ⚖️ kb_fetch_file 直链 → **拍板：直链不认证，边界=网关 IP 约束**（url 兜底保留；release 四b 固化 — DD-009）
- [x] 2026-08-24: ⚖️ MCP 三工具未注册 → **拍板：接线补全**（kb_list_sources/kb_list_tree/kb_get_file_url — iterate 执行中）（2026-08-24 拍板：见 user-decisions-pending.md / iterating 执行中）
- [x] 2026-08-24: ⚖️ deep=false 不清理 chunk 行 → **拍板：关闭即清理**（delete_chunk_rows + UI 确认提示 — iterate 执行中）（2026-08-24 拍板：见 user-decisions-pending.md / iterating 执行中）
- [x] 2026-08-24: ⚖️ sources 密码明文 → **拍板：登记长期债**（V2 加密计划；security-policy 已注明）（2026-08-24 拍板：见 user-decisions-pending.md / iterating 执行中）
- [x] 2026-08-24: ⚖️ pg_vector_table/dim 假配置 → **拍板：删除配置**（代码硬编码为准；iterate 执行中 — DD-009）
- [x] 2026-08-24: ⚖️ 双集合 + 路径语义 → **拍板：统一**（单一全集/子集 + 源内相对路径；iterate 执行中 — DD-009）
- [x] 2026-08-24: ⚖️ CLI 命令数 24≠28 → **拍板：28 为准**修文档 — iterate 执行中（2026-08-24 拍板：见 user-decisions-pending.md / iterating 执行中）
- [x] 2026-08-24: ⚖️ README 测试数 → **已修正**（356 passed 基线，见 tests/test-reports/baseline-2026-08-24.md）

## 设计声明但代码未实现（后续迭代）

- [x] 2026-08-24: 服务端频控 G1-G5 → **裁剪**（DD-009：结构性限流承担；resilience-policy 已声明）
- [x] 2026-08-24: 专用健康检查端点 → **裁剪**（DD-009：门禁 7 以 config+stats 代替；observability-policy 已声明）
- [ ] 2026-08-24: SMB/NFS/iSCSI 直连（R7-04）— 已收口：挂载型协议走「OS 挂载 → local」，应用层 SMB 直连保留为可选未启用（见 remaining-issues G-06）
- [ ] 2026-08-24: Idempotency-Key 头部（模板方法论）— 未实现（指纹链幂等替代，设计已声明差异）

## 2026-08-24 A1 验证发现（F4 批次登记）

- [x] 2026-08-24: Config `[nas]` 提取字段（v2 name/user）与 `_resolve_nas_identity` 期望（alias/protocol/username）不一致 → --nas 无法匹配 — **已修**（config.py 兼容提取：alias/name 互认 + username/user 互认；test_config_nas）
- [ ] 2026-08-24: F4-01 CLI sync-chunks `[deep].roots` 量纲与 doc.path 不一致（roots 相对 fs 根、doc.path 相对仓库目录）→ 目录级深析 CLI 路径失效（平台来源级 match_all 正常）— 低，后续修（cli sync-chunks 内把 doc.path 拼仓库前缀再判定，或 roots 语义对齐）
- [ ] 2026-08-24: F4-02 deep-eval 检索无来源过滤（应支持 --sources 限定；平台 kb_ask 有 sources 参数）— 低，后续修

## 本次补全引入、尚未落地的迁移

- [x] 2026-08-24: 内置测试（tests/）重组为 api/unit/integration 分层后，README「336 用例」与测试路径描述待更新 — Phase 10 统一更新（2026-08-24 已更新：381 passed 基线 + page-mock）
- [x] 2026-08-24: 前端 page-mock 执行层（vitest+MSW）接入 — 见 remaining-issues G-01（2026-08-24 P-002 闭环：执行层接入 + TC-M001~M010 10/10 全覆盖）
