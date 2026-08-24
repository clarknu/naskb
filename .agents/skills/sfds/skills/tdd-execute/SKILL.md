---
name: tdd-execute
version: 3.0.0
description: |
  TDD 测试执行与验证——三阶段架构（API → Page Mock → Integration）。
  逐阶段执行测试、失败分类溯源、修复循环、输出报告。
  v3 三阶段分离执行 + 阶段参数分发 + 逐阶段前置条件。
triggers:
  - TDD 执行
  - 运行测试
  - 测试报告
  - 执行测试
  - 测试验证
  - 跑测试
  - 测试失败分析
  - 回归测试
  - 全量测试
  - 跑 API 测试
  - 跑页面测试
  - 跑集成测试

lineage:
  origin: arb-hub
  sources:
    boxing:        {sha256: 28b165989b71}
    zy-iot-ai:     {sha256: 4c24a69e1b2d}
    zy-ai-consult: {sha256: 4c24a69e1b2d}
---

# TDD Execute — 测试执行与验证 Skill

> **本 skill 只负责测试的执行、报告、失败分析与修复循环。测试的设计与编码由 [`tdd-build`](../tdd-build/SKILL.md) 负责。**

---

## §1 阶段分发

> **调用方传入 Arguments 字符串，按以下规则自动分发到对应阶段。**

| 参数含 | 分发到 | 执行内容 |
|--------|--------|---------|
| `api` | **§3 API 测试执行** | 运行 `tests/api/` 下的后端测试 |
| `page-mock` | **§4 Page Mock 测试执行** | 运行 `tests/page-mock/` 下的 Web 前端 Mock 测试 |
| `miniprogram` | **§4b Mini Program 测试执行** | 通过微信开发者工具 automator 执行小程序模拟器测试 |
| `integration` | **§5 Integration 测试执行** | 运行 `tests/integration/` 下的 E2E 测试 |
| 为空 / `all` | **依次执行全部适用阶段** | 自动检测项目端类型，按需执行 §3→§4（如有 Web）→§4b（如有小程序）→§5 |

**阶段依赖关系：**

```
Stage 1 (API)     Stage 2 (Page Mock)     Stage 2b (Mini Program)     Stage 3 (Integration)
     ↓                  ↓                        ↓                          ↓
 依赖: API 代码    依赖: 前端代码完成      依赖: 小程序项目+工具就绪    依赖: 两端代码 + 前置全绿
     后端可启动    (后端无需启动)           (后端无需启动，Mock模式)     后端 + 前端均需启动
```

> **铁律：** Stage 3 不得在 Stage 1 或（对应端类型的）Stage 2/2b 未全部通过时启动。
> 如果 `arguments=all`，Stage 1 失败则中止；Stage 2 和 Stage 2b 彼此独立——Web 测试失败不影响小程序测试继续，反之亦然。

---

## §2 通用规则（三阶段共享）

| # | 规则 | 说明 |
|---|------|------|
| 1 | **实际执行铁律** | 必须亲自执行测试命令，记录实际输出。不得仅凭 TDD 报告中"全部通过"的声明跳过实际执行 |
| 2 | **阶段覆盖** | 运行当前阶段下的所有测试，不得遗漏任何文件 |
| 3 | **失败必溯源** | 每个失败测试按"测试代码→实现→设计→业务流程"逐级回溯，定位根因 |
| 4 | **修复必重跑** | 任何修复后，必须重新执行当前阶段全量测试 |
| 5 | **中文输出** | 所有报告、摘要、分析必须使用中文撰写 |
| 6 | **报告随测试代码归档** | 执行报告放在 `tests/test-reports/` 目录下 |

### 2.1 执行流程（各阶段共用）

