// 示例：业务流程文档数据文件
// 将本文件复制为 data/processes.js，修改内容为实际业务流程
// 覆盖 2.4 功能逻辑设计（完整 sections + blocks + flowchart 格式）
//
// 格式规范：
//   - 顶级为数组格式 [ ... ]，每个元素是一个独立流程
//   - 流程可有两种内容结构：
//     ① 简单结构：blocks[] + flowchart 直接挂载在流程对象上（见本示例）
//     ② 分组结构：sections[] 将 blocks 分组组织，支持多组独立 flowchart
//        (slug, domain, role, description, entry, result, last_updated 等元信息字段可选)
//   - 端标识替换为实际值（customer / fighter / operation 等）

var PS_DATA = window.PS_DATA = window.PS_DATA || {};
PS_DATA['{端标识}'] = PS_DATA['{端标识}'] || {};
PS_DATA['{端标识}'].processes = [
  {
    id: "main-flow",
    title: "主流程",
    level: 1,
    blocks: [
      { type: "p", text: "描述该流程的完整操作序列。从触发到完成，涉及 N 个页面和 M 种分支结果。" },
      { type: "h3", text: "核心步骤" },
      {
        type: "ol", items: [
          "步骤1 → 描述",
          "步骤2 → 描述",
          "步骤3 → 描述"
        ]
      },
      { type: "h3", text: "权限约束" },
      {
        type: "table",
        headers: ["角色", "权限", "引导策略"],
        rows: [
          ["角色A", "权限说明", "引导说明"],
          ["角色B", "权限说明", "引导说明"]
        ]
      },
      { type: "note", level: "info", text: "注意事项说明。" },
      { type: "h3", text: "边界条件" },
      {
        type: "table",
        headers: ["条件", "处理方式"],
        rows: [
          ["条件A", "处理方式A"],
          ["条件B", "处理方式B"]
        ]
      }
    ],
    flowchart: {
      layout: "topdown",
      nodes: [
        { id: "n1",  type: "start",   label: "流程开始" },
        { id: "n2",  type: "action",  label: "操作A" },
        { id: "n3",  type: "decision",label: "判断条件？" },
        { id: "n4",  type: "action",  label: "操作B（通过）" },
        { id: "n5",  type: "action",  label: "操作C（不通过）" },
        { id: "n6",  type: "end",     label: "流程结束" }
      ],
      edges: [
        { from: "n1", to: "n2" },
        { from: "n2", to: "n3" },
        { from: "n3", to: "n4", label: "通过" },
        { from: "n3", to: "n5", label: "不通过" },
        { from: "n4", to: "n6" },
        { from: "n5", to: "n6" }
      ]
    }
  }
];
