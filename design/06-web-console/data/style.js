// 设计风格结论数据文件 — NASKB Web 控制台（依据 naskb/web/public/styles.css）
var PS_DATA = window.PS_DATA = window.PS_DATA || {};
PS_DATA["web-console"] = PS_DATA["web-console"] || {};
PS_DATA["web-console"].style = [
  {
    id: "color",
    title: "配色方案",
    level: 1,
    blocks: [
      { type: "table", headers: ["角色", "色值", "用途"], rows: [
        ["页面背景", "#f5f6f8 (--bg)", "页面背景"],
        ["卡片", "#fff (--card)", "卡片/列表容器"],
        ["分隔线", "#e4e7ec (--line)", "边框/分隔"],
        ["主文本", "#1e2530 (--ink)", "正文/标题"],
        ["副文本", "#697386 (--sub)", "辅助说明/时间/大小"],
        ["强调色", "#2f6fed (--accent)", "主按钮/选中态/引擎徽章"],
        ["强调弱底", "#eef4ff (--accent-weak)", "强调徽章底"],
        ["成功", "#188a52 (--ok) / #e9f7ef (--ok-bg)", "ok 状态/已完成"],
        ["警告", "#b45309 (--warn) / #fff4e6 (--warn-bg)", "待更新/待处理/停用"]
        ,
        ["错误", "#c0392b (--bad) / #fdecea (--bad-bg)", "失败/源已消失/删除"]
      ]}
    ]
  },
  {
    id: "typo",
    title: "字体方案",
    level: 2,
    blocks: [
      { type: "table", headers: ["层级", "字号", "字重", "用途"], rows: [
        ["页面标题（h2）", "1.4rem", "600", "卡片标题"],
        ["正文", "0.95rem", "400", "列表/说明"],
        ["辅助", "0.85rem", "400", "状态/时间/大小"],
        ["徽章", "0.72rem", "500", "分类/状态/引擎"],
        ["等宽代码", "0.8rem", "monospace", "路径/哈希/job_id"]
      ]}
    ]
  },
  {
    id: "icon",
    title: "图标与图片",
    level: 2,
    blocks: [
      { type: "ul", items: [
        "导航/动作使用 Emoji 图标（📚🔍📁🗂️⚙️🧠 等）——零依赖策略",
        "缩略图：44×44 圆角 6px 方图（图片原图 / 视频 ffmpeg 第 4 秒抽帧）",
        "目录图标 📂、文件图标 📄、返回 ↩︎"
      ]}
    ]
  },
  {
    id: "interact",
    title: "交互模式",
    level: 2,
    blocks: [
      { type: "table", headers: ["场景", "反馈"], rows: [
        ["按钮点击", "ghost/small/danger 变体；异步按钮 disabled + “执行中…” 文案"],
        ["列表行点击", "行 hover + cursor:pointer；点击打开模态/进入目录"],
        ["加载态", "hint 文案（加载中…/检索中…/生成中…）"],
        ["空态", "hint 文案（如“尚无来源——请先到来源页注册”）"],
        ["错误态", "error 块（页内红字）或 Toast 2.6s"]
      ]}
    ]
  },
  {
    id: "spacing",
    title: "间距与圆角",
    level: 2,
    blocks: [
      { type: "ul", items: [
        "--radius: 10px（卡片/按钮/输入框统一圆角）",
        "卡片间距：16px；内容内边距 14px",
        "操作按钮组：flex row + gap 4px（small ghost 变体）",
        "模态：遮罩 + 居中卡片（width 720px max）；头部徽章 + 关闭 ✕"
      ]}
    ]
  }
];
