window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["observability-policy"] = {
  logging: { library: "serilog", correlationId: { header: "X-Request-Id" } },
  metrics: { endpoint: "/metrics", custom: ["business_booking_total"] },
  healthCheck: { endpoint: "/healthz", readinessProbe: "readiness: /readyz" },
  auditLog: { retention: "180d" },
  alerting: { rules: [{ name: "错误率", condition: "5xx>1%/5m", severity: "P2" }] }
};