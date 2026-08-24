/**
 * 分层策略 — Layering Strategy
 * NASKB 实际布局：naskb/server（HTTP 层）+ naskb/mcp（AI 接入层）+ naskb/skill（CLI 层）+ naskb/common（核心层）
 * 约束编号供 arch-contract.js 引用（单一来源铁律：谓词只在契约，本文件不重述）
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["layering-strategy"] = {
  layers: [
    { name: "HTTP 接口层(server)", path: "naskb/server/", responsibility: "FastAPI 协议适配/鉴权/路由/下载代理/预览/调度线程", dependsOn: ["common", "mcp?（否）", "skill?（否）"], forbiddenDeps: ["mcp", "skill"], codePattern: "路由函数无业务规则（业务在 common 域服务）", ruleIds: ["AC-001", "AC-008"] },
    { name: "AI 接入层(mcp)", path: "naskb/mcp/", responsibility: "MCP stdio 协议适配与工具清单（capabilities.py 单一事实源）", dependsOn: ["common"], forbiddenDeps: ["server", "skill"], codePattern: "工具函数只编排 common 域服务 + 审计", ruleIds: ["AC-002", "AC-008"] },
    { name: "CLI 层(skill)", path: "naskb/skill/", responsibility: "desc 命令组（28 命令）与 serve/serve-platform/serve-mcp 入口", dependsOn: ["common", "server", "mcp"], forbiddenDeps: [], codePattern: "命令 = 参数装配 + 域服务调用", ruleIds: ["AC-008"] },
    { name: "核心层(common)", path: "naskb/common/", responsibility: "确定性业务：仓库/检索/分析/整理/任务/配置/LLM 客户端", dependsOn: ["（外部依赖：DeepSeek/MiMo/MinerU/PG/fs 适配）"], forbiddenDeps: ["server", "mcp", "skill"], codePattern: "域切片（module-boundaries），无 HTTP/MCP 协议意识", ruleIds: ["AC-003", "AC-004", "AC-005", "AC-006", "AC-009"] }
  ],
  directoryTemplate: {
    "naskb/server/": "app.py + routes_*.py + auth.py + scheduler.py + ranges.py + office.py + thumb.py",
    "naskb/common/": "域切片子包/模块（pgstore/source_registry/retrieval/analyzer/batch/desc_store/reorganizer/plan_store/chunker/jobs/serve/config/llm/embeddings/…）+ fs/ + analyzer/",
    "naskb/mcp/": "server.py（14 工具 + Resources/Prompts）",
    "naskb/skill/": "cli.py（28 desc 命令）"
  }
};
