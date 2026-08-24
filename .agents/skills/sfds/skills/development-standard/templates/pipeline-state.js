/**
 * 管线状态 — Pipeline State（调度模式数据源）
 *
 * 消费：development-standard 调度模式（§4）——管线状态机唯一裁判。
 * 规则：每次阶段判定后由调度模式更新（status + history）；会话记忆不算状态。
 * schema：stages[].{id, status: not-started|in-progress|partial|done, evidence[], note}
 *        history[].{date, event, detail}
 */
window.PIPELINE_DATA = window.PIPELINE_DATA || {};
window.PIPELINE_DATA["pipeline-state"] = (function () {
  return {
    version: "1",
    projectName: "{{project-name}}",
    registryRef: ".agents/skills/sfds/_shared/pipeline-registry.js",

    stages: [
      { id: "raw-input",  status: "in-progress", evidence: [], note: "起始阶段" },
      { id: "workflow",   status: "not-started", evidence: [], note: "" },
      { id: "er",         status: "not-started", evidence: [], note: "" },
      { id: "api",        status: "not-started", evidence: [], note: "" },
      { id: "architecture", status: "not-started", evidence: [], note: "" },
      { id: "ui",         status: "not-started", evidence: [], note: "" },
      { id: "tdd",        status: "not-started", evidence: [], note: "" },
      { id: "impl",       status: "not-started", evidence: [], note: "" },
      { id: "verify",     status: "not-started", evidence: [], note: "" },
      { id: "review",     status: "not-started", evidence: [], note: "" },
      { id: "release",    status: "not-started", evidence: [], note: "" }
    ],

    history: [
      { date: "{{today}}", event: "init", detail: "项目初始化（development-standard §1），管线状态建立" }
    ]
  };
})();
