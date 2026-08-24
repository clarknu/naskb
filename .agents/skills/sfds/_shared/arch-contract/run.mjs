#!/usr/bin/env node
// run.mjs — 架构契约运行器（技术中性）
// 用法：
//   node run.mjs --contract design/05-backend-architecture/data/arch-contract.js \
//                --facts scripts/probes/out/facts.json \
//                --report design/review/arch-contract/<date>.json
// 退出码：0 通过（含 WARN）；1 存在未豁免 mechanical 违规；2 基础设施失败（schema/指针/文件）

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { compare } from './compare.mjs';

function fail(msg) {
  const report = { summary: { end_slug: 'arch-contract', producer: 'backend-architecture-design', error: msg, total_issues: 0 } };
  process.stdout.write(`[arch-contract] 基础设施失败：${msg}\n`);
  process.stdout.write(JSON.stringify(report, null, 2) + '\n');
  process.exit(2);
}

// ---------- CLI ----------
const argv = process.argv.slice(2);
const arg = (name) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : null;
};
const contractPath = arg('contract');
const factsPath = arg('facts');
const reportPath = arg('report');
if (!contractPath || !factsPath) fail('缺少 --contract 或 --facts');

// ---------- 加载设计 JS（window 命名空间挂载约定）----------
function loadDesignJs(absFile) {
  const code = fs.readFileSync(absFile, 'utf8');
  const sandbox = { window: {}, console: { log() {} } };
  vm.runInNewContext(code, sandbox, { filename: absFile });
  return sandbox.window;
}

function extractPath(windowNs, frag) {
  const segsList = frag.split('.').filter(Boolean);
  for (const nsKey of Object.keys(windowNs)) {
    const ns = windowNs[nsKey];
    if (!ns || typeof ns !== 'object') continue;
    // frag 逐段解析（首段为数据键，如 system-topology / 06-channel-access）
    let node = ns;
    let ok = true;
    for (const seg of segsList) {
      if (node && typeof node === 'object' && seg in node) node = node[seg];
      else { ok = false; break; }
    }
    if (ok) return node;
    if (segsList.length === 1 && ns[segsList[0]] !== undefined) return ns[segsList[0]];
  }
  return undefined;
}

// ---------- 解析契约 ----------
let contractData;
try {
  const win = loadDesignJs(path.resolve(contractPath));
  const key = path.basename(contractPath).replace(/\.js$/, '');
  contractData = win.ARCH_DATA ? win.ARCH_DATA['arch-contract'] || win.ARCH_DATA[key] : undefined;
} catch (e) {
  fail(`契约文件加载失败：${e.message}`);
}
if (!contractData || !Array.isArray(contractData.rules)) fail('契约缺少 rules 数组（schema 不合）');

// ---------- 加载并校验事实 ----------
let facts;
try {
  facts = JSON.parse(fs.readFileSync(path.resolve(factsPath), 'utf8'));
} catch (e) {
  fail(`facts.json 解析失败：${e.message}`);
}
(function validateFacts(f) {
  if (!f.probe || !f.probe.name) fail('facts 缺少 probe.name');
  if (!Array.isArray(f.units) || !f.units.length) fail('facts 缺少 units 数组');
  if (!f.facts || typeof f.facts !== 'object') fail('facts 缺少 facts 对象');
  for (const k of ['dependency', 'reference', 'assetRef', 'literal', 'registry']) {
    const arr = f.facts[k];
    if (arr !== undefined && !Array.isArray(arr)) fail(`facts.facts.${k} 必须是数组`);
  }
})(facts);

// ---------- 解析 design:// 指针（仅比较器实际消费的字段；source 为人读锚点，不参与解析）----------
const resolved = {};
const ACTIONABLE_KEYS = new Set(['whitelist', 'ownership', 'declared']);
function collectPointers(node, keyName, acc) {
  if (keyName && ACTIONABLE_KEYS.has(keyName) && typeof node === 'string' && node.startsWith('design://')) {
    acc.add(node);
  } else if (Array.isArray(node)) {
    node.forEach((n) => collectPointers(n, null, acc));
  } else if (node && typeof node === 'object') {
    for (const k of Object.keys(node)) collectPointers(node[k], k, acc);
  }
}
const pointers = new Set();
collectPointers(contractData.rules, null, pointers);
const designRoot = path.resolve(path.dirname(path.resolve(contractPath)), '../..'); // .../design/05-backend-architecture/data → design/
for (const ptr of pointers) {
  const rest = ptr.slice('design://'.length);
  const hashIdx = rest.indexOf('#');
  const rel = hashIdx >= 0 ? rest.slice(0, hashIdx) : rest;
  const frag = hashIdx >= 0 ? rest.slice(hashIdx + 1) : '';
  const abs = path.resolve(designRoot, rel);
  if (!fs.existsSync(abs)) fail(`design:// 指针目标不存在：${ptr}（${abs}）`);
  try {
    const win = loadDesignJs(abs);
    const value = frag ? extractPath(win, frag) : win;
    if (value === undefined) fail(`design:// 指针路径解析失败：${ptr}`);
    resolved[ptr] = value;
  } catch (e) {
    if (e.message && e.message.startsWith('design://')) fail(e.message);
    fail(`指针 ${ptr} 加载失败：${e.message}`);
  }
}

// ---------- 比较 ----------
const { summary, issues, exitCode } = compare({
  contract: contractData,
  facts,
  resolved,
  today: new Date().toISOString().slice(0, 10),
});

const report = { summary, issues };
if (reportPath) {
  const absReport = path.resolve(reportPath);
  fs.mkdirSync(path.dirname(absReport), { recursive: true });
  fs.writeFileSync(absReport, JSON.stringify(report, null, 2), 'utf8');
}

process.stdout.write(
  `[arch-contract] 规则 ${summary.rulesChecked} 条｜违规 ${summary.total_issues}（high ${summary.high} / medium ${summary.medium} / low ${summary.low}）｜` +
    `债务 ${summary.debtsActive}/${summary.debtsTotal} 生效｜未分组单元 ${summary.unmatchedUnits}｜退出码 ${exitCode}\n`
);
if (reportPath) process.stdout.write(`报告：${reportPath}\n`);
process.exit(exitCode);
