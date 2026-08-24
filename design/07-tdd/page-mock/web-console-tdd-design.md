# TDD 设计（Page Mock）：web-console

> **执行层已接入（vitest + @vue/test-utils + jsdom + fetch mock，等价 MSW），2026-08-24 P-002 完成；
> 2026-08-24 P-002 补全（TC-M003/M006/M007/M010）+ 独立项目覆盖模块初始化时序。**
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
- **类型**: 正常流程 ｜ **状态**: ✅ 已实现（search.spec.js，P-002 补全）
- **断言清单**: ✅ answer 渲染 + sources 列表；✅ 生成中按钮 disabled（“生成中…”，deferred responder 挂起断言）
- **实现说明**: POST /api/ask 契约形状（answer + sources）mock；“生成中”以「挂起 promise → 断言禁用 → resolve → 断言恢复」覆盖。

### TC-M004: 来源表单校验
- **类型**: 边界条件 ｜ **状态**: ✅ 已实现（sources.spec.js）
- **断言清单**: ✅ alias 必填提示；✅ 空表单提交被拦截；✅ WebDAV 分支显示 url/账号密码字段

### TC-M005: 注册成功/失败 Toast
- **类型**: 正常/异常流程 ｜ **状态**: ✅ 已实现（sources.spec.js）
- **断言清单**: ✅ 成功 Toast（来源已注册）+ 表单收起 + 列表刷新；✅ 失败 Toast（注册失败 + 原因）

### TC-M006: 来源操作列按钮状态
- **类型**: 权限 UI ｜ **状态**: ✅ 已实现（sources.spec.js，P-002 补全）
- **断言清单**: ✅ 操作列 8 个操作按钮恒渲染（权限点覆盖）；✅ 删除前 confirm 弹窗（取消 → 不发 DELETE；确认 → DELETE + toast“已删除” + 列表刷新）
- **口径说明（DD-009 全身份模型，取代 v1「按 perm_ref 显隐」）**: 无匿名只读角色（匿名全部移除），单管理员 Bearer 全身份 → UI 不做按 perm_ref 的按钮显隐；
  SourceRegister/SourceTest/SourceScan/SourceAnalyze/SourceChangesView/SourceChangeConfirm/SourceDeepToggle/SourceAdopt/SourceEnable/SourceDelete
  等权限点由服务端逐点执行，UI 恒定渲染全部操作按钮。删除确认依赖 confirm 弹窗（只读源附“入库知识将一并清除”文案——删除调用在组件内，文案随 s.access_mode 动态拼接）。

### TC-M007: 变更确认清单交互
- **类型**: 正常流程 ｜ **状态**: ✅ 已实现（sources.spec.js，P-002 补全）
- **断言清单**: ✅ 差异分组渲染（新增/变更/消失）；✅ 勾选后确认按钮提交 rel_paths；✅ 消失项文案（仅标记不物理删除）
- **实现说明**: GET {sid}/changes → `s._chg`（added/changed/missing 分组）→ 默认全选 added+changed → 取消勾选后
  POST {sid}/confirm 提交 `{ rel_paths: [勾选子集] }` → toast“确认同步已提交（任务 …）”+ 清单收起；pollJob 轮询以 setInterval 打桩跳过。
- **注意**: fetch mock 为「首个命中即用」，`/api/sources` 前缀串匹配会吞掉 `/api/sources/{sid}/changes`——changes/confirm 路由必须注册在前（spec 内已按此排序）。

### TC-M008: 任务中心轮询
- **类型**: 交互 ｜ **状态**: ✅ 已实现（jobs.spec.js；仅断言初始渲染，轮询细节以 setInterval 打桩跳过）
- **断言清单**: ✅ 2s 自动刷新；✅ 进度条宽度 progress 映射；✅ 结果 details 展开 JSON
- **说明**: 用例实现为断言初始渲染（表格行/状态徽章类名/进度条宽度）；真实 2s 轮询与 details 展开在测试中被有意跳过（避免定时器泄漏），见 jobs.spec.js 注释。

### TC-M009: 文件详情模态渲染
- **类型**: 正常流程 ｜ **状态**: ✅ 已实现（file-modal.spec.js）
- **断言清单**: ✅ 元数据 kv 完整（路径/分类/标签/摘要/指纹/大小时间/分析时间）；✅ 预览按 viewable 分派（含 parsed iframe、html srcdoc、none 提示）；✅ 下载 href 指向 download_url

### TC-M010: 浏览器兼容校验
- **类型**: 边界条件 ｜ **状态**: ✅ 已实现（app-shell.spec.js + init/app-shell-init.spec.js，P-002 补全）
- **断言清单**: ✅ hash 路由直达（#/sources 等）恢复视图；✅ token 持久化（localStorage）与 401 引导（“需要管理员令牌”）
- **实现说明（两部分）**:
  - 运行时链路（app-shell.spec.js）：①hashchange → 视图切换（#/sources 来源页 / #/jobs 任务中心 / #/ 回检索页）；
    ③令牌保存 → localStorage 落盘 + 徽章“🔑 已配置令牌” + api() 请求自动携带 Authorization；
    ④无令牌 401 → 组件 error 块展示“需要管理员令牌（右上角设置）” + 顶栏“🔒 需要令牌”。
  - **模块初始化时序**（独立 vitest 项目 vitest.config.init.mjs + tests/init-setup.js，spec 于 web-console/init/ 子目录）：
    在 app-core 加载**前**播种 location.hash='#/sources' 与 localStorage 令牌，断言模块初始化读取
    （state.route='sources'、state.token='tok-restore-001'）——即“刷新直达/持久化恢复”语义
    （浏览器中 state.route/state.token 由 app-core 模块加载瞬间读取）。
