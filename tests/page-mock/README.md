# Page Mock 测试目录说明

> 本目录为 tdd-build Stage 2（Page Mock TDD）的执行目录。
> **执行层已接入**（2026-08-24，P-002）：基于 Vitest + @vue/test-utils + jsdom，所有 HTTP 由
> fetch mock 按 URL 分派拦截（后端零依赖，等价于 MSW 的 mock 网络能力）。
> 用例规格：`design/07-tdd/page-mock/web-console-tdd-design.md`（TC-M001~M010）。

## 已接入说明

### 工具链

- 依赖安装在 `naskb/web/`（该目录的 `package.json` 仅供测试工具链使用，不设 `type: module`）：
  - devDeps：`vitest`、`@vue/test-utils`、`jsdom`
  - dep：`vue`（用于测试侧 ESM 运行构建；脚本沿用仓库既有依赖策略）
- 配置：`naskb/web/vitest.config.mjs`（`environment: jsdom`，`setupFiles: ./tests/setup.js`，
  `include` 指向本目录 `tests/page-mock/web-console/**/*.spec.js`，`css: false`）。
  - `resolve.alias` 把 `vue` 与 `@vue/test-utils` 指向绝对入口，并通过 `server.fs.allow` 放行
    仓库根 —— 因为用例位于仓库 root（root 外），需要同时解决「跨 root include」与「node_modules 解析」；
  - vue 统一解析到 `vue/dist/vue.esm-bundler.js`（含 runtime compiler），保证与 `@vue/test-utils`
    **同一份 Vue 实例**（若 app-core 走 vendor 的 `vue.esm-browser.prod.js`、测试走另一份，会出现
    「setup 的 ref 来自 A、渲染器来自 B」的响应式断链，值更新但 DOM 不刷新）。
- `naskb/web/tests/setup.js`：stub 全局 `fetch`（路由：`globalThis.__addApiMock(method, matcher, responder)` /
  `globalThis.__jsonResponse(status, body)`）、`confirm`；每个用例前重置 fetch 路由、app-core 共享
  `state`、`document.body`、`localStorage`；`afterEach` 清理 body 与 localStorage。

### 运行

```bash
cd naskb/web
npm i        # 首次安装
npm run test # 等价 vitest run
```

> 说明：本目录位于仓库根（`tests/page-mock/`），而 vitest 配置在 `naskb/web/` 下，`include` 通过
> 相对路径跨 root 引用。若在别处运行，以 `naskb/web` 为工作目录执行即可。

### 与 tdd-execute( page-mock ) 的对应

- 用例按 `{client-slug}`（= `web-console`）组织为四个 spec 文件：
  - `search.spec.js`：TC-M001（检索成功渲染）/ TC-M002（检索失败 error）
  - `sources.spec.js`：TC-M004（表单校验）/ TC-M005（注册 Toast）
  - `jobs.spec.js`：TC-M008（任务中心初始渲染；轮询细节以 setInterval 打桩跳过）
  - `file-modal.spec.js`：TC-M009（元数据 + viewable 预览分派）
- 断言全部中文描述；mock fetch 按 URL 分派返回契约形状（取自 `design/04-platform-api/data/rest/*`）。
- 组件的 `template` 字符串由测试侧的 esm-bundler（含 compiler）在挂载时编译。

### 浏览器运行时零构建说明

- 生产目录 `naskb/web/public/` 原生 ESM + import map，**无打包步骤**：
  - `index.html` 用 `<script type="importmap">` 把裸导入 `'vue'` 解析到 `vendor/vue.esm-browser.prod.js`（full build，含 runtime+compiler）；
  - `<script type="module" src="/app-main.js">` → `import { createNaskbApp } from './app-core.js'` → 挂载 `#app`；
  - `app-core.js` 仅为测试需要以裸导入 `'vue'` 写法（配合 import map 在浏览器解析到 vendor 文件），
    组件 options/setup 逻辑逐行保持。
- 因此即便测试链建立在 node_modules 之上，`public/` 仍自包含、运行时零 Node、零外部 CDN（满足 REQ-R6-05）。

### 覆盖情况（相对 TC 规格）

- 已实现：TC-M001、TC-M002、TC-M004、TC-M005、TC-M008、TC-M009。
- 未实现（⏳ 待后续，见 07-tdd 规格标注）：TC-M003（问答生成）、TC-M006（操作列权限显隐+删除确认）、
  TC-M007（变更确认清单勾选）、TC-M010（hash 直达 + 401 引导）—— 分别涉及 LLM 生成交互、权限口径
  显隐（需按 perm_ref 基线）、`confirm` 删改确认交互、路由/持久化/401 引导，可后续迭代补充。

## 引用

- 设计规格：design/06-web-console/data/tree.js（组件/权限/api_ref 基线）
- 用例规格：design/07-tdd/page-mock/web-console-tdd-design.md
- 差异登记：design/review/design-code-gap.md（G-XX）
