/* TC-M008 —— 任务中心页
 * 位置：tests/page-mock/web-console/jobs.spec.js
 * 说明：
 *  - JobsView onMounted 即 load() 并用 setInterval(load, 2000) 轮询。为规避真实轮询（定时器泄漏/持续拉取），
 *    本文件在挂载前把 setInterval/clearInterval 打桩为不真正调度，只做**初始渲染**断言（符合“跳过轮询细节”）。
 *  - mock GET /api/jobs 返回契约形状（id/kind/status/progress/result/error/created_at）。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { JobsView } from '../../../naskb/web/public/app-core.js';
import { jobsList } from './fixtures.js';

beforeEach(() => {
  // 将 2s 轮询的 setInterval 打桩为“不真正调度”，仅保留首次 load；避免真实定时器造成泄漏与持续请求。
  vi.spyOn(globalThis, 'setInterval').mockImplementation(() => 99999);
  vi.spyOn(globalThis, 'clearInterval').mockImplementation(() => {});
  globalThis.__addApiMock('GET', '/api/jobs', () =>
    globalThis.__jsonResponse(200, { jobs: jobsList }));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('TC-M008 任务中心轮询', () => {
  it('mock GET /api/jobs → 表格渲染各行 + 状态徽章类名 + 进度条宽度', async () => {
    const wrapper = mount(JobsView);
    await flushPromises();

    // 表格渲染 2 行（running / completed）
    expect(wrapper.findAll('tbody tr').length).toBe(2);
    const text = wrapper.text();
    expect(text).toContain('0a1b2c3d4e5f');
    expect(text).toContain('1b2c3d4e5f6a');
    expect(text).toContain('scan');
    expect(text).toContain('analyze');

    // 状态徽章类名：running → accent，completed → ok
    expect(wrapper.find('.badge.accent').exists()).toBe(true);
    expect(wrapper.find('.badge.ok').exists()).toBe(true);

    // 进度条宽度映射 progress（0.4 → 40%，1 → 100%；列表倒序，取全部断命中任一）
    const styles = wrapper.findAll('.progress-inner').map(b => b.attributes('style'));
    expect(styles.some(s => s.includes('40%'))).toBe(true);
    expect(styles.some(s => s.includes('100%'))).toBe(true);
  });
});
