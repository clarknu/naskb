/**
 * 可观测性 — Observability Policy
 * NASKB：结构化日志（stdout/stderr）+ 任务进度/结果 + MCP 写审计 + 健康/统计端点
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["observability-policy"] = {
  logging: {
    level: "INFO（config 可调）",
    structured: false,
    correlationId: "（无；任务以 job_id 关联）",
    sensitiveFieldMasking: ["password", "token"],
    note: "Windows 控制台 GBK 风险：部署/诊断脚本入口显式 UTF-8（CASE-007 教训）"
  },
  metrics: {
    provider: "none（统计端点 /api/stats、kb_stats；指标维度 2026-08-24 裁剪，DD-009）",
    endpoints: ["/api/stats"],
    customMetrics: ["docs", "chunks", "engine", "vector_index"],
    note: "裁剪口径：个人/家庭 NAS 场景不做 Prometheus 指标与 SLO；保留统计端点供人工/Agent 查询"
  },
  tracing: { enabled: false, header: "—", sampling: "—" },
  healthCheck: {
    enabled: false,
    note: "裁剪（DD-009）：不实现专用 /api/health；发布门禁 7 以 GET /api/config/public 200 + GET /api/stats 200 代替；就绪判断=来源/统计聚合可读 + 引擎链隐式探测",
    checks: ["config 可读", "stats 可聚合", "pg 可用性（引擎链内隐式）"],
    readinessProbe: "—"
  },
  auditLog: {
    enabled: true,
    events: ["mcp-write:kb_ingest", "mcp-write:kb_sync_vectors", "mcp-write:kb_index_vectors",
             "mcp-write:kb_plan_reorganize", "mcp-write:kb_apply_reorganize"],
    storage: "store/audit/<date>.log（追加）",
    retention: "按日期文件自然轮转"
  },
  notes: [
    "演进项：G1-G5 频控指标、trace、SLO（L3 边界内可后置）"
  ]
};