```
  ① 检查前置条件
        │
        ├── 未满足 → 报告缺失项，等待补充
        │
        └── 满足 → ② 发现测试文件
                      │
                      ▼
               ③ 执行测试命令
                      │
                      ├── 全部通过 → ④ 输出阶段报告 → 进入下一阶段（或完成）
                      │
                      └── 有失败 → ⑤ 失败分类与溯源
                                        │
                                        ▼
                                 ⑥ 按分类修正
                                        │
                                        ▼
                                 ⑦ 重新运行当前阶段 → 回到 ③
                                        │
                                   (最多 3 轮修复循环)
```

### 2.2 失败分类与溯源

| 测试结果 | 含义 | 处理方式 |
|---------|------|---------|
| ✅ 通过 | 实现符合设计契约 | 无需处理 |
| ❌ 测试代码问题 | 测试用例写错了（断言不对、参数不对、mock 配置错误） | 修正测试代码 → 重新运行 |
| ❌ 实现问题 | 测试正确但实现行为不符合设计 | 修正实现代码 → 重新运行 |
| ❌ 设计问题 | 测试和实现都对不上设计文档 | 回溯对应设计 skill 修正 → 更新测试 → 重新运行 |
| ❌ 业务流程问题 | 测试反映的业务逻辑与工作流不一致 | 回溯 §8.1 business-workflow → 更新设计 → 更新测试 → 重新运行 |
| ⏭️ 跳过 | 测试被显式跳过 | 审查跳过理由是否仍然有效 |
| ❌ 追溯链断裂 | 测试正确、实现正确，但数据字段在跨层传递时丢失 | 回溯到对应设计层修正 → 更新测试 → 重新运行 |

**溯源路径（逐级回溯）：**

```
测试失败
    │
    ├── ① 检查断言是否正确（对照设计文档）
    │     └── 断言错误 → 修正测试代码
    │
    ├── ② 检查实现是否与设计一致
    │     └── 实现偏差 → 修正实现代码
    │
    ├── ③ 检查设计是否与业务工作流一致
    │     └── 设计不一致 → 回溯对应设计 skill
    │
    └── ④ 检查业务工作流是否与原始需求一致
          └── 工作流缺失 → 回溯 §8.1
    │
    ├── ⑤ 检查追溯链是否完整
          └── 追溯链断裂 → 回溯到对应设计层
```

### 2.3 修复循环规则

```
┌──────────────────────────────────────────┐
│                                          │
│  ① 运行当前阶段测试                       │
│       │                                   │
│       ├── 全部通过 → 退出循环，输出报告     │
│       │                                   │
│       └── 有失败 → ② 分类溯源              │
│                     │                     │
│                     ↓                     │
│              ③ 按分类修正                  │
│                     │                     │
│                     ↓                     │
│              ④ 重新运行当前阶段             │
│                     │                     │
│                     └── 回到 ① ──────────→ │
│                                          │
│  最多 3 轮修复，超过需人工介入                │
└──────────────────────────────────────────┘
```

### 2.4 修正约束（各阶段通用）

| 修正类型 | 允许的动作 | 禁止的动作 |
|---------|----------|----------|
| **测试代码修正** | 修正断言、修正参数、修正 mock 配置 | 降低覆盖标准、删除"难测"的用例 |
| **实现代码修正** | 修正实现逻辑 | **修改设计契约**（API 路由/参数定义/页面功能树定义） |
| **设计修正** | 通过对应设计 skill 修改设计文档，同步更新测试 | 只改测试不改设计文档 |
| **业务流程修正** | 通过 §8.1 business-workflow skill 修改工作流 | 跳过设计层直接改代码 |

> **铁律：** 如果修复需要改动设计或业务流程，必须通过对应的设计 skill 执行，不可直接在修复循环中修改设计文件。

### 2.5 修正记录模板

