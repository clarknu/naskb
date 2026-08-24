# TDD 设计（Page Mock）：web-console

> 基于页面设计 v1 | API 设计 v1
> 日期：2026-08-24 | Stage: Page Mock TDD
> 反向记录说明（DD-004）+ 现状说明（DD-008）：Web 端为 Vue3 全局构建静态包（无 package.json/vitest 构建链），
> 当前不存在自动化前端测试基础设施——本设计文档定义 Page Mock 阶段规格；**执行层（tests/page-mock/）暂以说明性 README + 人工验收承担**，
> 接入工具链（Vitest + @vue/test-utils + MSW）后按本文件用例落地。此为显式差距，不静默（见 design/review/design-code-gap.md）。

## 测试范围

| 页面/组件 | 涉及交互 | Mock API | 权限 |
|----------|---------|---------|------|
| 检索问答页 | 检索/问答/命中打开 | GET /api/kb/search、POST /api/ask、GET /api/files/{rid} | public / KbAsk |
| 浏览知识库页 | 来源切换/目录进入/文件打开 | GET /api/sources、GET /api/tree | SourceList |
| 知识来源页 | 注册表单校验/来源操作列 | POST /api/sources、{sid}/scan|analyze|adopt|test、{sid}/changes|confirm、PATCH/DELETE {sid} | 全权限点 |
| 任务中心页 | 表格渲染/2s 轮询/结果展开 | GET /api/jobs、GET /api/jobs/{id} | JobsView |
| 文件详情模态 | 元数据/预览渲染/下载/关闭 | GET /api/files/{rid}、/preview、/parsed | FilePreview/FileDownload |

## 测试用例

### TC-M001: 检索问答页加载成功
- **类型**: 正常流程
- **前置条件**: Mock GET /api/kb/search 返回 3 条命中
- **操作序列**: 1. 渲染页面 2. 输入关键词 → 检索 3. 等待完成
- **断言清单**: ✅ 命中表格渲染 3 行（路径/分数/分类/标签/徽章）；✅ 引擎徽章显示 engine 值

### TC-M002: 检索失败展示错误
- **类型**: 异常流程 ｜ **前置条件**: Mock 500
- **断言清单**: ✅ 页内 error 块展示；✅ 不显示空列表（区分空态）

### TC-M003: 问答生成与来源
- **类型**: 正常流程 ｜ **断言清单**: ✅ answer 渲染 + sources 列表；✅ 生成中按钮 disabled（“生成中…”）

### TC-M004: 来源表单校验
- **类型**: 边界条件 ｜ **断言清单**: ✅ alias 必填提示；✅ 空表单提交被拦截；✅ WebDAV 分支显示 url/账号密码字段

### TC-M005: 注册成功/失败 Toast
- **类型**: 正常/异常流程 ｜ **断言清单**: ✅ 成功 Toast（来源已注册）+ 表单收起 + 列表刷新；✅ 失败 Toast（注册失败 + 原因）

### TC-M006: 来源操作列按钮状态
- **类型**: 权限 UI ｜ **断言清单**: ✅ 按 perm_ref 显隐（无令牌时写操作按钮…口径差异见 notes）；✅ 删除前 confirm 弹窗

### TC-M007: 变更确认清单交互
- **类型**: 正常流程 ｜ **断言清单**: ✅ 差异分组渲染（新增/变更/消失）；✅ 勾选后确认按钮提交 rel_paths；✅ 消失项文案（仅标记不物理删除）

### TC-M008: 任务中心轮询
- **类型**: 交互 ｜ **断言清单**: ✅ 2s 自动刷新；✅ 进度条宽度 progress 映射；✅ 结果 details 展开 JSON

### TC-M009: 文件详情模态渲染
- **类型**: 正常流程 ｜ **断言清单**: ✅ 元数据 kv 完整（路径/分类/标签/摘要/指纹/大小时间/分析时间）；✅ 预览按 viewable 分派（含 parsed iframe、html srcdoc、none 提示）；✅ 下载 href 指向 download_url

### TC-M010: 浏览器兼容校验
- **类型**: 边界条件 ｜ **断言清单**: ✅ hash 路由直达（#/sources 等）恢复视图；✅ token 持久化（localStorage）与 401 引导（“需要管理员令牌”）
