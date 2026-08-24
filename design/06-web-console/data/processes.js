// 业务流程文档数据文件 — NASKB Web 控制台（覆盖 2.4 功能逻辑设计）
var PS_DATA = window.PS_DATA = window.PS_DATA || {};
PS_DATA["web-console"] = PS_DATA["web-console"] || {};
PS_DATA["web-console"].processes = [
  {
    id: "browse-preview",
    title: "浏览与下载/预览流程",
    level: 1,
    blocks: [
      { type: "p", text: "用户在检索或浏览中找到知识资源，打开文件详情模态，先预览（按类型渲染）再按需下载；断点续传由下载代理支持。" },
      { type: "h3", text: "权限约束" },
      { type: "table", headers: ["角色", "权限", "引导策略"], rows: [
        ["匿名只读用户", "public（检索/浏览只读、下载/预览）", "无令牌直接使用（anonymous_read=true）"],
        ["平台管理员", "全部（含来源管理写操作）", "右上角配置令牌"]
      ]},
      { type: "note", level: "warning", text: "浏览页依赖 GET /api/sources（非匿名）——匿名模式下浏览页会 401（口径差异见 design-code-gap）。" }
    ],
    flowchart: {
      layout: "topdown",
      nodes: [
        { id: "n1", type: "start", label: "打开资源" },
        { id: "n2", type: "action", label: "加载元数据（/api/files/{rid}）" },
        { id: "n3", type: "action", label: "预览判定（viewable）" },
        { id: "n4", type: "decision", label: "支持在线预览？" },
        { id: "n5", type: "action", label: "按类型渲染（image/pdf/video/audio/text/html/office/parsed）" },
        { id: "n6", type: "action", label: "提示“可下载后本地打开”" },
        { id: "n7", type: "decision", label: "需要下载？" },
        { id: "n8", type: "action", label: "下载代理（Range/ETag/304/416/503）" },
        { id: "n9", type: "end", label: "结束" }
      ],
      edges: [
        { from: "n1", to: "n2" }, { from: "n2", to: "n3" }, { from: "n3", to: "n4" },
        { from: "n4", to: "n5", label: "支持" }, { from: "n4", to: "n6", label: "不支持" },
        { from: "n6", to: "n7" }, { from: "n5", to: "n7" },
        { from: "n7", to: "n8", label: "是" }, { from: "n7", to: "n9", label: "否" },
        { from: "n8", to: "n9" }
      ]
    }
  },
  {
    id: "source-lifecycle",
    title: "来源管理流程",
    level: 1,
    blocks: [
      { type: "h3", text: "核心步骤" },
      { type: "ol", items: [
        "填写注册表单 → 测试并注册（先连通后入库）",
        "扫描 → 变更清单（新增/变更/消失）",
        "勾选确认 → 同步并分析（任务化，幂等）",
        "可选：深度开关 / 收编 / 停用 / 删除"
      ]},
      { type: "note", level: "danger", text: "删除 ro 源 = 其入库知识一并清除（不可逆）。" }
    ],
    flowchart: {
      layout: "topdown",
      nodes: [
        { id: "n1", type: "start", label: "开始" },
        { id: "n2", type: "action", label: "填写表单" },
        { id: "n3", type: "action", label: "测试并注册" },
        { id: "n4", type: "decision", label: "连通成功？" },
        { id: "n5", type: "action", label: "注册失败提示" },
        { id: "n6", type: "action", label: "扫描（任务）" },
        { id: "n7", type: "decision", label: "有变更？" },
        { id: "n8", type: "action", label: "变更清单 + 勾选" },
        { id: "n9", type: "action", label: "确认同步并分析（任务）" },
        { id: "n10", type: "end", label: "结束" }
      ],
      edges: [
        { from: "n1", to: "n2" }, { from: "n2", to: "n3" }, { from: "n3", to: "n4" },
        { from: "n4", to: "n5", label: "失败" }, { from: "n4", to: "n6", label: "成功" },
        { from: "n5", to: "n10" }, { from: "n6", to: "n7" },
        { from: "n7", to: "n8", label: "是" }, { from: "n7", to: "n10", label: "否" },
        { from: "n8", to: "n9" }, { from: "n9", to: "n10" }
      ]
    }
  },
  {
    id: "search-qa",
    title: "检索问答流程",
    level: 1,
    blocks: [
      { type: "p", text: "检索（引擎链 pg→vector→bm25 自动降级）；问答（top_k 召回 → DeepSeek 生成 → 来源列表）。" },
      { type: "table", headers: ["角色", "权限", "引导策略"], rows: [
        ["匿名只读用户", "KbSearch / KbAsk（口径差异：POST 实际需 token）", "无令牌直接使用"]
      ]}
    ],
    flowchart: {
      layout: "leftright",
      nodes: [
        { id: "n1", type: "start", label: "输入查询/问题" },
        { id: "n2", type: "action", label: "引擎链判定" },
        { id: "n3", type: "action", label: "检索 hits / 问答 answer+sources" },
        { id: "n4", type: "end", label: "结束" }
      ],
      edges: [ { from: "n1", to: "n2" }, { from: "n2", to: "n3" }, { from: "n3", to: "n4" } ]
    }
  },
  {
    id: "job-flow",
    title: "任务观察流程",
    level: 1,
    blocks: [
      { type: "table", headers: ["场景", "反馈"], rows: [
        ["提交任务", "Toast（“扫描已提交（任务 xxxx）”）+ 自动轮询 job_id"],
        ["进行中", "任务中心 2s 轮询；进度条 progress"],
        ["完成", "Toast：新增/变更/消失/条款统计"],
        ["失败", "Toast：扫描失败 + error"]
      ]}
    ]
  }
];
