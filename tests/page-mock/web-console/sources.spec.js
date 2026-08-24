/* TC-M004 / TC-M005 / TC-M006 / TC-M007 —— 知识来源页
 * 位置：tests/page-mock/web-console/sources.spec.js
 * 说明：
 *  - 来源页 onMounted 即拉 GET /api/sources，故每个用例必须先 mock 该 GET，避免未处理拒绝。
 *  - TC-M004 表单校验：assert required 属性与 form.checkValidity()（jsdom 原生约束校验），
 *    并断言 webdav/local 分支字段的 v-if 显隐切换。
 *  - TC-M005 注册 Toast：读 app-core 的模块级 state.toast（toast 由组件 toast() 设置），断言成功/失败文案。
 *  - TC-M006 操作列（P-002 补全）：单管理员全身份口径（DD-009）→ UI 不按 perm_ref 显隐，
 *    9 个权限点由服务端逐点执行；断言 8 个操作按钮恒渲染 + 删除前 confirm 弹窗（取消/确认分支）。
 *  - TC-M007 变更确认清单（P-002 补全）：GET {sid}/changes → 差异分组（新增/变更/消失）+ 默认全选 →
 *    取消勾选 → POST {sid}/confirm 提交 rel_paths 子集；confirmCh → pollJob 轮询以 setInterval 打桩跳过。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
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

/* ── TC-M006 来源操作列按钮状态（P-002 补全） ──
 * 口径说明（DD-009 全身份模型）：单管理员 Bearer 全身份、无匿名只读 → UI 不做按 perm_ref 的
 * 按钮显隐（不存在“无令牌只读观众”角色）；SourceRegister/SourceTest/…/SourceDelete 等 9 个权限点
 * 由服务端逐点执行，UI 恒定渲染全部操作按钮。故断言：① 操作列按钮全量渲染；② 删除前 confirm 弹窗。
 */
describe('TC-M006 来源操作列按钮状态', () => {
  it('单管理员全身份：操作列 8 个操作按钮恒渲染（权限点在服务端执行，UI 无 perm_ref 显隐）', async () => {
    seedSources(() => globalThis.__jsonResponse(200, { sources: sourcesList }));
    const wrapper = mount(SourcesView);
    await flushPromises();

    const row = wrapper.find('tbody tr');
    const labels = ['测试', '扫描', 'AI 分析', '变更', '深度关', '收编', '停用', '删除'];
    for (const lb of labels) {
      expect(row.findAll('button').some((b) => b.text() === lb)).toBe(true);
    }
    expect(row.findAll('button').length).toBe(8);
  });

  it('删除前 confirm 弹窗：取消 → 不发 DELETE、列表不变、无 toast', async () => {
    seedSources(() => globalThis.__jsonResponse(200, { sources: sourcesList }));
    let delCalls = 0;
    globalThis.__addApiMock('DELETE', '/api/sources/s1', () => {
      delCalls++;
      return globalThis.__jsonResponse(200, { ok: true });
    });

    const orig = globalThis.confirm;
    globalThis.confirm = () => false;
    try {
      const wrapper = mount(SourcesView);
      await flushPromises();
      await wrapper.findAll('button').find((b) => b.text() === '删除').trigger('click');
      await flushPromises();
      expect(delCalls).toBe(0);
      expect(state.toast).toBe('');
      expect(wrapper.text()).toContain('home-nas-docs');
    } finally {
      globalThis.confirm = orig;
    }
  });

  it('删除前 confirm 弹窗：确认 → DELETE 发出 + toast“已删除” + 列表刷新', async () => {
    let srcCalls = 0;
    seedSources(() => {
      srcCalls++;
      return globalThis.__jsonResponse(200, { sources: srcCalls === 1 ? sourcesList : [] });
    });
    let delCalls = 0;
    globalThis.__addApiMock('DELETE', '/api/sources/s1', () => {
      delCalls++;
      return globalThis.__jsonResponse(200, { ok: true });
    });

    const wrapper = mount(SourcesView);
    await flushPromises();
    await wrapper.findAll('button').find((b) => b.text() === '删除').trigger('click');
    await flushPromises();

    expect(delCalls).toBe(1);
    expect(state.toast).toBe('已删除');
    // 列表刷新（删除后为空态提示）
    expect(wrapper.text()).toContain('还没有注册任何来源。');
  });
});

/* ── TC-M007 变更确认清单交互（P-002 补全） ──
 * 主干交互：GET {sid}/changes（差异）→ 勾选（默认全选 added+changed）→ POST {sid}/confirm
 * 提交 rel_paths 子集 → 提交后清单收起 + toast。
 */
describe('TC-M007 变更确认清单交互', () => {
  beforeEach(() => {
    // confirmCh → pollJob 会启动 1500ms 轮询：打桩为不真正调度（同 jobs.spec.js 约定）
    vi.spyOn(globalThis, 'setInterval').mockImplementation(() => 99999);
    vi.spyOn(globalThis, 'clearInterval').mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('差异分组渲染（新增/变更/消失）+ 默认全选 + 取消勾选后提交 rel_paths 子集', async () => {
    let confirmBody = null;
    // 注意注册顺序：先注册更精确的 /changes、/confirm 路由，再注册 GET /api/sources 前缀路由
    //（fetch mock 为「首个命中即用」，/api/sources 前缀串匹配会吞掉 /api/sources/s1/changes）。
    globalThis.__addApiMock('GET', /\/api\/sources\/s1\/changes$/, () =>
      globalThis.__jsonResponse(200, {
        diff: {
          added: ['docs/合同.pdf'],
          changed: ['docs/补充协议.pdf'],
          missing: ['docs/旧合同.pdf'],
        },
      }));
    globalThis.__addApiMock('POST', /\/api\/sources\/s1\/confirm$/, (url, init) => {
      confirmBody = JSON.parse(init.body || '{}');
      return globalThis.__jsonResponse(200, { job_id: 'j-0001' });
    });
    seedSources(() => globalThis.__jsonResponse(200, { sources: sourcesList }));

    const wrapper = mount(SourcesView);
    await flushPromises();
    await wrapper.findAll('button').find((b) => b.text() === '变更').trigger('click');
    await flushPromises();

    // 差异分组渲染：变更确认标题 + 新增/变更条目 + 消失文案（仅标记，不物理删除）
    const text = wrapper.text();
    expect(text).toContain('变更确认 — home-nas-docs');
    expect(text).toContain('新增');
    expect(text).toContain('docs/合同.pdf');
    expect(text).toContain('变更');
    expect(text).toContain('docs/补充协议.pdf');
    expect(text).toContain('消失（仅标记为缺失，不物理删除）：docs/旧合同.pdf');
    // toast 差异统计
    expect(state.toast).toContain('差异：新增 1 · 变更 1 · 消失 1');

    // 默认全选 added + changed → 2 个勾选项
    const boxes = wrapper.findAll('.hit input[type="checkbox"]');
    expect(boxes.length).toBe(2);
    expect(boxes.every((b) => b.element.checked)).toBe(true);

    // 取消勾选「变更」项（第 2 个）→ 提交 rel_paths 只剩 added
    await boxes[1].trigger('change');
    await wrapper.findAll('button').find((b) => b.text() === '确认同步并分析').trigger('click');
    await flushPromises();

    expect(confirmBody).toEqual({ rel_paths: ['docs/合同.pdf'] });
    expect(state.toast).toContain('确认同步已提交（任务 j-0001）');
    // 提交后清单收起
    expect(wrapper.text()).not.toContain('变更确认 — home-nas-docs');
  });
});
