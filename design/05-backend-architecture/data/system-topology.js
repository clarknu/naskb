/**
 * 系统拓扑 — System Topology
 * NASKB v0.1 平台版：复杂度判定 L3（模块化单体）
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["system-topology"] = (function () {

  var _trace = {
    consumes: ["workflow:01-source-management,02-ingestion-analysis,03-retrieval-qa,04-deep-analysis,05-knowledge-reorganize,06-platform-console",
               "er:01-source-management,02-ingestion-analysis,03-retrieval-qa,04-deep-analysis,05-knowledge-reorganize,06-platform-console",
               "api:rest/01..06, ai-tools"],
    produces: ["constraint:topology", "constraint:module-boundary", "constraint:layering",
               "constraint:caching", "constraint:resilience", "constraint:data-consistency",
               "constraint:observability", "constraint:security"]
  };

  return {
    _trace: _trace,
    complexityLevel: "L3",
    complexityRationale: "外部 LLM 依赖（DeepSeek/MiMo/MinerU，Q10）+ 异步任务与调度（Q11）+ 6 业务域（Q13）；无水平扩展/灰度/多租户（Q4/Q5/Q7/Q8 否），不达 L4",
    complexityQuestionnaire: {
      Q1_peakQps:         { answer: "no",  value: "<10",    note: "个人/家庭 NAS 场景" },
      Q2_dataVolume:      { answer: "no",  value: "万级",   note: "PG 主库万行级" },
      Q3_concurrentUsers: { answer: "no",  value: "<5",     note: "单管理员+匿名只读" },
      Q4_horizontalScale: { answer: "no",  value: "",       note: "" },
      Q5_multiService:    { answer: "no",  value: "",       note: "单进程服务" },
      Q6_strongConsist:   { answer: "no",  value: "",       note: "无支付/库存强一致" },
      Q7_grayRelease:     { answer: "no",  value: "",       note: "" },
      Q8_multiTenant:     { answer: "no",  value: "",       note: "单管理员" },
      Q9_compliance:      { answer: "no",  value: "",       note: "非金融级合规；开源纪律 REQ-R6-07" },
      Q10_externalDeps:   { answer: "yes", value: "DeepSeek/MiMo/MinerU/PG/WebDAV", note: "外部 AI 依赖为核心特征" },
      Q11_asyncTasks:     { answer: "yes", value: "JobManager+ScanScheduler", note: "扫描/分析/整理异步化" },
      Q12_stateMachines:  { answer: "yes", value: "3",      note: "来源 enabled/deep；资源状态机；整理方案状态机" },
      Q13_domainCount:    { answer: "yes", value: "6",      note: "六业务域（domain-registry）" },
      Q14_roleCount:      { answer: "no",  value: "3",      note: "Admin/AnonymousReader/MCPAgent（单管理员模式）" }
    },
    architectureStyle: {
      primary: "modular-monolith",
      rationale: ["单人维护的单进程服务（FastAPI + 进程内 JobManager + daemon 调度线程）",
                  "模块边界清晰（common 子包按域切片），跨模块只经服务接口",
                  "异步解耦=任务队列语义（无独立消息中间件，L3 事件契约以 Job 语义承担，见 event-contracts）"]
    },
    techStack: {
      runtime:   "Python 3.10+",
      framework: "FastAPI + Uvicorn（create_app 工厂 + run）",
      orm:       "psycopg 3 裸 SQL + pgvector（无 ORM；DDL 常量于 common/pgstore.py）",
      frontend:  "Vue3 静态包（无构建，naskb/web/public）",
      ai:        "DeepSeek（文本并发 4-6）/ MiMo（视觉/音频串行）/ MinerU（OCR 串行，独立 venv）"
    },
    domainCount: 6,
    totalEntities: 11,
    totalFlowcharts: 9
  };
})();
