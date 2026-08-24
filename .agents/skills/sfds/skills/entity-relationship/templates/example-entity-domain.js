// 示例：单域 ER 数据文件
// 将本文件复制为 data/XX-your-domain-slug.js，修改 key 和内容
// key 必须匹配文件名（不含 .js）

window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["XX-your-domain-slug"] = {
  "domain":      "XX",                    // 领域编号，如 "01", "02"
  "title":       "领域中文名称",           // 显示在页面标题
  "slug":        "your-domain-slug",       // URL slug，kebab-case
  "description": "领域描述，简短说明本领域的核心职责和覆盖范围。",
  "entities": [
    // ═══════════ 实体 1 ═══════════
    {
      "id": "entity_one",
      "name": "实体一",
      "table": "entity_ones",
      "description": "实体一的说明",
      "fields": [
        {"name": "id", "type": "UUID", "pk": true, "nn": true, "desc": "主键", "comment": "系统自增主键，创建后不可变"},
        {"name": "name", "type": "varchar(128)", "pk": false, "nn": true, "desc": "名称", "comment": "对外展示名称，必填"},
        {"name": "status", "type": "enum(draft,published,cancelled)", "pk": false, "nn": true, "default": "draft", "desc": "状态", "comment": "Draft=草稿(可编辑)→Published=已发布→Cancelled=已取消(终态)"},
        {"name": "sort_order", "type": "integer", "pk": false, "nn": false, "desc": "排序"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"}
      ],
      "indexes": [
        {"fields": ["status"]}
      ]
    },
    // ═══════════ 实体 2 ═══════════
    {
      "id": "entity_two",
      "name": "实体二",
      "table": "entity_twos",
      "description": "实体二的说明",
      "fields": [
        {"name": "id", "type": "UUID", "pk": true, "nn": true, "desc": "主键"},
        {"name": "entity_one_id", "type": "UUID", "pk": false, "nn": true, "fk": "entity_one.id", "desc": "关联实体一"},
        {"name": "code", "type": "varchar(32)", "pk": false, "nn": true, "uq": true, "desc": "唯一编码"},
        {"name": "value_cents", "type": "integer", "pk": false, "nn": true, "desc": "数值（分）"},
        {"name": "description", "type": "text", "pk": false, "nn": false, "desc": "备注"},
        {"name": "start_at", "type": "datetime", "pk": false, "nn": false, "desc": "开始时间"},
        {"name": "end_at", "type": "datetime", "pk": false, "nn": false, "desc": "结束时间"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"}
      ]
    },
    // ═══════════ 实体 N ═══════════
    {
      "id": "entity_three",
      "name": "实体三",
      "table": "entity_threes",
      "description": "实体三的说明，跨域引用示例",
      "fields": [
        {"name": "id", "type": "UUID", "pk": true, "nn": true, "desc": "主键"},
        {"name": "entity_one_id", "type": "UUID", "pk": false, "nn": true, "fk": "entity_one.id", "desc": "关联实体一"},
        {"name": "ref_user_id", "type": "UUID", "pk": false, "nn": true, "desc": "跨域引用用户（无 fk，仅存储 ID）"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"}
      ]
    }
  ],
  "relations": [
    // 域内关系
    {"from": "entity_two.entity_one_id", "to": "entity_one.id", "type": "N:1", "desc": "实体二归属实体一"},
    {"from": "entity_three.entity_one_id", "to": "entity_one.id", "type": "N:1", "desc": "实体三关联实体一"},
    // 跨域关系（渲染为橙色虚线 + ghost 节点）
    {"from": "entity_three.ref_user_id", "to": "customer_user.id", "type": "N:1", "desc": "实体三引用观众用户", "cross_domain": "01"}
  ]
};
