/**
 * AI Tools 协议定义 — MCP（Model Context Protocol, stdio）
 *
 * 数据文件：data/ai-tools/protocol.js（window.AI_TOOLS_DATA["protocol-mcp"]）
 * 命名空间声明：本项目 ai-tools 域使用 window.AI_TOOLS_DATA（bundle 未注册该域命名空间，声明于文件头；
 * 渲染待 api-viewer 协议视图扩展——已知 bundle 局限，见 review/remaining-issues.md）。
 * 消费者：外部 AI Agent（概率模型）——按 api-design §10.6 LLM 消费者铁律设计。
 */

window.AI_TOOLS_DATA = window.AI_TOOLS_DATA || {};
window.AI_TOOLS_DATA["protocol-mcp"] = {

  id: "mcp",
  name: "NASKB MCP",
  fullName: "NASKB Knowledge Base MCP（stdio）",
  description: "14 个 kb_* 工具（A 读 4 / B 写 job 5 / C 整理 3 / D 状态 2）+ 3 Resources + 3 Prompts；长任务返回 job_id；写操作审计 store/audit/<date>.log。",
  version: "1.0",
  projectScoped: true,

  glossary: {
    "kb_*": "工具前缀（kb = knowledge base）",
    "job_id": "长任务标识，轮询 kb_job_status 或收进度通知",
    "Resource": "MCP Resource 抽象（kb://stats、kb://sources、kb://status/{alias}）",
    "Prompt": "MCP Prompt 抽象（3 个预设提示）"
  },

  transports: [
    { type: "stdio", description: "naskb desc serve-mcp [--root X] [--pg]；长任务分钟级，同步返回 job_id 后立即返回" }
  ],

  identity: {
    credentials: [
      { name: "本地进程", format: "stdio（mcp.json 配置），无网络认证", purpose: "写操作经 store/audit 审计" }
    ],
    signingAlgorithm: { name: "none", description: "写操作审计代替鉴权（当前单机部署）；远端复用走平台 Bearer（演进项）" }
  },

  protocolContent: [
    { type: "markdown", title: "概述", data: { content: "<p>MCP Server 与平台 REST 走同一撮核心（四出口同源，ADR-20260816-2）。工具清单单一事实源：<code>common/capabilities.py</code>。</p>" } },
    { type: "table", title: "铁律（LLM 消费者契约）", data: { headers: ["#", "原则"], rows: [
      ["1", "参数尽量扁平——嵌套越深 LLM 结构化生成错误率越高"],
      ["2", "单职责——一个工具调用 = 一个原子动作；批量 = 一个回复多个 tool_calls"],
      ["3", "部分失败独立反馈——每个 tool_call 独立执行、独立结果回填"],
      ["4", "先列方案空间再选型（接口形态决策留痕）"],
      ["5", "语义与形态分开评审"],
      ["6", "无把握时主动暴露 2~3 方案"]
    ] } }
  ],

  envelopeContent: [
    { type: "nested", title: "长任务语义", data: { children: [
      { title: "提交", content: "写类工具（kb_ingest/kb_sync_vectors/kb_index_vectors/kb_plan_*/kb_apply_*）返回 {job_id, status: pending} 立即返回" },
      { title: "进度", content: "kb_job_status(job_id) / kb_list_jobs() 查询；JobManager 串行（max_workers=1）" },
      { title: "完成", content: "completed: {result}；failed: {error}；结果结构与平台任务一致" }
    ] } },
    { type: "nested", title: "审计", data: { children: [
      { title: "写操作", content: "kb_ingest/kb_sync_vectors/kb_index_vectors/kb_plan_*/kb_apply_* 经 _mk_wrap 写 store/audit/<date>.log" },
      { title: "读操作", content: "不写审计（当前）" }
    ] } }
  ],

  sections: [
    { id: "protocol", label: "📋 协议定义", icon: "📋", type: "protocol" },
    { id: "envelope", label: "📨 消息语义", icon: "📨", type: "envelope" }
  ],

  renderRules: { actions: { groupBy: "category" }, enums: {}, status: {} }
};
