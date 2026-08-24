// data/loader.js — 项目级 API 数据入口（HTML 只需加载这一个文件）
// 跨项目复用时：复制 api-viewer.html，然后修改本文件的 files 列表
// 每个数据文件把自身挂到 window.API_DATA['{slug}']（领域/REST）或 window.API_DATA['protocol-{id}']（协议）；
// 公共约定挂到 window.API_CONVENTIONS（可选）。
(function() {
  var files = [
    // 按领域编号列出所有 .js 数据文件（不含 .js 后缀），例如：
    // "01-user-auth",
    // "02-schedule",
    // 需要协议文件时同样加入（如 "protocol-mqtt"、"ai-tools/protocol"）
    "rest-domain-template"   // 模板示例（REST 领域数据）
  ];
  files.forEach(function(f) {
    document.write('<script src="data/' + f + '.js"><\/script>');
  });
})();
