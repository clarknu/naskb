/**
 * 架构契约 — Arch Contract（模板，对齐 _shared/arch-contract-spec.md）
 *
 * 复制到项目 design/05-backend-architecture/data/ 后编辑。
 * 消费方：node _shared/arch-contract/run.mjs --contract this.js --facts <probes/out/facts.json> --report <report>
 * 入口：window.ARCH_DATA['arch-contract']，必须含 rules[]（谓词数组）。
 * type 只能是 spec §3 的五种：dependency-direction / reference-whitelist / ownership / value-domain / set-relation。
 * enforcement 只能是 spec §4 的：mechanical / heuristic / review。每条规则必须有 source（design:// 指针）。
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["arch-contract"] = (function () {

  var _trace = {
    consumes: [
      "layering:layering-strategy",
      "module-boundary:module-boundaries",
      "event-contract:event-contracts",
      "api:rest-domain"
    ],
    produces: ["constraint:arch-contract"]
  };

  return {
    _trace: _trace,
    version: "1",
    complexityLevel: "L3",

    // 分组 = glob 模式（spec §2.2）
    groups: {
      "core":    ["app.core.**"],
      "channels":["app.channels.**", "app.api.wecom_callback"],
      "api":     ["app.api.**"],
      "modules.task":    ["app.services.task_*"],
      "modules.identity":["app.services.identity*"]
    },
    externalGroups: { "openproject": "external.openproject", "dify": "external.dify" },

    valueDomains: {
      "channel": { constantsUnit: "app.channels.__init__", values: ["wecom", "web", "debug"] }
    },

    // actualSet 名 → 探针约定（spec §5.2）
    registrySets: {
      "routes":          { probe: "static|runtime", keyStyle: "METHOD path-lowercase-noslash" },
      "event-handlers":  { probe: "static", keyStyle: "exact" },
      "idempotent-endpoints": { probe: "static", keyStyle: "METHOD path-lowercase-noslash" }
    },

    // 谓词（spec §3）；把「无法谓词化」的语义规则放 reviewLedger（spec §4.1）
    rules: [
      { id: "AC-001", type: "dependency-direction", enforcement: "mechanical",
        from: ["core"], forbid: ["channels"], kinds: ["import"],
        rationale: "核心层零渠道感知",
        source: "design://05-backend-architecture/data/layering-strategy.js#rules[0]" },
      { id: "AC-003", type: "reference-whitelist", enforcement: "mechanical",
        whitelist: "design://05-backend-architecture/data/module-boundaries.js#crossModuleCalls",
        rationale: "跨模块访问只走所属模块 service",
        source: "design://05-backend-architecture/data/module-boundaries.js" },
      { id: "AC-004", type: "ownership", enforcement: "mechanical",
        assetKind: "entity",
        ownership: "design://05-backend-architecture/data/module-boundaries.js#modules",
        moduleGroups: { "task-management": "modules.task", "identity-permission": "modules.identity" },
        rationale: "禁止跨域直查表",
        source: "design://05-backend-architecture/data/module-boundaries.js" },
      { id: "AC-005", type: "value-domain", enforcement: "mechanical",
        domain: "channel", allowLiteralIn: ["app.channels.__init__"],
        rationale: "渠道枚举唯一权威定义在 Channels",
        source: "design://05-backend-architecture/data/layering-strategy.js#rule[3]" },
      { id: "AC-007", type: "set-relation", enforcement: "mechanical",
        declared: "design://05-backend-architecture/data/event-contracts.js#events",
        actualSet: "event-handlers", mustMatch: "equal",
        rationale: "事件契约与 handler 注册一致",
        source: "design://05-backend-architecture/data/event-contracts.js" },
      { id: "AC-009", type: "set-relation", enforcement: "mechanical",
        declared: "design://04-platform-api/data/rest/channel-access.js#endpoints",
        actualSet: "routes", mustMatch: "equal", keyStyle: "METHOD path-lowercase-noslash",
        rationale: "路由与 API 设计一致",
        source: "design://04-platform-api/data/rest/channel-access.js" }
    ],

    // 语义约束账本（无法谓词化，spec §4.1）
    reviewLedger: [
      { id: "R-01", constraint: "Controller/API 层禁止包含业务逻辑",
        checkHint: "review D11 + 人抽查；关注 api/ 下出现状态机转换或业务校验" }
    ],

    // 存量违规豁免（spec §8）
    knownDebts: [
      { ruleId: "AC-001", scope: "legacy-notify", issue: "直连通知库", expires: "2026-10-01" }
    ]
  };
})();
