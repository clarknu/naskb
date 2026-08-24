/* Page Mock TDD 执行层 —— vitest 全局 setup
 *
 * 职责：
 *  1) 用可编程的 fetch mock 替换全局 fetch（按 method + URL 前缀/正则分派，无需任何真实后端/MSW）；
 *  2) 提供 localStorage / confirm / toast 所需环境桩；
 *  3) 每个用例前重置 fetch 路由 + 共享状态 + document.body + localStorage，保证隔离；
 *  4) 清理：afterEach 清空 document.body 与 localStorage。
 *
 * 测试用例在自身文件里通过 globalThis.__addApiMock(method, matcher, responder) 与
 * globalThis.__jsonResponse(status, body) 注册/构造契约形状的响应。
 */
import { vi, beforeEach, afterEach } from 'vitest';
import { state } from '../public/app-core.js';

/* ---------- 可编程 fetch mock ---------- */
const routes = [];

function jsonResponse(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    async json() { return body; },
  };
}

async function mockFetch(input, init = {}) {
  const method = (init.method || 'GET').toUpperCase();
  const url = typeof input === 'string'
    ? input
    : ((input && input.url) || String(input));
  for (const r of routes) {
    if (r.method !== method) continue;
    let matched = false;
    if (typeof r.matcher === 'string') matched = url.startsWith(r.matcher);
    else if (r.matcher instanceof RegExp) matched = r.matcher.test(url);
    if (!matched) continue;
    const out = await r.responder(url, init, r);
    if (out) return out;
  }
  return jsonResponse(404, { detail: 'mock 未命中路由: ' + method + ' ' + url });
}

globalThis.__addApiMock = (method, matcher, responder) => {
  routes.push({ method, matcher, responder });
};
globalThis.__jsonResponse = jsonResponse;

/* ---------- 环境桩 ---------- */
vi.stubGlobal('fetch', mockFetch);
vi.stubGlobal('confirm', () => true);

/* ---------- 每个用例前重置 ---------- */
beforeEach(() => {
  routes.length = 0;
  // 重置 app-core 的模块级共享状态（跨用例隔离）
  state.route = 'search';
  state.token = '';
  state.authRequired = false;
  state.anonymousRead = true;
  state.toast = '';
  localStorage.clear();
  document.body.innerHTML = '';
});

/* ---------- 每个用例后清理 ---------- */
afterEach(() => {
  document.body.innerHTML = '';
  localStorage.clear();
  state.route = 'search';
  state.token = '';
  state.toast = '';
});
