/**
 * 系统拓扑 — System Topology（示例模板）
 *
 * 复制到项目 design/03b-backend-architecture/data/ 后编辑
 * 版本：v1
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["system-topology"] = (function () {

  var _trace = {
    consumes: ["workflow:...", "er:...", "raw:..."],
    produces: ["constraint:topology", "constraint:module-boundary", "constraint:layering"]
  };

  return {
    _trace: _trace,
    complexityLevel: "L2",
    complexityRationale: "示例：事件驱动模块化单体，关键流程跨 3 个子域",
    complexityQuestionnaire: {
      Q1_peakQps:        { answer: "no", value: "", note: "" },
      Q2_dataVolume:     { answer: "no", value: "", note: "" },
      Q3_concurrentUsers:{ answer: "no", value: "", note: "" },
      Q4_horizontalScale:{ answer: "no", value: "", note: "" },
      Q5_multiService:   { answer: "no", value: "", note: "" },
      Q6_strongConsist:  { answer: "no", value: "", note: "" },
      Q7_grayRelease:    { answer: "no", value: "", note: "" },
      Q8_multiTenant:    { answer: "no", value: "", note: "" },
      Q9_compliance:     { answer: "no", value: "", note: "" },
      Q10_externalDeps:  { answer: "no", value: "", note: "" },
      Q11_asyncTasks:    { answer: "no", value: "", note: "" },
      Q12_stateMachines: { answer: "no", value: "", note: "" },
      Q13_domainCount:   { answer: "no", value: "", note: "" },
      Q14_roleCount:     { answer: "no", value: "", note: "" }
    },
    architectureStyle: {
      primary: "monolithic",
      rationale: ["示例：单体起步、模块边界清晰、事件异步解耦"]
    },
    techStack: {
      runtime:   "Node.js 20 (示例)",
      framework: "FastAPI + 模块化单体 (示例)",
      orm:       "SQLAlchemy (示例)"
    },
    domainCount: 0,
    totalEntities: 0,
    totalFlowcharts: 0
  };
})();
