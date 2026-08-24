/**
 * 架构契约 — Architecture Contract（机械执行层声明源）
 * 规范：.agents/skills/sfds/_shared/arch-contract-spec.md v0.1-draft
 * 探针：scripts/probes/probe_naskb.py → scripts/probes/out/facts.json
 * 运行：node .agents/skills/sfds/_shared/arch-contract/run.mjs --contract design/05-backend-architecture/data/arch-contract.js --facts scripts/probes/out/facts.json --report design/review/arch-contract/latest.json
 * 说明：白名单/表归属=存量依赖基线（探针事实反推）；新增跨组访问必须先更新 module-boundaries
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["arch-contract"] = (function () {
  var _trace = {
    consumes: ["architecture:layering-strategy", "architecture:module-boundaries",
               "architecture:resilience-policy", "architecture:data-consistency"],
    produces: ["constraint:arch-contract"]
  };
  return {
    _trace: _trace,
    version: "1",
    complexityLevel: "L3",
    groups: {
      "layer.api":               ["naskb.server.**"],
      "layer.mcp":               ["naskb.mcp.**"],
      "layer.cli":               ["naskb.skill.**"],
      "modules.common-root":     ["naskb", "naskb.common"],
      "modules.source-management": ["naskb.common.source_registry"],
      "modules.data-access":     ["naskb.common.pgstore"],
      "modules.ingestion":       ["naskb.common.analyzer.**", "naskb.common.batch", "naskb.common.desc_store",
                                  "naskb.common.inventory", "naskb.common.enrich", "naskb.common.adopt",
                                  "naskb.common.clean_export", "naskb.common.sidecar", "naskb.common.hashing",
                                  "naskb.common.exts"],
      "modules.retrieval":       ["naskb.common.retrieval", "naskb.common.pgsearch", "naskb.common.embeddings",
                                  "naskb.common.vector_index"],
      "modules.deep":            ["naskb.common.chunker", "naskb.common.deep_bench", "naskb.common.deep_eval"],
      "modules.reorganize":      ["naskb.common.reorganizer", "naskb.common.plan_store"],
      "modules.platform-core":   ["naskb.common.serve", "naskb.common.jobs", "naskb.common.config",
                                  "naskb.common.llm", "naskb.common.capabilities"],
      "modules.fs-ext":          ["naskb.common.fs.**"]
    },
    externalGroups: { "deepseek": "external.deepseek", "mimo": "external.mimo", "mineru": "external.mineru" },
    valueDomains: {
      "access_mode": { constantsUnit: "naskb.common.source_registry", values: ["ro", "rw"] }
    },
    registrySets: {
      "routes": { probe: "static", keyStyle: "METHOD path-lowercase-noslash" }
    },
    rules: [
      { id: "AC-001", type: "dependency-direction", enforcement: "mechanical",
        from: ["naskb.server.**"], forbid: ["naskb.mcp.**", "naskb.skill.**"], kinds: ["import"],
        rationale: "HTTP 接口层不得依赖 MCP/CLI 层（协议适配单向朝核心层）",
        source: "design://05-backend-architecture/data/layering-strategy.js#layers[0]" },
      { id: "AC-002", type: "dependency-direction", enforcement: "mechanical",
        from: ["naskb.mcp.**"], forbid: ["naskb.server.**", "naskb.skill.**"], kinds: ["import"],
        rationale: "AI 接入层不得依赖 HTTP/CLI 层（四出口同源 → 只调 common 域服务）",
        source: "design://05-backend-architecture/data/layering-strategy.js#layers[1]" },
      { id: "AC-003", type: "dependency-direction", enforcement: "mechanical",
        from: ["naskb.common.**"], forbid: ["naskb.server.**", "naskb.skill.**", "naskb.mcp.**"], kinds: ["import"],
        rationale: "核心层零协议意识（确定性层不感知 HTTP/MCP/CLI）",
        source: "design://05-backend-architecture/data/layering-strategy.js#layers[3]" },
      { id: "AC-004", type: "ownership", enforcement: "mechanical",
        assetKind: "table",
        ownership: "design://05-backend-architecture/data/module-boundaries.js#module-boundaries.modules",
        moduleGroups: { "source-management": "modules.source-management", "data-access": "modules.data-access" },
        rationale: "禁止跨组直访数据库表（SQL 唯一位于属主模块）",
        source: "design://05-backend-architecture/data/module-boundaries.js#module-boundaries.modules" },
      { id: "AC-005", type: "value-domain", enforcement: "mechanical",
        domain: "access_mode", allowLiteralIn: ["naskb.common.source_registry"],
        rationale: "访问模式值（ro/rw）唯一权威定义在 source_registry；API 模型/CLI 必须引用常量",
        source: "design://05-backend-architecture/data/layering-strategy.js#layers[3]" },
      { id: "AC-006", type: "set-relation", enforcement: "mechanical",
        declared: "design://04-platform-api/data/rest/01-source-management.js#01-source-management.endpoints",
        actualSet: "routes:source", mustMatch: "equal", declaredKeyFmt: "method path",
        rationale: "路由注册与 API 设计一致（01 来源管理）",
        source: "design://04-platform-api/data/rest/01-source-management.js" },
      { id: "AC-007", type: "set-relation", enforcement: "mechanical",
        declared: "design://04-platform-api/data/rest/03-retrieval-qa.js#03-retrieval-qa.endpoints",
        actualSet: "routes:retrieval", mustMatch: "equal", declaredKeyFmt: "method path",
        rationale: "路由注册与 API 设计一致（03 检索问答）",
        source: "design://04-platform-api/data/rest/03-retrieval-qa.js" },
      { id: "AC-008", type: "set-relation", enforcement: "mechanical",
        declared: "design://04-platform-api/data/rest/04-deep-analysis.js#04-deep-analysis.endpoints",
        actualSet: "routes:deep", mustMatch: "equal", declaredKeyFmt: "method path",
        rationale: "路由注册与 API 设计一致（04 深度分析）",
        source: "design://04-platform-api/data/rest/04-deep-analysis.js" },
      { id: "AC-009", type: "set-relation", enforcement: "mechanical",
        declared: "design://04-platform-api/data/rest/06-platform-console.js#06-platform-console.endpoints",
        actualSet: "routes:platform", mustMatch: "equal", declaredKeyFmt: "method path",
        rationale: "路由注册与 API 设计一致（06 平台服务）",
        source: "design://04-platform-api/data/rest/06-platform-console.js" },
      { id: "AC-010", type: "set-relation", enforcement: "mechanical",
        declared: "design://05-backend-architecture/data/resilience-policy.js#resilience-policy.idempotency.requiredEndpoints",
        actualSet: "routes", mustMatch: "declared-in-actual",
        rationale: "幂等端点声明全部真实注册（任务型端点的重复提交保证）",
        source: "design://05-backend-architecture/data/resilience-policy.js#idempotency" },
      { id: "AC-011", type: "reference-whitelist", enforcement: "mechanical",
        whitelist: "design://05-backend-architecture/data/module-boundaries.js#module-boundaries.modules",
        moduleGroups: {
          "source-management": "modules.source-management", "data-access": "modules.data-access",
          "ingestion": "modules.ingestion", "retrieval": "modules.retrieval", "deep": "modules.deep",
          "reorganize": "modules.reorganize", "platform-core": "modules.platform-core",
          "fs-ext": "modules.fs-ext", "api-layer": "layer.api", "mcp-layer": "layer.mcp",
          "cli-layer": "layer.cli"
        },
        from: ["naskb.**"],
        rationale: "跨组引用只走所属模块服务（白名单=存量依赖基线，新增跨组访问须先更新设计）",
        source: "design://05-backend-architecture/data/module-boundaries.js#module-boundaries.modules" }
    ],
    reviewLedger: [
      { id: "RL-001", rule: "HTTP 路由函数禁止包含业务规则（状态机转换/业务校验）——当前 routes_sources/routes_content 以函数直连 core 服务，需人工抽查", checkHint: "review D11 人抽查 server/routes_*.py 与 app.py 的函数体", source: "design://05-backend-architecture/data/layering-strategy.js#layers[0]" },
      { id: "RL-002", rule: "事件契约以任务语义承担（无消息中间件）：JobSubmitted/JobCompleted 为进程内信号，重启即失——人审确认该边界可接受", checkHint: "review D11 + 用户确认（内存队列设计决策）", source: "design://05-backend-architecture/data/event-contracts.js" },
      { id: "RL-003", rule: "MCP 工具与 REST 不重复维护端点（四出口同源）——新工具/新端点须确认出口映射唯一", checkHint: "iterate 增功能时对照 capabilities.py 与 rest 文件", source: "design://04-platform-api/data/ai-tools/tools.js" },
      { id: "RL-004", rule: "任务驱动的域（02/05）不建 REST 端点——如未来 Web 入口需要，须先评审再接线", checkHint: "review D9.1 覆盖检查时注意 02/05 的 endpoints=[] 声明", source: "design://04-platform-api/data/rest/02-ingestion-analysis.js" }
    ],
    knownDebts: [
      // 债务已清零（2026-08-24 清理 K-001/K-002：routes_sources/cli 的字面量改为引用
      // source_registry.ACCESS_MODES 常量——AC-005 违规 0；留此占位便于未来登记新存量债）
    ]
  };
})();
