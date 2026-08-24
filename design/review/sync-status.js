/**
 * 资产同步状态追踪 — Sync Status（review 每次复查后更新）
 * 2026-08-24 全量复查（DD-009 迭代后）：全部资产对已同步；dirty 仅保留真实未闭环项。
 */
window.SYNC_STATUS = window.SYNC_STATUS || {};
window.SYNC_STATUS = {
  last_sync_pulse: "2026-08-24T18:00:00",
  last_review: "2026-08-24-naskb-review-v1（✅ 已收敛并归档 _archived/；381 passed；契约 0；E2E 6/6；P-001~P-006 全处置）",

  assets: [
    { path: "design/01-raw-input/", version: 2,
      synced_with: [{ target: "design/02-business-workflow/data/*", version: 1 }], dirty: false },
    { path: "design/domain-registry.js", version: 1,
      synced_with: [{ target: "design/02-business-workflow/data/*", version: 1 }], dirty: false },
    { path: "design/pipeline-state.js", version: 3,
      synced_with: [{ target: ".agents/skills/sfds/_shared/pipeline-registry.js", version: 1 }], dirty: false },
    { path: "design/design-decisions.js", version: 2,
      synced_with: [], dirty: false },
    { path: "design/02-business-workflow/data/{01..06}-*.js", version: 2,
      synced_with: [{ target: "design/04-platform-api/data/rest/*", version: 2 },
                    { target: "design/06-web-console/data/tree.js", version: 2 }], dirty: false },
    { path: "design/03-entity-relationship/data/*", version: 1,
      synced_with: [{ target: "design/03-entity-relationship/data/core-er.js", version: 1 }], dirty: false },
    { path: "design/04-platform-api/data/rest/*", version: 2,
      synced_with: [{ target: "naskb/scripts/naskb/server/*.py", version: "（实现）" }], dirty: false,
      note: "DD-009 对齐：28 端点 equal；200 口径、folder 语义差异已按实现回写设计" },
    { path: "design/04-platform-api/data/ai-tools/*", version: 2,
      synced_with: [{ target: "naskb/scripts/naskb/mcp/server.py + capabilities.py", version: "（实现）" }], dirty: false,
      note: "17 工具对齐；直链网关边界已固化" },
    { path: "design/05-backend-architecture/data/*", version: 2,
      synced_with: [{ target: "design/04-platform-api/data/rest/*", version: 2 }], dirty: false },
    { path: "design/05-backend-architecture/data/arch-contract.js", version: 1,
      synced_with: [{ target: "scripts/probes/out/facts.json", version: "每次再生成" }], dirty: false },
    { path: "design/06-web-console/data/*", version: 2,
      synced_with: [{ target: "design/04-platform-api/data/rest/*", version: 2 },
                    { target: "naskb/web/public/app-core.js + app-main.js", version: "（实现，P-002 组件化拆分）" }], dirty: false },
    { path: "design/07-tdd/*", version: 3,
      synced_with: [{ target: "tests/", version: "（381 passed；page-mock 21 + 初始化时序 2）" }], dirty: false },
    { path: "design/review/user-decisions-pending.md", version: 2,
      synced_with: [{ target: "design/01-raw-input/07-user-decisions-2026-08-24.md", version: 1 }], dirty: false },
    { path: "tests/test_arch_contract.py", version: 1,
      synced_with: [{ target: "design/05-backend-architecture/data/arch-contract.js", version: 1 }], dirty: false },
    { path: "release/*", version: 2,
      synced_with: [{ target: "design/review/remaining-issues.md", version: 2 }], dirty: false }
  ]
};
