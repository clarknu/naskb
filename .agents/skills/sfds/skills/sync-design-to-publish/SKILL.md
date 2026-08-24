---
name: sync-design-to-publish
version: 1.1.0-arb.1
description: 将 design/ 下的设计文档查看器同步到发布目录并部署到统一的"设计文档域名"下的本项目节点（单一终结点）。方法论标准环节（CASE-009 泛化）：终结点唯一，项目差异全部外置为配置（project-slug、目标节点），禁止硬编码项目名。
lineage:
  origin: arb-hub
  case: CASE-009
  sources: {zy-ai-consult: 51FCDC5BAE70}
  note: 由"项目专属"转正为方法论标准环节；删除写死的智能床/Cloudflare 项目名，改固定域名+单终结点+每项目节点（project-slug）。
---

# Sync Design to Publish

> **通用方法论环节（CASE-009 泛化）。** 各项目用统一的"设计文档域名"承载自己的设计稿：每个项目是
> 该固定域名下的一个节点（`<固定域名>/<project-slug>/`），各项目自行同步、自行推送自己的节点。
> **终结点（发布端点）是唯一的**——一个固定域名 + 一个部署入口；项目差异（project-slug、
> 目标子路径、托管方式）全部外置为配置，禁止在技能内硬编码任何项目名或路径。

将最新的设计文档从 `design/` 目录同步到发布目录所需文件，然后通过项目配置读取的终结点/项目节点部署。

## 触发条件

当用户表达以下意图时调用此 Skill：
- "同步设计文档到发布目录"
- "发布设计文档"
- "更新 publish"
- "把最新的设计同步过去"

## 前置配置（项目初始化时一次性完成）

统一"设计文档域名"由基建提供；**单项目只需配置自己的节点（project-slug）与终结点**。依赖项目配置文件
（如 `release/design-publish.yaml` 或 `package.json` 扩展字段）中的三样东西：

- `project-slug`：本项目的节点名，发布到 `<固定域名>/<project-slug>/`；
- `endpoint`/`site`：唯一终结点（托管目标），各项目共用同一个；
- `publish` 目录：design/ 同步出来的静态文件目录。

示例（配置驱动，禁止硬编码项目名）：

```yaml
project-slug: <项目slug>
site: <固定设计文档域名或终结点标识>
publish-dir: publish
```

> 部署命令对应示例（wrangler Direct Upload 或其他静态托管——以终结点配置为准）：
> `npm run deploy` 读取上述配置（不写死项目名/路径）。

部署需要两个环境变量。**Agent 不得在 skill 内硬编码凭证**，一律按以下优先级获取：
1. 检查 `$env:CLOUDFLARE_API_TOKEN` / `$env:CLOUDFLARE_ACCOUNT_ID` 是否已设置
2. 若未设置，提示用户在终端设置后重试（或从项目 `.env` / 安全配置读取，禁止写入本 skill）
3. Agent 在执行 Step 5 部署前，确认环境变量就绪后执行 `npm run deploy`。**凭证缺失时不得自行猜填或跳过**。

> Agent 执行命令时按以下模式（凭证来自环境变量，不在 skill 中）：
> ```powershell
> $env:CLOUDFLARE_API_TOKEN = "<从环境/配置读取>"
> $env:CLOUDFLARE_ACCOUNT_ID = "<从环境/配置读取>"
> npm run deploy
> ```

> 更换项目：只需在项目配置中改 `project-slug` / `site`（终结点），无需改动本技能。

## 映射表

