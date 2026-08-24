// 多语言方案结论数据文件 — NASKB Web 控制台
// 现状：单语（zh-CN 直写模板）；本文件定义多语言扩展方案 + i18n key 结构（原则七文本精确化的键位约定）
var PS_DATA = window.PS_DATA = window.PS_DATA || {};
PS_DATA["web-console"] = PS_DATA["web-console"] || {};
PS_DATA["web-console"].i18n = [
  {
    id: "i18n-scope",
    title: "首版范围与支持语言",
    level: 1,
    blocks: [
      { type: "note", level: "info", text: "首版仅简体中文（zh-CN，模板直写）；extract 后键位按 naskb.{page}.{elem} 组织（见 i18n-struct）。" },
      { type: "table", headers: ["语言", "区域", "优先级"], rows: [
        ["简体中文", "zh-CN", "P0 首版（直写模板）"],
        ["英语", "en", "P1（提取键位后）"]
      ]}
    ]
  },
  {
    id: "i18n-struct",
    title: "键位结构（与路由/页面严格对应）",
    level: 2,
    blocks: [
      { type: "ul", items: [
        "naskb.search.q_placeholder / btn / err / hit_open",
        "naskb.ask.q_placeholder / btn / err / answer_label",
        "naskb.browse.source_placeholder / refresh / crumbs / dir_enter / file_open / thumb",
        "naskb.sources.alias_placeholder / protocol_placeholder / mode_placeholder / add_btn / add_ok / add_fail / cancel / test / scan / scan_ok / analyze / analyze_ok / changes / confirm_btn / confirm_ok / deep_toggle / deep_confirm / adopt / toggle / delete / delete_confirm / changes_list / alias_required",
        "naskb.jobs.status",
        "naskb.modal.meta_title / preview_title / download / close"
      ]},
      { type: "p", text: "键名与路由/组件层级严格对应（路由 web-console 无子路由页，故前缀到页面即可）。" }
    ]
  },
  {
    id: "i18n-ui",
    title: "UI 自适应与语言切换",
    level: 2,
    blocks: [
      { type: "table", headers: ["组件", "最大字符(中/英)", "超长处理"], rows: [
        ["按钮文字", "6/12", "截断+省略号"],
        ["导航标签", "4/8", "截断"],
        ["列表路径", "—", "自动换行（word-break:break-all）"],
        ["卡片摘要", "140/280", "slice(0,140) 截断"]
      ]},
      { type: "h3", text: "切换策略" },
      { type: "ul", items: [
        "现状无切换入口（单语直写）；P1 引入 i18n 库 + localStorage 语言键",
        "切换后立即刷新当前页面，不重新加载"
      ]}
    ]
  }
];
