// 示例域数据文件 — 参考此格式创建各领域的业务工作流
// 文件名格式：XX-slug.js（如 01-user-auth.js）
// 每个域一个文件，通过 loader.js 统一加载

window.WF_DATA = window.WF_DATA || {};
window.WF_DATA["example-domain"] = {
  "domain": "01",
  "title": "示例领域",
  "slug": "example-domain",
  "description": "领域的简要描述",
  "last_updated": "2026-06-14",

  // ── 权限控制点（可选但推荐） ──
  // 从本域的业务 action 节点提取的可独立授权控制的功能点。
  // 供 API 设计（端点→权限映射）和页面设计（组件→权限映射）阶段引用。
  // section 中应有一个对应的权限清单 table 供人阅读；此数组是等价的机器可读格式。
  "permissions": [
    {
      "id": "ExampleView",
      "name": "查看示例",
      "desc": "允许查看示例数据列表和详情",
      "category": "example_management",
      "section_refs": ["overview"]
    },
    {
      "id": "ExampleEdit",
      "name": "编辑示例",
      "desc": "允许创建和修改示例数据",
      "category": "example_management",
      "section_refs": ["main-flow"]
    },
    {
      "id": "ExampleDelete",
      "name": "删除示例",
      "desc": "允许删除示例数据",
      "category": "example_management",
      "section_refs": ["main-flow"]
    }
  ],

  // ── 角色定义（可选但推荐） ──
  // 基于流程中的参与者角色，定义每个角色聚合的权限点。
  // permission_ids 引用上面 permissions 数组中的 id。
  // 与 permissions 一起形成完整的 RBAC 授权规范。
  "roles": [
    {
      "id": "ExampleViewer",
      "name": "示例查看者",
      "desc": "只能浏览示例数据，不可修改",
      "client_group": "Customer",
      "permission_ids": ["ExampleView"]
    },
    {
      "id": "ExampleEditor",
      "name": "示例编辑者",
      "desc": "可以创建和修改示例数据",
      "client_group": "Staff",
      "permission_ids": ["ExampleView", "ExampleEdit"]
    },
    {
      "id": "ExampleAdmin",
      "name": "示例管理员",
      "desc": "拥有示例数据的完全管理权限",
      "client_group": "Staff",
      "permission_ids": ["ExampleView", "ExampleEdit", "ExampleDelete"]
    }
  ],

  "sections": [
    {
      "id": "overview",
      "title": "业务概述",
      "level": 1,
      "blocks": [
        { "type": "p", "text": "描述该领域的业务背景和目标。" },
        { "type": "note", "level": "info", "text": "这是一个信息提示框。level 可选 info/warning/danger。" },
        { "type": "h3", "text": "核心业务规则" },
        { "type": "ul", "items": [
          "规则1：说明第一条核心规则",
          "规则2：说明第二条核心规则",
          "规则3：说明第三条核心规则"
        ]}
      ]
    },
    {
      "id": "main-flow",
      "title": "主流程",
      "level": 2,
      "blocks": [
        { "type": "p", "text": "以下展示该领域的核心业务流程。" }
      ],
      "flowchart": {
        "layout": "topdown",
        "nodes": [
          { "id": "start",      "type": "start",    "label": "流程开始" },
          { "id": "step1",      "type": "action",   "label": "执行操作A" },
          { "id": "check",      "type": "decision", "label": "是否满足条件?" },
          { "id": "step2_yes",  "type": "action",   "label": "执行操作B\n（条件满足分支）" },
          { "id": "step2_no",   "type": "action",   "label": "执行操作C\n（条件不满足分支）" },
          { "id": "end",        "type": "end",      "label": "流程结束" }
        ],
        "edges": [
          { "from": "start",     "to": "step1" },
          { "from": "step1",     "to": "check" },
          { "from": "check",     "to": "step2_yes", "label": "是" },
          { "from": "check",     "to": "step2_no",  "label": "否" },
          { "from": "step2_yes", "to": "end" },
          { "from": "step2_no",  "to": "end" }
        ]
      }
    },
    {
      "id": "rules-table",
      "title": "业务规则表",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["规则编号", "规则内容", "优先级", "说明"],
          "rows": [
            ["R001", "规则内容示例", "高", "说明文字"],
            ["R002", "另一条规则", "中", "说明文字"],
            ["R003", "第三条规则", "低", "说明文字"]
          ]
        }
      ]
    }
  ]
};
