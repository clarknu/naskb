# Page Mock 测试目录说明

> 本目录为 tdd-build Stage 2（Page Mock TDD）的执行目录。
> 现状：Web 端（naskb/web）为 Vue3 全局构建静态包（无 package.json/vitest/@vue/test-utils 工具链），
> **无前端自动化测试基础设施**——执行层暂缺，规格见 `design/07-tdd/page-mock/web-console-tdd-design.md`（TC-M001~TC-M010）。

## 接入路线（后续迭代，按 iterate 流程执行）

1. 在 `naskb/web/` 引入 Vitest + @vue/test-utils + MSW（mock 全部 API，后端零依赖）；
2. 按 `design/07-tdd/page-mock/web-console-tdd-design.md` TC 用例落到 `<client>/pages|components` 测试文件；
3. 接入 `tdd-execute(page-mock)` 执行与报告（tests/test-reports/page-mock-execute-report-{date}.md）。

## 引用

- 设计规格：design/06-web-console/data/tree.js（组件/权限/api_ref 基线）
- 用例规格：design/07-tdd/page-mock/web-console-tdd-design.md
- 差异登记：design/review/design-code-gap.md（G-XX）