```markdown
| 循环轮次 | 失败用例 | 分类 | 根因 | 修正动作 | 修正文件 | 修正结果 |
|---------|---------|------|------|---------|---------|---------|
| R1 | test_xxx | 实现问题 | 未返回 201 | 添加 Created 响应 | controller.py | ✅ |
| R1 | test_yyy | 测试问题 | 断言写错 | 修正期望值 | test.py | ✅ |
| R2 | （无失败） | — | — | — | — | ✅ 全绿 |
```

### 2.6 "全部通过"的定义

以下状态视为"未全部通过"，必须继续修复循环：

| 情况 | 判定 |
|------|------|
| 任何测试文件有失败用例 | ❌ 未通过 |
| 任何测试文件编译/语法错误 | ❌ 未通过 |
| 任何测试文件无法运行（runtime error） | ❌ 未通过 |
| 覆盖度不满足标准（总体最低线 < 60%；分维度错误/边界 ≥80% 以 tdd-build 设计为准） | ❌ 未通过（需补充测试 → 回到 tdd-build） |

> **注记（已裁）：** 各阶段前置条件不含「TDD 设计文档存在且为最新版本」一行——TDD 设计文档由 tdd-build 产出、在一致性检查模式核验，不作为执行前置（2026-08-23 R-007 定案：维持 consult 对该行的删除，boxing 原行不回灌；小程序阶段既有同类行维持现状）。

---

## §3 Stage 1 — API 测试执行

> **Arguments 匹配：** 含 `api` 时执行本阶段。
> **触发词：** `跑 API 测试`、`API 测试执行`、`运行后端测试`

### 3.1 前置条件

| 条件 | 检查方式 |
|------|---------|
| API 测试代码存在 | `tests/api/` 目录非空 |
| API 实现代码编译通过 | 项目后端编译 0 错误 |
| 测试数据库可用 | DI 拦截配置正确（见 tdd-build §2.4） |

> **不需要**：前端代码、前端服务启动——Stage 1 完全在后端范围内运行。

### 3.2 执行步骤

1. **发现测试文件**：列出 `tests/api/` 下所有测试文件
2. **确保数据库就绪**：按 tdd-build §2.4 的 DI 拦截模式确认测试数据库就绪（运行迁移（如适用），或使用内存数据库/项目约定的测试库）
3. **执行测试命令**（按技术栈选对应命令）：

| 后端技术栈 | 执行命令 |
|-----------|---------|
| Python + FastAPI | `PYTHONPATH=src python -m pytest tests/api/ -v` |
| .NET | `dotnet test tests/api/ --verbosity normal` |
| Node.js | `npx jest tests/api/ --verbose` |
| Spring Boot | `./gradlew test --tests "*ApiTest*"` |

> **分层执行策略（先领域级后全量）：** 当 Stage 1 测试代码按用例层级分层组织（领域级用例与跨域旅程用例分属不同目录/命名空间/标记）时，先用过滤器只跑领域级用例层获得快速反馈；领域级全绿后再去掉过滤跑全量回归——全量结果含跨域旅程用例属预期，不计为异常。修复循环期间同样遵循此顺序。

4. **记录原始输出**：保留完整 stdout/stderr
5. **失败 → 进入 §2.2 分类溯源 + §2.3 修复循环**
6. **全部通过 → 输出 §3.3 报告**

### 3.3 Stage 1 报告

```markdown
# TDD 执行报告（API）：{领域/全域}

> 日期：{YYYY-MM-DD} | Stage: API TDD | 执行者：tdd-execute skill

## 整体结果

| 指标 | 数值 |
|------|------|
| 测试文件数 | N |
| 总用例数 | N |
| 通过 | N |
| 失败 | 0 |
| 跳过 | N |
| 耗时 | Ns |

## 覆盖统计

| 维度 | 覆盖 |
|------|------|
| API 端点覆盖 | N/N (100%) |
| 状态转换覆盖 | N/N (100%) |
| 错误场景覆盖 | N/N (≥80%) |
| 边界条件覆盖 | N/N (≥80%) |
| 权限覆盖 | N/N (100%) |
| 架构承诺覆盖（L2+） | N/N |

## 修复记录

| 轮次 | 失败数 | 修正数 | 结果 |
|------|--------|--------|------|
| ... | ... | ... | ... |
```

