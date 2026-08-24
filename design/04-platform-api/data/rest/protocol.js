/**
 * REST 协议定义 — NASKB 平台（FastAPI 实际行为基线）
 *
 * 本文件为 `design/04-platform-api/data/rest/protocol.js`：协议层定义（承载层/认证/错误/通用语义），
 * 供 api-design 协议消费方与后续契约测试引用。注意：api-viewer.html 为 REST 领域视图（参考实现），
 * 不渲染 protocol 视图——本协议内容由人工/契约工具查阅（已知 bundle 局限，见 review/remaining-issues.md）。
 */

window.API_DATA = window.API_DATA || {};
window.API_DATA["protocol-rest"] = {

  id: "rest",
  name: "NASKB REST",
  fullName: "NASKB 平台 REST API 协议",
  description: "FastAPI + JSON。单管理员 Bearer 认证 + 可选匿名只读；错误结构 {detail|error}；任务异步化（job_id）；流式下载用 HTTP Range。",
  version: "1.0",
  projectScoped: true,

  glossary: {
    "resource_id": "知识资源唯一标识（来源 + rel_path 的稳定引用）",
    "job_id": "长任务标识（12 位 hex），任务中心串行执行",
    "source_id": "知识来源唯一标识",
    "rel_path": "来源内相对路径",
    "access_mode": "ro|rw（只读知识库/可写双写）",
    "anonymous_read": "匿名只读开关（默认 true，仅 GET/HEAD + 匿名前缀）"
  },

  transports: [
    {
      type: "http",
      description: "HTTP/1.1，JSON 请求/响应；下载/预览走流式（StreamingResponse）",
      parameters: { baseUrl: "http://<host>:8765", docs: "/api/docs", openapi: "/api/openapi.json" }
    }
  ],

  identity: {
    credentials: [
      { name: "Bearer token", format: "Authorization: Bearer <token>", purpose: "管理员认证（config [server] tokens，compare_digest 比对）" }
    ],
    signingAlgorithm: { name: "none（Bearer 不签名）", description: "令牌为配置常量；匿名只读无需凭据（anonymous_read=true 且命中匿名前缀）" }
  },

  // ═══════════════════════════════════════════
  // 通用语义（协议层内容）
  // ═══════════════════════════════════════════
  protocolContent: [
    { type: "markdown", title: "协议概述", data: { content: "<p>平台 REST 契约按 ADR-20260816-2 保持稳定：<code>/api/search</code>、<code>/api/ask</code> 为后端抽象边界（换实现不换接口）。v0.1 主入口为 <code>serve-platform</code>（create_app 工厂 + run），遗留 <code>desc serve</code> 契约保留。</p>" } },
    { type: "table", title: "鉴权与匿名", data: { headers: ["场景", "行为"], rows: [
      ["无 [server] tokens 配置", "认证关闭，全部开放"],
      ["有 tokens 且 anonymous_read=true", "GET/HEAD + 匿名前缀免 token；写/管理端点恒需 token"],
      ["有 tokens 且 anonymous_read=false", "所有端点需 token（除 /api/config/public 与 /api/docs）"]
    ] } }
  ],

  envelopeContent: [
    { type: "nested", title: "错误结构", data: { children: [
      { title: "FastAPI 默认", content: "<code>{detail: ...}</code>（422 校验错误为 detail 数组）" },
      { title: "业务错误", content: "<code>{error: {code, message}}</code> 或 HTTP 状态码 + detail 文本；前端 api() 以 r.status + detail/error 呈现" }
    ] } },
    { type: "nested", title: "任务异步语义", data: { children: [
      { title: "提交", content: "POST 类任务端点返回 <code>{job_id}</code>（201/202），立即返回，后台串行执行" },
      { title: "进度", content: "<code>GET /api/jobs/{id}</code> 返回 {status: pending|running|completed|failed, progress, message, result, error}" }
    ] } },
    { type: "nested", title: "分页/列表", data: { children: [
      { title: "约定", content: "列表以 {sources|jobs|hits|...} 顶层键返回；无统一分页信封（当前规模全量返回）" }
    ] } }
  ],

  sections: [
    { id: "protocol", label: "📋 协议定义", icon: "📋", type: "protocol" },
    { id: "envelope", label: "📨 消息语义", icon: "📨", type: "envelope" }
  ],

  renderRules: { actions: { groupBy: "method" }, enums: {}, status: {} }
};
