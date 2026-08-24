// 06 平台服务 —— 单域 ER 数据文件
// 依据：JobManager（进程内内存队列）/ ScanScheduler / 下载代理 / 预览矩阵 / AuthPolicy 事实基线
// 域注册表：06-platform-console（无持久表——任务/预览/认证均以 VO + 服务建模）

window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["06-platform-console"] = {
  "domain":      "06",
  "title":       "平台服务",
  "slug":        "platform-console",
  "description": "平台能力支撑：任务（内存队列 VO）、下载/预览（VO + 服务）、认证策略（服务）。不持新表：任务为进程内内存字典（重启即失，当前设计）。",

  "enums": [
    { "id": "JobStatus", "name": "任务状态", "description": "JobManager 任务生命周期",
      "values": [
        { "code": "pending", "zh": "排队", "desc": "已入队" },
        { "code": "running", "zh": "执行中", "desc": "串行窗口内" },
        { "code": "completed", "zh": "完成", "desc": "带 result" },
        { "code": "failed", "zh": "失败", "desc": "带 error" }
      ] },
    { "id": "JobKind", "name": "任务类型", "description": "长任务类型（提交源）",
      "values": [
        { "code": "scan", "zh": "扫描", "desc": "来源扫描对账" },
        { "code": "analyze", "zh": "AI 分析", "desc": "来源富化" },
        { "code": "adopt", "zh": "收编", "desc": "导入源端 .naskb" },
        { "code": "confirm", "zh": "确认同步", "desc": "变更确认后对账+分析" },
        { "code": "snapshot", "zh": "快照", "desc": "扫描快照（B 组 job 语义）" }
      ] },
    { "id": "PreviewKind", "name": "预览类型", "description": "预览矩阵（_view_kind 按扩展名）",
      "values": [
        { "code": "image", "zh": "图片", "desc": "Pillow/原图" },
        { "code": "video", "zh": "视频", "desc": "video 标签" },
        { "code": "audio", "zh": "音频", "desc": "audio 标签" },
        { "code": "pdf", "zh": "PDF", "desc": "iframe" },
        { "code": "text", "zh": "文本", "desc": "pre 渲染" },
        { "code": "html", "zh": "HTML", "desc": "sandbox iframe" },
        { "code": "office", "zh": "Office", "desc": "docx/xlsx ≤30MB 零依赖" },
        { "code": "parsed", "zh": "解析视图", "desc": "MinerU HTML（rw 源）" },
        { "code": "none", "zh": "不支持", "desc": "提示可下载后本地打开" }
      ] },
    { "id": "HttpResponse", "name": "下载响应码", "description": "下载代理响应语义",
      "values": [
        { "code": "200", "zh": "完整响应", "desc": "无 Range" },
        { "code": "206", "zh": "部分内容", "desc": "Range 命中" },
        { "code": "304", "zh": "未修改", "desc": "If-None-Match 命中" },
        { "code": "416", "zh": "范围不可满足", "desc": "Range 越界" },
        { "code": "503", "zh": "暂不可用", "desc": "stale 提示" }
      ] }
  ],

  "entities": [],

  "value_objects": [
    {
      "id": "job",
      "name": "任务（VO）",
      "type": "vo",
      "description": "进程内任务记录（内存字典，非持久）",
      "fields": [
        {"name": "id", "type": "text", "pk": false, "nn": true, "desc": "12 位 hex job_id"},
        {"name": "kind", "type": "JobKind", "pk": false, "nn": true, "desc": "任务类型"},
        {"name": "status", "type": "JobStatus", "pk": false, "nn": true, "desc": "状态"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"},
        {"name": "started_at", "type": "datetime", "pk": false, "nn": false, "desc": "开始时间"},
        {"name": "completed_at", "type": "datetime", "pk": false, "nn": false, "desc": "完成时间"},
        {"name": "progress", "type": "decimal", "pk": false, "nn": false, "desc": "进度 0-1"},
        {"name": "message", "type": "text", "pk": false, "nn": false, "desc": "进度消息"},
        {"name": "result", "type": "json", "pk": false, "nn": false, "desc": "结果（含 deep.chunks 等）"},
        {"name": "error", "type": "text", "pk": false, "nn": false, "desc": "失败原因"}
      ]
    },
    {
      "id": "folder_entry_view",
      "name": "目录条目视图（VO）",
      "type": "vo",
      "description": "GET /api/folder 响应载荷（P-004 对齐，2026-08-24 用户拍板：设计与实现一致化）——folders 表登记或运行时枚举派生；与 02 域 folder_entry 实体同语义视图（file_count 为派生计数）",
      "fields": [
        {"name": "rel_path", "type": "text", "pk": false, "nn": true, "desc": "目录 rel_path"},
        {"name": "name", "type": "text", "pk": false, "nn": false, "desc": "目录名（根=来源 alias）"},
        {"name": "summary", "type": "text", "pk": false, "nn": false, "desc": "目录描述（folders 登记）"},
        {"name": "description", "type": "text", "pk": false, "nn": false, "desc": "folder.json description"},
        {"name": "tags", "type": "text[]", "pk": false, "nn": false, "desc": "标签"},
        {"name": "file_count", "type": "integer", "pk": false, "nn": false, "desc": "文件数（派生：folders 字段或 list_dir 枚举）"},
        {"name": "source", "type": "enum", "pk": false, "nn": true, "desc": "数据来源：folders|generated（未登记→现场枚举；空目录=合法空条目）"}
      ]
    },
    {
      "id": "range_request",
      "name": "Range 请求（VO）",
      "type": "vo",
      "description": "下载代理 Range 解析（仅单区间 bytes=a-b/a-/-suffix）",
      "fields": [
        {"name": "start", "type": "bigint", "pk": false, "nn": false, "desc": "起始字节"},
        {"name": "end", "type": "bigint", "pk": false, "nn": false, "desc": "结束字节"},
        {"name": "suffix", "type": "bigint", "pk": false, "nn": false, "desc": "末尾 N 字节"}
      ]
    }
  ],

  "services": [
    { "id": "job_manager", "name": "任务管理器",
      "description": "进程内串行队列（max_workers=1）",
      "methods": [
        {"name": "submit", "sig": "(kind, fn) → job_id", "desc": "提交长任务"},
        {"name": "get", "sig": "(job_id) → Job", "desc": "查询单任务（匿名可见）"},
        {"name": "list", "sig": "() → Job[]", "desc": "任务列表（需认证）"}
      ] },
    { "id": "scan_scheduler", "name": "扫描调度器",
      "description": "daemon 线程，tick 30s，每 tick 至多一个 scan",
      "methods": [
        {"name": "tick", "sig": "()", "desc": "遍历 enabled+scan_auto 来源判定"},
        {"name": "interval", "sig": "(source) → seconds", "desc": "max(5, scan_interval_min)*60"}
      ] },
    { "id": "download_proxy", "name": "下载代理",
      "description": "Range/ETag/304/416/503（ETag=file_hash）",
      "methods": [
        {"name": "resolve_resource", "sig": "(rid, src) → {fs, path}", "desc": "定位"},
        {"name": "etag", "sig": "(path) → str", "desc": "强/弱 ETag"},
        {"name": "stream", "sig": "(fs, path, range) → Response", "desc": "流式响应"}
      ] },
    { "id": "preview_renderer", "name": "预览渲染",
      "description": "按扩展名判定预览类型；解析视图/Office 零依赖简版",
      "methods": [
        {"name": "view_kind", "sig": "(name) → PreviewKind", "desc": "扩展名判定"},
        {"name": "render", "sig": "(kind, fs, path) → {viewable, url|content, reason}", "desc": "渲染输出"}
      ] },
    { "id": "auth_policy", "name": "认证策略",
      "description": "单管理员 Bearer（compare_digest）+ 匿名只读前缀",
      "methods": [
        {"name": "authorize", "sig": "(request, route) → bool", "desc": "token 校验/匿名判定"},
        {"name": "public_config", "sig": "() → {auth_required, anonymous_read}", "desc": "公开配置"}
      ] }
  ],

  "relations": []
};
