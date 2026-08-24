# 剩余问题与差距清单（Remaining Issues）

> 维护：review skill（归档门控，§6）。本文件登记已确认但暂不修复/待后续迭代的问题；
> 正式全量 Review（D0-D12）执行后，其 planned/suggest 类问题并入本文件。
> 日期：2026-08-24 ｜ 状态：存量接入初始基线

## 一、方法论 Bundle 层问题（外部依赖，本项目不修复，供方法论升级参考）

> 完整版报告（含文件+行号定位、实测证据、修复与验收建议、10 项补充核查项）：
> `docs/sfds-bundle-issues-report-2026-08-24.md`（可直接移交方法论项目）。
> **✅ 2026-08-24 已移交完成（用户搬运）**：方法论项目已在本仓库 bundle 内落地对应修复——
> `_shared/viewer-tests/verify-fixed.mjs`（M-02）、共享 §3 注册 `raw-input-to-*`（M-05）、
> registry 改名 `wechatide-automation`（M-04）、api-design loader 模板（M-01 配套）、
> arch-contract 模板重写对齐规范（A4）等；本区问题在方法论项目侧闭环，项目侧不再跟踪。
>
> **2026-08-24 更新**：六项主问题（M-01~M-06）已按报告建议修复并回填方法论母本（`packages/sfds-methodology-bundle`），并已同步到本项目 `.agents/skills/sfds`（母本与项目副本逐文件一致）。报告附表的 10 项补充核查项（A1~A10）也已在同批次修复。本节保留原登记作回溯，处置列更新为「✅ 已修」。

| 编号 | 问题 | 影响 | 处置 |
|------|------|------|------|
| M-01 | api-viewer.html 为 REST-only：不渲染 protocol-*/AI Tools 视图（api-design §9 的协议 Tab 为参考实现未落地于模板） | ai-tools/tools.js、rest/protocol.js 无渲染视图，人工以数据文件查阅 | ✅ 已修（2026-08-24：SKILL 定性为 REST 参考实现/协议视图规划中 §10.5 🟡；补齐 templates/loader.js） |
| M-02 | document-asset-format §6 要求的 `tools/viewer-tests/verify-fixed.mjs` 在 bundle 中不存在 | viewer 验证缺少官方脚本 | ✅ 已修（2026-08-24：补 `_shared/viewer-tests/verify-fixed.mjs` + 更新路径） |
| M-03 | 生成脚本/文档路径按扁平布局（`.agents/skills/_shared/…`）而实际为伞形（`.agents/skills/sfds/_shared/…`） | AGENTS.md 生成注释中的路径与 bundle 路径不一致（不影响运行——生成时已用实际路径） | ✅ 已修（2026-08-24：bundle 内路径统一伞形 `sfds/…` + 父技能「全 bundle 通用路径约定」） |
| M-04 | pipeline-registry 登记名 `wechatide-skill` 与 bundle 技能名 `wechatide-automation` 不一致 | 铁律表显示名与技能名不同（本项目无小程序端，不影响） | ✅ 已修（2026-08-24：登记名统一 `wechatide-automation`；`wechatide-skill` 明确为 WeChat IDE 自带外部工具技能，见 wechatide-automation 文首「概念区分」） |
| M-05 | review SKILL 引导 `raw-input-to-*` source 未在共享 §3 注册表登记 | 若执行该维度需先注册枚举（本项目执行 review 时按"先注册后使用"处理） | ✅ 已修（2026-08-24：共享 §3 登记 `raw-input-to-workflow/er/frontend`） |
| M-06 | 一致性检查输出形态差异：tdd-build §6.4 自有 JSON 结构未含共享规范的 ref_path/source 字段 | 汇总时按共享规范归一化 | ✅ 已修（2026-08-24：tdd-build §6.4 对齐共享 §1 + §2 登记全部 type） |

## 二、本项目差距清单（待后续迭代/Review）