**报告路径：** `tests/test-reports/api-execute-report-{date}.md`

---

## §4 Stage 2 — Page Mock 测试执行

> **Arguments 匹配：** 含 `page-mock` 时执行本阶段。
> **触发词：** `跑页面测试`、`页面测试执行`、`运行前端测试`

### 4.1 前置条件

| 条件 | 检查方式 |
|------|---------|
| Page Mock 测试代码存在 | `tests/page-mock/{client-slug}/` 目录非空 |
| 前端项目可编译 | `cd src/{client-slug} && npm run build` 或等效命令 0 错误 |
| Mock 配置完整 | `tests/page-mock/{client-slug}/setup.ts`（或等效）存在 |

> **不需要**：后端服务——Stage 2 全部 API 已 Mock，后端完全不需要启动。

### 4.2 执行步骤

1. **发现测试文件**：列出 `tests/page-mock/{client-slug}/` 下所有测试文件
2. **安装依赖**（如需要）：`npm install`
3. **执行测试命令**（按前端技术栈选对应命令）：

| 前端技术栈 | 执行命令 |
|-----------|---------|
| Vue 3 + Vitest | `cd src/{client-slug} && npx vitest run --config vitest.config.ts` |
| React + Jest | `npx jest tests/page-mock/ --verbose` |
| Angular + Jasmine | `ng test --watch=false --include='**/page-mock/*.spec.ts'` |

4. **记录原始输出**
5. **失败 → 进入 §2.2 分类溯源 + §2.3 修复循环**
6. **全部通过 → 输出 §4.3 报告**

### 4.3 Stage 2 报告

```markdown
# TDD 执行报告（Page Mock）：{客户端名}

> 日期：{YYYY-MM-DD} | Stage: Page Mock TDD | 执行者：tdd-execute skill

## 整体结果

| 指标 | 数值 |
|------|------|
| 测试文件数 | N |
| 总用例数 | N |
| 通过 | N |
| 失败 | 0 |
| 耗时 | Ns |

## 覆盖统计

| 维度 | 覆盖 |
|------|------|
| 页面组件覆盖 | N/N |
| 路由跳转覆盖 | N/N |
| 表单交互覆盖 | N/N |
| 权限 UI 覆盖 | N/N |

## 修复记录
...
```

**报告路径：** `tests/test-reports/page-mock-execute-report-{date}.md`

---

## §4b Stage 2b — Mini Program 测试执行

> **Arguments 匹配：** 含 `miniprogram` 时执行本阶段。
> **触发词：** `跑小程序测试`、`小程序测试执行`、`Mini Program 测试`
>
> **本阶段仅在项目中存在小程序端时适用。** 依赖 `wechatide-skill` 提供的 `wechatide` CLI 工具链；自动拉起/使用判定方法论见 `wechatide-automation`（工具名用**位置参数**、禁用 `-t`）。

### 4b.1 前置条件

| 条件 | 检查方式 |
|------|---------|
| Mini Program TDD 设计文档存在 | `design/07-tdd/miniprogram/{client-slug}-tdd-design.md` 存在 |
| 测试计划文件存在 | `tests/miniprogram/{client-slug}/test-plan.md` 存在 |
| 微信开发者工具已安装 | `wechatide` 命令可用 |
| 登录态有效 | `wechatide -c <clientName> check_wechatide_status --skill-version <version>` 返回 `loginExpired: false` 且 `versionRelation: equal`（**或**先 `node tests/miniprogram-harness/bin/harness.js up <projectId>` 自动拉起——登录态持久化，免扫码） |
| 小程序项目可打开 | `project.config.json` 存在且 `appid` 有效；以 `node tests/miniprogram-harness/bin/harness.js up <projectId>` 能拉起为准（免扫码自动开窗） |

