import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const vueBundler = path.resolve(__dirname, 'node_modules/vue/dist/vue.esm-bundler.js');

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.js'],
    include: ['../../tests/page-mock/web-console/**/*.spec.js'],
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
