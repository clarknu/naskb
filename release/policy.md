# NASKB 发布规则（release/policy.md）
# 依据：release-management（通用方法论）——本文件只承载项目侧数据（命令/路径/清单）。

## 一、门禁 9 项（不满足不发）

| # | 门禁 | 本项目命令/证据 |
|---|------|----------------|
| 1 | 全量测试绿 | `python -m pytest tests/ -v`（重组后目录：tests/api unit integration；0 失败） |
| 2 | e2e 绿 | 浏览器 E2E（保留，DD-009）：执行入口 = **全局 Playwright MCP server**（本机 `C:\Soft\Playwright MCP`，Reasonix 桌面版全局配置；他机用该机自己的 Playwright MCP 配置）；旅程规格 `design/07-tdd/integration/web-console-tdd-design.md`（TC-I001~I003）；证据截图 `tests/integration/evidence/` |
| 3 | ORM-DB 无差异 | 无 ORM/迁移工具：`python -m pytest tests/integration/test_pgstore.py -v`（真 PG schema 断言）+ 人工核对 pgstore _DDL_* 与库结构 |
| 4 | 迁移预演 | dev 环境先跑 `_ensure_pg_table` 链（幂等建表成功）后再发 prod（fail-fast 闸门） |
| 5 | 密钥齐全 | 目标环境 config.toml 含 [server] tokens + [llm.*] api_key；不入库、不随分发 |
| 6 | CHANGELOG 更新 | 本版本条目已写入 `release/CHANGELOG.md` |
| 7 | 健康检查 | 部署后 `GET /api/config/public` 200 + `GET /api/stats` 200（+ 前端首页 200）——**裁剪口径（DD-009）：不实现专用 /api/health** |
| 8 | 目标环境全量回归 | API 端点回归（认证 → /api/sources 断言 200 + 带参种子补测）+ 关键旅程冒烟：来源注册→扫描→检索→问答→预览→下载；环境对比（发 prod 时 dev 仍 200） |
| 9 | 架构契约校验（L2+） | `python -m pytest tests/test_arch_contract.py -v`（退出码 0 = 机械全过 + 债务未到期） |

> 时间安排（测试先行）：门禁 1/9 在发布前本地跑完；发布后回归 = 快速部署验证 + 目标环境冒烟。

## 二、版本与 Tag

- SemVer `X.Y.Z`（pyproject version 与 server VERSION 同步维护）。
- tag：发布到 prod 后打 `vX.Y.Z`；预发布 `vX.Y.Z-beta.N`。
- 分支：main 直发 + tag；大版本（X 变更）开 `release/vX.Y` 收敛；禁止在 tag 上改代码。
- 发布动作：tag + CHANGELOG 追加 + 记录回滚点（tag + schema 版本）。

## 三、标准发布流程（本项目）

1. 门禁 1/3/9 本地执行（pytest 全量 + 集成 PG + 架构契约）
2. bump 版本 + 更新 release/CHANGELOG.md
3. （如 schema 变更）改 pgstore DDL 常量 → 人工 review → dev 库验证
4. 构建发布产物：拷贝 naskb/ + NASKB_data/config.toml（目标环境独立密钥）+ Python 环境
5. 目标环境执行：启动 run.py（或常驻方式）→ 健康检查（门禁 7）→ 冒烟
6. 门禁 8 目标环境回归 + 环境对比
7. `git tag vX.Y.Z` + `git push --tags`
8. 记录回滚点

## 四、部署纪律（CASE-007 教训固化）

1. 部署/诊断脚本入口显式 UTF-8（Windows 控制台 GBK 风险）。
2. 依赖清单完整（pyproject optional-dependencies 分组：server/analyze/llm/media/vectors/pg/mcp/test——按环境安装）。
3. 敏感值传递防特殊字符截断（config.toml 直写；环境变量注入时转义）。
4. 发布脚本对机密操作幂等（配置/密钥生成重复执行不得不一致）。

## 四b、安全边界（DD-009 直链契约）

- 平台 API：全部端点需 Bearer token（例外：`/`、静态资源、`/api/config/public`、`/api/docs`、`/api/openapi.json`、`/api/files/{rid}/download` 直链）。
- **直链不认证**：MCP 生成的下载直链（kb_get_file_url/kb_fetch_file）无 token——**安全边界=外围网关层 IP 约束与限流**：部署时平台服务仅监听内网/受控网段或经网关反代；公网暴露前必须在网关配置 IP 白名单（Nginx/防火墙），否则视为违规暴露。

## 五、回滚

| 场景 | 动作 |
|------|------|
| 代码问题 | 切回上一 tag → 重走发布流程 |
| schema 问题 | 回退 DDL（幂等建表 + 保留数据）→ 修 DDL → 重新发布 |
| 服务故障 | 停止服务回退旧版本（单进程形态，简单物理回退） |