> **不需要**：后端服务（Mock 模式）、前端构建产物——Stage 2b 在微信开发者工具模拟器中直接运行源码。

### 4b.2 执行步骤

0. **自动拉起目标项目**（登录态持久化，免扫码）：harness 为唯一约定，无 harness 时人工开窗。
   ```bash
   node tests/miniprogram-harness/bin/harness.js up <projectId>
   ```
   随即 `wechatide` CLI 可正常使用。若未用 harness 拉起，再走环境检查。

1. **环境检查**（工具名位置参数，禁用 `-t`）：
   ```bash
   wechatide -c <clientName> check_wechatide_status --skill-version <version>
   ```
   确认 `loginExpired: false` 且 `versionRelation: equal`。如未登录，执行 `scan_login` 等待用户扫码。

2. **确认项目窗口已开**：harness 已拉起的窗口即目标窗口，无需再 `open_project_window`。
   若确实未开（未走 harness），再 fallback：
   ```bash
   wechatide -c <clientName> open_project_window --project <projectPath>
   ```
   前置：已读取 `project.config.json` 确认 `appid` 有效。

3. **执行 Mock 配置**（按测试计划中的 mock 章节）：
   ```bash
   # Mock wx API
   wechatide -c <clientName> -t automation_wx_api --project <p> --action mock --method getSystemInfo --result-file tests/miniprogram/{slug}/mock/wx-api-mocks.json
   ```

4. **按 test-plan.md 逐条执行用例**：每条用例翻译为 `wechatide` automator 命令序列：
   - 页面导航 → `automation_navigate`
   - 等待元素 → `automation_page_action --action waitFor`
   - 交互操作 → `automation_element_action`
   - 断言验证 → `automation_element_action --action text` / `automation_page_action --action getData`
   - 截图证据 → `simulator_screenshot --path <localPath>`

5. **记录每条用例结果**（pass/fail + 证据引用）

6. **失败 → 进入 §2.2 分类溯源 + §2.3 修复循环**
   - 小程序测试的额外失败分类：
     - `simulator-not-ready`：模拟器未就绪 → 尝试 `simulator_refresh` 后重试
     - `selector-not-found`：选择器未匹配 → 先用 `querySelectorAll` 确认当前页面元素
     - `timeout`：操作超时 → 按 automator SKILL.md 的 timeout 处理流程

7. **全部通过 → 输出 §4b.3 报告**

8. **清理**：恢复 Mock（`automation_wx_api --action restore`）；关闭窗口（`node tests/miniprogram-harness/bin/harness.js down <projectId>`）

### 4b.3 Stage 2b 报告

```markdown
# TDD 执行报告（Mini Program）：{客户端名}

> 日期：{YYYY-MM-DD} | Stage: Mini Program TDD | 执行者：tdd-execute skill
> 工具：微信开发者工具 automator | 项目路径：{projectPath}

## 环境检查

| 检查项 | 状态 |
|--------|------|
| wechatide 可用 | ✅ |
| 登录态（openid） | ✅ {openid} |
| 项目已打开 | ✅ |

## 整体结果

| 指标 | 数值 |
|------|------|
| 总用例数 | N |
| 通过 | N |
| 失败 | 0 |
| 截图证据数 | N |
| 总耗时 | Ns |

## 用例明细

| 用例 | 操作步骤 | 断言结果 | 截图证据 | 状态 |
|------|---------|---------|---------|------|
| TC-MP001 | navigate → waitFor → querySelectorAll | count >= 1 ✅ | tc-mp001.png | ✅ |
| TC-MP002 | navigate → waitFor .error-toast | 错误提示可见 ✅ | tc-mp002.png | ✅ |

## 覆盖统计

| 维度 | 覆盖 |
|------|------|
| 页面组件覆盖 | N/N |
| 路由跳转覆盖 | N/N |
| wx API Mock 覆盖 | N/N |
| 截图证据 | N/N |

## 修复记录
...
```

