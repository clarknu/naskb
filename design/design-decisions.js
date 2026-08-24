/**
 * 设计决策日志 — Design Decisions（跨步骤共享的决策账本）
 *
 * 定位：development-standard §6.4。任何"非从上游资产纯逻辑推导"的设计选择必须写入本文件；
 * 同步螺旋（§10.3b）上溯时先查本文件——不一致可能是有意决策，不是错误。
 * 规则：不可删除历史决策；旧决策标记 superseded_by；先记账后改资产（backend-architecture-design §4.2）。
 * 版本：v1（2026-08-24）
 */
window.DESIGN_DECISIONS = [
  {
    id: "DD-001",
    date: "2026-08-24",
    domain: "cross-domain",
    layer: "onboarding",
    trigger: "user-decision",
    summary: "存量项目按 SFDS 方法论补全资产：项目最初开发未遵循方法论（实现/测试先于设计资产存在），本次以'反向补全'方式建立全部设计资产，实现为部分资产的真相源",
    rationale: "用户明确：先完整补全方法论要求的全部资产，后续开发按方法论执行。资产反推自存量设计与代码事实基线，偏差显式记录而非静默掩盖",
    affected_assets: ["design/domain-registry.js", "design/pipeline-state.js", "design/01-raw-input/*"],
    alternatives_considered: ["推倒重建（不现实，在途 V2 功能不可中断）", "仅补骨架不填内容（不完整，违背'完整补全'）"],
    supersedes: []
  },
  {
    id: "DD-002",
    date: "2026-08-24",
    domain: "cross-domain",
    layer: "domain-modeling",
    trigger: "user-decision",
    summary: "业务域划为 6 域（source-management/ingestion-analysis/retrieval-qa/deep-analysis/knowledge-reorganize/platform-console）；MCP 不单列域，按 api-design 的 AI Tools 协议归入 04-platform-api/data/ai-tools/",
    rationale: "MCP 的 kb_* 工具是对既有域能力的访问面（读→retrieval-qa、写→ingestion-analysis/reorganize），业务逻辑不归属其自身；按 api-design §10.5 AI Tools 协议建模（LLM 消费者铁律 6 条）",
    affected_assets: ["design/domain-registry.js", "design/04-platform-api/data/ai-tools/*"],
    alternatives_considered: ["07-mcp-access 单列域（冗余边界，工具与域动作重复定义）"],
    supersedes: []
  },
  {
    id: "DD-003",
    date: "2026-08-24",
    domain: "cross-domain",
    layer: "raw-input",
    trigger: "user-decision",
    summary: "存量 14 份 design/*.md（平行叙述文档，方法论禁止）全部 git mv 归档至 design/01-raw-input/original-logs/，并生成整合需求文档（00-global + 各域 NN-{domain}.md，REQ 锚点）",
    rationale: "文档资产准入规则（document-asset-format §1）禁止手写 Markdown 平行承载设计内容；归档保 Git 历史，整合文档承接下游追溯锚点",
    affected_assets: ["design/01-raw-input/*", "design/*.md（已归档）"],
    alternatives_considered: ["保留 design/ 根目录（持续产生平行真相源，review D11 会持续告警）"],
    supersedes: []
  },
  {
    id: "DD-004",
    date: "2026-08-24",
    domain: "cross-domain",
    layer: "tdd",
    trigger: "user-decision",
    summary: "TDD 资产反向补全：把存量 355 用例映射为 design/07-tdd/{api,page-mock} 设计文档（TC 规格），tests/ 按方法论重组为 api/ unit/ integration/ 分层",
    rationale: "用户拍板重组 tests/ 目录（而非保持扁平）；TDD 设计文档记录'实现先行、文档后补'的真实状态，偏差不入未经审计的状态",
    affected_assets: ["design/07-tdd/*", "tests/*"],
    alternatives_considered: ["保持 tests/ 扁平 + 仅文档（风险小但与阶段目录约定不符）"],
    supersedes: []
  },
  {
    id: "DD-005",
    date: "2026-08-24",
    domain: "cross-domain",
    layer: "architecture-design",
    trigger: "upstream-change",
    summary: "架构复杂度判定为 L3 模块化单体（必产 9 文件 + arch-contract/decisions）：外部 LLM 依赖（DeepSeek/MiMo/MinerU，Q10）+ 异步任务/调度（Q11）+ 6 业务域（Q13）",
    rationale: "backend-architecture-design §1 问卷：Q10/Q11/Q13 为真；无水平扩展/灰度/多租户需求（Q4/Q5/Q7/Q8 否），不达 L4",
    affected_assets: ["design/05-backend-architecture/data/*"],
    alternatives_considered: ["L2（低估外部依赖风险，可靠性/可观测性策略缺失）", "L4（过度设计，单人运维单进程服务）"],
    supersedes: []
  },
  {
    id: "DD-006",
    date: "2026-08-24",
    domain: "cross-domain",
    layer: "api-design",
    trigger: "implementation-feedback",
    summary: "REST 端点事实以存量代码实际注册为准（26+ 端点）：设计资产按代码反推；代码与声明不一致点（如 GET /api/sources/{sid}/report 装饰器未生效、/api/folder 孤儿匿名前缀、/api/jobs 匿名不一致、多 token 仅首个有效等）作为差异基线列入 design/review/design-code-gap.md，待后续 review 仲裁决定修代码还是修设计",
    rationale: "实现先于方法论存在，且为经测试验证的行为；'设计=权威源'的默认规则在存量补全场景下以'代码行为是历史事实'为前提，差异显式暴露而非静默",
    affected_assets: ["design/04-platform-api/data/rest/*", "design/review/design-code-gap.md"],
    alternatives_considered: ["以既有设计文档为 API 真相源（与实现割裂，Review 会大面积不一致）"],
    supersedes: []
  },
  {
    id: "DD-007",
    date: "2026-08-24",
    domain: "retrieval-qa",
    layer: "business-workflow",
    trigger: "user-decision",
    summary: "检索/问答索引只用文件的摘要+描述（用户拍板：全文不参与向量/关键词检索，避免高频词稀释主题）；全文（ocr_text 等）保留为元数据，仅 RAG 生成阶段作为上下文",
    rationale: "记录自存量需求文档的既有拍板，作为 retrieval-qa 域的既有设计约束，反向补全时保持该决策",
    affected_assets: ["design/02-business-workflow/data/03-retrieval-qa.js", "design/03-entity-relationship/data/03-retrieval-qa.js"],
    alternatives_considered: [],
    supersedes: []
  },
  {
    id: "DD-008",
    date: "2026-08-24",
    domain: "cross-domain",
    layer: "desktop-ui-design",
    trigger: "upstream-change",
    summary: "Web 端是唯一客户端（Vue3 静态包无构建/无 TabBar），client-slug = web-console（06-web-console）；无移动端/小程序端，mobile-app-design 与 wechatide-automation 不适用",
    rationale: "desktop-ui-design 的 pages 格式与当前 UI（顶部导航 4 视图 + 文件模态）一致；无前端测试框架（无 package.json/vitest），page-mock 阶段以设计规格 + 后续接入说明呈现",
    affected_assets: ["design/06-web-console/*", "design/pipeline-state.js"],
    alternatives_considered: ["web-admin（与产品形态'知识库控制台'不符，界面非管理后台）"],
    supersedes: []
  },
  {
    id: "DD-009",
    date: "2026-08-24",
    domain: "cross-domain",
    layer: "iterate-batch",
    trigger: "user-decision",
    summary: "2026-08-24 拍板批次（iterate 路径 C，10 问题）：①执行遗漏修复：report 端点接回（函数体已存在，恢复装饰器）、/api/folder 目录级描述端点实现、匿名白名单全部移除（仅 /api/config/public、/api/docs、/api/openapi.json 匿名作启动引导）、deep=false 清理存量 chunk 行（UI 加确认提示）、MCP 三工具（kb_list_sources/kb_list_tree/kb_get_file_url）接线、直链不认证（安全边界=外围网关 IP 约束）；②裁剪口径：权限模型保留（企业非加密资料管理有用，运行时仍单管理员、多用户留 R7-15）/健康检查·频控·指标裁剪/TDD 行为承诺测试补齐/E2E 走全局 Playwright MCP（本机 C:\\Soft；他机各用其配置）；③发布节奏：不主动发布，明确指令才全做完并发布到指定环境",
    rationale: "决策原文存档 design/01-raw-input/07-user-decisions-2026-08-24.md；台账 design/review/user-decisions-pending.md",
    affected_assets: ["design/02-business-workflow/data/01..06", "design/03-entity-relationship/data/*（无字段变更，仅核对）", "design/04-platform-api/data/rest/*", "design/04-platform-api/data/ai-tools/tools.js", "design/05-backend-architecture/data/*", "design/06-web-console/data/*", "design/07-tdd/*", "naskb/scripts/naskb/server/*", "naskb/scripts/naskb/common/{auth? 无, pgstore, capabilities}", "naskb/scripts/naskb/mcp/server.py", "naskb/web/public/app.js"],
    alternatives_considered: [],
    supersedes: []
  },
  {
    id: "DD-010",
    date: "2026-08-24",
    domain: "retrieval-qa",
    layer: "api-design",
    trigger: "implementation-feedback",
    summary: "R5-05 混合检索落地（opt-in）：PG tsvector 关键词通道 + 向量 top-k 做 RRF 融合；中文分词用「CJK 单字+二元组 N-gram」（不依赖分词词典——jieba 未随包声明）；关键词通道对纯英文/数字与中文子串式查询可命中；engine 标注 pg-hybrid；默认关闭（向量路径不变），经 /api/kb/search?hybrid=1 或 CLI --hybrid 开启；条款级（chunk）不掺入混合（两级引用语义已定）",
    rationale: "草案 pg-vector-multi-nas §8.1 要求 tsvector+RRF；实现中验证 PG 原生 tsvector 不分词中文，且 jieba 未安装——改采用 N-gram（查询/写入同粒度），零依赖且子串可命中；opt-in 避免改变既有检索行为（R5-05 标记为可选增强）",
    affected_assets: ["design/04-platform-api/data/rest/03-retrieval-qa.js", "design/07-tdd/api/03-retrieval-qa-tdd-design.md", "naskb/scripts/naskb/common/pgstore.py", "naskb/scripts/naskb/common/pgsearch.py", "naskb/scripts/naskb/common/retrieval.py", "naskb/scripts/naskb/skill/cli.py", "naskb/scripts/naskb/server/app.py"],
    alternatives_considered: ["jieba 预分词（未随包声明，需新增依赖）", "pg_trgm 扩展（需 PG 超级权限，统一实例不可控）", "tsvector + 默认分词（对中文无效）"],
    supersedes: []
  }
];
