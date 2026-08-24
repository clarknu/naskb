/**
 * 事件契约 — Event Contracts
 * NASKB 无独立消息中间件（L3 事件驱动以 JobManager 任务语义承担）：
 * 事件 = 任务生命周期信号（进程内），契约=任务 kind 集合 + 结果结构。
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["event-contracts"] = {
  totalDomainEvents: 2, totalCommands: 0,
  eventRegistry: {
    DomainEvents: {
      "JobSubmitted": {
        producer: "platform-core/jobs", consumers: ["platform-core/scheduler", "manual-poll"],
        fields: { job_id: "string(12hex)", kind: "enum(scan|analyze|adopt|confirm)", created_at: "ISO-8601" },
        note: "进程内信号（内存队列）——非持久事件；重启即失（设计决策）"
      },
      "JobCompleted": {
        producer: "platform-core/jobs", consumers: ["source-management/routes", "mcp/kb_job_status"],
        fields: { job_id: "string", status: "completed|failed", result: "json", error: "string?" },
        note: "结果结构与平台任务响应一致（frontend pollJob 消费）"
      }
    },
    Commands: {}
  },
  taskKinds: ["scan", "analyze", "adopt", "confirm", "sync-vectors", "index-vectors", "plan-reorganize", "apply-reorganize"],
  knownZeroEvents: [
    "无外部消息 broker（不引入 RabbitMQ/Kafka——宿主化中间件原则 L3 边界）",
    "无领域事件总线；跨域协作 = 服务接口调用 + 任务队列（module-boundaries 白名单）"
  ]
};