**报告路径：** `tests/test-reports/miniprogram-execute-report-{date}.md`

---

## §5 Stage 3 — Integration 测试执行

> **Arguments 匹配：** 含 `integration` 时执行本阶段。
> **触发词：** `跑集成测试`、`集成测试执行`、`运行 E2E 测试`

### 5.1 前置条件（强制）

| 条件 | 检查方式 |
|------|---------|
| **Stage 1 全部通过** | `tests/test-reports/` 下存在最近一次 Stage 1 报告且全部通过 |
| **Stage 2 全部通过（如有 Web 端）** | `tests/test-reports/` 下存在最近一次 Stage 2 报告且全部通过 |
| **Stage 2b 全部通过（如有小程序端）** | `tests/test-reports/` 下存在最近一次 Stage 2b 报告且全部通过 |
| API 实现代码编译通过 | 后端项目编译 0 错误 |
| 前端代码编译通过 | 前端项目 build 0 错误 |
| 后端可独立启动 | 按项目配置登记的后端启动命令可成功启动（示例：`PYTHONPATH=src python -m uvicorn server.main:app`） |
| 前端可独立启动 | 按项目配置登记的前端启动命令可成功启动（示例：`cd src/{client-slug} && npx vite`） |
| 集成测试代码存在 | `tests/integration/{client-slug}/` 目录非空 |

> **任一前置条件未满足，Stage 3 不得启动。应报告缺失项并等待补充。**

### 5.2 执行步骤

> **服务启动原则：** 后端/前端的启动命令一律从项目配置读取——项目约定文档（如 AGENTS.md/README）、启动脚本、包管理配置中的 scripts 等；**禁止在执行中硬编码启动命令与端口**。本节出现的具体命令与端口均为示例（从配置读），实际以项目配置为准。

1. **检查 Stage 1 & 2/2b 通过状态**：确认项目端类型对应的前端测试阶段报告均为全绿
2. **启动后端服务**（后台运行）：启动命令从项目配置读取，下为示例（从配置读）：
   ```bash
   PYTHONPATH=src python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 &
   ```
3. **等待后端就绪**：轮询后端健康检查地址直到 200（地址/端口以项目配置为准）
4. **启动前端服务**（后台运行）：启动命令从项目配置读取，下为示例（从配置读）：
   ```bash
   cd src/{client-slug} && npx vite --port 5173 --strictPort &
   ```
5. **等待前端就绪**：轮询前端开发服务器地址直到 200（地址/端口以项目配置为准）
6. **执行集成测试**：

| 工具 | 执行命令 |
|------|---------|
| Playwright | `npx playwright test tests/integration/{client-slug}/ --config=playwright.config.ts` |
| Cypress | `npx cypress run --spec 'tests/integration/{client-slug}/**/*'` |

> **小程序端分支：** 小程序端不用 Playwright/Cypress，改用 wechatide automator 全集成模式（见 wechatide-skill），通过微信开发者工具操作真实小程序页面（后端仍为真实服务）。

7. **记录原始输出**
8. **失败 → 进入 §2.2 分类溯源 + §2.3 修复循环**（注意：修复后需重新走完整的启动→测试→停止流程）
9. **清理**：停止后端和前端服务
10. **关闭浏览器**：`browser_close`（杜绝残留 session）
11. **全部通过 → 输出 §5.3 报告**

### 5.3 Stage 3 报告

