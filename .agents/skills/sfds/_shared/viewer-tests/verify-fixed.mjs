#!/usr/bin/env node
// verify-fixed.mjs — Viewer 回归门禁脚本（document-asset-format.md §6.2 强制验证流程 第 3 步的门禁工具）
//
// 用途：viewer / 数据模板 / loader 变更后，用「模板原样构建各 viewer 测试页 → file:// 真实渲染 →
// 采集 console error + pageerror + emptyTexts → 截图」判定是否可合入。
// 判定口径与 document-asset-format.md §6.2 一致：0 console error、0 pageerror、emptyTexts 为空，另出截图供人工复核。
//
// 用法（在消费项目的 bundle 目录下运行，或显式指定）：
//   node .agents/skills/sfds/_shared/viewer-tests/verify-fixed.mjs
//   node .agents/skills/sfds/_shared/viewer-tests/verify-fixed.mjs --bundle <bundle根> --out <输出目录>
//
// 依赖：playwright（含 chromium）。需在消费项目安装 `npm i -D playwright`，并在首次跑 `npx playwright install chromium`。
// 若环境无 playwright，本脚本报错并以非 0 退出（门禁不可跳过）。

import { createRequire } from "node:module";
import { copyFileSync, mkdirSync, rmSync, existsSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── 参数解析 ──
const args = process.argv.slice(2);
function flag(name) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : null;
}
// bundle 根 = <本脚本>/../../  (verify-fixed.mjs 位于 <bundle>/_shared/viewer-tests/)
const bundleRoot = resolve(flag("--bundle") || dirname(dirname(__dirname)));
const OUT = resolve(flag("--out") || "viewer-smoke");

// ── 各 viewer 技能与其模板数据（与模板目录一致；新增 viewer 时在此登记）──
const cases = [
  { name: "business-workflow",           viewer: "workflow-viewer.html",     files: ["example-domain.js"], fromDataDir: false },
  { name: "entity-relationship",         viewer: "er-viewer.html",           files: ["core-er.js", "example-entity-domain.js"], fromDataDir: false },
  { name: "client-ui-design",            viewer: "design-viewer.html",       files: ["example-tree-mobile.js", "example-tree-desktop.js", "example-processes.js", "example-style.js", "example-i18n.js"], fromDataDir: false },
  { name: "backend-architecture-design", viewer: "architecture-viewer.html", files: ["system-topology.js", "module-boundaries.js", "layering-strategy.js", "event-contracts.js", "caching-strategy.js", "resilience-policy.js", "data-consistency.js", "observability-policy.js", "security-policy.js", "arch-contract.js", "design-decisions.js", "audit-dossier.js"], fromDataDir: true }
];

// ── 解析 playwright（从消费项目 node_modules）──
let chromium;
try {
  const require = createRequire(process.cwd() + "/");
  const pw = require("playwright");
  chromium = pw.chromium;
} catch (e) {
  console.error("[verify-fixed] 未找到 playwright：请在消费项目安装 `npm i -D playwright` 并 `npx playwright install chromium`。");
  process.exit(1);
}

const results = [];
const browser = await chromium.launch();
for (const c of cases) {
  const tpl = join(bundleRoot, "skills", c.name, "templates");
  if (!existsSync(join(tpl, c.viewer))) {
    results.push({ case: c.name, skipped: "viewer 模板缺失", errors: [] });
    continue;
  }
  const dir = join(OUT, c.name);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(join(dir, "data"), { recursive: true });
  copyFileSync(join(tpl, c.viewer), join(dir, c.viewer));
  copyFileSync(join(tpl, c.fromDataDir ? "data" : "", "loader.js"), join(dir, "data", "loader.js"));
  for (const f of c.files) {
    const src = c.fromDataDir ? join(tpl, "data", f) : join(tpl, f);
    copyFileSync(src, join(dir, "data", f));
  }
  const page = await browser.newPage();
  const errors = [];
  page.on("console", m => { if (m.type() === "error") errors.push(m.text().slice(0, 90)); });
  page.on("pageerror", e => errors.push("pageerror: " + e.message.slice(0, 120)));
  await page.goto("file:///" + join(dir, c.viewer).replace(/\\/g, "/"), { waitUntil: "load" });
  await page.waitForTimeout(900);
  const info = await page.evaluate(() => {
    return {
      bodyLen: document.body.innerText.length,
      emptyTexts: (document.body.innerText.match(/暂无数据|数据未加载|未加载|加载失败|TODO/g) || [])
    };
  });
  await page.screenshot({ path: join(dir, "fixed-screenshot.png"), fullPage: true });
  results.push({ case: c.name, errors, skipped: undefined, ...info });
  await page.close();
}
await browser.close();

// ── 判定与输出 ──
let failed = false;
let fails = 0;
for (const r of results) {
  const ok = (r.skipped === undefined) && r.errors.length === 0 && r.emptyTexts.length === 0;
  if (!ok) { failed = true; fails++; }
  console.log(`[${ok ? "PASS" : "FAIL"}] ${r.case}${r.skipped ? " (skip: " + r.skipped + ")" : ""}  errors=${r.errors.length}  emptyTexts=${JSON.stringify(r.emptyTexts)}`);
}
console.log(JSON.stringify(results, null, 2));
if (failed) {
  console.error(`[verify-fixed] ${fails} 个 viewer 未通过回归门禁（0 console error / 0 pageerror / emptyTexts 为空）——不合入。`);
  process.exit(1);
}
console.log(`[verify-fixed] 全部 ${results.length} 个 viewer 通过回归门禁（0 console error、0 pageerror、emptyTexts 为空，截图见 ${OUT}/）。`);
