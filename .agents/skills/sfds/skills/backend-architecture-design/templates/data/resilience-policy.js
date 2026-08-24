window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["resilience-policy"] = {
  timeout: { connect: "2s", read: "10s" },
  retry: { strategy: "指数退避+抖动", externalMaxAttempts: 3 },
  circuitBreaker: { targets: [{ service: "payment", threshold: "5/10s", recoveryTime: "30s" }], fallback: { payment: "返回临时失败" } },
  idempotency: { requiredEndpoints: ["POST /bookings", "POST /payments"] },
  rateLimit: { api: "100/min/用户", mqtt: "50/s/设备" },
  eventBus: true
};