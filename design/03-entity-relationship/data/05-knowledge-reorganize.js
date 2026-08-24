// 05 知识整理 —— 单域 ER 数据文件
// 依据：plan_store.py（PlanRecord DDL）事实基线
// 域注册表：05-knowledge-reorganize

window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["05-knowledge-reorganize"] = {
  "domain":      "05",
  "title":       "知识整理（重组）",
  "slug":        "knowledge-reorganize",
  "description": "整理方案的状态与存储：方案生成（plan/snapshot）→ 确认 → apply 执行；冲突三档与快照复检的领域模型。",

  "enums": [
    { "id": "PlanStatus", "name": "方案状态", "description": "整理方案生命周期",
      "values": [
        { "code": "pending", "zh": "待执行", "desc": "已生成待确认" },
        { "code": "applied", "zh": "已执行", "desc": "apply 完成" },
        { "code": "expired", "zh": "已过期", "desc": "快照不匹配/被替代" }
      ] },
    { "id": "ConflictResolution", "name": "冲突解决档", "description": "P0-2 目标冲突三档",
      "values": [
        { "code": "noop", "zh": "跳过", "desc": "目标一致不动" },
        { "code": "meta_only", "zh": "仅元数据", "desc": "只更新描述不动文件" },
        { "code": "rename", "zh": "递增重命名", "desc": "rename(1) 递增避冲突" }
      ] }
  ],

  "entities": [
    {
      "id": "plan_record",
      "name": "整理方案",
      "table": "plans（工作区 plans/）",
      "description": "方案持久化（plan_id + snapshot 指纹；原子写 tmp+os.replace）",
      "fields": [
        {"name": "plan_id", "type": "text", "pk": true, "nn": true, "desc": "方案 ID"},
        {"name": "root", "type": "text", "pk": false, "nn": true, "desc": "整理根目录"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"},
        {"name": "status", "type": "PlanStatus", "pk": false, "nn": true, "default": "pending", "desc": "状态"},
        {"name": "plan", "type": "json", "pk": false, "nn": false, "desc": "方案体（plan_name/rationale/new_folders/moves/rejected/total）"},
        {"name": "snapshot", "type": "json", "pk": false, "nn": false, "desc": "快照指纹 {规范化源路径: file_hash}（P0-3 复检）"},
        {"name": "applied_at", "type": "datetime", "pk": false, "nn": false, "desc": "执行时间"},
        {"name": "result", "type": "json", "pk": false, "nn": false, "desc": "执行结果"},
        {"name": "audit", "type": "json", "pk": false, "nn": false, "desc": "审计记录"},
        {"name": "meta", "type": "json", "pk": false, "nn": false, "desc": "扩展元数据"}
      ]
    }
  ],

  "value_objects": [
    {
      "id": "move_op",
      "name": "移动操作（VO）",
      "type": "vo",
      "description": "方案中的单条移动",
      "fields": [
        {"name": "from", "type": "text", "pk": false, "nn": true, "desc": "源路径"},
        {"name": "to", "type": "text", "pk": false, "nn": false, "desc": "目标路径"},
        {"name": "reason", "type": "text", "pk": false, "nn": false, "desc": "AI 理由"},
        {"name": "conflict", "type": "ConflictResolution", "pk": false, "nn": false, "desc": "执行时冲突判定"}
      ]
    },
    {
      "id": "snapshot_fp",
      "name": "快照指纹（VO）",
      "type": "vo",
      "description": "P0-3 复检输入：{规范化源路径: file_hash}",
      "fields": [
        {"name": "norm_path", "type": "text", "pk": false, "nn": true, "desc": "规范化路径"},
        {"name": "file_hash", "type": "text", "pk": false, "nn": true, "desc": "生成时指纹"}
      ]
    }
  ],

  "services": [
    { "id": "reorganizer", "name": "整理编排器",
      "description": "生成/预览/apply/级联/同步（reorganizer.py）",
      "methods": [
        {"name": "generate_plan", "sig": "(root) → Plan", "desc": "全量收集 + 分片两阶段"},
        {"name": "save_plan", "sig": "(plan) → plan_id", "desc": "持久化 + snapshot"},
        {"name": "preview", "sig": "(plan_id) → {moves, rejected}", "desc": "预览"},
        {"name": "apply_with_housekeeping", "sig": "(plan_id) → result", "desc": "三重校验 + 级联（root 互斥锁）"},
        {"name": "sync_after_apply", "sig": "(root) → report", "desc": "remap_paths + PG 增量（尽力而为）"}
      ] },
    { "id": "root_lock", "name": "root 互斥锁",
      "description": "plans/root-<sha1(root)[:12]>.lock（O_EXCL + pid/时间戳，STALE_AFTER=3600s 可接管）",
      "methods": [
        {"name": "acquire", "sig": "(root) → lock", "desc": "占用"},
        {"name": "release", "sig": "(lock)", "desc": "释放"},
        {"name": "steal_stale", "sig": "(lock) → bool", "desc": "过期接管"}
      ] }
  ],

  "relations": []
};
