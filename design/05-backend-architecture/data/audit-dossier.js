/**
 * 审计档案 — Audit Dossier（派生数据，由 backend-architecture-design 审计模式整体再生成）
 * 本文件为初始版骨架（generatedFrom 版本戳），审计模式（§3b）运行时将整体再生成并覆盖。
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["audit-dossier"] = (function () {
  var _trace = { consumes: ["architecture:*", "decisions:design-decisions", "contract:arch-contract"],
                 produces: ["report:audit-dossier"] };
  return {
    _trace: _trace,
    generatedFrom: {
      assets: [
        { file: "data/system-topology.js", version: "v1" },
        { file: "data/module-boundaries.js", version: "v1" },
        { file: "data/layering-strategy.js", version: "v1" },
        { file: "data/caching-strategy.js", version: "v1" },
        { file: "data/security-policy.js", version: "v1" },
        { file: "data/resilience-policy.js", version: "v1" },
        { file: "data/data-consistency.js", version: "v1" },
        { file: "data/observability-policy.js", version: "v1" },
        { file: "data/event-contracts.js", version: "v1" },
        { file: "data/arch-contract.js", version: "v1" }
      ],
      command: "backend-architecture-design 审计模式（初始骨架，待审计运行再生成）",
      generatedAt: "2026-08-24T13:49:00"
    },
    summary: {
      architectureStyle: "modular-monolith", complexityLevel: "L3",
      layerCount: 4, moduleCount: 11, decisionCount: 12, activeDebts: 2,
      contractLastRun: { report: "design/review/arch-contract/latest.json", exitCode: null, violations: null, warns: null }
    },
    layerXDomain: [
      { layer: "HTTP 接口层", module: "api-layer", contact: "server/*.py ↔ common 域服务（无业务规则）", note: "RL-001 人审" },
      { layer: "AI 接入层", module: "mcp-layer", contact: "capabilities.py 单一事实源", note: "RL-003" },
      { layer: "核心层", module: "source-management/ingestion/retrieval/deep/reorganize/data-access/platform-core/fs-ext", contact: "域切片服务接口", note: "白名单=存量基线" },
      { layer: "CLI 层", module: "cli-layer", contact: "29 命令 → 域服务 + 服务组装", note: "" }
    ],
    crossCuttingCoverage: [
      { concern: "caching", covered: ["download", "thumbnail", "vector-index"], missing: ["redis（裁剪：无集中缓存，DD-009）"] },
      { concern: "security", covered: ["auth", "authorization", "source-safety", "direct-link-gateway"], missing: ["password 加密（长期债 V2）"] },
      { concern: "observability", covered: ["audit", "stats"], missing: ["健康端点/指标（裁剪：DD-009，以 config+stats 代替）"] }
    ],
    traceMap: {
      forward: ["workflow → er → api → architecture → code/tests"],
      broken: []
    },
    reconciliation: { unsyncedDecisions: [], orphanChanges: [] },
    debts: [
      // K-001/K-002 已于 2026-08-24 清理（AC-005 违规 0，探针 literal=3 仅权威定义处）
    ],
    analystChecklist: [
      { id: "Q-01", dimension: "层方向", question: "新增协议出口（如 WebSocket）是否零修改核心层？", whereToLook: "data/module-boundaries.js#api-layer.crossModuleCalls" },
      { id: "Q-02", dimension: "SQL 归属", question: "新查询是否只在 data-access/source-management 中书写？", whereToLook: "arch-contract.js#AC-004" },
      { id: "Q-03", dimension: "值域权威", question: "新枚举值是否先定义常量再引用？", whereToLook: "arch-contract.js#AC-005" }
    ],
    analystNotes: [
      { id: "N-01", date: "2026-08-24", author: "AI", note: "初始骨架：审计模式完整运行后整体再生成（含契约运行摘要与对账结果）" }
    ]
  };
})();
