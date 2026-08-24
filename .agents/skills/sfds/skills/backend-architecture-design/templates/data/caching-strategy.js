window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["caching-strategy"] = {
  cacheBackend: { development: "内存", production: "Redis 独立实例" },
  policies: [
    { resource: "用户资料GET", layer: "本地", ttl: "5m", strategy: "cache-aside", invalidation: "写后删除" },
    { resource: "领域枚举", layer: "Redis", ttl: "24h", strategy: "cache-aside", invalidation: "发布事件" }
  ],
  antiPatterns: { "缓存穿透": "空值也缓存短TTL", "热点Key": "随机过期+本地兜底" }
};