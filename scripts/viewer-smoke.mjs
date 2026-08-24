// viewer-smoke.mjs — SFDS viewer 渲染核实（document-asset-format §6 强制验证流程）
// 用法：
//   1) 一次性依赖：mkdir .scratch/pw && cd .scratch/pw && npm init -y && npm i playwright（浏览器走 playwright 缓存）
//   2) node scripts/viewer-smoke.mjs
// 断言：file:// 打开 5 个 viewer（workflow/er/api/architecture/design-viewer），0 console error、0 pageerror、
//       关键内容（域列表/端点/公共约定/架构/L3/功能树）渲染命中。
import { pathToFileURL } from "url";
import path from "path";
import { createRequire } from "module";

// playwright 依赖：优先本机项目安装，其次 .scratch/pw（一次性环境：npm i playwright）
let pw;
try {
  pw = await import("playwright");
} catch {
  const require = createRequire(import.meta.url);
  try {
    pw = require(path.resolve(".scratch", "pw", "node_modules", "playwright"));
  } catch {
    console.error("[viewer-smoke] 需要 playwright：.scratch/pw 下 `npm i playwright`（浏览器走 playwright 缓存）");
    process.exit(2);
  }
}
const { chromium } = pw;
const root = path.resolve(process.cwd());const targets = [
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

const browser = await chromium.launch();
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
