// 示例：设计风格结论数据文件
// 将本文件复制为 data/style.js，修改内容为实际设计风格决策
// 覆盖 2.5 设计风格结论

var PS_DATA = window.PS_DATA = window.PS_DATA || {};
PS_DATA.demo = PS_DATA.demo || {};
PS_DATA.demo.style = [
  {
    id: "color",
    title: "配色方案",
    level: 1,
    blocks: [
      { type: "table", headers: ["角色", "色值", "用途"], rows: [
        ["主色", "#E61E2A", "主要按钮/价格强调/Tab选中态"],
        ["辅助色", "#1A1A2E", "顶部栏背景/大标题"],
        ["成功", "#10B981", "支付成功/已核销"],
        ["警告", "#F59E0B", "待处理/库存紧张"],
        ["错误", "#EF4444", "支付失败/已退款"],
        ["背景", "#F5F5F5", "页面背景"],
        ["卡片背景", "#FFFFFF", "卡片/列表项"],
        ["主文本", "#1F2937", "正文"],
        ["副文本", "#6B7280", "辅助说明"]
      ]}
    ]
  },
  {
    id: "typo",
    title: "字体方案",
    level: 2,
    blocks: [
      { type: "table", headers: ["层级", "字号", "字重", "行高", "用途"], rows: [
        ["H1", "20px", "Bold", "28px", "页面大标题"],
        ["H2", "17px", "Semibold", "24px", "功能区标题"],
        ["正文", "15px", "Regular", "22px", "列表/说明"],
        ["辅助", "13px", "Regular", "18px", "时间/状态"],
        ["标签", "11px", "Medium", "16px", "角标/徽章"]
      ]}
    ]
  },
  {
    id: "icon",
    title: "图标与图片",
    level: 2,
    blocks: [
      { type: "ul", items: [
        "图标风格：线框（stroke-width:1.5px），圆角端头",
        "列表图：16:9 比例",
        "头像：1:1 方形，圆角 8px",
        "占位图：灰色渐变+类型图标"
      ]}
    ]
  },
  {
    id: "interact",
    title: "交互模式",
    level: 2,
    blocks: [
      { type: "table", headers: ["场景", "反馈"], rows: [
        ["按钮点击", "缩放 0.96 回弹 + 背景加深"],
        ["列表点击", "背景变灰 200ms"],
        ["加载态", "内容页骨架屏/操作页菊花+文字"],
        ["空态", "插画+文字+推荐操作入口"],
        ["错误态", "Toast 2s 或页面级错误+重试"]
      ]}
    ]
  },
  {
    id: "spacing",
    title: "间距",
    level: 2,
    blocks: [
      { type: "ul", items: [
        "页边距：左右 16px，上下 12px",
        "卡片间距：垂直 12px",
        "功能区间距：24px",
        "圆角：按钮 8px/卡片 12px/浮窗 16px(顶)0(底)"
      ]}
    ]
  }
];
