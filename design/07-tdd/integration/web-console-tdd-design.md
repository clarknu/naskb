# TDD 设计（Integration）：web-console

> 基于 API TDD v1 | Page Mock TDD v1（规格） | 业务工作流 v1
> 日期：2026-08-24 | Stage: Integration TDD
> 出处：DD-009 T-4（E2E 保留，走全局 Playwright MCP；本机 C:\Soft\Playwright MCP，他机用各自配置）
> 执行前置：平台服务已启动（`python run.py --host 127.0.0.1`，WORKDIR 指向测试仓库）+ `NASKB_E2E_TOKEN`（或 UI 输入令牌）。

## 测试范围

| 用户旅程 | 涉及页面 | 涉及 API | 关键验证点 |
|---------|---------|---------|-----------|
| 认证 → 来源注册 → 扫描 → 检索 → 打开 → 预览 → 下载（TC-I001） | 来源/检索/浏览 + 文件模态 | POST/GET /api/sources、{sid}/scan、/api/kb/search、/api/files/{rid}(|download|preview) | 全身份口径下发证可用、流程端到端不中断 |
| 检索问答诚实性（TC-I002） | 检索问答 | GET /api/kb/search、POST /api/ask | 无命中/无 LLM 不编造；交互不崩溃 |
| 任务中心（TC-I003） | 任务 | GET /api/jobs、GET /api/jobs/{id} | 任务可见、结果可展开、2s 刷新 |

## 端到端测试用例

### TC-I001: 认证与来源闭环旅程
- **类型**: 用户旅程
- **涉及 Stage 1 测试**: TC-001~TC-007（01 域）、TC-P01~P09（06 域）
- **涉及 Stage 2 测试**: TC-M004~M009
- **操作序列**:
  1. 打开前端首页 → 无 pageerror（静态资源匿名放行）
  2. 若 token 需要：右上角输入 Bearer token 并保存（localStorage）
  3. 进入「来源」页 → 注册一个 local 临时目录来源（ro）→ 列表出现该来源
  4. 点击「扫描」→ 任务中心可见 scan 任务 → 完成（result 展示）
  5. 进入「检索」→ 检索该来源中文件关键词 → 命中列表出现
  6. 点击命中行 → 文件详情模态打开 → 预览区渲染（viewable 之一）
  7. 点击「下载」→ 下载代理返回文件（200/206/304）
- **断言清单**:
  - ✅ 首页与各视图 0 pageerror / 0 fatal console error
  - ✅ 来源注册成功（表单收起 + Toast + 列表出现）
  - ✅ 扫描任务 completed 且 result 含新增计数
  - ✅ 检索命中行含路径/分数/分类
  - ✅ 模态语义：元数据 kv + 预览区无“加载失败”
  - ✅ 下载响应 2xx/3xx 而非 401/403/500
- **证据**: `tests/integration/evidence/tc-i001-*.png`

### TC-I002: 检索问答诚实性旅程
- **类型**: 用户旅程（边界）
- **操作序列**:
  1. 「检索」输入无命中关键词 → 空态提示出现（不崩溃、不报错弹窗）
  2. 「问答」提问（无 LLM 配置/无命中场景）→ 页面显示明确错误或“未找到依据”，而非空白
- **断言清单**: ✅ 无命中走空态/兜底文案；✅ 错误呈现为页内 error 或文案（非静默白屏）
- **证据**: `tests/integration/evidence/tc-i002-*.png`

### TC-I003: 任务中心旅程
- **类型**: 用户旅程
- **操作序列**:
  1. 提交任一任务（如扫描）
  2. 进入「任务」页 → 表格出现该任务（kind/status/进度）
  3. 结果 details 展开 → JSON result 可见
- **断言清单**: ✅ 任务行渲染；✅ 状态徽章合法（pending/running/completed/failed）；✅ 结果展开无 JS 异常
- **证据**: `tests/integration/evidence/tc-i003-*.png`

## 执行方式（本机约定，DD-009）

1. **启动平台服务**（测试开工前）：`python run.py --host 127.0.0.1`（工作区配置测试 token：`NASKB_data/config.toml [server] tokens`；
   **隔离工作区样板**见 `tests/integration/e2e-work.config.example.toml`——复制为 `config.toml` 后
   `python run.py --work <隔离目录> --port 8877`，避免污染生产工作区；`NASKB_E2E_TOKEN` 对应输入）。
2. **驱动**：全局 Playwright MCP server（本机 `C:\Soft\Playwright MCP`）——Reasonix 桌面版全局 playwright 插件（`--headless --isolated --executable-path C:\Soft\Playwright MCP\browsers\chromium-1234\...\chrome.exe`）提供 browser_* 工具；或直接运行等价驱动脚本：
   ```
   node scripts/e2e/e2e-journeys.mjs [--base http://127.0.0.1:8765]
   ```
   （脚本复用同一全局 MCP 引擎：playwright-core@1.63 + chromium-1234，与 MCP server 同内核同 headless/isolated 模式。）
3. **他机**：换用该机器自己的 Playwright MCP 配置（`%APPDATA%\reasonix\config.toml [[plugins]] playwright`），旅程规格不变。
4. 验证后 `browser_close`（§8.10b 浏览器生命周期）。
