/**
 * 后端架构设计 — 数据加载器
 * 
 * 加载所有架构数据 JS 文件，挂载到 window.ARCH_DATA
 * 由 architecture-viewer.html 读取渲染
 */
(function () {
  var PS_DATA = window.PS_DATA = window.PS_DATA || {};
  var ARCH_DATA = window.ARCH_DATA = window.ARCH_DATA || {};

  var files = [
    "system-topology",
    "module-boundaries",
    "layering-strategy",
    "event-contracts",
    "caching-strategy",
    "resilience-policy",
    "data-consistency",
    "observability-policy",
    "security-policy"
  ];

  files.forEach(function (name) {
    var el = document.createElement("script");
    el.src = "data/" + name + ".js";
    document.head.appendChild(el);
  });
})();
