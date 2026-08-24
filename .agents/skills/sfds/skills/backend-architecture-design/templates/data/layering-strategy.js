window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["layering-strategy"] = {
  layers: [
    { name: "接口层(API)", path: "api/", responsibility: "协议适配与鉴权", dependsOn: ["application"], forbiddenDeps: ["infrastructure"], codePattern: "ApiController : 无业务逻辑" },
    { name: "应用层(Application)", path: "application/", responsibility: "用例编排与事务", dependsOn: ["domain"], forbiddenDeps: ["api", "infrastructure"] },
    { name: "领域层(Domain)", path: "domain/", responsibility: "业务规则与实体", dependsOn: [], forbiddenDeps: [] },
    { name: "基础设施层(Infrastructure)", path: "infrastructure/", responsibility: "外部资源适配", dependsOn: ["domain", "application"] }
  ],
  directoryTemplate: { "api/": "…", "application/": "…", "domain/": "…", "infrastructure/": "…" }
};