| 编号 | 差距 | 优先级 | 建议处置 |
|------|------|--------|---------|
| G-01 | 前端 Page Mock 执行层缺失（无 vitest/MSW 工具链） | 中 | ✅ 已解决（2026-08-24 P-002：已接入 vitest+@vue/test-utils+jsdom+fetch mock（等价 MSW）；**2026-08-24 P-002 补全：TC-M003/M006/M007/M010 落地，TC-M001~M010 10/10 全覆盖**（套件 21 + 初始化时序 2 全绿），见 tests/page-mock/web-console/ 与 design/07-tdd/page-mock/web-console-tdd-design.md） |
| G-02 | 平台 API 匿名口径不一致（7 项差异，见 design-code-gap.md） | 高 | Review D7/仲裁后修代码或修 _conventions 声明 |
| G-03 | 服务端频控未实现（模板 G1-G5 为演进项） | 低 | 登记为演进项（resilience-policy/rate-limit） |
| G-04 | 健康检查端点未实现（observability-policy 已登记） | 低 | 演进项 |
| G-05 | 真实标准文档（20-30 条）深析人工验证未做（当前合成基准 9 题） | 中 | ✅ 已闭环（2026-08-24 A1）：**真实文档验证 2 份/6 题，条款级 6/6 全中（人工真值）**——合同 5 题精确到「第几条第几款」+ 聚合根题两级引用（第2章 聚合）；摘要级 5/6（聚合根细节未覆盖=第二层价值实证）；详见 tests/test-reports/deep-eval-real-docs-2026-08-24.md。规模说明：验证按「真实样本起验证基准」执行（原文口径 20-30 条为理想面，采样 2 份覆盖文本层/扫描件两类形态） |
| G-06 | SMB/NFS/iSCSI 直连未实现（R7-04） | 中 | ✅ 已收口（2026-08-24）：挂载型协议一律走「OS 挂载 → 注册 local 源」（指南见 README「知识源接入」节）；应用层 SMB 直连=可选未启用（代码桩在，启用前需补测试/语义/文档） |
| G-07 | Min 数据库多存储协议适配测试无 | 低 | 设计上交由外部环境 |
| G-08 | CLI 28 命令无独立测试（仅主链路间接覆盖） | 中 | ✅ 已补（2026-08-24）：命令面完整性测试 unit/test_cli_commands.py（44 例：注册完整/--help/参数门面/错误路径/廉价冒烟，见 07-tdd/api/06-platform-console-tdd-design.md TC-C01~C06） |
| G-09 | ~~viewer 渲染核实（file:// 打开 5 个 viewer）~~ | — | ✅ 已解决：scripts/viewer-smoke.mjs（0 error + 内容命中；基线见 tests/test-reports/baseline-2026-08-24.md） |
| G-10 | pipeline-controller `.pipeline/` 未激活（opt-in 手势） | 低 | 需要时按 bootstrap 流程 |

## 三、待决问题（2026-08-24 已全部拍板，见 user-decisions-pending.md）

| 编号 | 问题 | 拍板结果（2026-08-24） |
|------|------|------------------------|
| D-01 | `GET /api/sources/{sid}/report` 死代码：修复接线还是移除声明？ | **接回实现**（一致性报告要做） |
| D-02 | `/api/folder` 孤儿匿名前缀：删除还是补实现？ | **补实现**（目录级描述端点） |
| D-03 | 匿名口径：POST /api/ask、/api/kb/ask 是否匿名？ | **全部需身份**（干掉匿名；/api/config/public、/api/docs 保留引导，待确认） |
| D-04 | 多 token 仅首个有效 | **声明单 token**（随 D-03 处置） |
| D-05 | 深析开关关闭后既有 chunk 行是否清理？ | **清理**（UI 加确认提示） |
| D-06 | source 密码加密存储 | **登记长期债**（V2 加密） |
