// data/loader.js — 项目级数据入口（HTML 只需加载这一个文件）
// 跨项目复用时：复制 workflow-viewer.html，然后修改本文件中的 files 列表即可
(function() {
  var files = [
    // 按领域编号列出所有 .js 数据文件（不含 .js 后缀）：
    "01-source-management",
    "02-ingestion-analysis",
    "03-retrieval-qa",
    "04-deep-analysis",
    "05-knowledge-reorganize",
    "06-platform-console"
  ];
  files.forEach(function(f) {
    document.write('<script src="data/' + f + '.js"><\/script>');
  });
})();
