// 05 知识整理 —— 业务工作流数据文件
// 依据：design/01-raw-input/05-knowledge-reorganize.md（REQ-R1-14/15）
// 域注册表：05-knowledge-reorganize

window.WF_DATA = window.WF_DATA || {};
window.WF_DATA["05-knowledge-reorganize"] = {
  "domain": "05",
  "title": "知识整理（重组）",
  "slug": "knowledge-reorganize",
  "description": "目录重组（仅 rw 源）：方案生成（两阶段）→ 预览确认 → apply 三重校验 → 整仓跟随与级联更新 → 向量/PG 同步（尽力而为）",
  "last_updated": "2026-08-24",

  // ── 权限控制点（唯一定义源）──
  "permissions": [
    { "id": "PlanReorganize", "name": "生成整理方案", "desc": "允许发起整理方案生成（只输出，不动盘）", "category": "reorganize", "section_refs": ["main-flow"] },
    { "id": "PlanPreview",    "name": "预览整理方案", "desc": "允许查看 moves 清单与冲突预判", "category": "reorganize", "section_refs": ["main-flow"] },
    { "id": "PlanApply",      "name": "执行整理",     "desc": "允许确认执行方案（凭 plan_id 复校验）", "category": "reorganize", "section_refs": ["apply-flow"] }
  ],

  // ── 角色定义 ──
  "roles": [
    { "id": "PlatformAdmin", "name": "平台管理员", "desc": "拥有整理全部权限", "client_group": "Staff",
      "permission_ids": ["PlanReorganize","PlanPreview","PlanApply"] },
    { "id": "MCPAgent", "name": "MCP 消费方 Agent", "desc": "通过 kb_plan_reorganize/kb_preview_reorganize/kb_apply_reorganize 整理知识（写操作受审计）", "client_group": "Agent",
      "permission_ids": ["PlanReorganize","PlanPreview","PlanApply"] }
  ],

  "sections": [
    {
      "id": "overview",
      "title": "业务概述",
      "level": 1,
      "blocks": [
        { "type": "p", "text": "针对 rw 来源的知识整理：AI（DeepSeek）基于当前库结构生成整理方案（新建目录/移动/驳回），用户确认后凭 plan_id 执行。" },
        { "type": "note", "level": "danger", "text": "仅 rw 源可整理（ro 只读源禁止写源端）。执行前 root 互斥锁——整理期间禁止并行整理。" },
        { "type": "note", "level": "warning", "text": "整仓跟随：移动不删除；.naskb（artifacts/folder/meta 随迁，index 保留目标）；源/目标/上层 folder.json 自动级联更新；搬空的源目录自动删除；子路径先移。" }
      ]
    },
    {
      "id": "main-flow",
      "title": "主流程：方案生成 → 预览 → 确认",
      "level": 2,
      "blocks": [
        { "type": "p", "text": "两段式：方案生成（只输出不动）→ 用户确认 → apply 执行（凭 plan_id 复校验，防 TOCTOU）。" }
      ],
      "flowchart": {
        "layout": "topdown",
        "nodes": [
          { "id": "start",  "type": "start",    "label": "流程开始" },
          { "id": "collect","type": "action",   "label": "全量收集 + 分片两阶段\n（AI 方案生成）", "inputs": ["root","site_meta"], "outputs": ["plan_draft"], "consumers": ["snapshot"] },
          { "id": "snapshot","type": "action",   "label": "方案持久化\n（plan_id + snapshot 指纹）", "inputs": ["plan_draft"], "outputs": ["plan_id","snapshot_fp"], "consumers": ["preview"] },
          { "id": "preview", "type": "action",   "label": "预览\n（moves 清单 + 冲突预判）", "inputs": ["plan_id"], "outputs": ["moves","rejected"], "consumers": ["confirm"] },
          { "id": "confirm", "type": "decision", "label": "用户确认执行？" },
          { "id": "end",    "type": "end",      "label": "流程结束（未确认）" },
          { "id": "apply",  "type": "action",   "label": "apply 执行\n（见 apply-flow）", "inputs": ["plan_id","snapshot_fp"], "outputs": ["apply_result"], "consumers": ["end2"] },
          { "id": "end2",   "type": "end",      "label": "流程结束" }
        ],
        "edges": [
          { "from": "start",   "to": "collect" },
          { "from": "collect", "to": "snapshot" },
          { "from": "snapshot","to": "preview" },
          { "from": "preview", "to": "confirm" },
          { "from": "confirm", "to": "apply", "label": "是" },
          { "from": "confirm", "to": "end", "label": "否" },
          { "from": "apply",   "to": "end2" }
        ]
      }
    },
    {
      "id": "apply-flow",
      "title": "子流程：apply 三重校验与级联",
      "level": 3,
      "blocks": [
        { "type": "p", "text": "执行整理时的安全闸门（P0 级）。" }
      ],
      "flowchart": {
        "layout": "leftright",
        "nodes": [
          { "id": "start",  "type": "start",    "label": "apply 开始" },
          { "id": "check1", "type": "action",   "label": "P0-1 越界校验\n（validate_move 路径不出根）" },
          { "id": "check3", "type": "action",   "label": "P0-3 快照复检\n（snapshot 指纹比对）" },
          { "id": "fail",   "type": "action",   "label": "拒绝执行，报告差异" },
          { "id": "move",   "type": "action",   "label": "逐个移动\n（子路径先移、整仓跟随）" },
          { "id": "check2", "type": "decision", "label": "P0-2 目标冲突？" },
          { "id": "noop",   "type": "action",   "label": "noop（跳过）" },
          { "id": "meta",   "type": "action",   "label": "meta_only（仅元数据）" },
          { "id": "rename", "type": "action",   "label": "rename(1) 递增重命名" },
          { "id": "cascade","type": "action",   "label": "级联刷新 folder.json 祖先链\n+ 空目录清理 + 向量/PG 同步", "outputs": ["entry_remap"], "consumers": ["end"] },
          { "id": "end",    "type": "end",      "label": "apply 结束" }
        ],
        "edges": [
          { "from": "start",  "to": "check1" },
          { "from": "check1", "to": "check3" },
          { "from": "check3", "to": "fail", "label": "不一致" },
          { "from": "check3", "to": "move", "label": "一致" },
          { "from": "move",   "to": "check2" },
          { "from": "check2", "to": "noop", "label": "无冲突" },
          { "from": "check2", "to": "meta", "label": "元数据冲突" },
          { "from": "check2", "to": "rename", "label": "命名冲突" },
          { "from": "noop",   "to": "cascade" },
          { "from": "meta",   "to": "cascade" },
          { "from": "rename", "to": "cascade" },
          { "from": "cascade","to": "end" },
          { "from": "fail",   "to": "end" }
        ]
      }
    },
    {
      "id": "rules",
      "title": "业务规则表",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["规则编号", "规则内容", "优先级", "说明"],
          "rows": [
            ["R001", "只有 rw 来源可整理", "高", "ro 禁写"],
            ["R002", "plan_id 快照复检；快照变化 → 拒绝执行", "高", "防 TOCTOU"],
            ["R003", "冲突三档：noop | meta_only | rename(1) 递增", "高", "P0-2"],
            ["R004", "整理后同步为尽力而为：remap_paths + PG 增量（失败记录不阻断）", "中", "PG 保留 resource_id"],
            ["R005", "root 互斥锁：整理期间禁止并行整理", "高", "并发"]
          ]
        }
      ]
    },
    {
      "id": "permissions-table",
      "title": "权限清单",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["权限点", "说明", "功能组"],
          "rows": [
            ["PlanReorganize", "生成整理方案", "知识整理"],
            ["PlanPreview", "预览整理方案", "知识整理"],
            ["PlanApply", "执行整理", "知识整理"]
          ]
        }
      ]
    }
  ]
};
