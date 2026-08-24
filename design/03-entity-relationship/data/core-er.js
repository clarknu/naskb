// data/core-er.js — 跨域关系总纲
// 定义所有域和跨域关系全集
// er-viewer.html?domain=all 全景图依赖此文件

window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["core-er"] = {
  "domains": [
    { "domain": "01", "title": "来源管理",     "slug": "source-management",     "description": "来源注册与安全边界", "color": "#2563eb" },
    { "domain": "02", "title": "采集与分析",   "slug": "ingestion-analysis",    "description": "资源/目录/描述仓库", "color": "#059669" },
    { "domain": "03", "title": "检索问答",     "slug": "retrieval-qa",          "description": "向量库/术语表/检索输出", "color": "#7c3aed" },
    { "domain": "04", "title": "深度分析",     "slug": "deep-analysis",         "description": "条款级分段/两级引用", "color": "#0891b2" },
    { "domain": "05", "title": "知识整理",     "slug": "knowledge-reorganize",  "description": "整理方案/快照", "color": "#ca8a04" },
    { "domain": "06", "title": "平台服务",     "slug": "platform-console",      "description": "任务/下载/预览/认证", "color": "#dc2626" }
  ],
  "core_relations": [
    { "from": "source.source_id",        "to": "resource.source_id",          "type": "1:N", "desc": "来源拥有知识资源",     "domains": ["01", "02"] },
    { "from": "source.source_id",        "to": "folder_entry.source_id",      "type": "1:N", "desc": "来源拥有目录条目",     "domains": ["01", "02"] },
    { "from": "resource.resource_id",    "to": "vector_row.resource_id",      "type": "1:N", "desc": "资源拥有向量行（级联删除）", "domains": ["02", "03"] },
    { "from": "vector_row.resource_id",  "to": "resource.resource_id",        "type": "N:1", "desc": "条款级向量行归属资源（04 引用 03，不重复定义）", "domains": ["04", "03"] }
  ]
};
