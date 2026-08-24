/* NASKB Web 控制台 —— 入口（运行时零构建，无打包步骤）
 * 业务逻辑与组件全部在 app-core.js；本文件只负责挂载：
 *   createNaskbApp('#app') 内部执行 createApp(App).mount + 启动期 hashchange/配置拉取。
 * 浏览器加载顺序：<script type="module" src="/app-main.js"></script>
 */
import { createNaskbApp } from './app-core.js';

createNaskbApp('#app');
