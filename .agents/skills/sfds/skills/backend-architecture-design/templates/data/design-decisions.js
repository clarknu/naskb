window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["design-decisions"] = {
  decisions: [
    { id: "D-001", date: "2026-08-23", trigger: "模块化单体选型", status: "applied", synced: true,
      decision: "采用模块化单体+事件总线", rationale: "团队规模与交付节奏权衡",
      truthSource: "raw-input/…", impactAssets: ["design/05-backend-architecture"], alternatives: "微服务（暂缓）" }
  ]
};