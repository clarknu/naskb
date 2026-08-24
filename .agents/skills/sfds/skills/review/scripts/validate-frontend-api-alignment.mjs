#!/usr/bin/env node

/**
 * validate-frontend-api-alignment.mjs
 * 
 * 扫描运营端小程序的所有前端 API 调用，与后端 Controller 路由逐条比对，
 * 输出不匹配报告。
 * 
 * 用法:
 *   node scripts/validate-frontend-api-alignment.mjs
 */

import { readFileSync, readdirSync, statSync } from 'fs';
import { join, resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));

// 自动检测项目根目录：优先使用 --project-root 参数，否则用 Git root
function findProjectRoot() {
  const arg = process.argv.find(a => a.startsWith('--project-root='));
  if (arg) return resolve(arg.split('=')[1]);
  try {
    return execSync('git rev-parse --show-toplevel', { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
  } catch {
    // 回退：从脚本位置向上找 3 级（scripts → skill 目录 → 项目根）
    return resolve(__dirname, '..', '..', '..');
  }
}

const ROOT = findProjectRoot();

// ── 递归列出文件 ──────────────────────────────────────────────────

function globRecursive(dir, ext) {
  const results = [];
  const entries = readdirSync(dir);
  for (const entry of entries) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      results.push(...globRecursive(full, ext));
    } else if (st.isFile() && full.endsWith(ext)) {
      results.push(full);
    }
  }
  return results;
}

// ── 1. 扫描前端 API 调用 ──────────────────────────────────────────