| 源文件 | 目标文件 |
|--------|---------|
| `design/02-business-workflow/workflow-viewer.html` | `publish/workflow/index.html` |
| `design/02-business-workflow/data/*.js` | `publish/workflow/data/*.js` |
| `design/03-entity-relationship/er-viewer.html` | `publish/er/index.html` |
| `design/03-entity-relationship/data/*.js` | `publish/er/data/*.js` |
| `design/03-entity-relationship/d3.v7.min.js` | `publish/er/d3.v7.min.js` |
| `design/index.html` | `publish/index.html` |
| `design/04-platform-api/api-viewer.html` | `publish/api/index.html` |
| `design/04-platform-api/data/*.js` | `publish/api/data/*.js` |
| `design/04-platform-api/data/rest/*.js` | `publish/api/data/rest/*.js` |
| `design/04-platform-api/data/iot/*.js` | `publish/api/data/iot/*.js` |
| `design/04-platform-api/data/internal/*.js` | `publish/api/data/internal/*.js` |
| `design/04-platform-api/data/ai-tools/*.js` | `publish/api/data/ai-tools/*.js` |
| `design/05-backend-architecture/architecture-viewer.html` | `publish/architecture/index.html` |
| `design/05-backend-architecture/data/*.js` | `publish/architecture/data/*.js` |
| `design/06-web-admin/design-viewer.html` | `publish/web-admin/index.html` |
| `design/06-web-admin/data/*.js` | `publish/web-admin/data/*.js` |

> 额外依赖：如果设计目录中有映射表未涵盖的依赖文件（如 `d3.v7.min.js`），也需一并复制到对应 publish 子目录。

## 执行流程

### Step 1: 确认同步范围

问用户要同步全部 5 个查看器还是指定某一个。如果用户在同一条消息里已经指明范围，跳过此问。

选项：
- 全部 5 个（默认）
- 单独指定（workflow / er / api / architecture / web-admin）

### Step 2: 执行文件复制

按映射表，用 shell 命令批量复制。Windows 用 `Copy-Item -Force`，macOS/Linux 用 `cp`。

### Step 3: 本地验证

用 Playwright `browser_run_code_unsafe` 以 `file://` 协议加载每个**被更新的**查看器 index.html，确认：
- 页面 title 正确
- 数据加载成功（域名下拉/菜单渲染正常）
- 0 console errors

### Step 4: Git 提交

```bash
git add publish/
git commit -m "同步设计文档到 publish/：{简述本次变更内容}"
```

### Step 5: 部署到本项目节点（单一终结点）

> 部署方式为静态上传（wrangler Direct Upload 或其他托管的唯一终结点），只上传 `publish/` 目录的静态文件。

1. 从项目配置读取 `project-slug` 与 `site`（终结点），确认为本项目的正确节点。
2. 检查环境变量 `CLOUDFLARE_API_TOKEN` 和 `CLOUDFLARE_ACCOUNT_ID` 是否已设置
3. 若未设置，提示用户设置后执行 `npm run deploy`
4. 若已设置，直接执行 `npm run deploy`
5. 输出部署结果 URL，用 Playwright 快速验证线上 5 个 viewer 的首页加载正常

## 重要约束

- **只复制文件，不修改文件内容**。设计文档的路径依赖（`data/xxx.js`、`protocols/xxx.js`）保持不变，因为发布目录结构与设计目录结构一致。
- **不复制非 .js 的 data 文件**（如 CHANGELOG.md），保持 publish/ 干净。
- **保留 publish/index.html 首页**，同步不覆盖首页。
- 如果用户新增了设计域（如 `design/08-xxx/`，注意 `07-tdd/` 已被占用）并希望发布，需先更新 publish/ 目录结构和首页导航。这种情况下告知用户需要手动扩展映射表。

## 浏览器生命周期（铁律）

> 本 Skill 的验证步骤（Step 3）使用 Playwright 外部浏览器。**验证完成后必须调用 `browser_close` 关闭浏览器**，杜绝旧 session 残留、端口占用、缓存干扰。下次启动时从干净环境开始。同一 turn 内如果 Skill 自身已 `browser_close`，无需重复关闭。
>
> **统一规则见 development-standard §8.10b「浏览器生命周期」**——本处为 Skill 内局部重申。
