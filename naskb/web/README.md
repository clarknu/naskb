# NASKB Web UI（v0.1）

Vue3 全局构建版（`vendor/vue.global.prod.js`）+ 原生 ES 模块，**无打包步骤**：
本目录即服务托管的生产产物（`naskb desc serve-platform` 直接挂载），
运行时零 Node、零外部 CDN——满足部署自包含（REQ-R6-05）。

## 页面

- 检索问答（默认）：`/api/kb/search` + `/api/ask`
- 浏览：来源 → 目录树罗列（`/api/tree`），点文件进详情
- 来源：注册/测试/扫描/AI 分析（local / WebDAV；rw|ro 只读知识库）
- 任务：JobManager 队列进度
- 文件详情模态：预览（图片/PDF/音视频/文本）+ 知识元数据 + 下载

## 升级路径

页面规模扩大后可迁移到 Vite 工程（SFC + 按需打包），构建产物仍输出到
本 `dist/` 即可，服务端零改动（platform-v3-design §6.1 决策 2）。