function extractFrontendApiCalls() {
  const pagesDir = join(ROOT, 'src', 'miniprogram-operation', 'pages');
  const jsFiles = globRecursive(pagesDir, '.js');

  const calls = [];

  for (const file of jsFiles) {
    const content = readFileSync(file, 'utf-8');
    const lines = content.split('\n');

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      // 匹配 api.get|post|put|del('path' + var + ...)
      // 支持字符串拼接：'api/v1/roles/' + id → api/v1/roles/:param
      const apiCallRe = /api\.(get|post|put|del)\s*\(\s*(['"`]([^'"`]*)['"`])/;
      const m = line.match(apiCallRe);
      if (!m) continue;

      const method = m[1].toUpperCase();
      // 标准化 HTTP 方法：del → DELETE
      const methodMap = { 'DEL': 'DELETE' };
      const normalizedMethod = methodMap[method] || method;
      let rawPath = m[3];

      // 处理字符串拼接：'path/' + variable + '/more' → path/:param/more
      // 查找同行后续的 + identifier 或 + expression 片段
      const restOfLine = line.substring(m.index + m[0].length);
      const concatRe = /\s*\+\s*([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)\s*/g;
      let cm;
      while ((cm = concatRe.exec(restOfLine)) !== null) {
        rawPath += ':param';
      }
      // 再检查是否有 + '/more' 继续拼接字符串
      const trailingStrRe = /\+\s*['"`]([^'"`]*)['"`]/g;
      let tm;
      while ((tm = trailingStrRe.exec(restOfLine)) !== null) {
        rawPath += tm[1];
      }

      // 跳过非 api/v1/ 路径
      if (!rawPath.startsWith('api/v1/') && !rawPath.startsWith('/api/v1/')) continue;
      const normalizedPath = rawPath.replace(/^\/api\/v1\//, 'api/v1/');

      // 提取查询参数：查找同语句块中的 params 对象字段
      const queryParams = [];
      const bodyFields = [];
      
      let depth = 0;
      let inBlock = false;
      
      for (let j = i; j < Math.min(i + 20, lines.length); j++) {
        const l = lines[j];
        if (j === i) {
          const openCount = (l.match(/\(/g) || []).length;
          const closeCount = (l.match(/\)/g) || []).length;
          depth = openCount - closeCount;
          if (depth <= 0) break;
          inBlock = true;
          continue;
        }
        
        if (inBlock) {
          const openCount = (l.match(/\(/g) || []).length;
          const closeCount = (l.match(/\)/g) || []).length;
          depth += openCount - closeCount;
          
          // 提取 params['key'] = 
          const bracketRe = /params\[['"](\w+)['"]\]\s*=/g;
          let bm;
          while ((bm = bracketRe.exec(l)) !== null) {
            queryParams.push(bm[1]);
          }
          
          // 提取 params.key = 
          const dotRe = /params\.(\w+)\s*=/g;
          let dm;
          while ((dm = dotRe.exec(l)) !== null) {
            queryParams.push(dm[1]);
          }
          
          // 提取 { key: value } 对象字面量字段名（用于 post/put body）
          if (method === 'POST' || method === 'PUT') {
            // 匹配对象字面量中的 key:
            const objKeyRe = /\{\s*(\w+)\s*:/g;
            let om;
            while ((om = objKeyRe.exec(l)) !== null) {
              const key = om[1];
              if (!['code', 'message', 'data'].includes(key) && !key.startsWith('_')) {
                bodyFields.push(key);
              }
            }
            // 也匹配独立行中的 key:
            const kvRe = /^\s*(\w+)\s*:\s*[^,{]+/;
            const kvm = l.match(kvRe);
            if (kvm && !['code', 'message', 'data'].includes(kvm[1]) && !kvm[1].startsWith('_')) {
              bodyFields.push(kvm[1]);
            }
          }
          
          if (depth <= 0) break;
        }
      }

      calls.push({
        method: normalizedMethod,
        path: normalizedPath,
        queryParams: [...new Set(queryParams)],
        bodyFields: [...new Set(bodyFields)],
        file: file.replace(join(ROOT, 'src', 'miniprogram-operation'), 'miniprogram-operation'),
        line: i + 1,
      });
    }
  }

  return calls;
}

// ── 2. 扫描后端 Controller 路由 ─────────────────────────────────────

function extractBackendRoutes() {
  const serverDir = join(ROOT, 'src', 'server-api', 'BoxingPlatform.Api');
  const csFiles = globRecursive(join(serverDir, 'Controllers'), '.cs');

  const routes = [];

  for (const file of csFiles) {
    const content = readFileSync(file, 'utf-8');
    const lines = content.split('\n');

    // 提取控制器级路由
    let controllerRoute = '';
    let controllerName = '';
    
    for (const line of lines) {
      const routeMatch = line.match(/\[Route\("([^"]+)"\)\]/);
      if (routeMatch && !line.includes('class')) {
        controllerRoute = routeMatch[1];
      }
      const classMatch = line.match(/class\s+(\w+Controller)\b/);
      if (classMatch) {
        controllerName = classMatch[1].replace('Controller', '');
      }
    }

    if (!controllerRoute || !controllerName) continue;

    // 标准化路由前缀
    if (!controllerRoute.startsWith('api/v1')) {
      controllerRoute = 'api/v1/' + controllerRoute.replace(/^\/+/, '');
    }

    // 逐行扫描 Action 方法
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const attrMatch = line.match(/\[(HttpGet|HttpPost|HttpPut|HttpPatch|HttpDelete)\s*(?:\(\s*"([^"]*)"\s*\))?\]/);
      
      if (attrMatch) {
        const httpMethod = attrMatch[1].replace('Http', '').toUpperCase();
        const actionRoute = attrMatch[2] || '';
        
        // 向下搜索方法签名
        let actionName = '';
        let params = [];
        let dtoType = null;
        
        for (let j = i; j < Math.min(i + 10, lines.length); j++) {
          // Match method signatures like: Task<IActionResult> MethodName(...)
          // or: async Task<ActionResult> MethodName(...)
          const sigMatch = lines[j].match(/(?:async\s+)?(?:Task<[^>]+>)\s+(\w+)\s*\(([^)]*)\)/);
          if (sigMatch) {
            actionName = sigMatch[1];
            const paramStr = sigMatch[2];
            
            // [FromQuery] 参数
            const fqRe = /\[FromQuery\]\s*\w+\??\s+(\w+)/g;
            let fqm;
            while ((fqm = fqRe.exec(paramStr)) !== null) {
              params.push(fqm[1]);
            }
            
            // [FromBody] 参数
            const fbRe = /\[FromBody\]\s*(\w+)\s+(\w+)/g;
            let fbm = fbRe.exec(paramStr);
            if (fbm) {
              dtoType = fbm[1];
              params.push('__body__:' + fbm[2]);
            }
            
            // 简单类型参数（long id, string xxx）
            const simpleRe = /(?:long|int|string|bool|Guid|DateTime)\??\s+(\w+)\s*[,)]/g;
            let sm;
            while ((sm = simpleRe.exec(paramStr)) !== null) {
              const pname = sm[1];
              if (!params.includes(pname) && !params.some(p => p.endsWith(':' + pname))) {
                params.push(pname);
              }
            }
            
            break;
          }
        }
        
        const fullPath = buildFullRoute(controllerRoute, actionRoute);
        
        routes.push({
          method: httpMethod,
          fullPath,
          controller: controllerName,
          action: actionName,
          params,
          dtoType,
          file: file.replace(join(ROOT, 'src', 'server-api'), 'server-api'),
        });
      }
    }
  }

  return routes;
}

function buildFullRoute(controllerRoute, actionRoute) {
  let base = controllerRoute.replace(/\/+$/, '');
  if (actionRoute) {
    return base + '/' + actionRoute.replace(/^\/+/, '');
  }
  return base;
}

// ── 3. 读取后端 DTO 字段 ──────────────────────────────────────────

function extractDtoFields() {
  const serverDir = join(ROOT, 'src', 'server-api', 'BoxingPlatform.Api');
  const allFiles = [
    ...globRecursive(join(serverDir, 'Models', 'DTOs'), '.cs'),
    ...globRecursive(join(serverDir, 'Controllers'), '.cs'),
  ];

  const dtoMap = new Map();

  for (const file of allFiles) {
    const content = readFileSync(file, 'utf-8');
    // 匹配 public record XxxRequest(...)
    const recordRe = /public\s+(?:sealed\s+)?record\s+(\w+)\s*\(([\s\S]*?)\)\s*[;{]/g;
    let m;
    while ((m = recordRe.exec(content)) !== null) {
      const recordName = m[1];
      const paramsStr = m[2];
      
      const fields = [];
      // 匹配 "Type FieldName" 或 "Type FieldName = default"
      const paramRe = /\w+\??\s+(\w+)\s*(?:=\s*[^,;]*)?/g;
      let pm;
      while ((pm = paramRe.exec(paramsStr)) !== null) {
        const fname = pm[1];
        if (!['string', 'int', 'long', 'bool', 'decimal', 'DateTime'].includes(fname)) {
          fields.push(fname);
        }
      }
      
      if (fields.length > 0) {
        dtoMap.set(recordName, fields.map(f => f.toLowerCase()));
      }
    }
  }

  return dtoMap;
}

// ── 4. 主比对逻辑 ──────────────────────────────────────────────────

function normalizePathForMatching(path) {
  return path
    .replace(/\{[^}]+\}/g, ':param')
    .replace(/\/+$/, '')
    .toLowerCase();
}

function main() {
  console.log('Scanning frontend API calls...');
  const frontendCalls = extractFrontendApiCalls();
  console.log(`  Found ${frontendCalls.length} frontend API calls`);

  console.log('Scanning backend controller routes...');
  const backendRoutes = extractBackendRoutes();
  console.log(`  Found ${backendRoutes.length} backend routes`);

  console.log('Scanning backend DTO fields...');
  const dtoFields = extractDtoFields();
  console.log(`  Found ${dtoFields.size} DTO/Request types\n`);

  // 构建后端路由索引: method + normalizedPath → routes
  const backendIndex = new Map();
  for (const route of backendRoutes) {
    const key = route.method + ' ' + normalizePathForMatching(route.fullPath);
    if (!backendIndex.has(key)) backendIndex.set(key, []);
    backendIndex.get(key).push(route);
  }

  // 分类统计
  const issues = [];
  let matched = 0;
  let notFound = 0;

  for (const call of frontendCalls) {
    const key = call.method + ' ' + normalizePathForMatching(call.path);

    if (!backendIndex.has(key)) {
      // 找不到精确匹配，尝试模糊匹配
      const alternatives = [];
      for (const [bk, routes] of backendIndex) {
        if (bk.startsWith(call.method + ' ')) {
          const callSegs = normalizePathForMatching(call.path).split('/');
          const backSegs = bk.replace(call.method + ' ', '').split('/');
          let score = 0;
          const minLen = Math.min(callSegs.length, backSegs.length);
          for (let s = 0; s < minLen; s++) {
            if (callSegs[s] === backSegs[s]) score++;
          }
          if (score >= 2) {
            alternatives.push({ path: routes[0].fullPath, score, max: Math.max(callSegs.length, backSegs.length) });
          }
        }
      }
      alternatives.sort((a, b) => (b.score / b.max) - (a.score / a.max));

      issues.push({
        call,
        issue: alternatives.length > 0
          ? `PATH NOT FOUND (closest: ${alternatives[0].path})`
          : 'PATH NOT FOUND (no matching backend route)',
        severity: 'CRITICAL',
        alternatives: alternatives.slice(0, 3),
      });
      notFound++;
      continue;
    }

    matched++;

    // 检查查询参数
    const matchedRoutes = backendIndex.get(key);
    if (call.queryParams.length > 0 && matchedRoutes.length > 0) {
      const routeParams = matchedRoutes[0].params.filter(p => !p.startsWith('__body__'));
      const missingParams = call.queryParams.filter(p => !routeParams.includes(p.toLowerCase()));
      if (missingParams.length > 0) {
        issues.push({
          call,
          issue: `QUERY PARAM mismatch: frontend sends [${missingParams.join(', ')}], backend expects [${routeParams.join(', ')}]`,
          severity: 'WARNING',
        });
      }
    }

    // 检查请求体字段
    if ((call.method === 'POST' || call.method === 'PUT') && call.bodyFields.length > 0) {
      const dtoType = matchedRoutes[0].dtoType;
      if (dtoType && dtoFields.has(dtoType)) {
        const expected = dtoFields.get(dtoType);
        const actual = call.bodyFields.map(f => f.toLowerCase());
        const missingInDto = actual.filter(f => !expected.includes(f) && f.length > 1);
        const missingInCall = expected.filter(f => !actual.includes(f) && f.length > 1);

        if (missingInDto.length > 0 || missingInCall.length > 0) {
          const parts = [];
          if (missingInDto.length > 0) parts.push(`frontend-only: [${missingInDto.join(', ')}]`);
          if (missingInCall.length > 0) parts.push(`backend-only: [${missingInCall.slice(0, 5).join(', ')}]`);
          issues.push({
            call,
            issue: `BODY FIELD mismatch with DTO ${dtoType}: ${parts.join('; ')}`,
            severity: 'CRITICAL',
          });
        }
      }
    }
  }

  // ── 输出报告 ──

  console.log('═══════════════════════════════════════════════');
  console.log('  Frontend-Backend API Alignment Report');
  console.log('═══════════════════════════════════════════════\n');

  const pct = frontendCalls.length > 0 ? ((matched / frontendCalls.length) * 100).toFixed(1) : '0';

  console.log('SUMMARY:');
  console.log(`  Frontend calls:  ${frontendCalls.length}`);
  console.log(`  Backend routes:  ${backendRoutes.length}`);
  console.log(`  Matched:         ${matched} (${pct}%)`);
  console.log(`  PATH NOT FOUND:  ${notFound}`);
  console.log('');

  if (issues.length === 0) {
    console.log('✅ All frontend API calls match backend routes!\n');
    return;
  }

  // 按文件分组
  const byFile = new Map();
  for (const iss of issues) {
    const f = iss.call.file;
    if (!byFile.has(f)) byFile.set(f, []);
    byFile.get(f).push(iss);
  }

  console.log('─── ISSUES ───\n');

  for (const [file, fileIssues] of byFile) {
    console.log(`File: ${file}`);
    for (const iss of fileIssues) {
      const tag = iss.severity === 'CRITICAL' ? '🔴' : '🟡';
      console.log(`  ${tag} L${iss.call.line}: ${iss.call.method} ${iss.call.path}`);
      console.log(`     ${iss.issue}`);
      if (iss.alternatives) {
        for (const alt of iss.alternatives) {
          console.log(`     → candidate: ${alt.method || iss.call.method} ${alt.path}`);
        }
      }
    }
    console.log('');
  }

  // 后端有但前端未调用的端点
  console.log('─── UNUSED BACKEND ROUTES (potentially missing frontend features) ───\n');
  const frontendSet = new Set();
  for (const call of frontendCalls) {
    frontendSet.add(call.method + ' ' + normalizePathForMatching(call.path));
  }

  const unused = [];
  for (const [key, routes] of backendIndex) {
    if (!frontendSet.has(key)) {
      unused.push(routes[0]);
    }
  }

  const relevant = unused.filter(r => {
    const p = r.fullPath.toLowerCase();
    if (p.includes('/me/') && !p.includes('/staff/') && !p.includes('/managed')) return false;
    if (p.includes('/auth/') && !p.includes('/staff/')) return false;
    if (p.includes('/i18n')) return false;
    if (p.includes('/health')) return false;
    return true;
  });

  console.log(`  ${relevant.length} potentially relevant unused routes:\n`);
  for (const route of relevant.slice(0, 40)) {
    console.log(`  ${route.method} ${route.fullPath}  (${route.controller}Controller.${route.action})`);
  }
  if (relevant.length > 40) {
    console.log(`  ... and ${relevant.length - 40} more`);
  }

  console.log(`\n💡 Run with: node scripts/validate-frontend-api-alignment.mjs > report.txt`);
}

main();
