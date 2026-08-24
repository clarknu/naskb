/**
 * REST 领域数据文件 — 知识整理
 * 说明：本域无独立 REST 端点——整理动作为 CLI（desc plan-reorganize --apply）与
 * MCP 出口（kb_plan_reorganize / kb_preview_reorganize / kb_apply_reorganize）承载。
 * 声明 endpoints=[] 并给出驱动映射（免误报 missing_endpoint）。
 */

window.API_DATA = window.API_DATA || {};
window.API_DATA["05-knowledge-reorganize"] = {

  domain: "05",
  title: "知识整理（重组）",
  slug: "knowledge-reorganize",
  description: "整理方案生成/预览/apply（三重校验/级联）——CLI + MCP 驱动域",
  last_updated: "2026-08-24",
  workflow_ref: "../../02-business-workflow/data/05-knowledge-reorganize.js",
  er_ref: "../../03-entity-relationship/data/05-knowledge-reorganize.js",

  _permission_lookup: {
    "PlanReorganize": "生成整理方案",
    "PlanPreview": "预览整理方案",
    "PlanApply": "执行整理"
  },

  overview_blocks: [
    { type: "table", headers: ["子域", "驱动入口", "说明"], rows: [
      ["生成方案", "CLI desc plan-reorganize <root>", "DeepSeek 全量收集+分片两阶段"],
      ["预览", "MCP kb_preview_reorganize", "moves 清单 + 冲突预判"],
      ["执行", "MCP kb_apply_reorganize / CLI --apply", "三重校验 + 整仓跟随 + 级联"],
      ["存储", "plans/（plan_store）", "plan_id + snapshot 指纹"]
    ]},
    { type: "note", level: "danger", text: "仅 rw 源；apply 前 root 互斥锁；快照不一致 → 拒绝（防 TOCTOU）。" }
  ],

  design_decisions: [
    { title: "整理走 CLI/MCP 而非 REST", detail: "整理为高影响低频动作，需人工确认（预览 + 复校验）；REST 表单/轮询模型不匹配，且与 01 域确认闸门语义重复" }
  ],

  endpoints: []
};
