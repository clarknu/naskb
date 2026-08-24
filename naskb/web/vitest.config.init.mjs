import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const vueBundler = path.resolve(__dirname, 'node_modules/vue/dist/vue.esm-bundler.js');

// 独立项目：TC-M010② 模块初始化时序（tests/page-mock/web-console/init/app-shell-init.spec.js）
// 与 vitest.config.mjs 的唯一差别：setup = tests/init-setup.js（播种 hash/token 后再加载 app-core）。
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/init-setup.js'],
    include: ['../../tests/page-mock/web-console/init/*.spec.js'],
    css: false,
  },
  server: { fs: { allow: [path.resolve(__dirname, '..', '..'), path.resolve(__dirname, 'node_modules')] } },
  resolve: {
    alias: [
      { find: '@vue/test-utils', replacement: path.resolve(__dirname, 'node_modules/@vue/test-utils/dist/vue-test-utils.esm-bundler.mjs') },
      { find: 'vue', replacement: vueBundler },
    ],
  },
});