```markdown
# TDD 执行报告（Integration）：{客户端名}

> 日期：{YYYY-MM-DD} | Stage: Integration TDD | 执行者：tdd-execute skill

## 前置检查

| 阶段 | 状态 |
|------|------|
| Stage 1 (API TDD) | ✅ 全部通过（{date}） |
| Stage 2 (Page Mock TDD) | ✅ 全部通过（{date}） |
| Stage 2b (Mini Program TDD) | ✅ 全部通过（{date}） |

## 整体结果

| 指标 | 数值 |
|------|------|
| 测试文件数 | N |
| 总用例数 | N |
| 通过 | N |
| 失败 | 0 |
| 耗时 | Ns |

## 用户旅程覆盖

| 旅程 | 状态 | 涉及页面 | 涉及 API | Stage 1/2/2b 对照 |
|------|------|---------|---------|---------------|
| 旅程1：{名称} | ✅ 全通 | 3 个页面 | 5 个端点 | TC-001~005, TC-M001~003 |
| ... | ... | ... | ... | ... |

## 烟雾验证结果
| 旅程 | 状态 | 断点说明 |
|------|------|---------|
| 旅程1：{名称} | ✅ 全通 | — |
| 旅程2：{名称} | ✅ 全通 | — |

## 修复记录
...
```

**报告路径：** `tests/test-reports/integration-execute-report-{date}.md`

---

## §6 被外部过程调用的规范

tdd-execute 被以下上游过程独立调用。每次调用都按 Arguments 中的阶段参数执行。

### 6.1 被流水线调用

**调用场景与阶段参数：**

| 流水线步骤 | arguments | 说明 |
|-----------|-----------|------|
| API 代码完成后 | `api` | 仅执行 Stage 1，验证 API 实现 |
| Web 前端代码完成后 | `page-mock` | 仅执行 Stage 2，验证 Web 页面实现 |
| 小程序前端代码完成后 | `miniprogram` | 仅执行 Stage 2b，通过模拟器验证小程序页面 |
| 两端代码全部完成后 | `all` 或 `integration` | 先 Stage 1 → 按端类型执行 Stage 2/2b → Stage 3 全量执行 |

### 6.2 被 Review 修复循环调用

**调用者：** review skill，在每轮修复的所有 `✅ fix` 问题处理完毕后。

**期望输出：** 确认修复未引入新回归 + 更新测试报告。

### 6.3 被提交前守卫调用

**调用者：** 开发者或自动化 hook。

**期望输出：** 当前阶段全绿 → 允许提交；有失败 → 阻止提交。

### 6.4 被 TDD 迭代闭环调用（标准 §10.3c）

设计变更后：确定影响的阶段 → 按 arguments 执行对应阶段 → 验证修复 → 输出报告。

---

## §7 与流水线其他步骤的关系

| 步骤 | Stage 1 (API) | Stage 2 (Page Mock) | Stage 3 (Integration) |
|------|:---:|:---:|:---:|
| **tdd-build §8.5** | 上游：提供测试代码 | 上游：提供测试代码 | 上游：提供测试代码 |
| §8.6 API 实现 | **前置依赖** | — | **前置依赖** |
| §8.7 前端实现 | — | **前置依赖** | **前置依赖** |
| §9 复查门控 | 互相引用 | 互相引用 | 互相引用 |
| §10.3 变更传播 | 强制守卫 | 强制守卫 | 强制守卫 |

---

## §8 完成检查清单

| 检查项 | 要求 |
|--------|------|
| 当前阶段所有测试已运行 | 无遗漏文件 |
| 全部测试通过（0 失败） | 每个测试文件通过率 100% |
| 失败已分类溯源 | 每个失败有分类（测试问题/实现问题/设计问题/流程问题） |
| 修复循环记录完整 | 每轮修正有记录（轮次/用例/根因/修正内容/结果） |
| 修正涉及设计层时已通过对应 skill | 设计变更通过对应设计 skill，而非直接编辑设计文件 |
| 测试报告已输出 | `tests/test-reports/{stage}-execute-report-{date}.md` 存在，中文撰写 |
| Stage 3 额外检查 | Stage 1+2（+2b，如有小程序端）全绿确认、后端/前端服务正常启停、用户旅程全覆盖无断点 |
