// data/loader.js — 项目级 ER 数据入口（HTML 只需加载这一个文件）
// 跨项目复用时：复制 er-viewer.html，然后修改本文件的 files 列表
(function() {
  var files = [
    // 按领域编号列出所有 .js 数据文件（不含 .js 后缀），最后加上 core-er，例如：
    // "01-user-auth",
    // "02-schedule",
    // "core-er"
  ];
  files.forEach(function(f) {
    document.write('<script src="data/' + f + '.js"><\/script>');
  });
})();
