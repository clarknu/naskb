/**
 * 缓存策略 — Caching Strategy
 * NASKB 现状：无 Redis 等集中缓存；缓存面 = ETag 校验 + 缩略图磁盘缓存 + 索引缓存（npz 本地）
 */
window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["caching-strategy"] = {
  layers: ["local-disk", "http-etag", "index-cache"],
  defaultTtl: { "index-cache": "直到索引重建", "thumbnail": "按 resource_id + w", "http-etag": "由 If-None-Match 判定" },
  caching: [
    {
      resource: "download-response",
      layer: "http",
      ttl: "强/弱 ETag（file_hash / size-mtime）",
      key: "ETag: \"file_hash\" | W/\"size-mtime\"",
      invalidation: "资源指纹变化即失效（304 自动命中）",
      antiBreakdown: "—（无并发热点）",
      antiPenetration: "—"
    },
    {
      resource: "thumbnail",
      layer: "disk",
      ttl: "store/thumbs/<resource_id>-<w>.*（来源删除时清理）",
      key: "store/thumbs/",
      invalidation: "来源删除/重建时清理",
      antiBreakdown: "—",
      antiPenetration: "—"
    },
    {
      resource: "vector-index",
      layer: "memory/disk",
      ttl: "db/vectors.npz + vectors.json（显式 build/reload）",
      key: "<work_path>/db/",
      invalidation: "index-vectors / sync-vectors 后重建",
      antiBreakdown: "—",
      antiPenetration: "—"
    },
    {
      resource: "legacy-serve-stats",
      layer: "none",
      ttl: "no-store",
      key: "—",
      invalidation: "—",
      antiBreakdown: "—",
      antiPenetration: "—"
    }
  ],
  notes: [
    "演进项：模板方法论 G1-G5 层级（Redis 缓存 TTL 10min、cache:{domain}:{resource}:{id}:{view} 键格式）——当前数据规模下不引入 Redis（宿主化中间件原则：需要时用统一管理实例，不在进程内自建）",
    "下载代理 Cache-Control: no-store（auth 中间件统一加）——ETag 协商仍生效"
  ]
};
