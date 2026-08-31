/**
 * SFDS 管线注册表 — Pipeline Registry（单一真相源）
 *
 * 职责：全 skill 的阶段归属、触发词、上下游关系、阶段出口门禁的**唯一权威登记处**。
 * 派生物（禁止手编，改了也会被下次生成覆盖）：
 *   - AGENTS.md 铁律表触发词段（.agents/skills/sfds/_shared/gen/generate-trigger-table.mjs 生成）
 * 消费者：
 *   - development-standard「调度模式」（读注册表 + design/pipeline-state.js 判定下一步/门禁）
 *   - 新 skill 准入（§admission 契约：登记即接线，未登记 = 方法论孤岛）
 * 变更管理：新增/修改 skill 必须先改本文件（对应 SKILL.md 的 frontmatter 同步），
 *   再跑生成脚本刷新 AGENTS.md。
 */
window.SFDS_DATA = window.SFDS_DATA || {};
window.SFDS_DATA["pipeline-registry"] = (function () {

  return {
    version: "1",

    // ═══ 阶段定义（顺序即流水线主序；iterate 为常驻旁路，任意阶段可入）═══
    stages: [
      { id: "raw-input",  name: "原始输入",   order: 1, skills: ["consolidate-raw-input"], exitGates: [{ name: "原始输入已归档", check: "design/01-raw-input/original-logs/ 存在对应时间戳文件" }] },
      { id: "workflow",   name: "业务设计",   order: 2, skills: ["business-workflow"], exitGates: [{ name: "工作流资产就绪", check: "design/02-business-workflow/data/{slug}.js 挂载 + loader 登记" }] },
      { id: "er",         name: "数据建模",   order: 3, skills: ["entity-relationship"], exitGates: [{ name: "ER 资产就绪", check: "design/03-entity-relationship/data/{slug}.js 挂载 + loader 登记" }] },
      { id: "api",        name: "API 设计",   order: 4, skills: ["api-design"], exitGates: [{ name: "API 契约就绪", check: "design/04-platform-api/data/{slug}.js 端点六维度完整" }] },
      { id: "architecture", name: "后端架构", order: 5, skills: ["backend-architecture-design"], optional: "L1 跳过", exitGates: [{ name: "架构资产 + 契约就绪（L2+）", check: "05-backend-architecture/data/* 完整 + arch-contract.js 规则全标 enforcement" }] },
      { id: "ui",         name: "页面设计",   order: 6, skills: ["client-ui-design"], optional: "按端类型", exitGates: [{ name: "功能树就绪", check: "design/{NN}-{client}/data/tree.js + loader 登记" }] },
      { id: "tdd",        name: "TDD 设计",   order: 7, skills: ["tdd-build"], exitGates: [{ name: "测试设计 + 代码就绪", check: "design/07-tdd/ 设计文档 + tests/ 代码（契约先行）" }] },
      { id: "impl",       name: "代码实现",   order: 8, skills: ["api-code-gen", "client-code-gen"], exitGates: [{ name: "后置一致性检查零差异", check: "各 code-gen skill 步骤 6 / 一致性检查模式" }, { name: "架构契约退出码 0（L2+）", check: "tests/test_arch_contract.py" }] },
      { id: "verify",     name: "测试执行",   order: 9, skills: ["tdd-execute"], exitGates: [{ name: "全量测试 0 失败", check: "tdd-execute 报告全绿" }] },
      { id: "review",     name: "全量复查",   order: 10, skills: ["review"], exitGates: [{ name: "D0-D12 通过且无新问题类别", check: "review 报告 + 收敛判据（§10）" }] },
      { id: "release",    name: "发布",       order: 11, skills: ["release-management"], exitGates: [{ name: "门禁 11 项全过 + tag", check: "release/policy.md" }] }
    ],

    // ═══ exitGates.check 占位符约定 ═══
    // {slug}=域/端 slug；{client}=端 client-slug；{NN}=设计目录编号前缀（与 development-standard 编号一致，
    // 如 ui 阶段=「06-」）。tests/test_arch_contract.py 是 Python 探针的门禁封装——架构契约门禁本身是语言无关的
    // （node _shared/arch-contract/run.mjs 退出码 0），该 .py 只是探针适配层，其他语言用等价适配即可。

    // 常驻旁路（不属于主序，任意阶段可触发）
    bypass: [
      { id: "iterate", name: "迭代引擎", skills: ["iterate"], note: "用户表达修正/新增/诊断意图时进入；出口 = §8.8 全绿 + review 无新实质问题 + C3.1 前置脚本全过" }
    ],

    // ═══ Skill 登记（准入契约：name/layer/stage/triggers/inputs/outputs 必填）═══
    skills: [
      { name: "iterate", layer: "编排", stage: "bypass", priority: 1,
        triggers: ["迭代", "更新", "调整", "修改", "改一下", "加功能", "新增", "重构", "变更", "修 bug", "报错", "500", "崩溃", "测试失败", "不对", "有问题", "少了", "缺了", "错误", "问题", "修复", "bug", "诊断", "问题排查", "根因分析", "联调", "联调修正", "集成调试", "前后端对接", "不匹配", "遗漏", "未同步", "对不上", "整体检查"],
        summary: "功能迭代 + Bug 修复 + 联调批量修正的统一级联编排器（§10.3b），三条路径：A 功能迭代 / B 诊断修复 / C 联调修正（批量）；阶段二执行/验证默认进 pipeline-controller 流水线（CASE-015/016）",
        inputs: ["用户变更/问题意图", "当前设计资产", "tests/"], outputs: ["级联修正后的设计+代码+测试", "迭代报告"],
        upstream: ["任意设计/实现 skill"], downstream: ["review"] },
      { name: "business-workflow", layer: "设计", stage: "workflow", priority: 2,
        triggers: ["业务设计", "工作流", "状态机"],
        summary: "业务梳理与流程设计（§8.1），workflow-viewer + data/*.js",
        inputs: ["design/01-raw-input/"], outputs: ["design/02-business-workflow/data/{slug}.js"],
        upstream: ["consolidate-raw-input"], downstream: ["entity-relationship", "api-design"] },
      { name: "entity-relationship", layer: "设计", stage: "er", priority: 2,
        triggers: ["ER 图", "实体关系", "数据建模"],
        summary: "实体关系图设计（§8.2），er-viewer + data/*.js",
        inputs: ["design/02-business-workflow/"], outputs: ["design/03-entity-relationship/data/{slug}.js"],
        upstream: ["business-workflow"], downstream: ["api-design", "api-code-gen"] },
      { name: "api-design", layer: "设计", stage: "api", priority: 2,
        triggers: ["API 设计", "接口设计", "REST API"],
        summary: "API 契约设计（§8.3），api-viewer + data/*.js（REST/IoT/AI Tools）",
        inputs: ["workflow", "er"], outputs: ["design/04-platform-api/data/{slug}.js"],
        upstream: ["business-workflow", "entity-relationship"], downstream: ["backend-architecture-design", "api-code-gen", "tdd-build"] },
      { name: "backend-architecture-design", layer: "设计", stage: "architecture", priority: 2,
        triggers: ["后端架构设计", "分层设计", "模块边界", "架构审计", "全量分析"],
        summary: "架构与服务体系设计（§8.3b）+ 审计模式（§3b）；产出架构契约（机械约束）",
        inputs: ["workflow", "er", "api", "AGENTS.md"], outputs: ["design/05-backend-architecture/data/*.js（含 arch-contract / design-decisions / audit-dossier）"],
        upstream: ["api-design"], downstream: ["api-code-gen", "tdd-build", "review（D11 委托）"] },
      { name: "client-ui-design", layer: "设计", stage: "ui", priority: 2,
        triggers: ["页面设计", "移动端设计", "小程序设计", "App 设计", "PC 端设计", "桌面端设计", "后台设计", "Web 后台设计"],
        summary: "客户端页面功能设计（§8.4），design-viewer + data/*.js（移动端 TabBar 根 / 桌面端页面集根，A1 合并）",
        inputs: ["workflow", "er", "api"], outputs: ["design/{NN}-{client}/data/tree.js 等"],
        upstream: ["business-workflow", "entity-relationship"], downstream: ["client-code-gen", "tdd-build"] },
      { name: "tdd-build", layer: "验证", stage: "tdd", priority: 3,
        triggers: ["TDD 设计", "测试设计", "写测试", "API 测试", "页面测试", "集成测试"],
        summary: "TDD 测试设计与编码——三阶段（api / page-mock / integration）（§8.5）",
        inputs: ["api", "er", "workflow", "页面设计", "backend-architecture"], outputs: ["design/07-tdd/ 设计文档", "tests/ 测试代码"],
        upstream: ["api-design", "backend-architecture-design", "client-ui-design"], downstream: ["tdd-execute"] },
      { name: "tdd-execute", layer: "验证", stage: "verify", priority: 3,
        triggers: ["TDD 执行", "运行测试", "测试报告", "跑测试"],
        summary: "TDD 测试执行与验证——三阶段（§8.8），失败分类溯源 + 修复循环",
        inputs: ["tests/", "实现代码"], outputs: ["测试执行报告"],
        upstream: ["tdd-build", "api-code-gen", "code-gen"], downstream: ["review"] },
      { name: "review", layer: "验证", stage: "review", priority: 3,
        triggers: ["复查", "一致性检查", "全量复查"],
        summary: "多维度全项目复查（§9）——D0-D12 逐层一致性校核，调度各 skill 检查模式",
        inputs: ["全部设计资产", "src/", "tests/"], outputs: ["复查报告", "迭代修复闭环"],
        upstream: ["tdd-execute"], downstream: ["release-management"] },
      { name: "api-code-gen", layer: "实现", stage: "impl", priority: 4,
        triggers: ["API 代码生成", "后端代码"],
        summary: "服务端代码生成与一致性检查（§8.6）——架构驱动，技术栈从 AGENTS.md 读取",
        inputs: ["backend-architecture", "api", "er", "AGENTS.md"], outputs: ["src/server/", "后置一致性检查报告"],
        upstream: ["backend-architecture-design", "api-design"], downstream: ["tdd-execute", "review"] },
      { name: "client-code-gen", layer: "实现", stage: "impl", priority: 4,
        triggers: ["客户端代码生成", "页面代码生成", "前端代码", "移动端代码生成", "桌面端代码生成", "后台代码", "Web 前端代码"],
        summary: "客户端代码生成（§8.7）——tree.js → 页面骨架 + 一致性校核（移动/桌面统一，A2 合并）",
        inputs: ["client-ui-design tree.js", "api"], outputs: ["客户端代码", "一致性检查报告"],
        upstream: ["client-ui-design"], downstream: ["tdd-execute", "review"] },
      { name: "ai-workflow-orchestration-design", layer: "设计（团队）", stage: "bypass", priority: 2,
        triggers: ["工作流编排", "编排设计", "Dify 流程设计", "节点走向", "会话隔离"],
        summary: "AI 工作流编排设计六原则 P1-P6（编排层+执行层分离架构）",
        inputs: ["项目工作流需求"], outputs: ["工作流编排设计决策（项目设计文档）"],
        upstream: [], downstream: [] },
      { name: "development-standard", layer: "基础", stage: "bypass", priority: 0,
        triggers: ["标准", "方法论", "项目初始化", "SFDS", "下一步", "继续", "当前进度", "该做什么", "拿不准", "流程状态", "新项目", "项目启动", "项目骨架", "new project"],
        summary: "SFDS v3 全标 + 新项目初始化 + **调度模式**（读 pipeline-registry + pipeline-state 判定当前阶段/下一步/门禁）",
        inputs: ["_shared/pipeline-registry.js", "design/pipeline-state.js"], outputs: ["项目骨架", "调度判定"],
        upstream: [], downstream: ["全部（调度关系，非数据关系）"] },
      { name: "consolidate-raw-input", layer: "基础", stage: "raw-input", priority: 0,
        triggers: ["整理原始输入", "合并原始需求"],
        summary: "原始输入整合归档（手动调用，非自动流水线）",
        inputs: ["会话/文档原始输入"], outputs: ["design/01-raw-input/ 规范文档 + original-logs/"],
        upstream: [], downstream: ["business-workflow"] },
      { name: "sync-design-to-publish", layer: "工具", stage: "bypass", priority: 5,
        triggers: ["发布设计文档", "同步设计文档到 publish"],
        summary: "设计文档同步到 publish/ 并部署 Cloudflare Pages",
        inputs: ["design/"], outputs: ["publish/ + 线上部署"],
        upstream: ["各设计 skill"], downstream: [] },
      { name: "release-management", layer: "工具", stage: "release", priority: 5,
        triggers: ["发布线上", "上线", "发版", "部署线上", "发布流程", "发线上", "更新到线上", "版本号", "打 tag", "回滚", "环境切换", "预发布", "环境退役", "停用环境", "下线环境", "decommission"],
        summary: "发布管理方法论——环境层级/发布门禁 11 项/版本规范/回滚/环境退役停用（过程资产 deployment-config-guide）",
        inputs: ["全绿测试", "review 报告"], outputs: ["tag vX.Y.Z", "线上部署", "CHANGELOG"],
        upstream: ["review"], downstream: [] },
      { name: "wechatide-automation", layer: "工具", stage: "bypass", priority: 5,
        triggers: ["微信开发者工具", "小程序预览", "小程序调试"],
        summary: "微信开发者工具（wechatide）使用与小程序自动化测试——能力门判定（有外置工具→可做自动化+做法 / 无→做不了、需补充）+ 驱动用法",
        inputs: ["微信开发者工具", "小程序项目"], outputs: ["判定结论 / 小程序自动化测试结果"],
        upstream: ["client-code-gen", "tdd-execute"], downstream: [] },
      { name: "credential-management", layer: "工具", stage: "bypass", priority: 5,
        triggers: ["密钥管理", "密钥库", "访问凭据", "访问令牌", "API 密钥", "API Key", "敏感配置", "加密配置", "部署密钥", "环境变量注入", "凭据管理", "credentials", "access token", "api key"],
        summary: "项目加密密钥/配置库（credentialctl）——passphrase 派生主密钥 + 每机 DPAPI 自动解锁；默认注入 <CREDENTIAL:proj/key> 占位符、仅 --env/--reveal 在部署时取真值；按项目 scope 认证 + 全程审计；数据在项目 .credential（gitignore）",
        inputs: ["项目 scope 声明", "agent.md / .credential\\config 绑定"], outputs: ["<CREDENTIAL:proj/key> 占位符", "$env:NAME='...' 注入", "审计记录"],
        upstream: [], downstream: [] },
      { name: "deployment-principles", layer: "原则", stage: "review", priority: 5,
        triggers: ["部署环境", "环境模型", "环境架构", "环境拓扑", "预发布环境", "预发环境", "生产环境", "线上环境", "环境规范", "子网", "网络转发", "Mock", "数据隔离", "同库主机", "库名不同", "逻辑隔离", "环境隔离", "部署架构", "中间件", "公共服务", "宿主化", "独立实例", "数据库实例", "Redis 缓存", "docker compose 自建", "部署原则", "环境配置", "服务隔离", "网络拓扑", "网络分层", "宿主端口", "Docker 网络", "Nginx", "反向代理", "内网", "公网", "域名映射"],
        summary: "部署总原则（原则/评审资产）——（合并 deployment-environment-model + infra-service-isolation，CASE-020；网络分层 CASE-021 + 细则定稿 CASE-022）把「环境拓扑规范 + 通用中间件资源放置 + 网络访问拓扑（宿主机分层）+ 部署原则」统一为一条部署合规评审：线上结构一致不超既定范围；本地开发自建/中间件/业务系统原则上不出子网（外网以 Mock/网络转发绕过）；预发布与线上共用同一第三方库主机、仅库名不同（逻辑隔离），自建组件复用同一主机、轻量系统组件独立部署一套；数据库跨环境一律逻辑隔离（不引入主机级物理隔离）；通用中间件用宿主机原生/统一独立实例（RDS/云 Redis/统一容器），禁止业务 compose 自建公共服务；公共中间件仅内网绑定（禁 0.0.0.0 公网）、业务全进 Docker、服务名 {env}-{service} 环境前缀、一项目一 Docker 网络、跨产品禁互访、对外只经 Nginx 域名映射（可多线并存，内网不出公网）；三环境同构、独立实例凭据集中管理；配置发布依赖架构文档圈定、机密存 Credential Vault。与 release-management（怎么发布）/ credential-management（机密）互补",
        inputs: ["项目环境配置", "部署架构文档", "环境拓扑", "业务 compose / 中间件布局", "宿主网络/端口布局"], outputs: ["部署合规评审结论 / 环境配置清单", "基础设施合规清单", "网络分层合规"],
        upstream: ["release-management", "review"], downstream: [] }
    ],

    // ═══ 入口架构（谁在每次会话始终在场）═══
    entry: {
      alwaysLoaded: "AGENTS.md（不变块：铁律指针 + 文档资产模式 + 全局规则）+ harness skill catalog 摘要",
      dispatcher: { skill: "development-standard", mode: "调度模式（第一部分 §4）", registry: "_shared/pipeline-registry.js", state: "design/pipeline-state.js" },
      routing: {
        fastPath: "触发词命中（AGENTS.md 铁律表，由注册表生成）→ 直接调用对应 skill",
        proceduralPath: "阶段推进/下一步/继续/进度类意图 → development-standard 调度模式判定 → 给出当前阶段 + 前置门禁差距 + 下一步 skill",
        recursionStop: "调度器是 development-standard（基础层，非新建 skill）；其自身由 AGENTS.md 铁律直接指向，不产生『谁路由路由器』递归"
      }
    },

    // ═══ 准入契约（新 skill / 变更 skill 必读）═══
    admission: {
      requiredFields: ["name", "layer", "stage", "priority", "triggers", "summary", "inputs", "outputs", "upstream", "downstream"],
      skillFile: "SKILL.md frontmatter（name/version/description/triggers）与本登记保持一致",
      procedure: [
        "1. 在本注册表 skills[] 增加登记（或修改既有条目）",
        "2. 创建/更新 {skill}/SKILL.md（frontmatter 与登记一致；遵循 document-asset-format 如含文档产物）",
        "3. 跑 .agents/skills/sfds/_shared/gen/generate-trigger-table.mjs --write 刷新 AGENTS.md 铁律表",
        "4. 涉及门禁/检查的，同步接线 review / iterate / release 对应条目"
      ],
      islandRule: "未登记本注册表的 skill = 方法论孤岛：不出现在铁律表、不被调度模式认知、不参与阶段门禁——等同不存在"
    },

    // ═══ 分发（项目级 ↔ 全局级）═══
    distribution: {
      projectLevel: ".agents/skills/sfds/（跟项目迭代，成熟后升全局）",
      globalLevel: "~/.agents/skills/（跨项目复用）",
      reconcile: "_shared/dist/reconcile.mjs（逐 skill 版本 + 内容 hash 对账：该升级/该回流/一致）",
      rule: "对账脚本报告为分发决策依据；_shared/ 规范文件双侧保持同步"
    }
  };
})();
