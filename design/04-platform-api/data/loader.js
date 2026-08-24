// data/loader.js — 项目级 API 数据入口（HTML 只需加载这一个文件）
// 约定：rest/ 下领域端点文件 + _conventions.js（公共约定附录）；
//       protocol.js（REST 协议定义）与 ai-tools/*（MCP 工具协议）为协议层资产，
//       由 IMPLEMENTATION-PLAN.md 与对应契约消费方引用（api-viewer 为 REST 领域视图参考实现）。
(function() {
  var files = [
    "rest/01-source-management",
    "rest/02-ingestion-analysis",
    "rest/03-retrieval-qa",
    "rest/04-deep-analysis",
    "rest/05-knowledge-reorganize",
    "rest/06-platform-console",
    "_conventions"
  ];
  files.forEach(function(f) {
    document.write('<script src="data/' + f + '.js"><\/script>');
  });
})();
