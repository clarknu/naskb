# Page Mock 测试目录说明

> 本目录为 tdd-build Stage 2（Page Mock TDD）的执行目录。
> **执行层已接入**（2026-08-24，P-002：vitest + @vue/test-utils + jsdom + fetch mock，HTTP 全 mock）；
> **2026-08-24 P-002 补全**：TC-M003/M006/M007/M010 落地，10 用例全覆盖。
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
npm run test # = vitest run（主套件）+ vitest run --config vitest.config.init.mjs（初始化时序）
```

> 说明：本目录位于仓库根（`tests/page-mock/`），而 vitest 配置在 `naskb/web/` 下，`include` 通过
> 相对路径跨 root 引用。若在别处运行，以 `naskb/web` 为工作目录执行即可。
> **双项目结构**：`app-shell-init.spec.js`（模块初始化时序）需在 app-core 加载前播种 hash/token，
> 与主套件 setup 冲突，故置于 `web-console/init/` 子目录由 `vitest.config.init.mjs`（setup =
> `tests/init-setup.js`）单独执行；主配置 include 为 `web-console/*.spec.js` 单层 glob，天然不匹配。

### 与 tdd-execute( page-mock ) 的对应

- 用例按 `{client-slug}`（= `web-console`）组织为五个 spec 文件 + init 子目录一个：
  - `search.spec.js`：TC-M001（检索成功渲染）/ TC-M002（检索失败 error）/ TC-M003（问答生成 + 来源 + “生成中”禁用）
  - `sources.spec.js`：TC-M004（表单校验）/ TC-M005（注册 Toast）/ TC-M006（操作列按钮 + 删除 confirm）/ TC-M007（变更确认清单）
  - `jobs.spec.js`：TC-M008（任务中心初始渲染；轮询细节以 setInterval 打桩跳过）
  - `file-modal.spec.js`：TC-M009（元数据 + viewable 预览分派）
  - `app-shell.spec.js`：TC-M010①/③/④（hash 路由切换 / token 保存持久化与请求携带 / 401 引导）
  - `init/app-shell-init.spec.js`：TC-M010②（模块初始化时序：直达 hash + localStorage 令牌恢复；独立 vitest 项目）
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

- **全部已实现（TC-M001 ~ M010，10/10）**：TC-M003（问答生成）、TC-M006（操作列 + 删除确认）、
  TC-M007（变更确认清单）、TC-M010（hash 路由 + token 持久化 + 401 引导）已于 P-002 补全批次落地；
  其中 TC-M010 拆为运行时链路（app-shell.spec.js）与模块初始化时序（init/ 独立项目）两部分。
- 口径记录：TC-M006 的「按 perm_ref 显隐」为 v1 设计假设，DD-009 全身份模型下**不适用**——见
  07-tdd 设计稿 TC-M006 口径说明；TC-M010 的 401 引导文案锚定 api() 的 `err.code === 401` 分支。

## 引用

- 设计规格：design/06-web-console/data/tree.js（组件/权限/api_ref 基线）
- 用例规格：design/07-tdd/page-mock/web-console-tdd-design.md
- 差异登记：design/review/design-code-gap.md（G-XX）
