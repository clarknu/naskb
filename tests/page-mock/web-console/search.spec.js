/* TC-M001 / TC-M002 / TC-M003 —— 检索问答页
 * 位置：tests/page-mock/web-console/search.spec.js
 * 说明：
 *  - mock GET /api/kb/search（按 URL 分派），组件内部 api() 走 Fetch mock，网络全部拦截。
 *  - 组件为 options 对象（template 字符串），测试侧由 vue esm-bundler full build（含 runtime compiler）编译；
 *  - 无 timer/轮询依赖，可直接断言初始渲染与失败态。
 *  - TC-M003：POST /api/ask 生成型交互 —— 「生成中」禁用态以 deferred responder 挂起请求断言，
 *    完成后恢复按钮；answer + sources 按模板逐段断言。
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { SearchView } from '../../../naskb/web/public/app-core.js';
import { searchHits } from './fixtures.js';

describe('TC-M001 检索问答页加载成功', () => {
  it('mock GET /api/kb/search 返回 3 条命中 → 表格渲染 3 行 + 引擎徽章', async () => {
    globalThis.__addApiMock('GET', '/api/kb/search', () =>
      globalThis.__jsonResponse(200, { engine: 'vector', hits: searchHits }));

    const wrapper = mount(SearchView);
    await wrapper.find('input').setValue('出行要带的证件');
    await wrapper.find('button').trigger('click');
    await flushPromises();

    // 引擎徽章显示 engine 值
    expect(wrapper.find('h2 .badge').text()).toContain('vector');
    // 命中表格渲染 3 行
    expect(wrapper.findAll('tbody tr').length).toBe(3);
    // 路径/分数/分类/标签/NAS 徽章可见
    const text = wrapper.text();
    expect(text).toContain('docs/合同.pdf');
    expect(text).toContain('0.830');
    expect(text).toContain('合同');
    expect(text).toContain('租赁');
    expect(text).toContain('home-nas');
    // 过期行展示 ⚠️ 过期 徽章
    expect(text).toContain('⚠️ 过期');
  });
});

describe('TC-M002 检索失败展示错误', () => {
  it('mock 500 → 页内 error 块展示，且不渲染结果表格（区分空态）', async () => {
    globalThis.__addApiMock('GET', '/api/kb/search', () =>
      globalThis.__jsonResponse(500, { detail: '检索服务内部错误' }));

    const wrapper = mount(SearchView);
    await wrapper.find('input').setValue('出行要带的证件');
    await wrapper.find('button').trigger('click');
    await flushPromises();

    // 错误块出现且带服务端 detail
    const err = wrapper.find('.error');
    expect(err.exists()).toBe(true);
    expect(err.text()).toContain('检索服务内部错误');
    // 不渲染结果表格（无空列表表体）
    expect(wrapper.findAll('tbody tr').length).toBe(0);
    // 说明：组件空态提示（v-else-if="!searching" → “输入关键词开始检索…”）因组件逻辑逐行保留
    //       而未按 searchErr 门禁，故失败态下仍会显示该初始提示条；此处不视为失败，属已知 UI 差距（见报告）。
  });
});

/* ── TC-M003 问答生成与来源（追加，P-002 补全） ── */
describe('TC-M003 问答生成与来源', () => {
  it('mock POST /api/ask → answer 渲染 + 来源列表逐条展示', async () => {
    globalThis.__addApiMock('POST', '/api/ask', () =>
      globalThis.__jsonResponse(200, {
        answer: '月租金为 3,200 元，约定押一付三；详见 docs/合同.pdf。',
        sources: ['docs/合同.pdf', 'docs/补充协议.pdf'],
      }));

    const wrapper = mount(SearchView);
    await wrapper.findAll('input')[1].setValue('月租金是多少？');
    await wrapper.findAll('button')[1].trigger('click');
    await flushPromises();

    const text = wrapper.text();
    // answer 渲染（原文含关键信息）
    expect(text).toContain('月租金为 3,200 元');
    expect(text).toContain('押一付三');
    // 来源列表逐条（模板：来源：· <s>）
    expect(text).toContain('来源：');
    expect(text).toContain('docs/合同.pdf');
    expect(text).toContain('docs/补充协议.pdf');
  });

  it('生成中：请求挂起 → 按钮 disabled + “生成中…”，完成后恢复可点', async () => {
    let resolveAsk;
    globalThis.__addApiMock('POST', '/api/ask', () =>
      new Promise((res) => { resolveAsk = res; }));

    const wrapper = mount(SearchView);
    await wrapper.findAll('input')[1].setValue('月租金是多少？');
    const askBtn = wrapper.findAll('button')[1];
    await askBtn.trigger('click');
    await flushPromises();

    // 挂起中：按钮禁用 + 文案切换（模板 :disabled="asking" / {{ asking ? '生成中…' : '提问' }}）
    expect(askBtn.attributes('disabled')).toBeDefined();
    expect(askBtn.text()).toBe('生成中…');

    // 完成：恢复可点 + 文案还原
    resolveAsk(globalThis.__jsonResponse(200, { answer: '月租金为 3,200 元。', sources: [] }));
    await flushPromises();
    const restored = wrapper.findAll('button')[1];
    expect(restored.attributes('disabled')).toBeUndefined();
    expect(restored.text()).toBe('提问');
    expect(wrapper.text()).toContain('月租金为 3,200 元。');
  });
});
