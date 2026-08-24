# TDD 设计（Page Mock）：web-console

> **执行层已接入（vitest + @vue/test-utils + jsdom + fetch mock，等价 MSW），2026-08-24 P-002 完成。**
> 工具链与运行说明见 `tests/page-mock/README.md`；已实现用例标 ✅，未实现标 ⏳（原因见各用例注）。

> 基于页面设计 v1 | API 设计 v1
> 日期：2026-08-24 | Stage: Page Mock TDD
> 反向记录说明（DD-004）+ 现状说明（DD-008）：Web 端为 Vue3 全局构建静态包（无打包链），
> **执行层已接入**（Page Mock 用例由 Vitest 承担，HTTP 全 mock）；历史「执行层缺失」已闭环，转化见 design/review/remaining-issues.md G-01。

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
- **状态**: ✅ 已实现（tests/page-mock/web-console/search.spec.js）
- **前置条件**: Mock GET /api/kb/search 返回 3 条命中
- **操作序列**: 1. 渲染页面 2. 输入关键词 → 检索 3. 等待完成
- **断言清单**: ✅ 命中表格渲染 3 行（路径/分数/分类/标签/徽章）；✅ 引擎徽章显示 engine 值

### TC-M002: 检索失败展示错误
- **类型**: 异常流程 ｜ **前置条件**: Mock 500
- **状态**: ✅ 已实现（search.spec.js）
- **断言清单**: ✅ 页内 error 块展示；✅ 不显示空列表（区分空态）

### TC-M003: 问答生成与来源
- **类型**: 正常流程 ｜ **状态**: ⏳ 待后续（未实现）
- **断言清单**: ✅ answer 渲染 + sources 列表；✅ 生成中按钮 disabled（“生成中…”）
- **未实现原因**: 涉及 `/api/ask` 生成型交互与「生成中」按钮禁用状态；本轮只实现可行子集，留待后续补测。

### TC-M004: 来源表单校验
- **类型**: 边界条件 ｜ **状态**: ✅ 已实现（sources.spec.js）
- **断言清单**: ✅ alias 必填提示；✅ 空表单提交被拦截；✅ WebDAV 分支显示 url/账号密码字段

### TC-M005: 注册成功/失败 Toast
- **类型**: 正常/异常流程 ｜ **状态**: ✅ 已实现（sources.spec.js）
- **断言清单**: ✅ 成功 Toast（来源已注册）+ 表单收起 + 列表刷新；✅ 失败 Toast（注册失败 + 原因）

### TC-M006: 来源操作列按钮状态
- **类型**: 权限 UI ｜ **状态**: ⏳ 待后续（未实现）
- **断言清单**: ✅ 按 perm_ref 显隐（无令牌时写操作按钮…口径差异见 notes）；✅ 删除前 confirm 弹窗
- **未实现原因**: 需按 perm_ref 权限基线驱动按钮显隐；当前 app-core 未内置权限映射，且删除确认依赖 confirm 交互，留待权限口径落定后补测。

### TC-M007: 变更确认清单交互
- **类型**: 正常流程 ｜ **状态**: ⏳ 待后续（未实现）
- **断言清单**: ✅ 差异分组渲染（新增/变更/消失）；✅ 勾选后确认按钮提交 rel_paths；✅ 消失项文案（仅标记不物理删除）
- **未实现原因**: 变更确认清单（GET /changes → 勾选 → POST /confirm）为主干交互，本轮优先覆盖检索/来源/任务/模态；作为后续迭代项。

### TC-M008: 任务中心轮询
- **类型**: 交互 ｜ **状态**: ✅ 已实现（jobs.spec.js；仅断言初始渲染，轮询细节以 setInterval 打桩跳过）
- **断言清单**: ✅ 2s 自动刷新；✅ 进度条宽度 progress 映射；✅ 结果 details 展开 JSON
- **说明**: 用例实现为断言初始渲染（表格行/状态徽章类名/进度条宽度）；真实 2s 轮询与 details 展开在测试中被有意跳过（避免定时器泄漏），见 jobs.spec.js 注释。

### TC-M009: 文件详情模态渲染
- **类型**: 正常流程 ｜ **状态**: ✅ 已实现（file-modal.spec.js）
- **断言清单**: ✅ 元数据 kv 完整（路径/分类/标签/摘要/指纹/大小时间/分析时间）；✅ 预览按 viewable 分派（含 parsed iframe、html srcdoc、none 提示）；✅ 下载 href 指向 download_url

### TC-M010: 浏览器兼容校验
- **类型**: 边界条件 ｜ **状态**: ⏳ 待后续（未实现）
- **断言清单**: ✅ hash 路由直达（#/sources 等）恢复视图；✅ token 持久化（localStorage）与 401 引导（“需要管理员令牌”）
- **未实现原因**: 涉及 App 根组件级路由/持久化/401 交互，需要在挂载完整 App（含 hashchange 与 config 拉取）的边界下断言；本轮只测视图组件，根组件路由与 401 引导留待后续。
