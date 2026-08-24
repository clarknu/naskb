/**
 * 域注册表 — Domain Registry
 *
 * 定义项目包含的所有业务领域及其标识（slug）。
 * 在初始域范围界定阶段创建初版，随流水线执行持续演进。
 * 参见：docs/development-standard.md §5.3
 * 读写规则：任何流水线步骤执行前先读本文件；改领域边界必须先写本文件再改自身数据。
 * 版本：v1（2026-08-24）
 */
(function () {
  var PS_DATA = window.PS_DATA = window.PS_DATA || {};
  PS_DATA.domainRegistry = {
    identity: {
      project: 'NASKB 知识库系统',
      standard: 'SFDS v3（仲裁版 bundle，.agents/skills/sfds）',
    },
    domains: [
      { id: '01', slug: 'source-management',     name: '来源管理',   description: '知识来源注册与安全边界：local/WebDAV、ro|rw 访问模式、连通测试、启停/删除、扫描/分析/收编任务入口、变更确认清单（/changes + /confirm）、深度分析开关' },
      { id: '02', slug: 'ingestion-analysis',    name: '采集与分析', description: '扫描对账（三级判定 L1 免检→L2 采样 hash→L3 重析、增量幂等）、多模态分析管线（文档/图片/音频/视频/目录/MinerU）、AI 富化（DeepSeek/MiMo 分工）、.naskb 描述仓库维护、干净导出（export-clean）' },
      { id: '03', slug: 'retrieval-qa',          name: '检索问答',   description: '摘要索引检索与 RAG 问答：bge-small 向量（512 维）+ pgvector/HNSW + BM25 降级、双引擎自动选择、带来源问答、术语表、统计与状态口径' },
      { id: '04', slug: 'deep-analysis',         name: '深度分析',   description: '条款级精细分析（REQ-R5-06）：[deep] roots 圈定、MinerU 结构化 md 按标题分段（target/limit/overlap）、条款级向量行（kind=chunk/title + chunk_seq + title_path）、两级引用问答、保真直返与无命中兜底' },
      { id: '05', slug: 'knowledge-reorganize',  name: '知识整理',   description: '目录重组（仅 rw 源）：方案生成（plan_name/rationale/new_folders/moves/rejected/snapshot）、预览确认、apply 三重校验（越界/快照复检/冲突三档 noop|meta_only|rename）、整仓跟随与级联更新' },
      { id: '06', slug: 'platform-console',      name: '平台服务',   description: '平台能力支撑：单管理员 Bearer 认证与匿名只读、进程内任务中心（串行 JobManager）、周期扫描调度、下载代理（Range/ETag/503）、在线预览矩阵（image/pdf/video/audio/text/html/office/parsed）、缩略图、统计/公开配置' },
    ],
  };
})();
