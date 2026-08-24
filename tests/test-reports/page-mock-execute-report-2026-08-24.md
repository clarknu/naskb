# Page Mock 测试执行报告（tdd-execute Phase 3）

> 日期：2026-08-24 | 执行：`cd naskb/web && npm run test`（= vitest run（主套件）+ vitest run --config vitest.config.init.mjs（初始化时序））| 耗时 ~2.5s
> 结果：**21 passed + 2 passed，0 failed**（主套件 5 文件 21 用例；init 项目 1 文件 2 用例）
> 执行者：P-002 补全批次（TC-M003/M006/M007/M010 落地后首轮全量执行）；门禁判定：✅ 可合入

## 整体结果

| 指标 | 数值 |
|------|------|
| 规格来源 | design/07-tdd/page-mock/web-console-tdd-design.md（TC-M001~M010） |
| 主套件 | 5 文件 21 用例（search 4 / sources 9 / jobs 1 / file-modal 4 / app-shell 3） |
| 初始化时序（独立项目） | 1 文件 2 用例（web-console/init/app-shell-init.spec.js） |
| 全量通过 | 23 / 23 |
| 失败 | 0 |

## 用例覆盖矩阵（相对 TC 规格 10/10）

| 用例 | 覆盖点 | 状态 |
|------|--------|------|
| TC-M001 | 检索成功渲染（3 命中行/引擎徽章/过期徽章） | ✅ |
| TC-M002 | 检索失败 error 块 + 不渲染空表 | ✅ |
| TC-M003 | 问答生成（answer + sources）；「生成中」单击禁用（deferred 挂起断言） | ✅ P-002 补全 |
| TC-M004 | 来源表单校验（required/checkValidity/协议分支 v-if） | ✅ |
| TC-M005 | 注册成功/失败 Toast（表单收起/保持展开 + 列表刷新/不变） | ✅ |
| TC-M006 | 操作列 8 按钮恒渲染（DD-009 全身份口径）；删除 confirm 取消/确认分支 | ✅ P-002 补全 |
| TC-M007 | 变更确认清单（分组渲染/默认全选/取消勾选提交 rel_paths 子集/消失文案） | ✅ P-002 补全 |
| TC-M008 | 任务中心初始渲染（行/徽章类名/进度条宽度；轮询打桩跳过） | ✅ |
| TC-M009 | 文件详情模态（元数据 kv/viewable 分派/下载 href） | ✅ |
| TC-M010 | ①hash 路由切换 ②模块初始化（直达 + 持久化恢复，独立项目）③token 保存→localStorage→Authorization ④无令牌 401 →「需要管理员令牌（右上角设置）」 | ✅ P-002 补全 |

## 已知点（记录不隐藏）

- jsdom 对 `location.hash` 赋值不触发 hashchange → 用例显式 `dispatch(new Event('hashchange'))`（含注释）。
- fetch mock 为「首个命中即用」：`/api/sources` 前缀串匹配会吞 `/api/sources/{sid}/changes` → spec 内按精确性排序注册（已在用例注释说明）。
- TC-M006 口径说明：v1 设计假设「按 perm_ref 显隐」在 DD-009 全身份模型（单管理员、无匿名只读）下不适用——UI 不做按权限点的按钮显隐，权限由服务端逐点执行；口径已回写设计稿。
- 模块初始化时序需在 app-core 加载**前**播种 hash/token，与主套件 setup 冲突 → 独立项目（vitest.config.init.mjs + tests/init-setup.js）承担，spec 置于 `web-console/init/` 子目录。

## 引用

- 套件：tests/page-mock/web-console/*.spec.js + init/app-shell-init.spec.js
- 规格：design/07-tdd/page-mock/web-console-tdd-design.md
- 工具链：naskb/web/package.json（`npm run test` 主套件 + init 项目连跑）
