/**
 * 域注册表 — Domain Registry
 *
 * 定义项目包含的所有业务领域及其标识（slug）。
 * 在初始域范围界定阶段创建初版，随流水线执行持续演进。
 * 参见：docs/development-standard.md §5.3
 * 版本：v1（{{date}}）
 */
(function () {
  var PS_DATA = window.PS_DATA = window.PS_DATA || {};
  PS_DATA.domainRegistry = {
    identity: {
      project: '{{project-name}}',
      standard: 'SFDS v3',
    },
    domains: [
      // 在初始域范围界定阶段逐步填充：
      // { id: '01', slug: 'first-domain',   name: 'TODO', description: '...' },
      // { id: '02', slug: 'second-domain',  name: 'TODO', description: '...' },
    ],
  };
})();
