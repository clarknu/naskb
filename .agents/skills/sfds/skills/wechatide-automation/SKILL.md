---
name: wechatide-automation
description: "微信开发者工具（wechatide）在 SFDS 方法论中的使用与小程序自动化测试说明。核心是一道能力门：能探测到外置 wechatide 工具（CLI）→ 可做小程序自动化测试，并给出可执行做法（含多端并存同步测试、CLI 位置参数语法、门禁流程、令牌与异常恢复、踩坑）；探测不到 → 自动化做不了，必须明确告知并补充/安装工具。属于编排/工具层技能，drives tdd-execute Stage 2b 与小程序调试。"
whenToUse: "用户涉及微信小程序开发调试、小程序自动化测试、多端（多个小程序模拟器）同步交互测试，或在 tdd-execute Stage 2b 需要跑小程序测试；也用于判断『当前环境能不能做小程序自动化』。"
lineage:
  origin: arb-hub
  case: CASE-011
  source: inbox/boxing-competition-operation/wechatide-setup@2026-08-23（泛化吸收）
  note: 本技能为方法论层通用版，泛化自 boxing wechatide-setup 的可复用内容；boxing 专属连接参数/端口/AppID 保留在其项目实例中。
---

# WeChat IDE 自动化（使用说明）

本技能说明如何用**外置的微信开发者工具（wechatide）**做小程序开发调试与自动化测试（含多端同步）。工具本体是外部件（随 DevTools 单向同步）；本技能是**使用与判定说明**，是 boxing `wechatide-setup` 的可复用泛化。

> 角色分工：本技能（方法论层：怎么用、怎么判定）· `wechatide-skill`（外部同步的根入口，其 `environment-readiness` 为门禁/令牌权威）· 项目实例（连接参数、端口、AppID，见各项目 harness 配置）。

## 能力门（第一步必须判）

```bash
wechatide --version           # 或
wechatide -c <clientName> check_wechatide_status --skill-version <version>
```

| 探测结果 | 结论 |
|---|---|
| `wechatide` 可用，`check_wechatide_status` 返回 `loginExpired: false` 且 `versionRelation: equal` | **可做小程序自动化测试** —— 走下方「可自动化」 |
| 工具不可用 / 未安装 / 版本不匹配 / 未登录 | **做不了** —— 走「不可自动化」分支：明确告知、降级为人工验证，或先补充/安装工具 |

> **原则：工具不存在时不假装能做自动化。** 要么补齐，要么把该阶段标记为「人工验证（工具缺失）」放行/阻塞，绝不可断言测试通过。

## 可自动化 → 具体做法

### 前置（一次性人工）
① 在 DevTools「设置 → 安全」开启「服务端口」；② 首次 `cli login` 扫码一次。此后登录态持久化，自动化拉起全程免扫码、免手工。

### 拉起与关闭（唯一约定）
DevTools 由 agent 用项目内 harness 按项目自动拉起/关闭，**用户不再逐个手开、不再扫码**：

```bash
node tests/miniprogram-harness/bin/harness.js up <projectId>     # 拉起并驻留（身份校验/专属端口）
node tests/miniprogram-harness/bin/harness.js down <projectId>   # 关窗、释放端口
node tests/miniprogram-harness/bin/harness.js status             # 登录态只读 + 各端口在线
node tests/miniprogram-harness/bin/harness.js smoke <id> [--page p] [--selector s] [--expect-text t]  # 一键闭环+断言
node tests/miniprogram-harness/bin/harness.js test <id>          # up → 跑该项目回归套件 → down
```

- 若直接调 `wechatide` 报 `MCP service is not reachable` → DevTools 未运行，**先 `harness up` 拉起**再继续。
- 通用性：新增项目只需在 `tests/miniprogram-harness/config.js` 的 `projects` 加 `(path, appid, autoPort)` 条目。

### 多端同步交互测试（多个小程序模拟器并存）
跨端流程（审批、邀约、客服会话、发布→可见、状态→可见等）需要**多端模拟器同时运行并交互**：

```bash
# 分别打开多端窗口——【用 cli open，不要用 cli auto，见坑#1】
"<DevTools>\cli.bat" open --project <abs>\src\miniprogram-operation
"<DevTools>\cli.bat" open --project <abs>\src\miniprogram-customer
# 或用 harness（内部走 cli auto）：
node tests/miniprogram-harness/bin/harness.js up operation
```

- **驱动各端**：`wechatide -c <clientName> <tool> --project <abs 路径>`，MCP 桥按 `--project` 定位目标实例；
- **跨端数据**：多端通过**共享后端**（如 `localhost:5164`）交换——一端写、另一端**重新进入/刷新页面**后读取（小程序页面不自动刷新）；
- **多端场景落点**：`tests/miniprogram-<端>-autotest/suites/multiend_*.py`，驱动层 `lib/multiend.py`；三端并存验证入口 `tests/miniprogram-harness/bin/multiend.js`。

