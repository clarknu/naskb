/* TC-M004 / TC-M005 —— 知识来源页
 * 位置：tests/page-mock/web-console/sources.spec.js
 * 说明：
 *  - 来源页 onMounted 即拉 GET /api/sources，故每个用例必须先 mock 该 GET，避免未处理拒绝。
 *  - TC-M004 表单校验：assert required 属性与 form.checkValidity()（jsdom 原生约束校验），
 *    并断言 webdav/local 分支字段的 v-if 显隐切换。
 *  - TC-M005 注册 Toast：读 app-core 的模块级 state.toast（toast 由组件 toast() 设置），断言成功/失败文案。
 */
import { describe, it, expect } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { SourcesView, state } from '../../../naskb/web/public/app-core.js';
import { sourcesList } from './fixtures.js';

function seedSources(responder) {
  globalThis.__addApiMock('GET', '/api/sources', responder);
}

describe('TC-M004 来源表单校验', () => {
  it('alias 必填：输入带 required 属性 + 标签提示', async () => {
    seedSources(() => globalThis.__jsonResponse(200, { sources: [] }));
    const wrapper = mount(SourcesView);
    await flushPromises();

    // 展开注册表单
    await wrapper.find('button').trigger('click');
    await flushPromises();

    const form = wrapper.find('form');
    expect(form.exists()).toBe(true);
    const alias = form.find('input[placeholder="如 home-nas-docs"]');
    expect(alias.exists()).toBe(true);
    // 必填标记：label 带 *，input 带 required
    expect(form.text()).toContain('别名 *');
    expect(alias.attributes('required')).toBeDefined();
  });

  it('空表单提交被拦截：alias 为空时原生校验不通过', async () => {
    seedSources(() => globalThis.__jsonResponse(200, { sources: [] }));
    const wrapper = mount(SourcesView);
    await flushPromises();
    await wrapper.find('button').trigger('click');
    await flushPromises();

    const form = wrapper.find('form').element;
    // alias 为空 → required 触发 invalid → 浏览器拦截 submit（jsdom 校验规则同实测）
    expect(form.checkValidity()).toBe(false);
    // 填了 alias 后校验通过（证明拦截确由 required 引起，而非其它字段）
    await wrapper.find('input[placeholder="如 home-nas-docs"]').setValue('home-nas-docs');
    await flushPromises();
    expect(form.checkValidity()).toBe(true);
  });

  it('WebDAV / local 分支字段随协议切换（v-if 显隐）', async () => {
    seedSources(() => globalThis.__jsonResponse(200, { sources: [] }));
    const wrapper = mount(SourcesView);
    await flushPromises();
    await wrapper.find('button').trigger('click');
    await flushPromises();

    // 默认 local：显示根路径（root_path），不显示 webdav url
    expect(wrapper.find('input[placeholder^="D:"]').exists()).toBe(true);
    expect(wrapper.find('input[placeholder^="https://"]').exists()).toBe(false);

    // 切换为 webdav：显示 url/账号/密码/SSL；根路径消失
    await wrapper.find('select').setValue('webdav');
    await flushPromises();
    expect(wrapper.find('input[placeholder^="https://"]').exists()).toBe(true);
    expect(wrapper.find('input[placeholder^="D:"]').exists()).toBe(false);
    expect(wrapper.find('input[type="text"]').attributes('placeholder')).not.toBe('');

    // 切回 local：根路径恢复、url 消失
    await wrapper.find('select').setValue('local');
    await flushPromises();
    expect(wrapper.find('input[placeholder^="D:"]').exists()).toBe(true);
    expect(wrapper.find('input[placeholder^="https://"]').exists()).toBe(false);
  });
});

describe('TC-M005 注册成功/失败 Toast', () => {
  it('POST 200 → toast “来源已注册” + 表单收起 + 列表刷新', async () => {
    let srcCalls = 0;
    seedSources(() => {
      srcCalls++;
      // 首次加载空列表；注册后的刷新返回 1 个来源（证明“列表刷新”）
      return globalThis.__jsonResponse(200, { sources: srcCalls === 1 ? [] : sourcesList });
    });
    globalThis.__addApiMock('POST', '/api/sources', () => globalThis.__jsonResponse(200, { source_id: 's1' }));

    const wrapper = mount(SourcesView);
    await flushPromises();
    await wrapper.find('button').trigger('click'); // 展开表单
    await flushPromises();
    await wrapper.find('input[placeholder="如 home-nas-docs"]').setValue('home-nas-docs');
    await flushPromises();
    await wrapper.find('form').trigger('submit'); // @submit.prevent="add"
    await flushPromises();

    // 成功 toast
    expect(state.toast).toBe('来源已注册');
    // 表单收起
    expect(wrapper.find('form').exists()).toBe(false);
    // 列表刷新：出现注册的来源行
    expect(wrapper.text()).toContain('home-nas-docs');
    expect(wrapper.findAll('tbody tr').length).toBeGreaterThan(0);
  });

  it('POST 500 → toast “注册失败 + 原因”，表单保持展开，列表不变', async () => {
    seedSources(() => globalThis.__jsonResponse(200, { sources: [] }));
    globalThis.__addApiMock('POST', '/api/sources', () =>
      globalThis.__jsonResponse(500, { detail: '别名已存在' }));

    const wrapper = mount(SourcesView);
    await flushPromises();
    await wrapper.find('button').trigger('click');
    await flushPromises();
    await wrapper.find('input[placeholder="如 home-nas-docs"]').setValue('home-nas-docs');
    await flushPromises();
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    // 失败 toast（含原因）
    expect(state.toast).toContain('注册失败');
    expect(state.toast).toContain('别名已存在');
    // 表单保持展开
    expect(wrapper.find('form').exists()).toBe(true);
    // 列表未新增（仍为空态提示）
    expect(wrapper.text()).toContain('还没有注册任何来源。');
  });
});
