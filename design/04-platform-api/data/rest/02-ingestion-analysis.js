/**
 * REST 领域数据文件 — 采集与分析
 * 说明：本域无独立 REST 端点——任务型动作为来源入口（01 域：scan/analyze/confirm/adopt）
 * 与 MCP 出口（data/ai-tools/tools.js：kb_ingest/kb_sync_vectors/kb_index_vectors）承载。
 * 依 api-design §8 一致性检查：本文件声明 endpoints=[] 并给出驱动映射（免误报 missing_endpoint）。
 */

window.API_DATA = window.API_DATA || {};
window.API_DATA["02-ingestion-analysis"] = {

  domain: "02",
  title: "采集与分析",
  slug: "ingestion-analysis",
  description: "扫描对账/多模态分析/.naskb 双写/导出——任务驱动域（无独立 REST）",
  last_updated: "2026-08-24",
  workflow_ref: "../../02-business-workflow/data/02-ingestion-analysis.js",
  er_ref: "../../03-entity-relationship/data/02-ingestion-analysis.js",

  _permission_lookup: {
    "AnalyzeRun": "运行 AI 分析",
    "FolderDescribe": "目录级描述",
    "ExportClean": "干净导出",
    "TermbaseManage": "术语表管理"
  },

  overview_blocks: [
    { type: "table", headers: ["子域", "驱动入口", "说明"], rows: [
      ["扫描对账", "01 域 POST /api/sources/{sid}/scan", "三级判定、增量幂等"],
      ["AI 分析", "01 域 POST /api/sources/{sid}/analyze|confirm", "多模态富化 + .naskb 双写"],
      ["收编", "01 域 POST /api/sources/{sid}/adopt", "导入源端 .naskb → PG"],
      ["导出/术语表", "MCP：kb_ingest / CLI：export-clean、termbase-add", "REQ-R5-02 / 关键词通道"],
      ["本地索引", "MCP：kb_index_vectors / CLI：index-vectors", "npz 向量索引构建"]
    ]},
    { type: "note", level: "warning", text: "设计决策：不为同一业务动作同时维护 REST 与 MCP 两套端点，避免契约双源（api-design §7 映射唯一性）。" }
  ],

  design_decisions: [
    { title: "任务驱动而非 CRUD REST", detail: "分析管线无用户可见的实体表级 CRUD；入口收敛到来源任务端点 + MCP 工具（四出口同源，ADR-20260816-2）" },
    { title: "导出走 CLI/MCP", detail: "export-clean、termbase-* 为确定性操作，保持 CLI 形态（工具命令）" }
  ],

  endpoints: []
};
