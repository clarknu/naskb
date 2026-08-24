/**
 * REST 领域数据文件模板 — {领域名称}
 *
 * 使用方式：复制到 design/04-platform-api/data/{domain-slug}.js，
 * 替换所有 {PLACEHOLDER} 并填充实际内容。
 *
 * 字段说明：
 *   - 每个 endpoint 穷尽 6 维度 business_logic
 *   - 错误场景引用 §7.2 的错误码区间
 *   - 幂等/缓存/频控遵循 §7 公共约定
 */

window.API_DATA = window.API_DATA || {};
window.API_DATA["{domain-slug}"] = {

  // ═══ 元信息 ═══
  domain: "{编号如 01}",
  title: "{领域名称}",
  slug: "{domain-slug}",
  description: "{领域描述}",
  last_updated: "{YYYY-MM-DD}",
  workflow_ref: "../../02-business-workflow/data/{domain-slug}.js",
  er_ref: "../../03-entity-relationship/data/{domain-slug}.js",

  // ═══ 权限名备用查找表 ═══
  // 从 business-workflow 复制本域权限点。当 WF_DATA 不可用时兜底
  _permission_lookup: {
    "{PermissionId}": "{中文名称}"
  },

  // ═══ 领域概述 ═══
  overview_blocks: [
    { type: "table", headers: ["子域", "核心实体", "说明"], rows: [
      ["{子域1}", "{Entity1 / Entity2}", "{说明}"]
    ]},
    { type: "note", level: "info", text: "{设计说明}" }
  ],

  // ═══ 关键设计决策 ═══
  design_decisions: [
    { title: "{决策标题}", detail: "{决策详情}" }
  ],

  // ═══════════════════════════════════════
  // 端点定义
  // ═══════════════════════════════════════
  endpoints: [

    // ── GET 列表示例 ──
    {
      id: "{rest-endpoint-id}",           // kebab-case 唯一 ID
      protocol: "rest",
      method: "GET",
      path: "/api/v1/{resources}",
      permission: "{PermissionId | public}",
      summary: "{一句话摘要}",
      scenario: "{使用场景描述}",
      description: "{详细说明}",

      // ── 6 维度业务逻辑 ──
      business_logic: {
        preconditions: ["{前置条件1}"],
        steps: [
          "① {步骤1}",
          "② {步骤2}"
        ],
        post_effects: ["{后置效果}"],
        state_machine: "{状态机描述，无则填'无状态变更'}",
        side_effects: ["{副作用，如发送通知/写日志}"],
        related_apis: [
          "GET /api/v1/{resources}/{id} — 获取详情",
          "POST /api/v1/{resources} — 创建"
        ]
      },

      // ── 请求参数 ──
      path_params: [                              // 无路径参数可省略
        ["{param_name}", "{type}", "是/否", "{含义}", "{约束}", "{示例值}"]
      ],
      query_params: [                             // 无查询参数可省略
        ["{param_name}", "{type}", "是/否", "{含义}", "{约束}", "{默认值}", "{示例值}"]
      ],
      body_params: [                              // GET/DELETE 无 body
        ["{field}", "{type}", "是/否", "{含义}", "{约束}", "{示例值}"]
      ],

      // ── 响应定义 ──
      responses: [
        {
          description: "成功响应 — HTTP 200",
          json: '{\n  "items": [...],\n  "total": 10\n}',
          fields: [
            ["{field}", "{type}", "{说明}"]
          ]
        }
      ],

      // ── 错误场景（3-6 个）──
      // 引用 §7.2 错误码区间：[HTTP码, "error_code (code)", "触发条件", "说明"]
      errors: [
        ["400", "INVALID_PARAMETER (40001)", "{触发条件}", "{说明}"],
        ["401", "UNAUTHORIZED (41001)", "未登录或 token 过期", "未认证"],
        ["403", "FORBIDDEN (41011)", "无权限", "权限不足"],
        ["404", "NOT_FOUND (42001)", "{资源不存在}", "{说明}"]
      ],

      // ── 幂等 / 缓存 / 频控 ──
      idempotency: { is_idempotent: true, method: "GET 请求天然幂等", retry: "网络超时可直接重试" },
      caching:    { method: "HTTP 缓存", ttl: "5 min", note: "公开资源" },
      rate_limit: { limit: "100 req/min", dimension: "per-user", note: "常规频控" }
    },

    // ── POST 创建示例 ──
    {
      id: "{rest-endpoint-id}",
      protocol: "rest",
      method: "POST",
      path: "/api/v1/{resources}",
      permission: "{PermissionId}",
      summary: "{创建资源的摘要}",
      scenario: "{场景}",
      description: "{详细说明}",

      business_logic: {
        preconditions: ["{前置条件}"],
        steps: [
          "① 验证请求参数",
          "② 创建资源记录",
          "③ 返回创建结果"
        ],
        post_effects: ["{数据变化}"],
        state_machine: "{状态变更}",
        side_effects: [],
        related_apis: ["GET /api/v1/{resources}/{id} — 获取详情"]
      },

      body_params: [
        ["{field}", "{type}", "是", "{含义}", "{约束}", "{示例值}"]
      ],

      responses: [
        {
          description: "成功响应 — HTTP 201",
          json: '{\n  "id": "uuid",\n  "name": "示例"\n}',
          fields: [["{field}", "{type}", "{说明}"]]
        }
      ],

      errors: [
        ["400", "INVALID_PARAMETER (40001)", "{触发条件}", "{说明}"],
        ["409", "DUPLICATE_REQUEST (42012)", "重复的 Idempotency-Key", "重复请求"],
        ["422", "CONFLICT (42011)", "{业务冲突条件}", "{说明}"]
      ],

      idempotency: { is_idempotent: false, method: "通过 Idempotency-Key 头部支持", retry: "失败可重试，使用相同 key 防重复创建" }
    }
  ]
};
