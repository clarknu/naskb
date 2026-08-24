// 06 平台服务 —— 业务工作流数据文件
// 依据：design/01-raw-input/06-platform-console.md（REQ-R7-02/05/08/09/10）
// 域注册表：06-platform-console

window.WF_DATA = window.WF_DATA || {};
window.WF_DATA["06-platform-console"] = {
  "domain": "06",
  "title": "平台服务",
  "slug": "platform-console",
  "description": "平台能力支撑：单管理员 Bearer 认证与匿名只读、进程内任务中心（串行）、周期扫描调度、下载代理（Range/ETag/503）、在线预览矩阵、缩略图、统计与公开配置",
  "last_updated": "2026-08-24",

  // ── 权限控制点（唯一定义源）──
  "permissions": [
    { "id": "JobsView",     "name": "查看任务中心", "desc": "允许查看任务列表与进度", "category": "platform_console", "section_refs": ["job-flow"] },
    { "id": "FileDownload", "name": "下载文件",     "desc": "允许通过下载代理流式下载（Range 断点）", "category": "platform_console", "section_refs": ["download-flow"] },
    { "id": "FilePreview",  "name": "在线预览",     "desc": "允许预览图片/PDF/音视频/文本/解析视图/Office", "category": "platform_console", "section_refs": ["preview-flow"] },
    { "id": "ConfigView",   "name": "查看公开配置", "desc": "允许读取 auth_required/anonymous_read 公开配置", "category": "platform_console", "section_refs": ["rules"] },
    { "id": "StatsView",    "name": "查看统计",     "desc": "允许读取平台统计（引擎/文档数/索引状态）", "category": "platform_console", "section_refs": ["rules"] }
  ],

  // ── 角色定义（2026-08-24 拍板 DD-009：移除匿名只读；权限点保留为契约）──
  "roles": [
    { "id": "PlatformAdmin", "name": "平台管理员", "desc": "拥有平台服务全部权限", "client_group": "Staff",
      "permission_ids": ["JobsView","FileDownload","FilePreview","ConfigView","StatsView"] }
  ],

  "sections": [
    {
      "id": "overview",
      "title": "业务概述",
      "level": 1,
      "blocks": [
        { "type": "p", "text": "平台服务是能力支撑域：认证/任务/调度/下载/预览/统计，被 01-05 域使用。" },
        { "type": "note", "level": "info", "text": "认证（2026-08-24 拍板 DD-009）：单管理员 Bearer（[server] tokens，compare_digest）；**全部端点需 token**（仅 /api/config/public、/api/docs、/api/openapi.json 匿名作启动引导）；未配置 token = 本机开放模式。" },
        { "type": "note", "level": "warning", "text": "任务中心为进程内内存队列（JobManager，max_workers=1 串行）——进程重启任务丢失（现状设计，非持久任务表）。" }
      ]
    },
    {
      "id": "job-flow",
      "title": "主流程：任务生命周期",
      "level": 2,
      "blocks": [
        { "type": "p", "text": "扫描/AI 分析/收编/确认同步/整理等长任务统一提交 JobManager，返回 job_id；前端轮询 /api/jobs 或单任务查询。" }
      ],
      "flowchart": {
        "layout": "topdown",
        "nodes": [
          { "id": "start",  "type": "start",    "label": "流程开始" },
          { "id": "submit", "type": "action",   "label": "提交任务\n（kind: scan|analyze|adopt|confirm|...）", "inputs": ["kind","payload"], "outputs": ["job_id"], "consumers": ["queue"] },
          { "id": "queue",  "type": "action",   "label": "入队\n（pending，串行窗口）", "inputs": ["job_id"], "outputs": ["queued_job"], "consumers": ["run"] },
          { "id": "run",    "type": "action",   "label": "执行\n（running，progress 可读）", "inputs": ["queued_job"], "outputs": ["result"], "consumers": ["finish"] },
          { "id": "finish", "type": "action",   "label": "完成/失败\n（completed | failed + error）", "inputs": ["result"], "outputs": ["job_state"], "consumers": ["end"] },
          { "id": "end",    "type": "end",      "label": "流程结束" }
        ],
        "edges": [
          { "from": "start",  "to": "submit" },
          { "from": "submit", "to": "queue" },
          { "from": "queue",  "to": "run" },
          { "from": "run",    "to": "finish" },
          { "from": "finish", "to": "end" }
        ]
      }
    },
    {
      "id": "download-flow",
      "title": "子流程：下载代理（Range/ETag）",
      "level": 2,
      "blocks": [
        { "type": "p", "text": "按资源定位（resource_id）流式读取源文件，支持断点续传与过期提示。" }
      ],
      "flowchart": {
        "layout": "leftright",
        "nodes": [
          { "id": "start",  "type": "start",    "label": "开始" },
          { "id": "resolve","type": "action",   "label": "解析 resource_id → 源路径", "inputs": ["rid","src"], "outputs": ["fs","path"], "consumers": ["etag"] },
          { "id": "etag",   "type": "action",   "label": "ETag 计算\n（file_hash 强 / size-mtime 弱）", "inputs": ["path"], "outputs": ["etag_value"], "consumers": ["ifmatch"] },
          { "id": "ifmatch","type": "decision", "label": "If-None-Match 匹配？" },
          { "id": "stale",  "type": "decision", "label": "源已消失/过期？" },
          { "id": "range",  "type": "action",   "label": "Range 流式响应\n（206/416；byte-a / byte-a-b / suffix）", "inputs": ["fs","path"], "outputs": ["stream"], "consumers": ["end"] },
          { "id": "notfound","type": "action",  "label": "404 / 503（stale 提示）", "outputs": ["error"], "consumers": ["end"] },
          { "id": "end",    "type": "end",      "label": "结束" }
        ],
        "edges": [
          { "from": "start",   "to": "resolve" },
          { "from": "resolve", "to": "etag" },
          { "from": "etag",    "to": "ifmatch" },
          { "from": "ifmatch", "to": "stale", "label": "否" },
          { "from": "ifmatch", "to": "notfound", "label": "304 → 直接结束" },
          { "from": "stale",   "to": "notfound", "label": "是" },
          { "from": "stale",   "to": "range", "label": "否" },
          { "from": "range",   "to": "end" },
          { "from": "notfound","to": "end" }
        ]
      }
    },
    {
      "id": "preview-flow",
      "title": "子流程：在线预览矩阵",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["类型", "方式", "限制"], "rows": [
          ["image", "原图（缩略图 Pillow ≤12MB）", "—"],
          ["video", "video 标签（第 4 秒缩略图 ffmpeg ≤100MB）", "—"],
          ["audio", "audio 标签", "—"],
          ["pdf", "iframe", "—"],
          ["text", "纯文本渲染（截断）", "—"],
          ["html", "sandbox iframe srcdoc", "无脚本"],
          ["office (docx/xlsx)", "零依赖简版渲染（≤30MB）", "pptx 不支持"],
          ["parsed", "解析视图 iframe（MinerU HTML，rw 源）", "ro 源不可用"]
        ]},
        { "type": "note", "level": "info", "text": "不支持类型 → 提示'可下载后本地打开'（不报错）。" }
      ]
    },
    {
      "id": "rules",
      "title": "业务规则表",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["规则编号", "规则内容", "优先级", "说明"],
          "rows": [
            ["R001", "认证模式：全部端点需 token（启动引导端点除外）；无 token 配置 = 本机开放模式", "高", "AuthPolicy（DD-009 匿名移除）"],
            ["R002", "定时扫描 tick 30s，每 tick 至多一个 scan job", "中", "ScanScheduler"],
            ["R003", "任务串行（max_workers=1）；失败带 error 字段", "高", "JobManager"],
            ["R005", "目录条目端点（GET /api/folder，review 补记）：浏览的伴生只读——folders 表优先，未登记则现场枚举（空目录=合法条目）", "中", "与 /api/tree 同源 list_dir"],
            ["R004", "下载 ETag 强/弱双模式；stale → 503", "中", "REQ-R7-08"],
            ["R005", "中间产物（tmp md/缩略图源件）即清，不入持久层", "高", "中间产物纪律"]
          ]
        }
      ]
    },
    {
      "id": "permissions-table",
      "title": "权限清单",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["权限点", "说明", "功能组"],
          "rows": [
            ["JobsView", "查看任务中心", "平台服务"],
            ["FileDownload", "下载文件", "平台服务"],
            ["FilePreview", "在线预览", "平台服务"],
            ["ConfigView", "查看公开配置", "平台服务"],
            ["StatsView", "查看统计", "平台服务"]
          ]
        }
      ]
    }
  ]
};
