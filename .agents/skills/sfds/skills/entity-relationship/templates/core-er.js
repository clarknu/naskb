// data/core-er.js — 跨域关系总纲
// 定义所有域和跨域关系全集
// er-viewer.html?domain=all 全景图依赖此文件

window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["core-er"] = {
  "domains": [
    // 列出所有域。domain 编号必须与 data/XX-slug.js 文件名中的编号一致
    { "domain": "01", "title": "第一个域",     "slug": "first-domain",  "description": "域说明", "color": "#2563eb" },
    { "domain": "02", "title": "第二个域",     "slug": "second-domain", "description": "域说明", "color": "#059669" },
    { "domain": "03", "title": "第三个域",     "slug": "third-domain",  "description": "域说明", "color": "#7c3aed" }
  ],
  "core_relations": [
    // 跨域关系全集。domains: [源域编号, 目标域编号]
    // 按约定，跨域关系在两个域的各自 data/ 文件中也要标注 cross_domain
    { "from": "entity_two.id",            "to": "third_entity.ref_entity_two_id", "type": "1:N", "desc": "实体二被实体三引用", "domains": ["01", "03"] },
    { "from": "person.id",               "to": "asset.uploaded_by",             "type": "1:N", "desc": "用户上传文件",       "domains": ["01", "02"] }
  ]
};