### CLI 调用语法（铁律：位置参数）

```powershell
wechatide -c <clientName> <toolName> [flags...] [--token <cliAccessToken>]
```

- 工具名用**位置参数**；**禁用 `-t <tool>` 旧语法**；参数用 `--project <绝对路径>`；对工具名不确定先 `wechatide <tool> -h` 或查 tool-index / tools.yaml。
- 常用：`check_wechatide_status` / `simulator_refresh` / `simulator_open_page` / `automation_navigate --action <navigateTo|switchTab|redirectTo|back>` / `automation_page_action --action <getData|tap|input>` / `automation_element_action --action <tap|wxml> --selector` / `automation_evaluate --fn-source` / `simulator_screenshot --path evidence/<tc>.png` / `debug_clear_cache --action cleanAll` / `get_simulator_console`。

### 门禁流程（每次会话一次）
```
check_wechatide_status --skill-version <from frontmatter>
  → versionRelation: agent_behind → 从内置整目录覆盖 agent 侧后重载
  → loginExpired? 是 → login 扫码 → 重查
  → tokenRequired? 是 → 见令牌；完整分支见 wechatide-skill environment-readiness
```
版本取 `wechatide-skill/SKILL.md` frontmatter 顶层 `version`，**勿硬编码、勿读 skill.yaml**。

### CLI 访问令牌（tokenRequired）
- 已有记忆中的 token → 直接复用，不再询问；
- 无 token 且 `tokenRequired: true` → 询问用户提供「设置 → 安全」中的令牌，停在门禁；
- **禁止猜测、禁止从 DevTools 侧翻找、不得写入项目仓库**。

## 异常恢复

| 现象 | 处理 |
|---|---|
| `MCP service is not reachable` | DevTools 未运行 → 先 `harness up <projectId>`，就绪后重试 |
| `cli auto` 失败 / 端口被占 | `harness down <id>` 清理，再 `up <id>`；或改 config 的 `autoPort` |
| 身份校验超时 | 新项目首编较慢，harness 已自动重试；仍失败确认 `config.js` 的 `appid` 与 `project.config.json` 一致 |
| `timeout waiting for automator response` | 模拟器编译中，等几秒重试 |
| 页面缓存问题 | `debug_clear_cache --action cleanAll` 后重试 |
| `CONNECT_ERROR` / `AUTH_*` | 必要时 `wechatide auth -c <clientName>` |

## 踩坑记录（重要经验）

1. **`cli auto`（启用自动化端口）在开发态经常卡死**（停在“IDE may already started/等待端口”）；**多端/日常一律 `cli open`**（普通窗口），MCP 桥在普通窗口稳定；automator-WS 路径（`smoke`/`multiend`）依赖 `cli auto`，偶发卡死先 `harness quit` 重试。
2. `cli open` 冷启动也可能先报“IDE may already started at 27720”，但它会自动恢复（√ open），不是失败。
3. **身份确定性**：登录态持久化 + DevOverrides 钉身份（不同端绑定不同测试账号）；多端用例身份是确定的。
4. **缓存会骗人**：代码修改后页面无变化 → `cleanAll` 清缓存。
5. **`setData` 路径语法有坑**：`'obj.key'` 可能失效，改用 `Object.assign` 创建新对象。
6. **同名函数覆盖**：Page 中第二个同名函数覆盖第一个；不同弹窗用不同函数名。
7. **`bindinput` 被 setData 触发**：改 input 的 value 会触发 bindinput 死循环 → 改用 `bindblur`。
8. **harness 拉起后直接可连**：`up` 后 MCP 随 GUI 自动运行；首次 `check_wechatide_status` 等几秒桥接。
9. **内部实现稳健性**：`lifecycle.js` 的 `runCli` 不用 `cmd /d /c cli.bat`（Windows 下间歇挂起），而是用 `ELECTRON_RUN_AS_NODE=1` 直接调起 Electron 的 cli/index.js。
10. **已知竞态**：DevTools 已在 `27720` 运行时的 `cli auto` 偶发挂起（DevTools 自身状态问题），`harness up` 卡住则先 `quit` 再 `up`。

## 不可自动化 → 补充路径

- 未安装 → 引导安装/同步 wechatide 工具（其自身有 installer/初始化子命令），完成后重走能力门；
- 已装但无登录态 → `login`（新版异步：返回 taskId 后 `polling_task_result` 轮询）；
- 确实无法提供工具 → 把小程序自动化阶段标记为「人工验证（工具缺失）」，放行前提是人已实测或明确接受风险。

## 边界

- 本技能**不含 wechatide 工具自身实现**（在外部件里）；只定义「能否判定 + 怎么驱动 + 不能时怎么办」。
- 小程序自动化是 tdd-execute Stage 2b 的一部分；其余阶段（API/Page Mock/Integration）不受影响。
