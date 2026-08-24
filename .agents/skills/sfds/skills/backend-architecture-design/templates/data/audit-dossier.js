window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["audit-dossier"] = {
  generatedFrom: { generatedAt: "2026-08-23", runtime: "arb-sample" },
  summary: { architectureStyle: "模块化单体", complexityLevel: "L2", layerCount: 4, moduleCount: 2, decisionCount: 1, activeDebts: 1,
    contractLastRun: { report: "design/review/arch-contract/latest.json", exitCode: 0, violations: 0, warns: 1 } },
  reconciliation: { unsyncedDecisions: [], orphanChanges: [] },
  layerXDomain: [{ layer: "应用层", module: "booking", contact: "Saga", note: "示例" }],
  crossCuttingCoverage: [{ concern: "鉴权", covered: ["UserAppService"], missing: [] }],
  traceMap: { broken: [] },
  analystChecklist: [{ id: "Q-1", dimension: "理念", question: "分层是否被穿透？", whereToLook: "layering-strategy" }],
  analystNotes: [{ id: "N-1", author: "human", date: "2026-08-23", note: "样例审计备注" }]
};