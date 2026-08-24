#!/usr/bin/env node
// generate-trigger-table.mjs — 从 pipeline-registry.js 生成 AGENTS.md 铁律表（单一真相源的派生物）
//
// 用法：
//   node .agents/skills/sfds/_shared/gen/generate-trigger-table.mjs            # 预览（stdout）
//   node .agents/skills/sfds/_shared/gen/generate-trigger-table.mjs --write     # 写入 AGENTS.md（需已存在标记块）
//
// 标记块（AGENTS.md 内手工放置一次）：
//   <!-- BEGIN skill-table (generated from pipeline-registry.js; edit registry, not here) -->
//   ... 表格 ...
//   <!-- END skill-table -->
//
// 新 skill 接入流程（注册表 admission.procedure）：改注册表 → 本脚本 --write → 接线门禁。

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const here = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const registryPath = path.resolve(here, '..', 'pipeline-registry.js');
const agentsPath = path.resolve(process.cwd(), 'AGENTS.md');

const sandbox = { window: {} };
vm.runInNewContext(fs.readFileSync(registryPath, 'utf8'), sandbox, { filename: registryPath });
const registry = sandbox.window.SFDS_DATA['pipeline-registry'];
if (!registry) { console.error('[gen] pipeline-registry.js 未挂载 SFDS_DATA'); process.exit(2); }

// 按 priority 升序（编排/基础在前），同 priority 保持登记序
const skills = [...registry.skills].sort((a, b) => (a.priority - b.priority));

const rows = skills.map((s) => {
  const trig = s.triggers.map((t) => (t.length > 6 || /[，,]/.test(t) ? `**${t}**` : t)).join('、');
  return `| ${trig} | \`${s.name}\` | ${s.layer} | ${s.summary.split('——')[0].replace(/\s*（.*$/, '')} |`;
});

const block = [
  '<!-- BEGIN skill-table (generated from pipeline-registry.js; edit registry, not here) -->',
  '',
  '> **任何任务，只要其意图与下表触发词匹配，必须先调用对应 Skill，按技能规定的流程推进工作。**',
  '> **禁止**在未加载 Skill 的情况下直接对 `design/` 或 `src/` 做 Read→Edit→Write 操作。',
  '> 本表由 `.agents/skills/sfds/_shared/pipeline-registry.js` 生成（`node .agents/skills/sfds/_shared/gen/generate-trigger-table.mjs --write`），勿手编。',
  '',
  '| 触发词 | 技能 | 层 | 一句话 |',
  '|--------|------|----|------|',
  ...rows,
  '',
  '<!-- END skill-table -->',
].join('\n');

if (!process.argv.includes('--write')) {
  process.stdout.write(block + '\n');
  process.stdout.write('[gen] 预览模式（--write 写入 AGENTS.md）\n');
  process.exit(0);
}

if (!fs.existsSync(agentsPath)) { console.error(`[gen] 未找到 ${agentsPath}（请在项目根目录运行）`); process.exit(2); }
const agents = fs.readFileSync(agentsPath, 'utf8');
const BEGIN = '<!-- BEGIN skill-table';
const END = '<!-- END skill-table -->';
const i = agents.indexOf(BEGIN);
const j = agents.indexOf(END);
if (i < 0 || j < 0) {
  console.error('[gen] AGENTS.md 缺少标记块——请手工放置一次（BEGIN/END 之间的旧表将被接管）');
  process.exit(2);
}
const next = agents.slice(0, i) + block + agents.slice(j + END.length);
fs.writeFileSync(agentsPath, next, 'utf8');
console.log(`[gen] AGENTS.md 铁律表已再生成（${skills.length} skills，来源 registry v${registry.version}）`);
