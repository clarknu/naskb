/**
 * 可靠性策略 — Resilience Policy
 * NASKB：外部 AI 依赖失败降级/串行风控；任务队列串行；retry/backoff 在 LLM 客户端
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["resilience-policy"] = {
  timeout: { default: "长任务不设（JobManager 串行，进度可查询）", external: "LLM 调用 httpx timeout（客户端默认）" },
  retry: {
    strategy: "external-only",
    maxAttempts: 3,
    backoff: "exponential",
    note: "401 停止重试（风控/密钥失效，提示检查 key）"
  },
  circuitBreaker: {
    targets: ["deepseek-text", "mimo-vision-audio", "mineru-ocr", "pg"],
    threshold: "进程内串行纪律替代熔断（无并发放大器）",
    recoveryTime: "重启/提示重试"
  },
  idempotency: {
    requiredEndpoints: [
      "post /api/sources/{sid}/scan",
      "post /api/sources/{sid}/analyze",
      "post /api/sources/{sid}/confirm",
      "post /api/sources/{sid}/adopt",
      "post /api/pg/rebind"
    ],
    keyHeader: "（未实现 Idempotency-Key 头部；以指纹链增量幂等替代——见 design-decisions DD 注记）",
    cacheSuccess: "—",
    cacheFailure: "—"
  },
  fallback: {
    "pg": "回退本地向量索引 → BM25（检索链不减功能）",
    "deepseek-text": "问答无命中/不可达 → 诚实兜底（no_hit_mode）",
    "mimo-vision-audio": "失败 → 单文件标记失败，其余继续（批次容错）",
    "mineru-ocr": "失败 → 快速路径文本保留，提示人工处理"
  },
  rateLimit: {
    global: { perIp: "—（裁剪：不实现服务端频控 G1-G5，DD-009）", note: "个人场景；结构性限流（任务串行）为主" },
    write: { perUser: "任务串行（max_workers=1）", note: "结构性限流" },
    sensitive: { perUser: "整理 apply 需人工确认（两段式）", note: "结构性限流" }
  },
  notes: [
    "风控纪律：MiMo/MinerU/ffmpeg/Word COM 严格串行（并行触发平台风控冻结 key）——结构化限流",
    "任务队列为内存队列：进程重启即失（当前设计，非持久任务表；演进项：PG job 表）"
  ]
};
