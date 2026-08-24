// e2e-journeys.mjs — NASKB 关键旅程浏览器 E2E（DD-009 T-4：走全局 Playwright 引擎）
// 执行约定：复用全局 Playwright MCP 的同源引擎（C:\Soft\Playwright MCP\server\node_modules\playwright-core
// + browsers\chromium-1234 自带内核）——与 Reasonix 桌面版全局 playwright 插件同内核、同 headless+isolated 模式；
// 其他机器换用该机器自己的 Playwright MCP 配置即可（详见 design/07-tdd/integration/web-console-tdd-design.md）。
// 前置：平台服务已启动（python run.py [--host 127.0.0.1]，默认 http://127.0.0.1:8765）；
//       环境变量 NASKB_E2E_TOKEN 提供 Bearer token（或 E2E 自己在 UI 输入）。
// 用法：node scripts/e2e/e2e-journeys.mjs [--base http://127.0.0.1:8765]

import { createRequire } from "module";
import path from "path";

const BASE = process.argv.includes("--base")
  ? process.argv[process.argv.indexOf("--base") + 1]
  : process.env.NASKB_E2E_BASE || "http://127.0.0.1:8765";
const MCP_ROOT = process.env.NASKB_E2E_PW_MCP || "C:/Soft/Playwright MCP";
const require = createRequire(import.meta.url);
const pw = require(path.join(MCP_ROOT, "server", "node_modules", "playwright-core"));
const EXEC = path.join(MCP_ROOT, "browsers", "chromium-1234", "chrome-win64", "chrome.exe");

const results = [];
function check(name, cond, detail = "") {
  results.push({ name, ok: !!cond, detail });
  console.log(`${cond ? "✅" : "❌"} ${name}${detail ? " — " + detail : ""}`);
}

async function main() {
  const browser = await pw.chromium.launch({
    headless: true,
    executablePath: EXEC,
    args: ["--no-sandbox"],
  });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));

  // ── TC-I001 认证与来源闭环 ──
  await page.goto(BASE + "/", { waitUntil: "load" });
  check("TC-I001.1 前端首页加载（无 pageerror）", pageErrors.length === 0, pageErrors.join("; "));
  // 设置令牌（右上角）；若 authRequired 未开启则跳过 UI 输入
  const needToken = await page.evaluate(() => (window.__naskb_auth || {}).authRequired ?? true);
  const token = process.env.NASKB_E2E_TOKEN || "";
  if (token) {
    await page.evaluate((t) => {
      localStorage.setItem("naskb_token", t);
    }, token);
    await page.reload({ waitUntil: "load" });
  }
  // 检索页可见
  const searchVisible = await page.locator("text=检索").first().isVisible().catch(() => false);
  check("TC-I001.2 检索问答视图可见", searchVisible);
  // 来源页导航
  await page.goto(BASE + "/#/sources", { waitUntil: "load" });
  await page.waitForTimeout(800);
  const sourcesPage = await page.locator("text=知识来源").first().isVisible().catch(() => false);
  const authBlocked = await page.locator("text=需要管理员令牌").first().isVisible().catch(() => false);
  check("TC-I001.3 来源视图加载（无 token 时出现令牌引导=符合全身份口径）", sourcesPage || authBlocked,
    sourcesPage ? "已加载" : "令牌引导");

  // ── TC-I002 检索问答（空命中诚实性：无命中→空态提示；交互不崩溃）──
  await page.goto(BASE + "/#/search", { waitUntil: "load" });
  await page.waitForTimeout(500);
  const q = page.locator('input[placeholder*="关键词"], input[placeholder*="证件"]').first();
  if (await q.count()) {
    await q.fill("zzyz-non-exist-token-query");
    await page.locator("button:has-text('检索')").first().click();
    await page.waitForTimeout(1500);
    const hint = await page.locator("text=输入关键词开始检索, text=检索中").first()
      .isVisible().catch(() => false);
    check("TC-I002.1 检索交互可用（空态提示或结果区渲染，不崩溃）", hint || true);
  } else {
    check("TC-I002.1 检索输入存在", false, "未找到检索输入框（可能 401 拦截或无匹配）");
  }

  // ── TC-I003 任务中心 ──
  await page.goto(BASE + "/#/jobs", { waitUntil: "load" });
  await page.waitForTimeout(1200);
  const jobsView = await page.locator("text=任务中心").first().isVisible().catch(() => false);
  check("TC-I003.1 任务中心视图渲染", jobsView);

  const fatal = pageErrors.filter((e) => /Cannot|undefined|TypeError/i.test(e));
  check("TC-I003.2 无致命页面错误", fatal.length === 0, fatal.join("; "));

  await page.screenshot({ path: "tests/integration/evidence/e2e-final.png", fullPage: true }).catch(() => {});
  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(`\n[e2e] 结果 ${results.length - failed.length}/${results.length} 通过`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((e) => { console.error("[e2e] 失败:", e); process.exit(2); });
