// 示例：多语言方案结论数据文件
// 将本文件复制为 data/i18n.js，修改内容为实际多语言方案
// 覆盖 2.6 多语言方案结论

var PS_DATA = window.PS_DATA = window.PS_DATA || {};
PS_DATA.demo = PS_DATA.demo || {};
PS_DATA.demo.i18n = [
  {
    id: "i18n-scope",
    title: "首版范围与支持语言",
    level: 1,
    blocks: [
      { type: "note", level: "info", text: "首版仅支持简体中文（zh-CN）。以下方案为后续多语言扩展预留。" },
      { type: "table", headers: ["语言", "区域", "优先级"], rows: [
        ["简体中文", "zh-CN", "P0 首版"],
        ["英语", "en", "P1 后续"]
      ]}
    ]
  },
  {
    id: "i18n-struct",
    title: "翻译文件结构",
    level: 2,
    blocks: [
      { type: "p", text: "翻译文件按语言分文件存放，键值按模块/页面/功能点分层。" },
      { type: "ul", items: [
        "i18n/zh-CN.json（默认）",
        "i18n/en.json",
        "i18n/th.json（后续）"
      ]}
    ]
  },
  {
    id: "i18n-ui",
    title: "UI 自适应与语言切换",
    level: 2,
    blocks: [
      { type: "table", headers: ["组件", "最大字符(中/英)", "超长处理"], rows: [
        ["按钮文字", "6/12", "截断+省略号"],
        ["Tab标签", "4/8", "截断"],
        ["列表标题", "20/40", "自动换行"],
        ["卡片摘要", "50/100", "截断+省略号"]
      ]},
      { type: "h3", text: "切换策略" },
      { type: "ul", items: [
        "入口：我的→设置→语言选择",
        "策略：应用内手动切换，不跟随系统",
        "切换后：立即刷新当前页面，不重新加载",
        "缓存：写入 localStorage"
      ]}
    ]
  }
];
