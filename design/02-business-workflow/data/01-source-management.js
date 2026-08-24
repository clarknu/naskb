// 01 来源管理 —— 业务工作流数据文件
// 依据：design/01-raw-input/01-source-management.md（REQ-R7-03 等）
// 域注册表：01-source-management

window.WF_DATA = window.WF_DATA || {};
window.WF_DATA["01-source-management"] = {
  "domain": "01",
  "title": "来源管理",
  "slug": "source-management",
  "description": "知识来源注册与安全边界：local/WebDAV、ro|rw 访问模式、连通测试、启停/删除、扫描/分析/收编任务入口、变更确认清单、深度分析开关",
  "last_updated": "2026-08-24",

  // ── 权限控制点（唯一定义源）──
  "permissions": [
    { "id": "SourceList",        "name": "查看来源列表", "desc": "允许查看知识来源列表与统计", "category": "source_management", "section_refs": ["overview"] },
    { "id": "SourceRegister",    "name": "注册来源",     "desc": "允许注册 local/WebDAV 来源（含连通测试）", "category": "source_management", "section_refs": ["main-flow"] },
    { "id": "SourceTest",        "name": "测试连通",     "desc": "允许对单个来源执行连通性测试", "category": "source_management", "section_refs": ["main-flow"] },
    { "id": "SourceScan",        "name": "发起扫描",     "desc": "允许触发来源扫描对账任务", "category": "source_management", "section_refs": ["main-flow"] },
    { "id": "SourceAnalyze",     "name": "AI 分析",      "desc": "允许触发来源 AI 富化分析任务", "category": "source_management", "section_refs": ["main-flow"] },
    { "id": "SourceChangesView", "name": "查看变更清单", "desc": "允许查看来源变更确认清单（added/changed/missing）", "category": "source_management", "section_refs": ["change-confirm"] },
    { "id": "SourceChangeConfirm","name": "确认同步并分析", "desc": "允许勾选路径并确认同步分析（对账 + AI 分析入库）", "category": "source_management", "section_refs": ["change-confirm"] },
    { "id": "SourceAdopt",       "name": "收编描述",     "desc": "允许导入来源端已有的 .naskb 描述", "category": "source_management", "section_refs": ["main-flow"] },
    { "id": "SourceDeepToggle",  "name": "深度分析开关", "desc": "允许切换来源的深度分析开关（关闭 = 清理该来源存量条款级 chunk 行，UI 需确认提示）", "category": "source_management", "section_refs": ["main-flow", "rules"] },
    { "id": "SourceEnable",      "name": "启用/停用来源", "desc": "允许启用或停用来源", "category": "source_management", "section_refs": ["main-flow"] },
    { "id": "SourceDelete",      "name": "删除来源",     "desc": "允许删除来源（ro 源连带清除入库知识）", "category": "source_management", "section_refs": ["main-flow"] }
  ],

  // ── 角色定义 ──
  "roles": [
    { "id": "PlatformAdmin", "name": "平台管理员", "desc": "拥有来源管理全部权限", "client_group": "Staff",
      "permission_ids": ["SourceList","SourceRegister","SourceTest","SourceScan","SourceAnalyze","SourceChangesView","SourceChangeConfirm","SourceAdopt","SourceDeepToggle","SourceEnable","SourceDelete"] }
  ],

  "sections": [
    {
      "id": "overview",
      "title": "业务概述",
      "level": 1,
      "blocks": [
        { "type": "p", "text": "知识来源是平台的输入边界。支持 local（本机目录/NFS/iSCSI 挂载点）与 WebDAV 两种协议；访问模式分 ro（只读知识库，源端一个字节不写）与 rw（可写，保留源端 .naskb 双写）。" },
        { "type": "note", "level": "info", "text": "一切知识寻址凭 resource_id（来源 + rel_path 的稳定引用），源端目录不直接暴露给 API 调用方。" },
        { "type": "note", "level": "warning", "text": "删除 ro 源 = 其入库知识一并清除（不可逆）；rw 源删除不删源端 .naskb。" },
        { "type": "h3", "text": "核心业务规则" },
        { "type": "ul", "items": [
          "规则1：来源注册必须先通过连通测试（POST /api/sources?test=true），失败拒绝注册",
          "规则2：自动扫描按 scan_interval_min（下限 5 分钟）由调度器驱动，每 tick 至多一个扫描任务",
          "规则3：只读源停源/缺源后检索仍可用，结果带 missing/stale 徽章",
          "规则4：深度分析按来源开关（deep）；**关闭即清理该来源存量条款级 chunk 向量行**（拍板 2026-08-24，UI 需确认提示；开关只影响后续扫描/分析，不回溯重建）",
          "规则5：一致性报告（GET /api/sources/{sid}/report）为巡检派生态（review 补记）：来源总览（to_api 脱敏 + source_stats），明细走变更清单 /changes"
        ]}
      ]
    },
    {
      "id": "main-flow",
      "title": "主流程：来源全生命周期",
      "level": 2,
      "blocks": [
        { "type": "p", "text": "注册 → 测试 →（自动/手动）扫描 → 变更确认 → 分析入库；期间可停用/启用、开深度、收编存量描述。" }
      ],
      "flowchart": {
        "layout": "topdown",
        "nodes": [
          { "id": "start",     "type": "start",    "label": "流程开始" },
          { "id": "register",  "type": "action",   "label": "注册来源\n（local/WebDAV + ro/rw + 参数）", "inputs": ["alias","protocol","access_mode","root_path|url","username","password","verify_ssl","label","scan_auto","scan_interval_min","deep"], "outputs": ["source_id"], "consumers": ["test"] },
          { "id": "test",      "type": "action",   "label": "连通性测试", "inputs": ["source_id"], "outputs": ["test_ok"], "consumers": ["register_ok"] },
          { "id": "register_ok","type": "decision", "label": "测试通过？" },
          { "id": "saved",     "type": "action",   "label": "来源入库\n（sources 表 + 可选 nas_registry）", "inputs": ["source_id","test_ok"], "outputs": ["source_record"], "consumers": ["scan"] },
          { "id": "reject",    "type": "action",   "label": "注册失败，提示连通错误" },
          { "id": "scan",      "type": "action",   "label": "扫描对账\n（新增/变更/消失）", "inputs": ["source_record"], "outputs": ["job_id","reconcile_diff"], "consumers": ["changes_view"] },
          { "id": "changes_view","type": "decision", "label": "存在待确认变更？" },
          { "id": "confirm",   "type": "action",   "label": "变更确认 + 同步分析\n（勾选 rel_paths）", "inputs": ["reconcile_diff","rel_paths"], "outputs": ["job_id"], "consumers": ["end"] },
          { "id": "end",       "type": "end",      "label": "流程结束" }
        ],
        "edges": [
          { "from": "start",      "to": "register" },
          { "from": "register",   "to": "test" },
          { "from": "test",       "to": "register_ok" },
          { "from": "register_ok","to": "saved", "label": "通过" },
          { "from": "register_ok","to": "reject", "label": "失败" },
          { "from": "reject",     "to": "end" },
          { "from": "saved",      "to": "scan" },
          { "from": "scan",       "to": "changes_view" },
          { "from": "changes_view","to": "confirm", "label": "是" },
          { "from": "changes_view","to": "end", "label": "否" },
          { "from": "confirm",    "to": "end" }
        ]
      }
    },
    {
      "id": "change-confirm",
      "title": "变更确认清单",
      "level": 2,
      "blocks": [
        { "type": "p", "text": "扫描后发现源端与知识库不一致时，不自动入库——先列出变更清单（新增/变更/消失），用户勾选后确认同步并分析。" },
        { "type": "table", "headers": ["状态", "含义", "处理"] , "rows": [
          ["added", "源端新增文件", "勾选 → 同步 + AI 分析"],
          ["changed", "源端文件已变更", "勾选 → 对账 + 重分析（幂等）"],
          ["missing", "源端文件消失", "仅标记缺失，不物理删除（ro/rw 同）"]
        ]},
        { "type": "note", "level": "info", "text": "确认动作幂等：重复确认同一清单不会重复入库。" }
      ]
    },
    {
      "id": "permissions-table",
      "title": "权限清单",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["权限点", "说明", "功能组"],
          "rows": [
            ["SourceList", "查看来源列表", "来源管理"],
            ["SourceRegister", "注册来源", "来源管理"],
            ["SourceTest", "测试连通", "来源管理"],
            ["SourceScan", "发起扫描", "来源管理"],
            ["SourceAnalyze", "AI 分析", "来源管理"],
            ["SourceChangesView", "查看变更清单", "来源管理"],
            ["SourceChangeConfirm", "确认同步并分析", "来源管理"],
            ["SourceAdopt", "收编描述", "来源管理"],
            ["SourceDeepToggle", "深度分析开关", "来源管理"],
            ["SourceEnable", "启用/停用来源", "来源管理"],
            ["SourceDelete", "删除来源", "来源管理"]
          ]
        }
      ]
    }
  ]
};
