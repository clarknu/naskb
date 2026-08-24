/**
 * 数据一致性 — Data Consistency
 * NASKB：源端 .naskb 为原始仲裁端（rw 双写原子）；PG 为派生根（可重建）；整理同步尽力而为
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["data-consistency"] = {
  strategy: "local-transaction-with-promoted-source",
  rationale: "无跨服务事务；一致性靠『源端 .naskb 原子双写 + PG 派生可重建 + 指纹幂等』三层架构",
  outbox: {
    storage: "（无消息中间件；任务语义=JobManager 内存队列）",
    publisher: "—",
    retryLimit: "—",
    deadLetterQueue: "失败 job 带 error 字段，人工重试"
  },
  compensation: { enabled: false, strategy: "整理 apply 前校验（P0-1/P0-3）+ root 互斥锁；失败记录不阻断（尽力而为）" },
  consistencyPoints: [
    { point: ".naskb 双写（files/ + index.json）", mechanism: "set_entry/move_entry/remove_entry 单次原子写", guarantee: "源端仓库一致" },
    { point: "PG 同步（resources/vectors/folders）", mechanism: "增量四操作（增/改/删/移）+ 指纹比对", guarantee: "PG 可重建（ENV 主库为权威，源端 .naskb 为仲裁）" },
    { point: "本地向量索引", mechanism: "VectorIndex.remap_paths（移动不改向量）+ 重建", guarantee: "路径一致，向量无需重嵌入" },
    { point: "整理后 PG 同步", mechanism: "sync_vectors 保留 resource_id（移动识别）", guarantee: "失败记录不阻断（显式降级）" }
  ],
  driftChecks: [
    "sync-status <root> [--nas]：只读一致性差异清单",
    "pg-status：已注册 NAS 向量库统计",
    "source 变更确认闸门（/changes + /confirm）阻止未确认漂移入库"
  ]
};
