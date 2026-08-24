/* TC-M010①/③/④ —— App 根组件级：hash 路由 / token 持久化 / 401 引导
 * 位置：tests/page-mock/web-console/app-shell.spec.js
 * 说明：
 *  - 挂载完整 App（header 令牌面板 + hashchange 监听 + /api/config/public 拉取 + <component :is> 视图切换）。
 *  - jsdom 对 location.hash 赋值不保证触发 hashchange —— 显式 dispatch(new Event('hashchange'))。
 *  - “刷新直达/持久化恢复”的**模块初始化**时序（state.route = location.hash…、state.token = localStorage…）
 *    由 app-shell-init.spec.js（独立 vitest 项目 vitest.config.init.mjs，在 app-core 加载前播种）覆盖；
 *    本文件覆盖运行时链路：hashchange → 视图、保存 → localStorage 落盘 → api() 请求携带 Bearer、401 → 引导文案。
 *  - App 子页面可能启动轮询（JobsView 2s / SourcesView 任务轮询 1.5s）：setInterval 打桩为不真正调度。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { App, state, api } from '../../../naskb/web/public/app-core.js';

beforeEach(() => {
  vi.spyOn(globalThis, 'setInterval').mockImplementation(() => 99999);
  vi.spyOn(globalThis, 'clearInterval').mockImplementation(() => {});
});
afterEach(() => {
  vi.restoreAllMocks();
});

function seedConfig() {
  globalThis.__addApiMock('GET', '/api/config/public', () =>
    globalThis.__jsonResponse(200, {
      version: 'v0.1-test',
      auth_required: true,
      anonymous_read: false,
    }));
}

describe('TC-M010① hash 路由与视图切换', () => {
  it('hashchange → 视图切换：#/sources 来源页、#/jobs 任务中心、#/ 回检索页', async () => {
    seedConfig();
    // 子页面 onMounted 即拉取：来源页 /api/sources、任务页 /api/jobs（路由切换时挂载）
    globalThis.__addApiMock('GET', '/api/sources', () =>
      globalThis.__jsonResponse(200, { sources: [] }));
    globalThis.__addApiMock('GET', '/api/jobs', () =>
      globalThis.__jsonResponse(200, { jobs: [] }));

    const wrapper = mount(App);
    await flushPromises();
    // 默认态：检索问答页（main 区首个标题）
    expect(wrapper.find('main').text()).toContain('🔍 检索');

    location.hash = '#/sources';
    window.dispatchEvent(new Event('hashchange'));
    await flushPromises();
    expect(state.route).toBe('sources');
    expect(wrapper.find('main').text()).toContain('知识来源');

    location.hash = '#/jobs';
    window.dispatchEvent(new Event('hashchange'));
    await flushPromises();
    expect(state.route).toBe('jobs');
    expect(wrapper.find('main').text()).toContain('任务中心');

    location.hash = '#/';
    window.dispatchEvent(new Event('hashchange'));
    await flushPromises();
    expect(state.route).toBe('search');
    expect(wrapper.find('main').text()).toContain('🔍 检索');
  });
});

describe('TC-M010③ token 持久化与请求携带', () => {
  it('保存令牌 → localStorage 落盘 + 徽章切“已配置” + 后续请求带 Authorization', async () => {
    seedConfig();
    const wrapper = mount(App);
    await flushPromises();
    // 无令牌：徽章提示需要令牌
    expect(wrapper.text()).toContain('🔒 需要令牌');

    // 展开令牌面板 → 输入 → 保存
    const details = wrapper.find('header details');
    await details.find('summary').trigger('click');
    await details.find('input[placeholder="管理员 Bearer token"]').setValue('tok-live-001');
    await details.find('button').trigger('click');
    await flushPromises();

    // 持久化：localStorage 落盘 + 会话令牌生效 + 徽章切换
    expect(localStorage.getItem('naskb_token')).toBe('tok-live-001');
    expect(state.token).toBe('tok-live-001');
    expect(wrapper.text()).toContain('🔑 已配置令牌');

    // 生效链路：api() 请求自动携带 Bearer
    let authHeader = null;
    globalThis.__addApiMock('GET', '/api/kb/search', (url, init) => {
      authHeader = (init.headers || {}).Authorization || null;
      return globalThis.__jsonResponse(200, { engine: 'vector', hits: [] });
    });
    await api('/api/kb/search?query=' + encodeURIComponent('月租金'));
    expect(authHeader).toBe('Bearer tok-live-001');
  });
});

describe('TC-M010④ 401 引导', () => {
  it('无令牌 401 → 组件 error 块展示“需要管理员令牌（右上角设置）”', async () => {
    seedConfig();
    globalThis.__addApiMock('GET', '/api/kb/search', () =>
      globalThis.__jsonResponse(401, { detail: '未认证' }));

    const wrapper = mount(App);
    await flushPromises();
    await wrapper.find('main input').setValue('出行要带的证件');
    await wrapper.find('main button').trigger('click');
    await flushPromises();

    // 401 → api() 抛「需要管理员令牌（右上角设置）」→ 页面 error 块展示该引导文案
    const err = wrapper.find('main .error');
    expect(err.exists()).toBe(true);
    expect(err.text()).toContain('需要管理员令牌（右上角设置）');
    // 顶栏同步提示：🔒 需要令牌
    expect(wrapper.text()).toContain('🔒 需要令牌');
  });
});
