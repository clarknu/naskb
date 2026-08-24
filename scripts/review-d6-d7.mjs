// review-d6-d7.mjs — D6/D7 机械核对：tree.js api_ref ↔ API 设计端点（DD-009 复查用）
// 输出：三层对齐（前端 api_ref / 设计声明 method+path / 实现注册 set-relation 已由契约覆盖）
import fs from "node:fs";
import vm from "node:vm";

const win = { window: {}, console: { log() {} }, document: { write() {} } };
function load(f) {
  const code = fs.readFileSync(f, "utf8");
  vm.runInNewContext(code, win, { filename: f });
}

// 1) 设计端点（含 202 status 等不在实体内的字段——取 method+path）
load("design/04-platform-api/data/rest/01-source-management.js");
load("design/04-platform-api/data/rest/03-retrieval-qa.js");
load("design/04-platform-api/data/rest/04-deep-analysis.js");
load("design/04-platform-api/data/rest/06-platform-console.js");
const api = win.window.API_DATA || {};
const designed = new Set();
for (const k of Object.keys(api)) {
  const d = api[k];
  if (!Array.isArray(d.endpoints)) continue;
  for (const e of d.endpoints) designed.add(`${e.method} ${e.path}`);
}
console.log(`[D6/D7] 设计端点登记=${designed.size}（keys=${Object.keys(api).join(",")}）`);

// 2) tree.js api_ref
load("design/06-web-console/data/tree.js");
const tree = win.window.PS_DATA["web-console"].tree;
const refs = [];
function walk(nodes) {
  for (const n of nodes) {
    if (n.api_ref) refs.push({ ref: n.api_ref, node: n.name });
    if (n.children) walk(n.children);
  }
}
walk(tree.pages);
(tree.shared_components || []).forEach((c) => walk([c]));

// 3) 比对（api_ref 形如 "GET /api/..."；端点路径参数 {xx} 归一为 {x}）
let ok = 0, bad = [];
for (const r of refs) {
  const [rop, rp] = r.ref.split(" ");
  const norm = rp.replace(/\/\{[^}]+\}/g, "/{x}");
  const match = [...designed].some((ep) => {
    const [op, p] = ep.split(" ");
    if (op !== rop) return false;
    const need = p.replace(/\/\{[^}]+\}/g, "/{x}");
    return need === norm;
  });
  if (match) ok++; else bad.push({ ref: r.ref, node: r.node });
}
console.log(`[D6/D7] tree.js api_ref=${refs.length}｜匹配设计端点=${ok}｜未匹配=${bad.length}`);
bad.forEach((b) => console.log(`  ❌ ${b.ref}（${b.node}）`));
process.exit(bad.length ? 1 : 0);
