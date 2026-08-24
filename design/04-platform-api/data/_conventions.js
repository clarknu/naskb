/**
 * REST 公共约定 — window.API_CONVENTIONS（api-viewer 自动渲染为附录）
 * 依据：api-design §7 公共约定（boxing 固化），结合 NASKB FastAPI 实际行为（代码基线）
 */
window.API_CONVENTIONS = {
  title: "NASKB REST 公共约定",
  description: "响应结构、错误、幂等、缓存、频控、数据格式与认证口径（以代码实际行为为准；与模板方法论的差异在备注标注）",

  sections: [
    { id: "response", title: "响应结构", blocks: [
      { type: "table", headers: ["场景", "结构"], rows: [
        ["列表", "{sources|jobs|hits|dirs|files|...}: [...]（顶层键按端点约定）"],
        ["对象", "{resource|source|stats|job|preview|meta|...}: {...}"],
        ["任务提交", "{job_id: \"...\"}"],
        ["错误", "HTTP 状态码 + {detail: ...|error: ...}（FastAPI 422 为 detail 数组）"]
      ]}
    ]},
    { id: "error", title: "错误码分配", blocks: [
      { type: "table", headers: ["HTTP", "含义", "说明"], rows: [
        ["400", "INVALID_PARAMETER", "参数错误（含 WebDAV 连通失败）"],
        ["401", "UNAUTHORIZED", "缺少/无效 Bearer token"],
        ["403", "FORBIDDEN", "permission 不足（单管理员场景等价 401）"],
        ["404", "NOT_FOUND", "来源/资源/任务不存在"],
        ["409", "CONFLICT", "状态冲突（如确认清单与实况不一致）"],
        ["416", "RANGE_NOT_SATISFIABLE", "Range 越界"],
        ["422", "VALIDATION_ERROR", "Pydantic 校验失败"],
        ["503", "DEPENDENCY_UNAVAILABLE", "PG 不可达/stale 源（下载代理 503）"],
        ["500", "INTERNAL_ERROR", "服务器内部错误"]
      ]}
    ]},
    { id: "idempotency", title: "幂等性", blocks: [
      { type: "note", level: "info", text: "GET/PUT/DELETE 天然幂等；扫描/分析/确认/收编均为任务型触发，重复提交不重复执行（增量幂等由指纹链保证）——区别于模板方法论的 Idempotency-Key 头部方案（本项目未实现该头部）。" }
    ]},
    { id: "caching", title: "缓存策略", blocks: [
      { type: "table", headers: ["资源", "策略", "说明"], rows: [
        ["下载响应", "ETag（强 file_hash / 弱 W/\"size-mtime\"）+ If-None-Match", "304 命中"],
        ["公开配置 /api/config/public", "客户端存储（localStorage token）+ 启动时拉取", "无服务端缓存"],
        ["缩略图", "store/thumbs/ 磁盘缓存（按 resource_id + w）", "生命周期：来源删除时清理"]
      ]}
    ]},
    { id: "rate-limit", title: "频率限制", blocks: [
      { type: "note", level: "info", text: "裁剪（DD-009）：不实现服务端频控 G1-G5；结构性限流（JobManager 串行 + MiMo/MinerU 串行风控纪律）承担；外部模型风控由并发纪律保证。" }
    ]},
    { id: "format", title: "数据格式约定", blocks: [
      { type: "table", headers: ["类型", "规则"], rows: [
        ["日期时间", "ISO 8601（created_at/mtime/last_scan_at 等）"],
        ["路径", "rel_path 均为 / 分隔相对路径（跨平台归一化）"],
        ["哈希", "sha256:full | sha256:sample8x64k"],
        ["枚举", "snake_case（ro/rw/local/webdav/pending/running/completed/failed）"],
        ["大小", "size_bytes 字节整数；前端格式化展示"]
      ]}
    ]},
    { id: "auth", title: "认证（2026-08-24 拍板：全部需身份，DD-009）", blocks: [
      { type: "table", headers: ["端点", "规则"], rows: [
        ["全部业务端点", "需 Bearer token（配置 [server] tokens 后；未配置 = 本机开放模式，文档明示）"],
        ["/api/config/public", "匿名例外（前端启动引导必需）"],
        ["/api/docs、/api/openapi.json", "匿名例外（OpenAPI 文档，纯只读）"],
        ["其余一切", "一律需 token——匿名白名单机制已移除（原 /api/ask、/api/jobs 等口径差异项随移除一并清零）"]
      ]},
      { type: "note", level: "warning", text: "多 token 仅 tokens[0] 有效（单管理员模型——声明单 token，文档修正）；直链（MCP kb_fetch_file/kb_get_file_url）不带 token，安全边界=外围网关 IP 约束（DD-009 显式决策）。" }
    ]}
  ]
};
