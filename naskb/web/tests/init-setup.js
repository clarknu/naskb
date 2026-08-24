/* tests/init-setup.js —— TC-M010② 专用 setup（模拟“页面加载”时序）
 *
 * 目的：验证 app-core **模块初始化**时对 location.hash / localStorage 的读取
 * （“刷新直达 #/sources / 刷新后令牌恢复”）。浏览器时序 = 模块加载瞬间读取；
 * 因此本 setup 必须在 app-core 加载**之前**播种，再动态加载 setup.js（其静态
 * import 链会引入 app-core），并把初始化结果快照到 globalThis.__NASKB_INIT_SNAPSHOT。
 *
 * 仅被 vitest.config.init.mjs（独立项目）引用，不影响主套件的用例隔离。
 */
location.hash = '#/sources';
localStorage.setItem('naskb_token', 'tok-restore-001');

// 动态加载主 setup（fetch mock / confirm 桩 / 用例间清理），确保 app-core 在播种之后才被初始化
await import('./setup.js');

const { state } = await import('../public/app-core.js');
globalThis.__NASKB_INIT_SNAPSHOT = {
  route: state.route,   // 期望 'sources'（来自 location.hash）
  token: state.token,   // 期望 'tok-restore-001'（来自 localStorage）
};
