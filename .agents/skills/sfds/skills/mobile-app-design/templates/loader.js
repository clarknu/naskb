/**
 * loader.js — 统一加载器
 *
 * 定义 PS_DATA 命名空间 + identity 元信息，然后自动加载所有子模块。
 * HTML 只需引用此文件，无需逐个添加子模块的 script 标签。
 *
 * 子模块列表（按加载顺序）：
 *   tree.js       — 2.1~2.3 功能结构树 + 公共页面 + 前端流程
 *   processes.js  — 2.4 业务流程文档（sections + flowchart）
 *   style.js      — 2.5 设计风格结论
 *   i18n.js       — 2.6 多语言方案结论
 */
(function() {
  /* ── 命名空间 + 元信息 ── */
  var PS_DATA = window.PS_DATA = window.PS_DATA || {};
  PS_DATA['{端标识}'] = {
    identity: {
      app_name:    "小程序/App 名称",
      description: "一句话描述覆盖的功能范围",
      version:     "v3（YYYY-MM）",
      design_doc:  "design.md"
    }
  };

  /* ── 子模块清单 ── */
  var files = [
    // 在此处列出所有数据文件名（含 .js 后缀），例如：
    // "tree.js",
    // "processes.js",
    // "style.js",
    // "i18n.js"
  ];

  /* ── 动态加载 ── */
  var base = document.currentScript
    ? document.currentScript.src.replace(/loader\.js$/, '')
    : '';

  var remaining = files.length;

  files.forEach(function(f) {
    var s = document.createElement('script');
    s.async = false;
    s.src = base + f;
    s.onload = s.onerror = function() {
      remaining--;
      if (remaining === 0) {
        document.dispatchEvent(new CustomEvent('PSDataReady'));
      }
    };
    document.body.appendChild(s);
  });
})();
