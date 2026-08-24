# 平台服务

> 文档 ID: REQ-platform-console | 最后更新：2026-08-24 | 从 3 个存量文档整合（original-logs/）
> 本文档为整合后的当前设计结论。原始讨论记录见 `original-logs/`。

## 一、核心决策

> **[R7-02]** 单管理员 Bearer 认证：`[server] tokens`（compare_digest）；`anonymous_read`（默认 true）下 GET/HEAD 且命中匿名前缀免 token；写/管理端点恒需 token。

> **[R7-05]** 任务中心：进程内 JobManager（内存字典，非 DB 表），`max_workers=1` 串行；job 记录 {id(12 hex), kind, status: pending|running|completed|failed, created_at/started_at/completed_at, progress, message, result, error}；长任务返回 job_id。

> **[R7-05]** 周期扫描调度：ScanScheduler daemon 线程（tick 30s），逐 enabled+scan_auto 来源按 `interval=max(5, scan_interval_min)*60` 提交 scan，每 tick 至多一个。

> **[R7-08]** 下载代理：Range 流式（单区间 bytes=a-b/a-/-suffix）、ETag = file_hash（强/弱 W/"size-mtime"）、304/206/416/503（stale 提示）。

> **[R7-09]** 在线预览矩阵：image / video / audio / pdf / text / html / office（docx/xlsx ≤30MB 零依赖渲染；pptx 不支持）/ parsed（解析视图，MinerU HTML）——不支持类型提示"可下载后本地打开"。

> **[R7-10]** 缩略图：图片 Pillow（≤12MB）/ 视频 ffmpeg 第 4 秒（≤100MB）；缓存 store/thumbs/。

## 二、详细设计

### 2.1 认证与前端

- 前端：hash 路由 4 视图（检索问答/浏览/来源/任务）+ 文件详情模态；token 存 localStorage；`/api/config/public` 返回 auth_required/anonymous_read。
- 匿名口径差异（/api/sources 非匿名、/api/jobs/{id} 匿名、/api/ask 被列入匿名前缀但实际需 token 等）→ design-code-gap。

### 2.2 服务结构

- `create_app(config)` 工厂 + run(host=127.0.0.1, port=8765)；VERSION 0.1.0；`/api/docs` OpenAPI。
- app.state：registry/pg/core/jobs/auth/scheduler/embedder。
- 静态挂载 `web/public`（README/app.py 提示 dist 的差异见 design-code-gap）。

### 2.3 与下游的关系

- 本域是能力支撑域：认证/调度被 01-05 域使用；下载/预览消费 02 域的 artifacts 与 resource 元数据。
- ER：Job（运行态，非持久实体，建模为 value object/服务）；AuthPolicy（安全策略）——见 06-platform-console.js。
- API：06 域 REST 端点（见 04/rest/06）；MCP 的 job 语义（kb_job_status/kb_list_jobs）见 ai-tools。

## 三、仍待决策

- ⚠️ 待定：多 token 仅首个有效（tokens[0]）——权限模型演进（多角色/多用户 R7-15 前置）。
- ⚠️ 待定：`GET /api/sources/{sid}/report` 装饰器失效（死代码，见 design-code-gap）。

## 四、来源索引

| 原始文件 | 主要贡献内容 |
|---------|-------------|
| platform-v3-design.md | 平台服务八项拍板、认证、下载/预览清单 |
| requirement.md | R7 平台系统化需求组 |
| agent-interface-design.md | REST/MCP 出口同源 |
