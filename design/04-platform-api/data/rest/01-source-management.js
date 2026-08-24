/**
 * REST 领域数据文件 — 来源管理
 * 依据：server/routes_sources.py 实际注册（代码基线为准，差异见 design-code-gap.md）
 */

window.API_DATA = window.API_DATA || {};
window.API_DATA["01-source-management"] = {

  domain: "01",
  title: "来源管理",
  slug: "source-management",
  description: "知识来源注册与安全边界：注册/测试/扫描/分析/收编/变更确认/启停删除",
  last_updated: "2026-08-24",
  workflow_ref: "../../02-business-workflow/data/01-source-management.js",
  er_ref: "../../03-entity-relationship/data/01-source-management.js",

  _permission_lookup: {
    "SourceList": "查看来源列表",
    "SourceRegister": "注册来源",
    "SourceTest": "测试连通",
    "SourceScan": "发起扫描",
    "SourceAnalyze": "AI 分析",
    "SourceChangesView": "查看变更清单",
    "SourceChangeConfirm": "确认同步并分析",
    "SourceAdopt": "收编描述",
    "SourceDeepToggle": "深度分析开关",
    "SourceEnable": "启用/停用来源",
    "SourceDelete": "删除来源"
  },

  overview_blocks: [
    { type: "table", headers: ["子域", "核心实体", "说明"], rows: [
      ["来源登记", "Source / NasReg", "local/WebDAV、ro|rw、连通测试后入库"],
      ["任务入口", "Job", "扫描/分析/收编/确认同步均为任务型（返回 job_id）"],
      ["变更确认", "ReconcileDiff", "扫描差异清单 + 勾选确认同步"]
    ]},
    { type: "note", level: "info", text: "删除 ro 源 = 连带清除入库知识（前端确认提示）；rw 源删除不删源端 .naskb。" }
  ],

  design_decisions: [
    { title: "注册即测试", detail: "POST /api/sources?test=true 先连通再入库——失败拒绝注册，避免坏来源污染清单" },
    { title: "扫描/分析任务化", detail: "不阻塞请求；前端轮询 /api/jobs/{id}（进度与 result 内嵌 deep.chunks 统计）" },
    { title: "变更确认闸门", detail: "扫描发现差异不自动入库；/changes 出清单 → /confirm 勾选 rel_paths 才同步分析（幂等）" }
  ],

  endpoints: [

    // ── GET 列表 ──
    { id: "list-sources", protocol: "rest", method: "GET", path: "/api/sources", permission: "SourceList",
      summary: "来源列表（含统计与最近扫描）", scenario: "来源管理页/浏览页加载",
      description: "返回全部来源；stats 含 files/ok/stale_source/missing_source/analyzed/chunks；密码等敏感字段不返回（to_api 脱敏）。",
      business_logic: {
        preconditions: ["已认证（非匿名）"],
        steps: ["① 读取 sources 表", "② 按来源聚合统计（resources/vectors）", "③ 脱敏序列化（去 password）"],
        post_effects: [],
        state_machine: "无状态变更",
        side_effects: [],
        related_apis: ["POST /api/sources — 注册", "GET /api/sources/{sid}/changes — 变更清单"]
      },
      query_params: [],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "sources": [\n    {\n      "source_id": "uuid",\n      "alias": "home-nas-docs",\n      "protocol": "local",\n      "access_mode": "ro",\n      "root_path": "D:\\\\NAS\\\\docs",\n      "deep": false,\n      "enabled": true,\n      "stats": { "files": 120, "ok": 118, "stale_source": 1, "missing_source": 1, "analyzed": 105, "chunks": 0 },\n      "last_scan_at": "2026-08-24T10:00:00"\n    }\n  ]\n}',
          fields: [["sources[].source_id","UUID","来源 ID"],["sources[].alias","varchar","别名"],["sources[].protocol","enum","local|webdav"],["sources[].access_mode","enum","ro|rw"],["sources[].root_path|url","varchar","端点"],["sources[].deep","bool","深度分析开关"],["sources[].enabled","bool","启停"],["sources[].stats","object","知识统计"],["sources[].last_scan_at","datetime","最近扫描"]] }
      ],
      errors: [
        ["401", "UNAUTHORIZED (41001)", "未认证", "匿名只读不含本端点"],
        ["500", "INTERNAL_ERROR (50001)", "PG 异常", "服务器内部错误"]
      ],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可直接重试" },
      caching: { method: "no-store", ttl: "—", note: "实时统计" },
      rate_limit: { limit: "—（未实现）", dimension: "—", note: "演进项" }
    },

    // ── POST 注册 ──
    { id: "register-source", protocol: "rest", method: "POST", path: "/api/sources", permission: "SourceRegister",
      summary: "注册来源（先连通测试）", scenario: "来源页『注册来源』表单",
      description: "表单字段：alias/protocol/access_mode/root_path|url/username/password/verify_ssl/label/scan_auto/scan_interval_min/deep。登记入 sources 表；webdav 同时登记 nas_registry（五要素）。",
      business_logic: {
        preconditions: ["已认证", "alias 唯一"],
        steps: ["① 按协议创建 fs adapter", "② 连通性测试（失败 → 400 拒绝注册）", "③ 写入 sources（+ nas_registry）"],
        post_effects: ["sources 表新增行"],
        state_machine: "新增来源 → enabled=true, status=initial",
        side_effects: ["可选：登记 nas_registry（多 NAS 场景）"],
        related_apis: ["POST /api/sources/{sid}/test — 测试", "POST /api/sources/{sid}/scan — 扫描"]
      },
      path_params: [],
      query_params: [["test","boolean","否","是否先测试再注册","默认 true","true"]],
      body_params: [
        ["alias","string","是","来源别名","唯一","home-nas-docs"],
        ["protocol","enum","是","local|webdav","枚举","local"],
        ["access_mode","enum","是","ro|rw","枚举","ro"],
        ["root_path","string","条件","local 必须","本地根路径","D:\\NAS\\docs"],
        ["url","string","条件","webdav 必须","远程 URL","https://host:5006/home/docs"],
        ["username/password","string","否","webdav 凭据","—","—"],
        ["verify_ssl","bool","否","SSL 校验","—","true"],
        ["label","string","否","备注","—","—"],
        ["scan_auto","bool","否","自动扫描","—","false"],
        ["scan_interval_min","int","否","扫描间隔","≥5","60"],
        ["deep","bool","否","深度分析开关","—","false"]
      ],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "source": {\n    "source_id": "uuid",\n    "alias": "home-nas-docs"\n  }\n}',
          fields: [["source.source_id","UUID","来源 ID"],["source.alias","varchar","别名"]] }
      ],
      errors: [
        ["400", "INVALID_PARAMETER (40001)", "连通测试失败/参数错误", "注册拒绝"],
        ["401", "UNAUTHORIZED (41001)", "未认证", "—"],
        ["409", "CONFLICT (42011)", "alias 已存在", "唯一冲突"],
        ["500", "INTERNAL_ERROR (50001)", "写入异常", "—"]
      ],
      idempotency: { is_idempotent: false, method: "alias 唯一约束兜底", retry: "重试前先确认来源不存在" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── PATCH 更新 ──
    { id: "update-source", protocol: "rest", method: "PATCH", path: "/api/sources/{sid}", permission: "SourceEnable|SourceDeepToggle",
      summary: "更新来源（enabled/deep/scan 等）", scenario: "来源页『停用/启用』『深度开/关』",
      description: "按字段局部更新；当前 UI 使用 enabled 与 deep 两个开关。",
      business_logic: {
        preconditions: ["已认证", "来源存在"],
        steps: ["① 定位来源", "② 更新指定字段", "③ 返回更新后对象"],
        post_effects: ["sources 行更新"],
        state_machine: "enabled: true↔false；deep: false→true（后续扫描/分析建 chunk 行，不回溯）",
        side_effects: ["deep=false 不删除既有 chunk 行（待确认，见 design-code-gap）"],
        related_apis: ["GET /api/sources — 列表"]
      },
      path_params: [["sid","UUID","是","来源 ID","—","—"]],
      body_params: [["enabled","bool","否","启停","—","true"],["deep","bool","否","深度开关","—","false"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "source": { "source_id": "uuid", "enabled": false }\n}',
          fields: [["source.source_id","UUID","来源 ID"],["source.enabled","bool","更新后状态"]] }
      ],
      errors: [["404", "NOT_FOUND (42001)", "来源不存在", "—"],["401", "UNAUTHORIZED (41001)", "未认证", "—"]],
      idempotency: { is_idempotent: true, method: "PATCH 幂等（字段赋值）", retry: "可重试" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── DELETE 删除 ──
    { id: "delete-source", protocol: "rest", method: "DELETE", path: "/api/sources/{sid}", permission: "SourceDelete",
      summary: "删除来源", scenario: "来源页『删除』（确认弹窗）",
      description: "ro 源：连带清除其入库知识（resources/vectors 级联）；rw 源：不删源端 .naskb。",
      business_logic: {
        preconditions: ["已认证", "来源存在"],
        steps: ["① 定位来源", "② 删除 sources 行", "③ 清除关联入库知识（ro）/ 保留源端（rw）"],
        post_effects: ["sources/（ro 的）resources/vectors/folders 删除"],
        state_machine: "来源终态：删除",
        side_effects: ["缩略图缓存清理"],
        related_apis: ["GET /api/sources — 列表"]
      },
      path_params: [["sid","UUID","是","来源 ID","—","—"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "ok": true\n}', fields: [["ok","bool","是否成功"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在","—"],["401","UNAUTHORIZED (41001)","未认证","—"]],
      idempotency: { is_idempotent: true, method: "DELETE 天然幂等", retry: "重复删除返回 404" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── POST 测试 ──
    { id: "test-source", protocol: "rest", method: "POST", path: "/api/sources/{sid}/test", permission: "SourceTest",
      summary: "连通性测试", scenario: "来源列表『测试』",
      description: "按协议执行 stat/list 探活，返回耗时。",
      business_logic: {
        preconditions: ["已认证", "来源存在"],
        steps: ["① 创建 adapter", "② 探活（list/stat 根路径）", "③ 计时"],
        post_effects: [],
        state_machine: "无状态变更",
        side_effects: [],
        related_apis: ["POST /api/sources — 注册"]
      },
      path_params: [["sid","UUID","是","来源 ID","—","—"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "ok": true,\n  "ms": 42\n}', fields: [["ok","bool","连通"],["ms","int","耗时（毫秒）"],["error","string","失败原因（ok=false 时）"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在","—"],["401","UNAUTHORIZED (41001)","未认证","—"]],
      idempotency: { is_idempotent: true, method: "无副作用", retry: "可重试" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── POST 扫描 ──
    { id: "scan-source", protocol: "rest", method: "POST", path: "/api/sources/{sid}/scan", permission: "SourceScan",
      summary: "发起扫描对账任务", scenario: "来源页『扫描』",
      description: "提交 scan 任务（JobManager），返回 job_id；扫描结果（新增/变更/消失）写对账清单。",
      business_logic: {
        preconditions: ["已认证", "来源存在且 enabled"],
        steps: ["① 入队 scan job", "② 后台：frag 枚举 + 与 .naskb/index 比对", "③ 写对账差异（added/changed/missing）"],
        post_effects: ["对账差异生成"],
        state_machine: "任务 pending→running→completed|failed",
        side_effects: ["deep 来源扫描随带 deep.diff（chunk 统计）"],
        related_apis: ["GET /api/jobs/{id} — 进度", "GET /api/sources/{sid}/changes — 差异清单"]
      },
      path_params: [["sid","UUID","是","来源 ID","—","—"]],
      responses: [
        { description: "成功响应 — HTTP 200（实现口径：任务提交返回 200 + job_id，202 语义未启用 — 与代码对齐）", json: '{\n  "job_id": "0a1b2c3d4e5f"\n}', fields: [["job_id","string","任务 ID（12 hex）"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在","—"],["409","CONFLICT (42011)","已有同类任务","任务串行"]],
      idempotency: { is_idempotent: true, method: "增量对账幂等（重复扫描结果一致）", retry: "可重复提交" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── POST 分析 ──
    { id: "analyze-source", protocol: "rest", method: "POST", path: "/api/sources/{sid}/analyze", permission: "SourceAnalyze",
      summary: "发起 AI 分析任务", scenario: "来源页『AI 分析』",
      description: "提交 analyze job：三级判定链 + 多模态富化 + .naskb 双写 + PG 同步。",
      business_logic: {
        preconditions: ["已认证", "来源存在", "（建议）已扫描"],
        steps: ["① 入队 analyze job", "② 后台：L1→L2→L3 判定 + 分析", "③ 写 .naskb + PG 同步"],
        post_effects: ["资源描述更新（analyzed_at/file_hash/summary/...）"],
        state_machine: "资源状态 ok↔stale_source→ok",
        side_effects: ["deep 来源：建条款级 chunk 行"],
        related_apis: ["GET /api/jobs/{id} — 进度"]
      },
      path_params: [["sid","UUID","是","来源 ID","—","—"]],
      responses: [
        { description: "成功响应 — HTTP 200（实现口径：任务提交返回 200 + job_id，202 语义未启用 — 与代码对齐）", json: '{\n  "job_id": "0a1b2c3d4e5f"\n}', fields: [["job_id","string","任务 ID"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在","—"],["503","DEPENDENCY_UNAVAILABLE (45001)","LLM 未配置","外部依赖缺失"]],
      idempotency: { is_idempotent: true, method: "指纹链增量幂等", retry: "可重复提交" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── POST 收编 ──
    { id: "adopt-source", protocol: "rest", method: "POST", path: "/api/sources/{sid}/adopt", permission: "SourceAdopt",
      summary: "收编来源端已有 .naskb 描述", scenario: "来源页『收编』",
      description: "导入来源端既有描述仓库 → PG 主库（幂等；复用 collect_docs + sync_vectors 富化回填；文件夹描述写 folders）；不改源端。",
      business_logic: {
        preconditions: ["已认证", "来源存在", "源端存在 .naskb"],
        steps: ["① 入队 adopt job", "② 读取源端 .naskb（index/files/folder）", "③ 回填 PG（resources/folders/vectors）"],
        post_effects: ["PG 入库（增量）"],
        state_machine: "任务 pending→completed",
        side_effects: [],
        related_apis: ["GET /api/jobs/{id}"]
      },
      path_params: [["sid","UUID","是","来源 ID","—","—"]],
      responses: [
        { description: "成功响应 — HTTP 200（实现口径：任务提交返回 200 + job_id，202 语义未启用 — 与代码对齐）", json: '{\n  "job_id": "0a1b2c3d4e5f"\n}', fields: [["job_id","string","任务 ID"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在/无 .naskb","—"],["503","DEPENDENCY_UNAVAILABLE (45001)","PG 不可达","外部依赖缺失"]],
      idempotency: { is_idempotent: true, method: "幂等导入（指纹比对）", retry: "可重试" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 变更清单 ──
    { id: "source-changes", protocol: "rest", method: "GET", path: "/api/sources/{sid}/changes", permission: "SourceChangesView",
      summary: "查看变更确认清单", scenario: "来源页『变更』",
      description: "返回最近扫描对账的 diff：added[]/changed[]/missing[]（勾选后确认同步并分析）。",
      business_logic: {
        preconditions: ["已认证", "已扫描（有对账结果）"],
        steps: ["① 读取对账差异", "② 分组 added/changed/missing"],
        post_effects: [],
        state_machine: "无状态变更",
        side_effects: [],
        related_apis: ["POST /api/sources/{sid}/confirm", "POST /api/sources/{sid}/scan"]
      },
      path_params: [["sid","UUID","是","来源 ID","—","—"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "diff": {\n    "added": ["a.pdf"],\n    "changed": ["b.pdf"],\n    "missing": ["c.pdf"]\n  }\n}',
          fields: [["diff.added","string[]","新增 rel_path"],["diff.changed","string[]","变更 rel_path"],["diff.missing","string[]","消失 rel_path（仅标记）"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在/无可比对结果","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "以最近扫描为准" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── POST 确认同步 ──
    { id: "confirm-source", protocol: "rest", method: "POST", path: "/api/sources/{sid}/confirm", permission: "SourceChangeConfirm",
      summary: "确认变更并同步分析", scenario: "来源页『确认同步并分析』",
      description: "按勾选 rel_paths 触发对账 + AI 分析入库（幂等）；消失项仅标记 missing。",
      business_logic: {
        preconditions: ["已认证", "有未确认 diff"],
        steps: ["① 校验 rel_paths ⊆ diff", "② 入队 confirm job", "③ 后台：对账 + 分析 + 入库"],
        post_effects: ["资源状态更新（ok/stale_vector 复位）", "深析来源：chunk 行再建"],
        state_machine: "任务 pending→completed",
        side_effects: [],
        related_apis: ["GET /api/sources/{sid}/changes", "GET /api/jobs/{id}"]
      },
      path_params: [["sid","UUID","是","来源 ID","—","—"]],
      body_params: [["rel_paths","string[]","是","勾选确认的路径","⊆ diff.added+changed","[\"a.pdf\"]"]],
      responses: [
        { description: "成功响应 — HTTP 200（实现口径：任务提交返回 200 + job_id，202 语义未启用 — 与代码对齐）", json: '{\n  "job_id": "0a1b2c3d4e5f"\n}', fields: [["job_id","string","任务 ID"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在","—"],["409","CONFLICT (42011)","清单与实况不一致","重新扫描"],["422","VALIDATION_ERROR (40001)","rel_paths 越界","勾选项不在 diff 中"]],
      idempotency: { is_idempotent: true, method: "对账+分析幂等", retry: "可重试" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    },

    // ── GET 一致性报告 ──
    { id: "source-report", protocol: "rest", method: "GET", path: "/api/sources/{sid}/report", permission: "login_required",
      summary: "来源一致性报告（总览）", scenario: "一致性巡检/运维查看；CLI sync-status 的 REST 形态",
      description: "返回来源一致性总览：source（to_api 脱敏）+ backend（registry 后端）+ knowledge（pg 侧 source_stats：stats/reconcile/deep/chunks）；PG 不可达时 knowledge 内嵌 error（不静默，2026-08-24 拍板接回，DD-009）。",
      business_logic: {
        preconditions: ["已认证", "来源存在"],
        steps: ["① 读取来源记录并脱敏", "② 聚合统计（若 PG 可用）", "③ 返回总览；PG 失败 → knowledge.error 字段"],
        post_effects: [],
        state_machine: "无状态变更",
        side_effects: [],
        related_apis: ["DELETE /api/sources/{sid} — 删除", "GET /api/sources/{sid}/changes — 明细"]
      },
      path_params: [["sid","UUID","是","来源 ID","—","—"]],
      responses: [
        { description: "成功响应 — HTTP 200", json: '{\n  "source": { "source_id": "uuid", "alias": "home-nas-docs", "access_mode": "ro" },\n  "backend": "pg|json",\n  "knowledge": { "files": 120, "ok": 118, "stale_source": 1, "missing_source": 1, "analyzed": 105, "chunks": 12 }\n}',
          fields: [["source","object","来源（脱敏 to_api）"],["backend","enum","pg|json（registry 后端）"],["knowledge","object|null","source_stats：files/ok/stale_source/missing_source/analyzed/chunks"],["knowledge.error","string","PG 不可达时内嵌错误（不静默）"]] }
      ],
      errors: [["404","NOT_FOUND (42001)","来源不存在","—"],["401","UNAUTHORIZED (41001)","未认证","—"]],
      idempotency: { is_idempotent: true, method: "GET 天然幂等", retry: "可重试" },
      caching: { method: "no-store", ttl: "—", note: "实时聚合" },
      rate_limit: { limit: "—", dimension: "—", note: "演进项" }
    }
  ]
};
