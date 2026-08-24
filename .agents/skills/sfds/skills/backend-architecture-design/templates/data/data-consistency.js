window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["data-consistency"] = {
  strategy: { primary: "模块内本地事务", crossModule: "Saga+事件补偿", longRunning: "Outbox 异步" },
  outbox: { storage: "同库 outbox 表", publisher: { type: "轮询发布器" }, guarantee: "at-least-once" },
  transactionBoundaries: [{ scenario: "下单跨域", strategy: "Saga", steps: ["创建预订", "扣减额度", "失败则补偿"], note: "示例" }]
};