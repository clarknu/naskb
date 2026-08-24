// viewer-smoke.mjs — NASKB 设计资产 viewer 渲染核实（document-asset-format §6 强制验证流程）
//
// 与官方门禁的分工（2026-08-24 对齐核实）：
//  - 官方 `_shared/viewer-tests/verify-fixed.mjs`：验证 **方法论 bundle 自带模板 viewer**
//    （skills/*/templates，5 技能：business-workflow/entity-relationship/mobile-app-design/
//    desktop-ui-design/backend-architecture-design）——本机实测 5/5 PASS（0 console error、
//    0 pageerror、emptyTexts 空）。注意其用例清单不含 api-design（本轮项目 api-viewer 由本脚本覆盖，
//    如需官方工具覆盖 api-design 模板，需在 bundle 侧登记（用户工作，未代改）。
//  - 本脚本：验证 **本项目设计资产 viewer**（design/02..06 的 viewer + data/*.js，含 api-viewer），
//    断言 0 console error、0 pageerror + 关键内容渲染命中。
//
// 执行约定（同 e2e-journeys.mjs）：复用全局 Playwright MCP 同源引擎（C:\Soft\Playwright MCP\
// server\node_modules\playwright-core + browsers\chromium-1234 自带内核）；其他机器用该机自己的
// Playwright MCP 配置（环境变量 NASKB_E2E_PW_MCP 指向 MCP 根）。无需 .scratch/pw 一次性安装。
// 用法：node scripts/viewer-smoke.mjs
import { pathToFileURL } from "url";
import path from "path";
import { createRequire } from "module";

const MCP_ROOT = process.env.NASKB_E2E_PW_MCP || "C:/Soft/Playwright MCP";
const require = createRequire(import.meta.url);
let pw;
try {
  pw = require(path.join(MCP_ROOT, "server", "node_modules", "playwright-core"));
} catch {
  console.error(`[viewer-smoke] 需要全局 Playwright MCP 引擎（未找到 ${MCP_ROOT}）；其他机器设置 NASKB_E2E_PW_MCP 指向该机 MCP 根。`);
  process.exit(2);
}
const EXEC = path.join(MCP_ROOT, "browsers", "chromium-1234", "chrome-win64", "chrome.exe");

const targets = [
  { name: "workflow-viewer", file: "design/02-business-workflow/workflow-viewer.html",
    expect: ["来源管理", "采集与分析", "主流程", "权限清单"], mode: "load" },
  { name: "er-viewer", file: "design/03-entity-relationship/er-viewer.html",
    expect: ["跨域全景", "来源管理", "知识资源"], mode: "wait" },
  { name: "api-viewer", file: "design/04-platform-api/api-viewer.html",
    expect: ["来源管理", "注册来源", "公共约定"], mode: "wait" },
  { name: "architecture-viewer", file: "design/05-backend-architecture/architecture-viewer.html",
    expect: ["系统拓扑", "L3"], mode: "wait" },
  { name: "design-viewer(06-web-console)", file: "design/06-web-console/design-viewer.html",
    expect: ["功能结构树", "检索问答", "知识来源"], mode: "wait" },
];

const root = path.resolve(process.cwd());
const browser = await pw.chromium.launch({ headless: true, executablePath: EXEC, args: ["--no-sandbox"] });
let failures = 0;
for (const t of targets) {
  const page = await browser.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  const url = pathToFileURL(path.resolve(root, t.file)).href;
  try {
    await page.goto(url, { waitUntil: "load", timeout: 20000 });
    if (t.mode === "wait") await page.waitForTimeout(1500);
    const body = await page.evaluate(() => document.body ? document.body.innerText : "");
    const missing = t.expect.filter((s) => !body.includes(s));
    const ok = errors.length === 0 && missing.length === 0;
    console.log(`${ok ? "✅" : "❌"} ${t.name} errors=${errors.length} missing=[${missing.join(",")}]`);
    if (!ok) {
      console.log("    内容抽样：", body.slice(0, 220).replace(/\n/g, " │ "));
      errors.forEach((e) => console.log("    " + e));
    }
    if (!ok) failures++;
  } catch (e) {
    console.log(`❌ ${t.name} 加载失败: ${e.message}`);
    failures++;
  }
  await page.close();
}
await browser.close();
process.exit(failures ? 1 : 0);
