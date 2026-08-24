/* TC-M010② —— 模块初始化时序（独立 vitest 项目，见 naskb/web/vitest.config.init.mjs）
 * 位置：tests/page-mock/web-console/init/app-shell-init.spec.js
 * （置于子目录：主配置 include 为 web-console/*.spec.js 单层 glob，本文件只由 init 项目执行）
 *
 * 浏览器里“刷新直达”时，app-core 模块初始化即读取：
 *   state.route = location.hash.replace(/^#\/?/, "") || "search"
 *   state.token = localStorage.getItem("naskb_token") || ""
 * 本项目的 setup（naskb/web/tests/init-setup.js）在 app-core **加载前**播种 #/sources + 令牌，
 * 因此模块初始化值（globalThis.__NASKB_INIT_SNAPSHOT）即“直达 hash 恢复视图 +
 * 刷新后令牌恢复”时序的证明；下行链路（视图渲染 / 请求携带）复用快照恢复 state 后断言。
 * 说明：setup.js 的全局 beforeEach 会把 state 重置为 search/''，故此处按快照恢复，
 * 且初始化读取断言针对快照常量（不受重置影响）。
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { App, state, api } from '../../../../naskb/web/public/app-core.js';

describe('TC-M010② 模块初始化（直达 + 持久化恢复）', () => {
  beforeEach(() => {
    // 按“页面加载时序”恢复为模块初始化结果（setup.js 的 beforeEach 已重置为 search/''）
    if (globalThis.__NASKB_INIT_SNAPSHOT) {
      state.route = globalThis.__NASKB_INIT_SNAPSHOT.route;
      state.token = globalThis.__NASKB_INIT_SNAPSHOT.token;
    }
  });

  it('初始化读取：#/sources → route=sources；localStorage 令牌 → 会话恢复', () => {
    expect(globalThis.__NASKB_INIT_SNAPSHOT).toEqual({
      route: 'sources',
      token: 'tok-restore-001',
    });
  });

  it('直达恢复视图：App 渲染来源页；恢复的令牌随请求发出 Authorization', async () => {
    globalThis.__addApiMock('GET', '/api/config/public', () =>
      globalThis.__jsonResponse(200, {
        version: 'v0.1-test',
        auth_required: true,
        anonymous_read: false,
      }));
    let authHeader = null;
    globalThis.__addApiMock('GET', '/api/sources', (url, init) => {
      authHeader = (init.headers || {}).Authorization || null;
      return globalThis.__jsonResponse(200, { sources: [] });
    });

    const wrapper = mount(App);
    await flushPromises();
    // 直达 #/sources → 来源页
    expect(wrapper.find('main').text()).toContain('知识来源');
    // 刷新恢复的令牌：顶栏徽章 + 请求自动携带
    expect(wrapper.text()).toContain('🔑 已配置令牌');

    await api('/api/sources');
    expect(authHeader).toBe('Bearer tok-restore-001');
  });
});
