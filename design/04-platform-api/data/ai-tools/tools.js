/**
 * AI Tools 数据文件 — MCP 14 个 kb_* 工具（window.AI_TOOLS_DATA["tools-mcp"]）
 * 依据：common/capabilities.py 单一事实源（工具清单/参数/返回），与 mcp/server.py 注册一致。
 * 消费者：外部 AI Agent（概率模型）——参数扁平、单职责（api-design §10.6 铁律）。
 * 工具分组：A 读（4）/ B 写 job（5）/ C 整理（3）/ D 状态（2）；另有 3 Resources + 3 Prompts（见 protocol.js）。
 */

window.AI_TOOLS_DATA = window.AI_TOOLS_DATA || {};
window.AI_TOOLS_DATA["tools-mcp"] = {
  domain: "ai-tools",
  title: "MCP 工具集（kb_*）",
  slug: "mcp-tools",
  description: "14 个 kb_* 工具：检索/问答/文件获取（读），入库/同步/索引/任务（写 job），整理三工具（写+审计），状态/统计",
  last_updated: "2026-08-24",
  tooling_ref: "naskb/scripts/naskb/mcp/server.py",
  capabilities_ref: "naskb/scripts/naskb/common/capabilities.py",

  groups: [
    { id: "A", label: "读组（同步返回）", tools: [
      {
        id: "kb_search", name: "知识搜索", direction: "read", sync: true,
        description: "语义/关键词检索知识库（摘要索引；支持 NAS/来源过滤）",
        params: [
          { name: "query", type: "string", required: true, desc: "查询词（语义/关键词）", example: "出行要带的证件" },
          { name: "top_k", type: "integer", required: false, desc: "返回条数 1-100，默认 20" },
          { name: "nas", type: "string", required: false, desc: "NAS alias 过滤" },
          { name: "sources", type: "string[]", required: false, desc: "来源过滤（扁平数组，铁律 2）" }
        ],
        returns: { shape: "{engine, hits[{resource_id,path,score,summary,category,tags,stale,nas,source_alias}]}", note: "文档级；条款级命中含 kind/chunk_seq/title_path" },
        job: false
      },
      {
        id: "kb_ask", name: "知识问答", direction: "read", sync: true,
        description: "RAG 问答（带来源）；deep=true 时条款级（两级引用 + direct_return 保真直返）",
        params: [
          { name: "question", type: "string", required: true, desc: "问题" },
          { name: "top_k", type: "integer", required: false, desc: "召回条数，默认 5" },
          { name: "deep", type: "boolean", required: false, desc: "true=条款级（需 PG+deep 配置；无则静默回退文档级）" },
          { name: "direct_return", type: "boolean", required: false, desc: "条款级保真直返（≥0.9 直接返回原文，默认 true）" }
        ],
        returns: { shape: "{answer, level(chunk|summary), sources[] | citations[{path,chunk_seq,title_path,score}], engine}", note: "A'（P-003）：deep=true 却回退文档级时 level=summary + note 提示——调用方据此换问题或先建条款索引；无命中诚实兜底" },
        job: false
      },
      {
        id: "kb_get_doc", name: "获取文档详情", direction: "read", sync: true,
        description: "按 resource_id/路径获取知识元数据（分类/标签/摘要/内容描述）",
        params: [
          { name: "resource_id", type: "string", required: true, desc: "资源 ID" },
          { name: "src", type: "string", required: false, desc: "来源 ID（歧义时）" }
        ],
        returns: { shape: "{resource{name,rel_path,category,tags,summary,content_description,status,mtime,size_bytes}}", note: "脱敏（不含密码等）" },
        job: false
      },
      {
        id: "kb_fetch_file", name: "获取文件内容", direction: "read", sync: true,
        description: "下载文件（返回直链/内容；直链不带 token——安全边界=外围网关 IP 约束，API 层不认证，DD-009 拍板）",
        params: [
          { name: "resource_id", type: "string", required: true, desc: "资源 ID" },
          { name: "src", type: "string", required: false, desc: "来源 ID" }
        ],
        returns: { shape: "{url | content, size_bytes}", note: "大文件给直链；网关层 IP 白名单限流（网络/部署边界）" },
        job: false
      },
      {
        id: "kb_list_sources", name: "列出知识来源", direction: "read", sync: true,
        description: "列出已注册来源（别名/协议/访问模式/统计/状态）——Agent 定位写入目标时先查来源",
        params: [],
        returns: { shape: "{sources[{source_id, alias, protocol, access_mode, enabled, deep, stats}]}", note: "脱敏（无密码）" },
        job: false
      },
      {
        id: "kb_list_tree", name: "浏览目录树", direction: "read", sync: true,
        description: "按来源+目录列出子目录/文件（浏览知识库的路径入口）",
        params: [
          { name: "src", type: "string", required: true, desc: "来源 ID" },
          { name: "dir", type: "string", required: false, desc: "目录 rel_path（空=根）" }
        ],
        returns: { shape: "{dirs[{rel_path,name,file_count,summary}], files[{resource_id,name,size_bytes,summary,category,status}]}" },
        job: false
      },
      {
        id: "kb_get_file_url", name: "获取文件直链", direction: "read", sync: true,
        description: "生成文件下载直链（平台 server_base_url + 下载端点；不带 token——网关层 IP 约束）",
        params: [
          { name: "resource_id", type: "string", required: true, desc: "资源 ID" },
          { name: "src", type: "string", required: false, desc: "来源 ID" }
        ],
        returns: { shape: "{url, size_bytes}", note: "直链可被外部网下访问前须经网关 IP 白名单（部署边界）" },
        job: false
      }
    ]},
    { id: "B", label: "写组（job 异步）", tools: [
      {
        id: "kb_ingest", name: "知识入库", direction: "write", sync: false,
        description: "把路径/目录内容写入知识库（分析+同步；幂等指纹链）",
        params: [
          { name: "path", type: "string", required: true, desc: "源内相对路径/根（rw 源）" },
          { name: "source_id", type: "string", required: true, desc: "目标来源（必须 rw）" },
          { name: "deep", type: "boolean", required: false, desc: "条款级分段（来源 deep 开关）" }
        ],
        returns: { shape: "{job_id, status: pending}" },
        job: true, audit: true
      },
      {
        id: "kb_sync_vectors", name: "同步向量", direction: "write", sync: false,
        description: "把 .naskb 描述同步进 PG 多 NAS 向量库（增改删移四操作）",
        params: [
          { name: "root", type: "string", required: true, desc: "源根（rw/ro 均可读）" },
          { name: "nas", type: "string", required: false, desc: "NAS alias（默认配置）" },
          { name: "rebuild", type: "boolean", required: false, desc: "全量重建" }
        ],
        returns: { shape: "{job_id, status: pending}" },
        job: true, audit: true
      },
      {
        id: "kb_index_vectors", name: "本地建索引", direction: "write", sync: false,
        description: "构建本地语义向量索引（bge-small-zh；无 PG 场景）",
        params: [
          { name: "root", type: "string", required: true, desc: "源根" }
        ],
        returns: { shape: "{job_id, status: pending}" },
        job: true, audit: true
      },
      {
        id: "kb_job_status", name: "任务状态", direction: "read", sync: true,
        description: "查询长任务进度/结果",
        params: [
          { name: "job_id", type: "string", required: true, desc: "任务 ID" }
        ],
        returns: { shape: "{id,status,progress,message,result,error}" },
        job: false
      },
      {
        id: "kb_list_jobs", name: "任务列表", direction: "read", sync: true,
        description: "列出近期任务（含失败原因）",
        params: [],
        returns: { shape: "{jobs[{id,kind,status,created_at,error}]}" },
        job: false
      }
    ]},
    { id: "C", label: "整理组（写+审计）", tools: [
      {
        id: "kb_plan_reorganize", name: "生成整理方案", direction: "write", sync: false,
        description: "对 rw 源生成整理方案（只输出不动盘；返回方案 ID 供预览/执行）",
        params: [
          { name: "root", type: "string", required: true, desc: "整理根（rw 源）" }
        ],
        returns: { shape: "{plan_id, status: pending}" },
        job: true, audit: true
      },
      {
        id: "kb_preview_reorganize", name: "预览整理方案", direction: "read", sync: true,
        description: "按 plan_id 查看 moves/驳回清单与冲突预判",
        params: [
          { name: "plan_id", type: "string", required: true, desc: "方案 ID" }
        ],
        returns: { shape: "{plan_name, new_folders[], moves[{from,to,reason}], rejected[], total}" },
        job: false
      },
      {
        id: "kb_apply_reorganize", name: "执行整理", direction: "write", sync: false,
        description: "确认执行方案（三重校验：越界/快照/冲突三档；整仓跟随+级联）",
        params: [
          { name: "plan_id", type: "string", required: true, desc: "方案 ID（快照复检）" }
        ],
        returns: { shape: "{job_id, status: pending}" },
        job: true, audit: true
      }
    ]},
    { id: "D", label: "状态组", tools: [
      {
        id: "kb_status", name: "知识库状态", direction: "read", sync: true,
        description: "整体状态（引擎/索引/PG 可用性/来源数）",
        params: [],
        returns: { shape: "{engine, vector_index, pg, sources}" },
        job: false
      },
      {
        id: "kb_stats", name: "知识库统计", direction: "read", sync: true,
        description: "统计（文档数/条款数/按来源计数）",
        params: [],
        returns: { shape: "{docs, chunks, by_source[]}" },
        job: false
      }
    ]}
  ],

  resources: [
    { uri: "kb://stats", name: "统计资源", desc: "KbStats 同构" },
    { uri: "kb://sources", name: "来源资源", desc: "只读来源清单（脱敏）" },
    { uri: "kb://status/{alias}", name: "来源状态资源", desc: "单来源一致性状态" }
  ],

  prompts: [
    { id: "kb-analyze-prompt", name: "分析提示", desc: "预设：对给定目录执行分析" },
    { id: "kb-search-prompt", name: "检索提示", desc: "预设：检索并总结" },
    { id: "kb-reorganize-prompt", name: "整理提示", desc: "预设：生成并预览整理方案" }
  ],

  design_decisions: [
    { title: "批量 = 多 tool_calls 而非批量参数", detail: "kb_ingest 单路径单职责（铁律 2）；多文件由 Agent 一个回复多个 tool_calls（模型原生能力，部分失败独立回填）" },
    { title: "整理工具与 REST 不重复", detail: "整理属高影响低频动作，MCP 工具语义下探到 C 组（写+审计）" },
    { title: "直链不认证，边界在网关（DD-009）", detail: "kb_fetch_file/kb_get_file_url 直链不带 token；安全边界=外围网关 IP 约束与限流策略（网络/部署层），API 层不认证——与平台『全部需身份』口径的差异是显式决策（内网/受控网段场景），非遗漏" },
    { title: "来源/目录/直链三工具（kb_list_sources/kb_list_tree/kb_get_file_url）接线", detail: "2026-08-24 拍板：对外 Agent 日常定位来源/浏览路径/取直链是高频价值；与 REST 同源（capabilities.py 单一事实源）" }
  ]
};
