/**
 * REST 领域数据文件 — 平台服务
 * 依据：server/routes_content.py + routes_sources.py（jobs 部分）+ app.py（config）实际注册
 */

window.API_DATA = window.API_DATA || {};
window.API_DATA["06-platform-console"] = {

  domain: "06",
  title: "平台服务",
  slug: "platform-console",
  description: "内容访问（目录树/文件元数据）、下载代理（Range/ETag）、在线预览矩阵、任务中心、公开配置",
  last_updated: "2026-08-24",
  workflow_ref: "../../02-business-workflow/data/06-platform-console.js",
  er_ref: "../../03-entity-relationship/data/06-platform-console.js",

  _permission_lookup: {
    "JobsView": "查看任务中心",
    "FileDownload": "下载文件",
    "FilePreview": "在线预览",
    "ConfigView": "查看公开配置",
    "StatsView": "查看统计"
  },

  overview_blocks: [
    { type: "table", headers: ["子域", "核心实体", "说明"], rows: [
      ["目录浏览", "FolderEntry / Resource", "GET /api/tree（来源下拉 + 目录树）"],
      ["文件详情", "Resource", "GET /api/files/{rid}（知识元数据）"],
      ["下载代理", "RangeRequest", "GET /api/files/{rid}/download（Range/ETag/304/416/503）"],
      ["在线预览", "PreviewKind", "GET /api/files/{rid}/preview|parsed|thumbnail"],
      ["任务中心", "Job", "GET /api/jobs、GET /api/jobs/{id}"],
      ["公开配置", "config", "GET /api/config/public（auth_required/anonymous_read）"]
    ]},
    { type: "note", level: "info", text: "内容访问以 resource_id + src 寻址（不含源端绝对路径，安全边界）。" }
  ],

  design_decisions: [
    { title: "浏览/下载/预览复用同一寻址", detail: "tree→files/{rid}→download/preview 全链以 resource_id 为锚，缩略图按 resource_id+w 缓存于 store/thumbs" },
    { title: "预览矩阵独立判定", detail: "view_kind 按扩展名判定；不支持类型返回 reason（'可下载后本地打开'），不静默失败" }
  ],

  endpoints: [

    // ── GET 目录条目（/api/folder）──
    { id: "folder-entry", protocol: "rest", method: "GET", path: "/api/folder", permission: "login_required",
      summary: "目录级条目（文件夹描述）", scenario: "目录描述展示；MCP kb_list_tree 的数据来源之一",
      description: "按 src+dir 返回目录条目：优先 folders 表（summary/description/tags/file_count）；未登记时现场枚举生成（空目录=合法空条目）。2026-08-24 拍板接回（DD-009）。",
      business_logic: {
        preconditions: ["已认证", "来源存在"],
        steps: ["① 解析 src+dir", "② 查 folders 表；无 → list_dir 枚举生成（rw 源的 folder.json 兜底为后续增强）", "③ 返回条目（来源不存在才 404）"],
        post_effects: [],
        state_machine: "无状态变更",
        side_effects: [],
        related_apis: ["GET /api/tree — 目录树", "GET /api/files/{rid} — 文件详情"]
      },
      query_params: [["src","string","是","来源 ID","—","uuid"],["dir","string","否","目录 rel_path","rel_path","docs"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "rel_path": "docs",\n  "name": "docs",\n  "summary": "…",\n  "description": "…",\n  "tags": ["合同"],\n  "file_count": 12,\n  "source": "v2.json|generated"\n}',
          fields: [["rel_path","text","目录 rel_path"],["name","text","目录名"],["summary","text","目录描述"],["description","text","folder.json description"],["tags","text[]","标签"],["file_count","int","文件数"],["source","enum","folders|folder.json|generated（数据来源）"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在","—（空目录返回 generated 空条目，非 404）"],["401","UNAUTHORIZED (41001)","未认证","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "实时" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 目录树 ──
    { id: "tree", protocol: "rest", method: "GET", path: "/api/tree", permission: "login_required",
      summary: "目录浏览（树/列表）", scenario: "浏览页：来源选择 → 目录 → 文件列表",
      description: "按 src（来源）+ dir（rel_path）列出子目录与文件；缩略图 URL 内嵌资源字段。",
      business_logic: {
        preconditions: ["来源存在（get/list 匿名口径差异见 _conventions.auth）"],
        steps: ["① 解析 src+dir", "② 枚举子项 + 元数据", "③ 返回 dirs/files"],
        post_effects: [],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/files/{rid} — 文件详情", "GET /api/files/{rid}/thumbnail"]
      },
      query_params: [["src","string","是","来源 ID","—","uuid"],["dir","string","否","目录 rel_path","—","docs"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "dirs": [{ "rel_path": "docs", "name": "docs", "file_count": 12, "summary": "…" }],\n  "files": [{ "resource_id": "uuid", "name": "合同.pdf", "size_bytes": 120, "summary": "…", "category": "合同", "status": "ok" }]\n}',
          fields: [["dirs[].rel_path","text","目录 rel_path"],["dirs[].name","text","目录名"],["dirs[].file_count","int","文件数"],["dirs[].summary","text","目录描述"],["files[].resource_id","UUID","资源 ID"],["files[].name","text","文件名"],["files[].size_bytes","bigint","大小"],["files[].summary","text","摘要"],["files[].category","text","分类"],["files[].status","enum","ok|stale_source|stale_vector|missing_source"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在","—"],["401","UNAUTHORIZED (41001)","认证开启且未命中匿名","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "实时枚举" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 文件详情 ──
    { id: "file-meta", protocol: "rest", method: "GET", path: "/api/files/{rid}", permission: "login_required",
      summary: "文件知识元数据", scenario: "文件详情模态头部（元数据区）",
      description: "返回 resource 元数据 + download_url（预览模态用）。",
      business_logic: {
        preconditions: ["资源存在"],
        steps: ["① 解析 rid+src", "② 读取元数据", "③ 组装 download_url"],
        post_effects: [],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/files/{rid}/preview", "GET /api/files/{rid}/download"]
      },
      path_params: [["rid","UUID","是","资源 ID","—","—"]],
      query_params: [["src","string","否","来源 ID","—","uuid"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "resource": {\n    "name": "合同.pdf",\n    "rel_path": "docs/合同.pdf",\n    "category": "合同",\n    "tags": ["租赁"],\n    "summary": "…",\n    "content_description": "…",\n    "file_hash": "sha256:…",\n    "hash_algorithm": "sha256:sample8x64k",\n    "size_bytes": 120,\n    "mtime": "2026-08-01T10:00:00",\n    "analyzed_at": "2026-08-02T10:00:00",\n    "status": "ok"\n  },\n  "download_url": "/api/files/uuid/download?src=uuid"\n}',
          fields: [["resource.name","text","文件名"],["resource.rel_path","text","相对路径"],["resource.category","text","分类"],["resource.tags","text[]","标签"],["resource.summary","text","摘要"],["resource.content_description","text","内容描述"],["resource.file_hash","text","指纹"],["resource.hash_algorithm","enum","指纹算法"],["resource.size_bytes","bigint","大小"],["resource.mtime","datetime","修改时间"],["resource.analyzed_at","datetime","分析时间"],["resource.status","enum","状态"],["download_url","text","下载地址"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","资源不存在","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "元数据实时" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 下载代理 ──
    { id: "download", protocol: "rest", method: "GET", path: "/api/files/{rid}/download", permission: "login_required",
      summary: "流式下载（Range/ETag）", scenario: "文件详情『下载』；播放器/预览源使用",
      description: "ETag=file_hash（强/弱 W/\"size-mtime\"）；支持 If-None-Match→304、Range 单区间→206/416、stale→503。",
      business_logic: {
        preconditions: ["资源存在", "源可达（stale → 503 提示）"],
        steps: ["① 解析 rid+src → fs+path", "② ETag 计算与 If-None-Match 比对", "③ Range 解析 → 流式响应"],
        post_effects: [],
        state_machine: "无",
        side_effects: ["访问日志"],
        related_apis: ["GET /api/files/{rid}", "GET /api/files/{rid}/preview"]
      },
      path_params: [["rid","UUID","是","资源 ID","—","—"]],
      query_params: [["src","string","否","来源 ID","—","uuid"],["disposition","string","否","inline|attachment","—","inline"]],
      responses: [
        { description: "成功响应 — HTTP 206", json: "（二进制流）", fields: [["ETag","header","强/弱 ETag"],["Accept-Ranges","header","bytes"],["Content-Range","header","bytes a-b/total"]] },
        { description: "缓存命中 — HTTP 304", json: "（空体）", fields: [["ETag","header","比对命中"]] }
      ],
      errors: [
        ["404","NOT_FOUND (42001)","资源不存在","—"],
        ["416","RANGE_NOT_SATISFIABLE (44001)","Range 越界","合并/重发"],
        ["503","DEPENDENCY_UNAVAILABLE (45001)","源消失/过期","stale 提示"]
      ],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试（断点续传）" },
      caching: { method: "ETag 校验", ttl: "—", note: "强/弱双模式" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 预览 ──
    { id: "preview", protocol: "rest", method: "GET", path: "/api/files/{rid}/preview", permission: "login_required",
      summary: "在线预览判定与渲染", scenario: "文件详情模态预览区",
      description: "viewable: image|video|audio|pdf|text|html|office|parsed|none + url/content/reason。",
      business_logic: {
        preconditions: ["资源存在"],
        steps: ["① view_kind 判定（扩展名）", "② 按类型取 url（内部端点）/content（text/html）", "③ 不支持 → reason"],
        post_effects: [],
        state_machine: "无",
        side_effects: ["（parsed）rw 源解析视图；ro 源不可用"],
        related_apis: ["GET /api/files/{rid}", "GET /api/files/{rid}/parsed"]
      },
      path_params: [["rid","UUID","是","资源 ID","—","—"]],
      query_params: [["src","string","否","来源 ID","—","uuid"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "viewable": "pdf",\n  "url": "/api/files/uuid/stream?src=uuid"\n}',
          fields: [["viewable","enum","预览矩阵"],["url","text","渲染地址"],["content","text","text/html 内容"],["parsed_url","text","解析视图地址"],["reason","text","不支持原因"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","资源不存在","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "—" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 解析视图 ──
    { id: "parsed", protocol: "rest", method: "GET", path: "/api/files/{rid}/parsed", permission: "login_required",
      summary: "MinerU 解析视图（HTML）", scenario: "文件详情『解析视图』iframe",
      description: "返回 MinerU 产物 HTML；仅 rw 源（持久 artifacts）。",
      business_logic: {
        preconditions: ["资源存在", "rw 源 + 存在 artifacts"],
        steps: ["① 定位 artifacts md/html", "② 渲染 HTML"],
        post_effects: [],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/files/{rid}/preview"]
      },
      path_params: [["rid","UUID","是","资源 ID","—","—"]],
      query_params: [["src","string","否","来源 ID","—","uuid"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: "（HTML）", fields: [["—","—","解析视图 HTML（iframe 渲染）"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","无解析产物","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "—" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 缩略图 ──
    { id: "thumbnail", protocol: "rest", method: "GET", path: "/api/files/{rid}/thumbnail", permission: "login_required",
      summary: "缩略图（资源缓存）", scenario: "浏览页/文件列表缩略图",
      description: "图片 Pillow（≤12MB）/ 视频 ffmpeg 第 4 秒（≤100MB）；缓存 store/thumbs/。",
      business_logic: {
        preconditions: ["资源存在"],
        steps: ["① 缓存命中 → 直接返回", "② 生成缩略图（Pillow/ffmpeg）", "③ 写缓存"],
        post_effects: ["缓存写"],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/tree"]
      },
      path_params: [["rid","UUID","是","资源 ID","—","—"]],
      query_params: [["src","string","否","来源 ID","—","uuid"],["w","int","否","宽度","—","80"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: "（图片流）", fields: [["—","—","JPEG/PNG 缩略图"]] }
      ],
      errors: [["415","UNSUPPORTED (43001)","不可生图类型","—"],["404","NOT_FOUND (42001)","资源不存在","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "磁盘缓存", ttl: "按 resource_id + w", note: "来源删除时清理" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 任务列表 ──
    { id: "jobs-list", protocol: "rest", method: "GET", path: "/api/jobs", permission: "JobsView",
      summary: "任务列表（串行队列）", scenario: "任务中心页（2s 轮询）",
      description: "返回全部任务（内存队列，重启即失）。",
      business_logic: {
        preconditions: ["已认证（口径差异见 _conventions.auth）"],
        steps: ["① 读 JobManager 字典", "② 倒序返回"],
        post_effects: [],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/jobs/{job_id}"]
      },
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "jobs": [{ "id": "0a1b2c3d4e5f", "kind": "scan", "status": "running", "progress": 0.4, "message": "…", "created_at": "2026-08-24T10:00:00" }]\n}',
          fields: [["jobs[].id","string","任务 ID"],["jobs[].kind","enum","scan|analyze|adopt|confirm"],["jobs[].status","enum","pending|running|completed|failed"],["jobs[].progress","decimal","进度 0-1"],["jobs[].message","text","进度消息"],["jobs[].result","json","结果"],["jobs[].error","text","失败原因"],["jobs[].created_at","datetime","创建时间"]] }
      ],
      errors: [["401","UNAUTHORIZED (41001)","未认证","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "实时" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 任务详情 ──
    { id: "job-detail", protocol: "rest", method: "GET", path: "/api/jobs/{job_id}", permission: "login_required",
      summary: "任务详情（进度轮询）", scenario: "来源页 pollJob（1.5s）",
      description: "按 id 返回任务（result 内含 deep.chunks 等统计）。",
      business_logic: {
        preconditions: ["任务存在"],
        steps: ["① 读 JobManager", "② 返回 job"],
        post_effects: [],
        state_machine: "无",
        side_effects: [],
        related_apis: ["GET /api/jobs"]
      },
      path_params: [["job_id","string","是","任务 ID","12 hex","0a1b2c3d4e5f"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "id": "0a1b2c3d4e5f",\n  "status": "completed",\n  "result": { "added": 2, "stale_source": 1, "missing": 0, "deep": { "chunks": 12 } }\n}',
          fields: [["id","string","任务 ID"],["status","enum","状态"],["progress","decimal","进度"],["message","text","消息"],["result","json","结果（扫描统计/deep.chunks）"],["error","text","失败原因"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","任务不存在","内存队列重启即失"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "实时" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 公开配置 ──
    { id: "public-config", protocol: "rest", method: "GET", path: "/api/config/public", permission: "ConfigView|public",
      summary: "公开配置（认证状态）", scenario: "前端启动时拉取",
      description: "返回 auth_required / anonymous_read；UI 据此显示令牌输入区。",
      business_logic: {
        preconditions: [],
        steps: ["① 读配置", "② 组装公开字段"],
        post_effects: [],
        state_machine: "无",
        side_effects: [],
        related_apis: []
      },
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "auth_required": true,\n  "anonymous_read": true\n}', fields: [["auth_required","bool","是否要求认证"],["anonymous_read","bool","匿名只读开关"]] }
      ],
      errors: [],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "客户端存储", ttl: "会话级", note: "—" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    }
  ]
};
