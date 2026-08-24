/**
 * 管线状态 — Pipeline State（调度模式数据源）
 *
 * 消费：development-standard 调度模式（§4）——管线状态机唯一裁判。
 * 规则：每次阶段判定后由调度模式更新（status + history）；会话记忆不算状态。
 * 状态判定方式：SFDS 项目首次接入（存量项目补全）——初始状态按项目真实进度赋值，
 * 证据 grade：直接引用可核验证据（文件存在/测试基线/报告），不凭印象。
 * schema：stages[].{id, status: not-started|in-progress|partial|done, evidence[], note}
 *        history[].{date, event, detail}
 */
window.PIPELINE_DATA = window.PIPELINE_DATA || {};
window.PIPELINE_DATA["pipeline-state"] = (function () {
  return {
    version: "2",
    projectName: "NASKB 知识库系统",
    registryRef: ".agents/skills/sfds/_shared/pipeline-registry.js",

    stages: [
      { id: "raw-input",  status: "partial", evidence: [
          "design/01-raw-input/original-logs/ 归档（14 份存量设计 md，git mv 保历史）",
          "整合文档 00-global-design-decisions.md + 各域 NN-{domain}.md",
          "_archive-manifest.md 归档清单"
        ], note: "存量项目补全：原交互已不可恢复，以存量设计文档为原始材料归档；后续新讨论按 §7 原文追加" },
      { id: "workflow",   status: "partial", evidence: [
          "design/02-business-workflow/data/{01..06}-*.js 挂载 + loader 登记",
          "permissions/roles 已定义（权限点唯一定义源）"
        ], note: "资产已建；数据协议字段（inputs/outputs/consumers）初始已填，复查阶段强制核验" },
      { id: "er",         status: "partial", evidence: [
          "design/03-entity-relationship/data/{01..06}-*.js 挂载 + loader 登记 + core-er.js 跨域总纲"
        ], note: "实体字段以代码事实基线为准（存量实现反推）；source/consumers 追溯字段初始已填" },
      { id: "api",        status: "partial", evidence: [
          "design/04-platform-api/data/rest/{01..06}-*.js 端点六维度完整（28 端点：含 report/folder，DD-009）",
          "data/rest/protocol.js + _conventions.js + data/ai-tools/{protocol,tools}.js（MCP 17 工具，DD-009 三工具接线）"
        ], note: "端点以代码实际注册为准；匿名移除/直链契约口径已固化（_conventions §auth、release 四b）" },
      { id: "architecture", status: "partial", evidence: [
          "复杂度判定 L3 模块化单体（外部 LLM 依赖 + 异步任务 + 6 域，Q10/Q11 为真）",
          "design/05-backend-architecture/data/* 10 文件 + arch-contract.js 规则全标 enforcement"
        ], note: "arch-contract 探针与 tests/test_arch_contract.py 已建；契约运行器退出码 0 待首轮执行核验" },
      { id: "ui",         status: "partial", evidence: [
          "design/06-web-console/data/tree.js + loader 登记（pages 格式，桌面端）"
        ], note: "Web 端为唯一客户端（Vue3 静态包，无 TabBar）；api_ref/sends/page_input/output 已填" },
      { id: "tdd",        status: "partial", evidence: [
          "design/07-tdd/api/{01..06}-tdd-design.md + page-mock/web-console-tdd-design.md",
          "tests/ 已按方法论重组（api/ unit/ integration/ page-mock-doc/）"
        ], note: "存量测试 355 用例反向记录为 TC 规格；偏差（无前端测试框架/DIS 拦截形式）记入 design-decisions" },
      { id: "impl",       status: "partial", evidence: [
          "实现代码已存在且含 DD-009 批次变更（report/folder/MCP 17 工具/匿名移除/deep 清理钩子）",
          "tests/test_arch_contract.py 随全量通过（契约退出码 0：11 规则、0 high/0 medium）",
          "待跑：api-code-gen 后置一致性检查（设计→代码比对）作为 Review D 维度输入"
        ], note: "实现先于方法论存在；后续一致性差异以 Review/design-code-gap 追踪" },
      { id: "verify",     status: "partial", evidence: [
          "pytest 全量基线：378+ passed / 1 skipped（DD-009 迭代后；含行为承诺 14 用例与端点回归）",
          "架构契约退出码 0（探针 51 units/56 路由，report/folder 自动对齐）",
          "viewer smoke 5/5（0 error）；E2E 旅程 6/6（全局 Playwright 引擎，全身份口径）"
        ], note: "正式 tdd-execute 阶段报告与 Review 全量复查为下一步" },
      { id: "review",     status: "not-started", evidence: [], note: "D0-D12 全量复查待 tdd-execute 报告就绪后启动（review skill）" },
      { id: "release",    status: "not-started", evidence: [], note: "release/ 资产已建（environments.yaml/policy.md/CHANGELOG.md）；实际发布走 release-management 门禁" }
    ],

    history: [
      { date: "2026-08-24", event: "sfds-onboard", detail: "存量项目补全：按 SFDS 方法论建立全部设计资产（01-raw-input~07-tdd + review + release），AGENTS.md 按模板重写并生成铁律表" },
      { date: "2026-08-24", event: "domain-registry-v1", detail: "六域划分确定：source-management / ingestion-analysis / retrieval-qa / deep-analysis / knowledge-reorganize / platform-console；MCP 按 AI Tools 协议归入 04-platform-api/ai-tools" },
      { date: "2026-08-24", event: "decision", detail: "遗留 design/*.md 按 disallowed 平行叙述文档处理：git mv 归档 original-logs/，同时生成整合需求文档（用户拍板）" },
      { date: "2026-08-24", event: "decision", detail: "tests/ 按方法论重组（用户拍板）；TDD 设计文档为反向记录（实现先行、文档后补）" },
      { date: "2026-08-24", event: "phase-verify", detail: "验证基线：pytest 356 passed/1 skipped；架构契约退出码 0（11 规则）；5 viewer file:// 渲染核实 0 error（scripts/viewer-smoke.mjs）" },
      { date: "2026-08-24", event: "iterate-dd009", detail: "DD-009 拍板批次（iterate 路径 C，10 问题）：匿名全移除/report+folder 接回/MCP 17 工具/deep 关闭清理 chunk/直链网关边界/裁剪落账（权限保留·健康频控裁剪·行为承诺补齐·E2E 全局 Playwright MCP）；验证 378+ passed、契约 0、smoke 5/5、E2E 6/6" }
    ]
  };
})();
