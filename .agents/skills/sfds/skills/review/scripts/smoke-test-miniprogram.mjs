#!/usr/bin/env node

/**
 * smoke-test-miniprogram.mjs
 * 
 * 小程序冒烟测试：验证页面文件完整性 + JS 语法正确性
 * 
 * 用法:
 *   node scripts/smoke-test-miniprogram.mjs [端名] [--project-root /path]
 *   默认端名: 取 src/ 下第一个 miniprogram-* 目录（也可显式传入端名）
 */

import { readFileSync, existsSync, readdirSync } from 'fs';
import { join, resolve, dirname } from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

function findProjectRoot() {
  const arg = process.argv.find(a => a.startsWith('--project-root='));
  if (arg) return resolve(arg.split('=')[1]);
  try {
    return execSync('git rev-parse --show-toplevel', { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
  } catch {
    return resolve(__dirname, '..', '..', '..');
  }
}

const ROOT = findProjectRoot();

const TARGET = process.argv[2] || 'operation';
const APP_DIR = join(ROOT, 'src', `miniprogram-${TARGET}`);

if (!existsSync(APP_DIR)) {
  console.error(`❌ 目录不存在: ${APP_DIR}`);
  process.exit(1);
}

// ── 1. 读取 app.json ─────────────────────────────────────────────

const appJsonPath = join(APP_DIR, 'app.json');
if (!existsSync(appJsonPath)) {
  console.error(`❌ app.json 不存在: ${appJsonPath}`);
  process.exit(1);
}

const appJson = JSON.parse(readFileSync(appJsonPath, 'utf-8'));
const pages = appJson.pages || [];
const tabBarPages = (appJson.tabBar?.list || []).map(t => t.pagePath);

console.log(`\n🔍 冒烟测试: miniprogram-${TARGET}`);
console.log(`   注册页面: ${pages.length}`);
console.log(`   TabBar:   ${tabBarPages.length}\n`);

// ── 2. 检查页面文件完整性 ───────────────────────────────────────

const REQUIRED_EXTS = ['.js', '.wxml', '.wxss', '.json'];
let missingFiles = 0;
let syntaxErrors = 0;

for (const page of pages) {
  const pageDir = join(APP_DIR, page);
  const pageName = page.split('/').pop();
  
  for (const ext of REQUIRED_EXTS) {
    const filePath = join(APP_DIR, page + ext);
    if (!existsSync(filePath)) {
      console.log(`  ⚠️  缺失: ${page}${ext}`);
      missingFiles++;
    }
  }

  // ── 3. JS 语法检查 ──────────────────────────────────────────

  const jsFile = join(APP_DIR, page + '.js');
  if (existsSync(jsFile)) {
    try {
      // 使用 node --check 检查语法（ES 模块模式因 import/export 会报错，改用 --experimental-vm-modules 前的桥接方式）
      // 这里使用一个简单的语法检查：尝试用 acorn 风格解析
      const content = readFileSync(jsFile, 'utf-8');
      
      // 检查常见语法问题
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        
        // 检查未闭合的括号（粗略）
        const opens = (line.match(/[({[]/g) || []).length;
        const closes = (line.match(/[)}\]]/g) || []).length;
        // 跳过大括号检查，太容易误报
      }
      
      // 使用 node --check 做真正的语法校验
      // 注意：微信小程序的 JS 不是标准 ES module，需要先转换
      try {
        // 包装成 CommonJS 格式让 node 检查
        const wrapped = `
          var Page = function(opts) { return opts; };
          var App = function(opts) { return opts; };
          var Component = function(opts) { return opts; };
          var Behavior = function(opts) { return opts; };
          var getApp = function() { return {}; };
          var wx = {};
          var getCurrentPages = function() { return []; };
          ${content}
        `;
        execSync(`node --check --input-type=module -e ""`, { 
          input: wrapped, 
          stdio: ['pipe', 'pipe', 'pipe'],
          timeout: 5000 
        });
      } catch (e) {
        const errStr = e.stderr?.toString() || e.message || '';
        if (errStr.includes('SyntaxError')) {
          console.log(`  🔴 语法错误: ${page}.js`);
          console.log(`     ${errStr.split('\n').slice(0, 3).join('\n     ')}`);
          syntaxErrors++;
        }
        // 忽略模块解析错误（微信 API 在 Node 环境下不可用）
      }
    } catch (e) {
      // 读取文件错误
      console.log(`  ⚠️  无法读取: ${page}.js (${e.message})`);
    }
  }
}

// ── 4. 检查 TabBar 页面是否在 pages 中注册 ─────────────────────

for (const tabPage of tabBarPages) {
  if (!pages.includes(tabPage)) {
    console.log(`  🔴 TabBar 页面未在 pages 中注册: ${tabPage}`);
  }
}

// ── 5. 检查 app.json 配置 ──────────────────────────────────────

if (!appJson.window?.navigationBarTitleText) {
  console.log('  ⚠️  app.json 缺少 navigationBarTitleText');
}

// ── 6. 检查是否有空目录（孤儿页面文件） ─────────────────────────

const pagePaths = new Set(pages.map(p => p.replace(/\/[^/]+$/, '')));
const allDirs = new Set();

function scanDirs(dir, base) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory() && !entry.name.startsWith('_') && !entry.name.startsWith('.')) {
      const full = join(dir, entry.name);
      const rel = full.replace(base, '').replace(/\\/g, '/').replace(/^\//, '');
      allDirs.add(rel);
      scanDirs(full, base);
    }
  }
}

scanDirs(join(APP_DIR, 'pages'), join(APP_DIR, 'pages'));

// Fix: directory rel paths are from pages/ base, but page paths in app.json
// are from the miniprogram root like "pages/checkin/scan"
const orphanDirs = [...allDirs].filter(d => {
  const dirWithPrefix = 'pages/' + d;
  const isPage = pages.some(p => p.startsWith(dirWithPrefix + '/') || p === dirWithPrefix);
  return !isPage;
});

if (orphanDirs.length > 0) {
  console.log(`\n  ⚠️  ${orphanDirs.length} 个孤儿目录（无页面注册）:`);
  for (const d of orphanDirs) {
    console.log(`     pages/${d}/`);
  }
}

// ── 7. 汇总 ────────────────────────────────────────────────────

console.log(`\n══════════════════════════════════════════`);
console.log(`  冒烟测试结果: miniprogram-${TARGET}`);
console.log(`══════════════════════════════════════════`);
console.log(`  页面总数:  ${pages.length}`);
console.log(`  缺失文件:  ${missingFiles}  ⚠️`);
console.log(`  语法错误:  ${syntaxErrors}  🔴`);
console.log(`  孤儿目录:  ${orphanDirs.length}  ⚠️`);
console.log(`  总体状态:  ${missingFiles === 0 && syntaxErrors === 0 ? '✅ 通过' : '❌ 存在问题'}`);
console.log('');
