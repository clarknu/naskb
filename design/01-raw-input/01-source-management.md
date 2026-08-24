# 来源管理

> 文档 ID: REQ-source-management | 最后更新：2026-08-24 | 从 4 个存量文档整合（original-logs/）
> 本文档为整合后的当前设计结论。原始讨论记录见 `original-logs/`。

## 一、核心决策

> **[R7-03]** 来源是安全边界：一切知识寻址凭 `resource_id`（= 来源 + rel_path 的稳定引用），源端目录不直接暴露给 API 调用方。

> **[R7-03]** 访问模式 `ro`（只读知识库，源端一个字节不写）与 `rw`（可写，保留源端 .naskb 双写）——**只读源是 v0.1 的核心差异**：停源/缺源后检索仍可用，带 missing/stale 徽章。

> **[R7-03]** 数据模型：`public.sources`（22 字段：source_id/nas_id/schema_name/root_path/url/protocol/access_mode/label/scan_auto/scan_interval_min/deep/enabled/verify_ssl/username/password 等）+ 可选 `public.nas_registry`（五要素身份：协议+主机+端口+账号 hash12，schema 名 `nas_<proto>_<host>_<port>_u<h12>`）。

> **[R7-03]** 来源状态机：`enabled`（启用/停用）；删除 ro 源 = 其入库知识一并清除；rw 源删除不删源端 .naskb。

> **[R7-12]** 深度分析按来源开关（`SourceRecord.deep`）：扫描/分析/定时自动按标题层级建条款级 chunk 行（只读源用暂存 md，不留存）。

## 二、详细设计

### 2.1 来源生命周期

1. 注册（POST /api/sources?test=true：先连通测试再入库）→ 2. 测试（{sid}/test：连通性 + 耗时 ms）→ 3. 扫描（{sid}/scan → job_id，新增/变更/消失对账）→ 4. 变更确认（{sid}/changes：diff 清单 added/changed/missing；勾选后 {sid}/confirm → 对账 + AI 分析入库，幂等）→ 5. 收编（{sid}/adopt：导入源端已有 .naskb 描述，走 job）→ 6. 停用/启用（PATCH enabled）→ 7. 删除（DELETE；ro 源连带清除入库知识）。

### 2.2 关键业务规则

- 自动扫描：`scan_auto` + `scan_interval_min`（下限 5），由 ScanScheduler 判定（每 tick 至多一个 scan job）。
- WebDAV：username/password/verify_ssl（群晖自签默认 false）；webdav4 实现。
- 连通测试失败 → 注册拒绝；`/test` 返回 `{ok, ms, error}`。
- `GET /api/sources` 列表内含 `stats`（files/ok/stale_source/missing_source/analyzed/chunks）与 `last_scan_at`；`SourceRecord.to_api()` 脱敏（password 不返）。

### 2.3 与下游的关系

- 扫描与分析的**任务执行**归 02 域（jobs）；本章只定义来源侧入口与状态。
- ER 引用：Source / NasRegistry（见 03-entity-relationship/data/01-source-management.js）。
- API 端点：POST/GET `/api/sources`、PATCH/DELETE `/api/sources/{sid}`、POST `{sid}/test|scan|confirm|analyze|adopt`、GET `{sid}/changes`（见 04-platform-api/data/rest/01-source-management.js）。

## 三、仍待决策

- ⚠️ 待定：SMB/NFS/iSCSI 直连（R7-04，V2 规划；现阶段以挂载盘 + local 接入）。
- ⚠️ 待定：`sources` 表密码字段加密存储策略（现为明文 config/DB，见 design/review/design-code-gap.md）。

## 四、来源索引

| 原始文件 | 主要贡献内容 |
|---------|-------------|
| platform-v3-design.md | 来源模型、access_mode、resource_id 安全边界 |
| requirement.md | R7 平台系统化需求 |
| pg-vector-multi-nas.md | nas_registry 五要素 |
| mcp-kb-design.md | 来源化工具（kb_list_sources 等）来源语义 |
