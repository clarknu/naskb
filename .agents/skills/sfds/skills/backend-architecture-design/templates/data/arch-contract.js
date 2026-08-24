window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["arch-contract"] = {
  version: "v0.1", complexityLevel: "L2",
  rules: [
    { id: "A-01", type: "分层", enforcement: "mechanical", rationale: "禁止基础设施层被接口层直接依赖" },
    { id: "R-01", type: "事务边界", enforcement: "review", rationale: "跨模块写必须走事件" }
  ],
  reviewLedger: [{ id: "R-01", rule: "跨模块写", checkHint: "检查是否存在模块间直连写库" }],
  knownDebts: [{ ruleId: "A-01", scope: "legacy-notify", issue: "直连通知库", expires: "2026-10-01" }]
};