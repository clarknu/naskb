# TDD 设计变更说明 v0 → v1

> 存量项目 SFDS 方法论接入：反向记录既有测试套件（DD-004）+ tests/ 按方法论重组。
> 日期：2026-08-24

---

## 变更 1：建立阶段化 TDD 设计文档

**类型**：新增测试设计（反向记录）
**来源**：SFDS 方法论补全（既有 355 用例 → TC 规格映射 + 追溯链补齐）

### 变更内容

| 之前 | 之后 |
|------|------|
| 无 TDD 设计文档 | api/{6 域}-tdd-design.md + page-mock/web-console-tdd-design.md |

- `api/01-source-management-tdd-design.md`：TC-001~007（注册/脱敏/启停/删除/测试/变更/凭据）
- `api/02-ingestion-analysis-tdd-design.md`：TC-A01~A08（管线/幂等/批次/仓库/导出/对账/指纹）
- `api/03-retrieval-qa-tdd-design.md`：TC-R01~R06（命中/降级/空查询/RAG/直返兜底/统计）
- `api/04-deep-analysis-tdd-design.md`：TC-D01~D06（分段/幂等/表格/索引行/两级引用/基准）
- `api/05-knowledge-reorganize-tdd-design.md`：TC-O01~O07（生成/快照/三级校验/级联/锁）
- `api/06-platform-console-tdd-design.md`：TC-P01~P09（树/元数据/预览矩阵/解析/缩略图/Range/认证/任务/配置）
- `page-mock/web-console-tdd-design.md`：TC-M001~M010（前端规格；执行层暂缺——显式差距）

### 变更 2：tests/ 按方法论重组

- `tests/api/`（5 文件）：HTTP/协议契约（TestClient + 旧 serve HTTP + MCP 服务对象）
- `tests/unit/`（24 文件）：领域单元
- `tests/integration/`（2 文件）：真 PG（pgstore/inventory）
- `tests/page-mock/`：README（无前端框架——接入路线）
- `tests/test_arch_contract.py`：架构契约门禁（留存根级）
- `tests/test-reports/`：执行报告目录（Phase 后置）

### 理由

- 用户拍板重组 tests/ 目录；偏差（扁平→阶段分层）与缺口（page-mock 执行层）显式登记。

---

## 变更 2：行为承诺套件 + Integration E2E 规格（DD-009 T-3/T-4）

**类型**：新增测试设计/规格｜**来源**：用户拍板（2026-08-24）

- 	ests/api/test_arch_contract_behavior.py（14 用例）：幂等重复提交 / 任务状态机合法性 / ETag 304·缩略图缓存 / 无 PG 回退·无 LLM 明确 503 / MCP 写审计与读不审计 / 权限绕过与匿名例外（全身份口径）
- integration/web-console-tdd-design.md：TC-I001~I003（认证→来源→扫描→检索→预览→下载；诚实性；任务中心），执行方式=全局 Playwright MCP（本机 C:\\Soft，他机各自配置）
- 既有用例适配：test_server_api TestAuth 匿名断言改为新口径（仅引导/直链例外），新增 DD-009 端点回归 4 例；test_arch_contract_behavior 与 api 子集（61+14) 全绿

---

## 变更 3：Page Mock 执行层接入（vitest + @vue/test-utils + jsdom + fetch mock）（P-002）

**类型**：执行层接入（前端测试基础设施补全）｜**来源**：用户拍板 P-002 / remaining-issues G-01

### 变更内容

| 之前 | 之后 |
|------|------|
| tests/page-mock/ 仅 README（无工具链，人工验收） | tests/page-mock/web-console/ 落地 4 个 spec 文件（Vitest），HTTP 全 fetch mock |

- `naskb/web/` 新增 `package.json`（name: naskb-web，无 type: module；scripts.test = vitest run；dep：vue；devDeps：vitest/@vue/test-utils/jsdom）
- `naskb/web/vitest.config.mjs`：jsdom + setup.js + include 指向仓库 tests/page-mock/web-console/**；`resolve.alias` 统一 vue（esm-bundler，含 compiler）与 @vue/test-utils 入口；`server.fs.allow` 放行仓库根（跨 root include）
- `naskb/web/tests/setup.js`：可编程 fetch mock（`__addApiMock`/`__jsonResponse`）+ confirm 桩 + 用例间状态/body/localStorage 清理
- 组件化（保持运行时零构建）：`app.js` → `app-core.js`（ESM 组件内核 + createNaskbApp）+ `app-main.js`（入口，`createNaskbApp('#app')`）；`index.html` 以 import map 把 `'vue'` 解析到 `vendor/vue.esm-browser.prod.js`（full build），`<script type="module" src="/app-main.js">`
- 已实现用例（✅）：TC-M001/M002/M004/M005/M008/M009；未实现（⏳）：TC-M003/M006/M007/M010（见 tdd-design 标注）

### 理由

- 用户拍板补全 page-mock 执行层；采用 fetch mock（等价 MSW）实现后端零依赖；App 组件保持逐行逻辑，仅将全局 Vue 解构改为 ESM 导入；浏览器运行时依旧**零构建**（import map + 原生 ESM）。

---

## 变更 4：Page Mock 用例补全（TC-M003/M006/M007/M010）（P-002 后续）

**类型**：测试用例补全｜**来源**：用户拍板（2026-08-24，🟢 四项一次做完）

### 变更内容

| 之前 | 之后 |
|------|------|
| 已实现 TC-M001/M002/M004/M005/M008/M009；M003/M006/M007/M010 ⏳ | **10/10 全覆盖**：M003/M006/M007 按规格落地；M010 拆运行时链路 + 模块初始化时序两部分 |

- `search.spec.js` +2：TC-M003 问答生成（answer + sources 渲染；“生成中”按钮禁用以 deferred responder 断言）
- `sources.spec.js` +5：TC-M006（操作列 8 按钮恒渲染——DD-009 全身份口径，取代 v1「按 perm_ref 显隐」；删除 confirm 取消/确认分支）、TC-M007（变化清单分组 + 默认全选 + 取消勾选提交 rel_paths 子集）
- `app-shell.spec.js`（新）：TC-M010①/③/④——hashchange 视图切换、令牌保存 → localStorage → api() Authorization、无令牌 401 → “需要管理员令牌（右上角设置）”引导
- `init/app-shell-init.spec.js`（新）+ `naskb/web/tests/init-setup.js` + `vitest.config.init.mjs`：TC-M010② 模块初始化时序——在 app-core 加载**前**播种 `#/sources` + localStorage 令牌，断言初始化读取（刷新直达/持久化恢复语义）；`npm run test` = 主套件 + init 项目连跑
- 已知点（记录不隐藏）：jsdom 对 location.hash 赋值不触发 hashchange（显式 dispatch）；fetch mock 首命中即用，`/api/sources` 前缀会吞 `/changes`（spec 内按精确性排序注册）
