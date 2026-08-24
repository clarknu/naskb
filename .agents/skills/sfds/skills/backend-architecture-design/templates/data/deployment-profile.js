/**
 * 部署概要 — Deployment Profile（L4+ 模板）
 *
 * 复制到项目 design/05-backend-architecture/data/ 后编辑
 * 版本：v1
 *
 * 适用等级：L4+（多服务/微服务/需要灰度与独立配置治理时）。
 * 字段对齐 backend-architecture-design SKILL.md §2 数据文件表（deployment-profile.js 行）与出口门禁 L688。
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["deployment-profile"] = (function () {

  var _trace = {
    consumes: ["topology:system-topology", "arch:arch-contract", "workflow:..."],
    produces: ["constraint:deployment"]
  };

  return {
    _trace: _trace,

    // 服务拓扑：每个服务/模块的部署形态（镜像、副本数、启动方式）
    services: [
      {
        id: "api-gateway",
        kind: "gateway",            // gateway | service | worker | scheduler
        replicas: 2,
        containerPort: 8080,
        scaling: { mode: "replicas", min: 2, max: 5, targetCPU: 70 },
        health: { path: "/healthz", intervalSec: 10 }
      },
      {
        id: "core-api",
        kind: "service",
        replicas: 2,
        containerPort: 8000,
        env: ["DB_POOL_SIZE=20", "REDIS_URL=${REDIS_URL}"]
      }
    ],

    // 网关：路由/限流/鉴权挂载点
    gateway: {
      kind: "edge",                 // edge（入口网关）| mesh（服务网格）| api（API 网关）
      routes: [
        { prefix: "/api/v1", target: "core-api", stripPrefix: true }
      ],
      rateLimit: { qps: 1000, burst: 2000 },
      auth: { type: "jwt", issuer: "https://idp.example" }
    },

    // 注册/发现
    registry: {
      kind: "consul",               // consul | eureka | k8s-service | nacos
      enabled: true,
      ttl: 30
    },

    // 灰度发布
    canary: {
      enabled: true,
      stages: [                     // 灰度批次（按比例或按分流规则）
        { id: "canary-5", weight: 5,  criteria: "internal_users" },
        { id: "canary-30", weight: 30, criteria: "feature_flag:safe_rollout" },
        { id: "full",      weight: 100 }
      ],
      rollback: { auto: true, thresholdFailRate: 0.05, sampleWindowSec: 300 }
    },

    // 配置：集中配置/密钥管理
    config: {
      kind: "configmap",            // configmap | apollo | nacos | env-file
      secrets: "vault",             // vault | kms | ssm | env
      required: ["DB_URL", "REDIS_URL", "JWT_PUBKEY"]
    }
  };
})();
