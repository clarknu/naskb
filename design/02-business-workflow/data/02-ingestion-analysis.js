// 02 采集与分析 —— 业务工作流数据文件
// 依据：design/01-raw-input/02-ingestion-analysis.md（REQ-R1、REQ-R5-02、ADR-20260816-4）
// 域注册表：02-ingestion-analysis

window.WF_DATA = window.WF_DATA || {};
window.WF_DATA["02-ingestion-analysis"] = {
  "domain": "02",
  "title": "采集与分析",
  "slug": "ingestion-analysis",
  "description": "扫描对账（三级判定、增量幂等）、多模态分析管线（文档/图片/音频/视频/目录/MinerU）、AI 富化（DeepSeek/MiMo 分工）、.naskb 描述仓库维护、干净导出",
  "last_updated": "2026-08-24",

  // ── 权限控制点（唯一定义源）──
  "permissions": [
    { "id": "AnalyzeRun",      "name": "运行 AI 分析",   "desc": "允许触发文档/图片/音频/视频/目录分析任务", "category": "ingestion_analysis", "section_refs": ["main-flow", "pipeline"] },
    { "id": "FolderDescribe",  "name": "目录级描述",     "desc": "允许生成目录级 folder.json 描述", "category": "ingestion_analysis", "section_refs": ["pipeline"] },
    { "id": "ExportClean",     "name": "干净导出",       "desc": "允许把 .naskb 分析产物导出为干净 Markdown/ZIP（REQ-R5-02）", "category": "ingestion_analysis", "section_refs": ["pipeline"] },
    { "id": "TermbaseManage",  "name": "术语表管理",     "desc": "允许读写 NAS 术语表（jieba 自定义词典）", "category": "ingestion_analysis", "section_refs": ["rules"] }
  ],

  // ── 角色定义 ──
  "roles": [
    { "id": "PlatformAdmin", "name": "平台管理员", "desc": "拥有采集分析全部权限", "client_group": "Staff",
      "permission_ids": ["AnalyzeRun","FolderDescribe","ExportClean","TermbaseManage"] },
    { "id": "MCPAgent", "name": "MCP 消费方 Agent", "desc": "通过 kb_ingest/kb_sync_vectors/kb_index_vectors 写入知识", "client_group": "Agent",
      "permission_ids": ["AnalyzeRun"] }
  ],

  "sections": [
    {
      "id": "overview",
      "title": "业务概述",
      "level": 1,
      "blocks": [
        { "type": "p", "text": "对已注册来源执行扫描对账与 AI 富化。分析产物写入被分析目录的 .naskb/ 隐藏仓库（meta.json + index.json 轻量索引 + files/<rel>.json 大字段 + folder.json + artifacts/）。" },
        { "type": "note", "level": "info", "text": "增量幂等：hash 一致跳过、变更重分析、删除清孤儿；可反复跑、可中断重跑。" },
        { "type": "note", "level": "warning", "text": "模型风控：MiMo/MinerU/ffmpeg/Word COM 严格串行（并行会触发平台风控冻结 key）；DeepSeek 文本并发 4-6（上限 8）。" }
      ]
    },
    {
      "id": "main-flow",
      "title": "主流程：扫描 → 分析 → 入库",
      "level": 2,
      "blocks": [
        { "type": "p", "text": "来源（01 域）触发扫描/分析任务后，本域执行实际管线：对账 → 三级判定 → 多模态分析 → .naskb 双写 → 可选 PG 同步。" }
      ],
      "flowchart": {
        "layout": "topdown",
        "nodes": [
          { "id": "start",   "type": "start",    "label": "流程开始" },
          { "id": "recon",   "type": "action",   "label": "扫描对账\n（读源 → 与 .naskb/index 比对）", "inputs": ["source_id","root"], "outputs": ["valid_list","stale_list","missing_list"], "consumers": ["l1_check"] },
          { "id": "l1_check", "type": "decision", "label": "L1 免检命中？\n（path+size+mtime+ctime 一致）" },
          { "id": "skip",    "type": "action",   "label": "跳过（hash 一致，幂等）" },
          { "id": "l2_check", "type": "action",   "label": "L2 采样 hash 复核\n（8×64KB，ADR-20260816-4）", "inputs": ["file_path"], "outputs": ["sampled_hash"], "consumers": ["l2_decide"] },
          { "id": "l2_decide","type": "decision", "label": "hash 与上次一致？" },
          { "id": "analyze", "type": "action",   "label": "L3 重析：多模态分析\n（文档/图片/音频/视频/目录）", "inputs": ["file_path","file_type"], "outputs": ["category","tags","summary","content_description","text_meta"], "consumers": ["store"] },
          { "id": "store",   "type": "action",   "label": ".naskb 双写\n（files/ 大字段 + index.json 轻量索引）", "inputs": ["category","tags","summary","content_description","text_meta"], "outputs": ["entry_updated"], "consumers": ["pg_sync"] },
          { "id": "pg_sync", "type": "action",   "label": "PG 同步（可选）\nresources/vectors/termbase", "inputs": ["entry_updated","source_id"], "outputs": ["resource_id"], "consumers": ["end"] },
          { "id": "end",     "type": "end",      "label": "流程结束" }
        ],
        "edges": [
          { "from": "start",    "to": "recon" },
          { "from": "recon",    "to": "l1_check" },
          { "from": "l1_check", "to": "skip", "label": "命中" },
          { "from": "l1_check", "to": "l2_check", "label": "未命中" },
          { "from": "skip",     "to": "end" },
          { "from": "l2_check", "to": "l2_decide" },
          { "from": "l2_decide","to": "skip", "label": "一致" },
          { "from": "l2_decide","to": "analyze", "label": "不一致" },
          { "from": "analyze",  "to": "store" },
          { "from": "store",    "to": "pg_sync" },
          { "from": "pg_sync",  "to": "end" }
        ]
      }
    },
    {
      "id": "pipeline",
      "title": "分析管线与并发约束",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["管线", "模型", "并发", "产物"], "rows": [
          ["文档（PDF/DOCX/XLSX/PPTX/文本）", "PyMuPDF/python-docx/openpyxl；文本不足 30% → MinerU", "DeepSeek 并发 4-6（上限 8）", "分类/摘要/标签/全文"],
          ["DOCX 档位 1/2", "XML 图文流 + MiMo 结构识别 / Word 转 PDF → MinerU", "MiMo 串行", "图文流描述"],
          ["图片", "EXIF + MiMo 视觉描述", "MiMo 严格串行", "视觉描述/标签"],
          ["音频", "ffmpeg 16kHz 分段（25min）→ MiMo 转写", "MiMo 严格串行", "逐段转写"],
          ["视频", "路径/关键词/时长分级 → metadata_only/keyframes_only/full", "ffmpeg 串行", "分级描述"],
          ["目录", "结构收集 → DeepSeek 摘要", "DeepSeek（1 次/目录）", "folder.json"],
          ["扫描件 OCR", "MinerU（独立 venv，本机 CPU，严格串行）", "MinerU 串行", "md/html/middle.json 等"]
        ]},
        { "type": "note", "level": "warning", "text": "401 时停止重试并提示检查 key（风控/失效）。" }
      ]
    },
    {
      "id": "rules",
      "title": "业务规则表",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["规则编号", "规则内容", "优先级", "说明"],
          "rows": [
            ["R001", "三级判定链：L1 免检 → L2 采样 hash → L3 重析", "高", "幂等核心（ADR-20260816-4）"],
            ["R002", "MiMo/MinerU/ffmpeg/Word COM 严格串行", "高", "防风控冻结 key"],
            ["R003", "deep 分析来源的 chunk 再建走 04 域（来源开关）", "中", "域间联动"],
            ["R004", "被忽略文件（exclusions）记'可能含义'轻量条目", "中", "不参与向量检索"],
            ["R005", "导出 clean 产物供外部引擎，绝不回写源端", "高", "REQ-R5-02"],
            ["R006", "术语表 jieba 词典仅供关键词通道（二期）", "低", "TermbaseManage"]
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
            ["AnalyzeRun", "运行 AI 分析", "采集分析"],
            ["FolderDescribe", "目录级描述", "采集分析"],
            ["ExportClean", "干净导出", "采集分析"],
            ["TermbaseManage", "术语表管理", "采集分析"]
          ]
        }
      ]
    }
  ]
};
