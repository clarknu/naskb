/* TC-M009 —— 文件详情模态（模态）
 * 位置：tests/page-mock/web-console/file-modal.spec.js
 * 说明：
 *  - FileModal 在 setup 里注册 window.addEventListener('open-file', …)，挂载后向 window 派发
 *    CustomEvent（detail: {rid,src}）即触发 load()：GET /api/files/{rid} + GET /api/files/{rid}/preview。
 *  - 按 preview.viewable 断言预览分派：pdf → iframe、image → img、none → 提示文案；并断元数据 kv。
 */
import { describe, it, expect } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { FileModal } from '../../../naskb/web/public/app-core.js';
import { fileMeta, filePreview } from './fixtures.js';

function mountAndOpen(rid = 'r1', src = 's1') {
  const wrapper = mount(FileModal);
  window.dispatchEvent(new CustomEvent('open-file', { detail: { rid, src } }));
  return wrapper;
}

function seedMeta() {
  globalThis.__addApiMock('GET', /\/api\/files\/r1\?/, () =>
    globalThis.__jsonResponse(200, fileMeta('r1')));
}
function seedPreview(preview) {
  globalThis.__addApiMock('GET', /\/api\/files\/r1\/preview/, () =>
    globalThis.__jsonResponse(200, preview));
}

describe('TC-M009 文件详情模态渲染', () => {
  it('元数据 kv 渲染完整（路径/分类/标签/摘要/指纹/大小时间/分析时间）', async () => {
    seedMeta();
    seedPreview(filePreview('pdf', { url: '/api/files/r1/stream?src=s1' }));
    const wrapper = mountAndOpen();
    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain('🧠 知识元数据');
    expect(text).toContain('docs/合同.pdf');   // 路径
    expect(text).toContain('合同');           // 分类
    expect(text).toContain('租赁');           // 标签
    expect(text).toContain('月租金为 3,200 元。'); // 摘要
    expect(text).toContain('sha256');          // 指纹算法（hash_algorithm 前缀）
    expect(text).toContain('分析时间');
    // 下载 href 指向 download_url
    expect(wrapper.find('a.button').attributes('href')).toBe('/api/files/r1/download?src=s1');
  });

  it('viewable=pdf → 渲染 iframe（src=preview.url）', async () => {
    seedMeta();
    seedPreview(filePreview('pdf', { url: '/api/files/r1/stream?src=s1' }));
    const wrapper = mountAndOpen();
    await flushPromises();

    const iframe = wrapper.find('.viewer iframe');
    expect(iframe.exists()).toBe(true);
    expect(iframe.attributes('src')).toBe('/api/files/r1/stream?src=s1');
  });

  it('viewable=image → 渲染 img（src=preview.url）', async () => {
    seedMeta();
    seedPreview(filePreview('image', { url: '/api/files/r1/stream?src=s1' }));
    const wrapper = mountAndOpen();
    await flushPromises();

    const img = wrapper.find('.viewer img');
    expect(img.exists()).toBe(true);
    expect(img.attributes('src')).toBe('/api/files/r1/stream?src=s1');
  });

  it('viewable=none → 渲染提示文案（含 reason）', async () => {
    seedMeta();
    seedPreview(filePreview('none', { reason: '不支持的二进制格式' }));
    const wrapper = mountAndOpen();
    await flushPromises();

    // none 分支是 <div v-else>（无 .viewer 类），提示文案在该 div 内的 .hint 中
    const hint = wrapper.find('.hint');
    expect(hint.exists()).toBe(true);
    expect(hint.text()).toContain('暂不支持在线查看');
    expect(hint.text()).toContain('不支持的二进制格式');
  });
});
