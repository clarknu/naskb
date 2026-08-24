/**
 * 架构域决策账本 — 架构设计决策（先记账后改资产）
 * 项目级全量账本：design/design-decisions.js（window.DESIGN_DECISIONS，§6.4 权威）
 * 本文件 = 架构域视角视图（供 architecture-viewer 决策视图使用），条目与项目账本同 ID。
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["design-decisions"] = {
  ledgerRef: "design/design-decisions.js",
  entries: [
    { id: "DD-005", date: "2026-08-24", domain: "cross-domain", layer: "architecture-design",
      trigger: "upstream-change", summary: "复杂度判定 L3 模块化单体（外部 LLM + 异步任务 + 6 域）",
      rationale: "backend-architecture-design §1 问卷：Q10/Q11/Q13 为真；Q4/Q5/Q7/Q8 否",
      status: "applied", synced: true },
    { id: "DD-A001", date: "2026-08-24", domain: "platform-console", layer: "architecture-design",
      trigger: "user-decision", summary: "任务中心 = 进程内内存队列（JobManager max_workers=1），无持久任务表；进程重启即失",
      rationale: "单人单机场景；任务为短生命周期信号（扫描/分析/整理分钟级），持久化收益低于复杂度；演进项：PG job 表",
      status: "applied", synced: true },
    { id: "DD-A002", date: "2026-08-24", domain: "cross-domain", layer: "architecture-design",
      trigger: "user-decision", summary: "无独立消息中间件：事件契约以任务语义承担（JobSubmitted/JobCompleted 进程内信号）",
      rationale: "宿主化中间件原则（L3 边界内不引入 RabbitMQ/Kafka）；跨域协作 = 服务接口 + 任务队列",
      status: "applied", synced: true },
    { id: "DD-A003", date: "2026-08-24", domain: "cross-domain", layer: "architecture-design",
      trigger: "implementation-feedback", summary: "跨模块调用白名单以存量依赖基线为准（探针事实反推），新增跨组访问必须先更新 module-boundaries 再实现",
      rationale: "存量补全原则（DD-006）：机械校验零误报 + 约束未来漂移",
      status: "applied", synced: true },
    { id: "DD-A004", date: "2026-08-24", domain: "ingestion-analysis", layer: "architecture-design",
      trigger: "user-decision", summary: "数据一致性 = 源端 .naskb 原子双写（仲裁端）+ PG 派生可重建 + 指纹幂等；无需 Outbox/Saga",
      rationale: "无跨服务事务；L3 边界内 local-transaction-with-promoted-source 足够",
      status: "applied", synced: true },
    { id: "DD-A005", date: "2026-08-24", domain: "cross-domain", layer: "architecture-design",
      trigger: "user-decision", summary: "SQL 唯一位于 data-access 域（pgstore）+ source-management 域（sources 表）；其余域禁止直写 SQL",
      rationale: "所有权规则（AC-004 机械校验）：表归属显式化，防跨组直查",
      status: "applied", synced: true }
  ]
};
