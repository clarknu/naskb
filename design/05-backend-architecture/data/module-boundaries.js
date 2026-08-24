/**
 * 模块边界 — Module Boundaries
 * 分域 = 域注册表 6 域 + 协议层（api/mcp/cli）+ 平台核心 + 数据访问 + fs 扩展
 * 跨模块调用白名单 = 存量实现基线（探针事实反推：scripts/probes/probe_naskb.py）；
 * 机械校验零误报的前提是白名单与事实一致——新增跨组访问必须先改本文件（review 检查）。
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["module-boundaries"] = {
  modules: {
    "source-management": {
      name: "来源管理域", description: "来源注册/测试/启停/删除/变更确认",
      ownsEntities: ["sources"],
      applicationService: { SourceRegistry: { methods: ["list()","register(dto)","update(sid, patch)","delete(sid)","test(sid)","list_changes(sid)","confirm(sid, rel_paths)"] } },
      events: { publishes: [], subscribes: [] },
      crossModuleCalls: [
        { target: "data-access", via: "pgstore", reason: "sources 表持久化（存量基线）" },
        { target: "fs-ext", via: "fs.local/webdav", reason: "源访问适配（存量基线）" }
      ],
      databaseOwnership: "public.sources", independentDeployable: false
    },
    "ingestion": {
      name: "采集分析域", description: "扫描对账/多模态分析/.naskb 双写/收编/导出",
      ownsEntities: ["resources", "folders"],
      applicationService: { DescStore: { methods: ["set_entry","move_entry","remove_entry","check"] }, Batch: { methods: ["analyze_path","analyze_tree"] } },
      events: { publishes: [{ event: "JobCompleted", fields: "job_id, kind, result", desc: "作业完成信号（JobManager 语义）" }], subscribes: [] },
      crossModuleCalls: [
        { target: "data-access", via: "pgstore", reason: "resources/folders 持久化（存量基线）" },
        { target: "fs-ext", via: "fs.base", reason: "源文件读取与采样（存量基线）" },
        { target: "platform-core", via: "llm/embeddings", reason: "DeepSeek/MiMo/嵌入调用（存量基线）" },
        { target: "retrieval", via: "retrieval.collect_docs", reason: "Doc 收集（存量基线）" },
        { target: "source-management", via: "source_registry", reason: "来源上下文（存量基线）" }
      ],
      databaseOwnership: "{schema}.resources/{schema}.folders", independentDeployable: false
    },
    "retrieval": {
      name: "检索问答域", description: "向量库/术语表/检索问答/统计",
      ownsEntities: ["vectors", "termbase"],
      applicationService: { Retrieval: { methods: ["search(query, top_k, nas)","ask(question, top_k)"] } },
      events: { publishes: [], subscribes: [] },
      crossModuleCalls: [
        { target: "data-access", via: "pgstore", reason: "向量/术语表持久化（存量基线）" },
        { target: "ingestion", via: "desc_store", reason: "索引输入采集（存量基线）" }
      ],
      databaseOwnership: "{schema}.vectors/{schema}.termbase", independentDeployable: false
    },
    "deep": {
      name: "深度分析域", description: "条款级分段/深析基准/深析评估",
      ownsEntities: [],
      applicationService: { MdChunker: { methods: ["split(md, params) -> Chunk[]"] } },
      events: { publishes: [], subscribes: [] },
      crossModuleCalls: [
        { target: "platform-core", via: "llm/serve", reason: "深析问答/基准（存量基线）" },
        { target: "retrieval", via: "retrieval/embeddings", reason: "条款级召回（存量基线）" }
      ],
      databaseOwnership: "{schema}.vectors（level=chunk 行）", independentDeployable: false
    },
    "reorganize": {
      name: "知识整理域", description: "整理方案/快照/apply/级联",
      ownsEntities: [],
      applicationService: { Reorganizer: { methods: ["generate_plan","save_plan","preview","apply_with_housekeeping"] } },
      events: { publishes: [], subscribes: [] },
      crossModuleCalls: [
        { target: "data-access", via: "pgstore.sync_vectors", reason: "整理后同步（存量基线）" },
        { target: "fs-ext", via: "fs.base", reason: "移动执行（存量基线）" },
        { target: "ingestion", via: "desc_store.move_entry", reason: "整仓跟随（存量基线）" },
        { target: "retrieval", via: "vector_index.remap_paths", reason: "路径重映射（存量基线）" }
      ],
      databaseOwnership: "plans/（工作区文件）", independentDeployable: false
    },
    "data-access": {
      name: "数据访问域", description: "PG 主库访问与多 NAS schema（仅此模块可直写 SQL）",
      ownsEntities: ["nas_registry", "resources", "vectors", "folders", "termbase"],
      applicationService: { PgStore: { methods: ["ensure_schema","sync_vectors","sync_chunks","search","stats","rebind"] } },
      events: { publishes: [], subscribes: [] },
      crossModuleCalls: [
        { target: "deep", via: "chunker", reason: "条款级分段（存量基线）" },
        { target: "ingestion", via: "hashing/exts", reason: "指纹与类型判定（存量基线）" },
        { target: "retrieval", via: "embeddings/retrieval", reason: "嵌入与检索上下文（存量基线）" }
      ],
      databaseOwnership: "public + 每 NAS {schema}", independentDeployable: false
    },
    "platform-core": {
      name: "平台核心域", description: "服务/任务/调度/配置/LLM 客户端/能力清单",
      ownsEntities: [],
      applicationService: { JobManager: { methods: ["submit","get","list"] }, ScanScheduler: { methods: ["tick"] } },
      events: { publishes: [{ event: "JobSubmitted", fields: "job_id, kind", desc: "任务入队信号" }], subscribes: [] },
      crossModuleCalls: [
        { target: "retrieval", via: "retrieval.search/ask", reason: "serve 与问答（存量基线）" }
      ],
      databaseOwnership: "无（任务=内存队列）", independentDeployable: false
    },
    "fs-ext": {
      name: "文件系统扩展域", description: "fs 抽象（base/local/webdav）",
      ownsEntities: [],
      applicationService: { FsAdapter: { methods: ["create","scan","stat","sample","stream"] } },
      events: { publishes: [], subscribes: [] },
      crossModuleCalls: [],
      databaseOwnership: "无", independentDeployable: false
    },
    "api-layer": {
      name: "HTTP 接口层", description: "server.app 工厂 + 路由 + 认证 + 下载/预览 + 调度线程",
      ownsEntities: [],
      applicationService: { AuthPolicy: { methods: ["authorize","public_config"] } },
      events: { publishes: [], subscribes: [] },
      crossModuleCalls: [
        { target: "source-management", via: "SourceRegistry", reason: "来源端点（存量基线）" },
        { target: "retrieval", via: "Retrieval", reason: "检索/问答端点（存量基线）" },
        { target: "data-access", via: "PgStore", reason: "统计/rebind（存量基线）" },
        { target: "platform-core", via: "JobManager", reason: "任务中心（存量基线）" },
        { target: "ingestion", via: "inventory/analyzer/batch", reason: "扫描/分析入口（存量基线）" },
        { target: "fs-ext", via: "fs.base", reason: "下载/预览源读取（存量基线）" }
      ],
      databaseOwnership: "无", independentDeployable: false
    },
    "mcp-layer": {
      name: "MCP 层", description: "mcp.server（14 工具 + Resources/Prompts + 审计）",
      ownsEntities: [],
      applicationService: { McpServer: { methods: ["list_tools","call(tool, args)"] } },
      events: { publishes: [], subscribes: [] },
      crossModuleCalls: [
        { target: "source-management", via: "SourceRegistry", reason: "来源上下文（存量基线）" },
        { target: "retrieval", via: "Retrieval", reason: "kb_search/kb_ask（存量基线）" },
        { target: "ingestion", via: "Batch", reason: "kb_ingest/kb_sync_vectors（存量基线）" },
        { target: "reorganize", via: "Reorganizer", reason: "kb_plan_*/apply（存量基线）" },
        { target: "platform-core", via: "JobManager", reason: "kb_job_status（存量基线）" },
        { target: "data-access", via: "PgStore", reason: "kb_status/kb_stats（存量基线）" },
        { target: "fs-ext", via: "fs.base", reason: "kb_fetch_file（存量基线）" }
      ],
      databaseOwnership: "无", independentDeployable: false
    },
    "cli-layer": {
      name: "CLI 层", description: "desc 命令组（28 命令）与 serve*/serve-platform 入口",
      ownsEntities: [],
      applicationService: { Cli: { methods: ["main(ctx)","dispatch(command, args)"] } },
      events: { publishes: [], subscribes: [] },
      crossModuleCalls: [
        { target: "api-layer", via: "server.app", reason: "serve-platform 组装（存量基线）" },
        { target: "mcp-layer", via: "mcp.server", reason: "serve-mcp 组装（存量基线）" },
        { target: "source-management", via: "SourceRegistry", reason: "来源命令（存量基线）" },
        { target: "retrieval", via: "Retrieval", reason: "检索/问答命令（存量基线）" },
        { target: "data-access", via: "PgStore", reason: "同步/状态命令（存量基线）" },
        { target: "deep", via: "chunker/deep_bench", reason: "深析命令（存量基线）" },
        { target: "fs-ext", via: "fs.base", reason: "目录命令（存量基线）" },
        { target: "ingestion", via: "Batch", reason: "分析命令（存量基线）" },
        { target: "platform-core", via: "serve/jobs/config", reason: "serve/配置命令（存量基线）" },
        { target: "reorganize", via: "Reorganizer", reason: "整理命令（存量基线）" }
      ],
      databaseOwnership: "无", independentDeployable: false
    }
  }
};
