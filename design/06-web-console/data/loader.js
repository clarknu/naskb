// data/loader.js — 桌面端设计数据加载器（异步注入 + PSDataReady）
// 说明：design-viewer.html 等待 PSDataReady 事件后渲染（见模板契约）
(function () {
  var files = ["tree", "processes", "style", "i18n"];
  var pending = files.length;
  function ready() {
    document.dispatchEvent(new Event("PSDataReady"));
    window.dispatchEvent(new Event("PSDataReady"));
  }
  files.forEach(function (f) {
    var el = document.createElement("script");
    el.src = "data/" + f + ".js";
    el.onload = function () { if (--pending <= 0) ready(); };
    el.onerror = function () { if (--pending <= 0) ready(); };
    document.head.appendChild(el);
  });
})();
