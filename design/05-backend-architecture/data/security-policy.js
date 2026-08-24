/**
 * 安全策略 — Security Policy
 * NASKB：单管理员 Bearer + 匿名只读；敏感字段脱敏；源端零写（ro）
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["security-policy"] = {
  auth: {
    scheme: "Bearer token（config [server] tokens，compare_digest 常量比较，无签名/无过期）",
    tokenLifetime: "常驻（管理端静态令牌；单 token 声明——多 token 仅首个生效已明示，DD-009）",
    refreshToken: "—",
    anonymous: "无（2026-08-24 拍板 DD-009：全部端点需身份；仅 /api/config/public、/api/docs、/api/openapi.json 匿名作启动引导）"
  },
  authorization: {
    model: "permission-based（business-workflow permissions 唯一定义源；RBAC 以角色聚合权限点）",
    enforcement: "端点 permission 标注与实际鉴权（单管理员：token 有→全权；匿名→匿名前缀只读）",
    note: "设计资产按权限点标注；当前实现为单管理员模型，permission 细化属演进项（R7-15 多用户）"
  },
  tenantIsolation: { enabled: false, strategy: "—" },
  sensitiveData: {
    encryption: ["（webdav password 明文存储现状——加密策略待定，见 design-code-gap）"],
    hashing: ["（无用户口令——单管理员静态 token）"],
    masking: ["password（to_api 脱敏）", "token（日志）"]
  },
  exposure: {
    internalOnlyEndpoints: ["POST /api/pg/rebind", "POST /api/reload"],
    anonymousOnly: { endpoints: ["/api/config/public", "/api/docs", "/api/openapi.json"], note: "启动引导/文档，纯只读——匿名例外（DD-009）" },
    note: "其余一切端点需 Bearer token；匿名白名单机制已移除"
  },
  directLinkBoundary: {
    policy: "MCP 直链（kb_fetch_file / kb_get_file_url）不带 token——安全边界=外围网关层 IP 约束与限流策略（网络/部署边界），API 层不认证",
    rationale: "DD-009 显式决策（内网/受控网段场景）：文件直链用于 Agent/浏览器流式读取；网络层白名单+限流承担访问控制",
    implementation: "部署形态：平台服务仅监听内网/受控网段或经网关反代（release/environments.yaml 与 policy.md 注明）；公网暴露前须网关 IP 白名单"
  },
  sourceSafety: {
    ro_readonly: "ro 源端一个字节不写（fs adapter 只读通道）",
    rw_writeback: "rw 源仅 .naskb 双写 + 整理移动（明确用户确认）",
    no_src_path_expose: "API 寻址只用 resource_id + src（不暴露源端绝对路径）"
  }
};
