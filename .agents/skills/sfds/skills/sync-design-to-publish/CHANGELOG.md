# CHANGELOG · sync-design-to-publish（仲裁版）

## 1.1.0-arb.1 — 2026-08-23

CASE-009 泛化：从"项目专属"转正为方法论标准环节。

- 终结点唯一：固定设计文档域名 + 单一部署入口；每项目一个节点（`<固定域名>/<project-slug>/`）
- 删除写死的 Cloudflare 项目名与智能床路径；项目差异外置为配置（project-slug/site/publish-dir）
- 前端子自声明"⚠️ 项目专属"改为"通用方法论环节"
- 映射表保留为项目侧实例示例
- 新增 frontmatter lineage（origin: arb-hub, case: CASE-009）
