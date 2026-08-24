// 功能结构树数据文件（桌面端版）— NASKB Web 控制台
// 依据：naskb/web/public/app.js（Vue3 单页：4 视图 hash 路由 + 文件详情模态）
// 端标识：web-console（唯一客户端，无 TabBar——顶部导航 + 页面直接展开）

var PS_DATA = window.PS_DATA = window.PS_DATA || {};
PS_DATA["web-console"] = PS_DATA["web-console"] || {};
PS_DATA["web-console"].identity = {
  app_name: "NASKB 知识库系统（平台控制台）",
  description: "检索问答 / 浏览 / 来源 / 任务 四视图 + 文件详情模态；Vue3 静态包（运行时零 Node）",
  version: "v0.1"
};
PS_DATA["web-console"].tree = {

  pages: [
    /* ===== 页面一：检索问答 ===== */
    {
      name: "页面：检索问答",
      desc: "语义/关键词检索（摘要索引）+ RAG 问答（带来源）",
      perm_ref: "login_required",
      page_input: { from: "page:launch", params: [] },
      page_output: { to: "page:文件详情模态(shared)", params: ["resource_id", "src"] },
      children: [
        {
          type: "zone", name: "功能区：检索",
          desc: "关键词/语义描述输入；结果表格（分数/分类/标签/过期徽章/NAS 徽章）",
          perm_ref: "KbSearch",
          children: [
            { type: "component", name: "[input] 检索输入", componentType: "input",
              placeholder: { key: "naskb.search.q_placeholder", zh: "关键词或语义描述（如：出行要带的证件）" },
              api_ref: "GET /api/kb/search", sends: ["query", "top_k"] },
            { type: "component", name: "[button] 检索按钮", componentType: "button",
              label: { key: "naskb.search.btn", zh: "检索" },
              feedback: { error: { key: "naskb.search.err", zh: "检索失败" } },
              api_ref: "GET /api/kb/search", sends: ["query", "top_k"] },
            { type: "component", name: "[button] 命中行（打开文件）", componentType: "button",
              label: { key: "naskb.search.hit_open", zh: "打开" },
              perm_ref: "login_required", refs: ["shared:文件详情模态"],
              refEntity: "03-retrieval-qa:VectorRow", refFields: ["resource_id", "path", "score", "summary", "category", "tags", "stale", "nas", "source_alias"],
              api_ref: "GET /api/files/{rid}", sends: ["resource_id", "src"] }
          ]
        },
        {
          type: "zone", name: "功能区：问答",
          desc: "向知识库提问；回答 + 来源列表（条款级问答见 04 域）",
          perm_ref: "KbAsk",
          children: [
            { type: "component", name: "[input] 问题输入", componentType: "input",
              placeholder: { key: "naskb.ask.q_placeholder", zh: "向知识库提问（如：月租金是多少？和谁签的？）" },
              api_ref: "POST /api/ask", sends: ["question", "top_k"] },
            { type: "component", name: "[button] 提问按钮", componentType: "button",
              label: { key: "naskb.ask.btn", zh: "提问" },
              feedback: { error: { key: "naskb.ask.err", zh: "生成失败" } },
              api_ref: "POST /api/ask", sends: ["question", "top_k"] },
            { type: "component", name: "[display] 回答与来源", componentType: "display",
              text: { key: "naskb.ask.answer_label", zh: "回答" },
              refEntity: "03-retrieval-qa:Hit", refFields: ["answer", "sources"] }
          ]
        }
      ]
    },

    /* ===== 页面二：浏览知识库 ===== */
    {
      name: "页面：浏览知识库",
      desc: "来源下拉 + 目录树/面包屑 + 文件列表（缩略图/状态/摘要）+ 知识元数据入口",
      perm_ref: "SourceList",
      page_input: { from: "page:检索问答", params: [] },
      page_output: { to: "page:文件详情模态(shared)", params: ["resource_id", "src"] },
      children: [
        {
          type: "zone", name: "功能区：来源与导航",
          perm_ref: "SourceList",
          children: [
            { type: "component", name: "[input] 来源下拉", componentType: "input",
              placeholder: { key: "naskb.browse.source_placeholder", zh: "选择来源（别名/模式）" },
              api_ref: "GET /api/sources", sends: [] },
            { type: "component", name: "[button] 刷新", componentType: "button",
              label: { key: "naskb.browse.refresh", zh: "刷新" },
              api_ref: "GET /api/tree", sends: ["src", "dir"] },
            { type: "component", name: "[display] 面包屑（目录返回）", componentType: "display",
              text: { key: "naskb.browse.crumbs", zh: "根" },
              api_ref: "GET /api/tree", sends: ["src", "dir"] }
          ]
        },
        {
          type: "zone", name: "功能区：目录与文件列表",
          desc: "目录行（file_count/描述）、文件行（大小/状态徽章/摘要/分类/缩略图）",
          perm_ref: "SourceList",
          children: [
            { type: "component", name: "[button] 目录行（进入）", componentType: "button",
              label: { key: "naskb.browse.dir_enter", zh: "进入" },
              refEntity: "02-ingestion-analysis:FolderEntry", refFields: ["rel_path", "name", "file_count", "summary"],
              api_ref: "GET /api/tree", sends: ["src", "dir"] },
            { type: "component", name: "[button] 文件行（打开模态）", componentType: "button",
              label: { key: "naskb.browse.file_open", zh: "打开" },
              perm_ref: "login_required", refs: ["shared:文件详情模态"],
              refEntity: "02-ingestion-analysis:Resource", refFields: ["resource_id", "name", "size_bytes", "summary", "category", "status"],
              api_ref: "GET /api/files/{rid}", sends: ["resource_id", "src"] },
            { type: "component", name: "[display] 文件缩略图", componentType: "display",
              text: { key: "naskb.browse.thumb", zh: "缩略图" },
              api_ref: "GET /api/files/{rid}/thumbnail", sends: ["resource_id", "src", "w"] }
          ]
        }
      ]
    },

    /* ===== 页面三：来源管理 ===== */
    {
      name: "页面：知识来源",
      desc: "注册表单（测试+注册）/ 来源表格（测试/扫描/AI 分析/变更/深度开关/收编/启停/删除）/ 变更确认清单",
      perm_ref: "SourceList",
      page_input: { from: "page:任务中心", params: [] },
      page_output: { to: "page:任务中心", params: ["job_id"] },
      children: [
        {
          type: "zone", name: "功能区：注册来源表单",
          desc: "别名/协议/访问属性/根路径或 WebDAV URL/账号密码/SSL/备注/自动扫描/深度分析（测试通过才注册）",
          perm_ref: "SourceRegister",
          children: [
            { type: "component", name: "[input] 别名", componentType: "input",
              placeholder: { key: "naskb.sources.alias_placeholder", zh: "如 home-nas-docs" },
              validation: [{ rule: "required", error: { key: "naskb.sources.alias_required", zh: "别名必填" } }] },
            { type: "component", name: "[input] 协议选择", componentType: "input",
              placeholder: { key: "naskb.sources.protocol_placeholder", zh: "local（本机目录/挂载盘）| WebDAV" } },
            { type: "component", name: "[input] 访问属性选择", componentType: "input",
              placeholder: { key: "naskb.sources.mode_placeholder", zh: "ro 只读知识库（绝不写源端）| rw 可写（保留源端 .naskb 双写）" },
              refEntity: "01-source-management:Source", refFields: ["access_mode"] },
            { type: "component", name: "[button] 测试并注册", componentType: "button",
              label: { key: "naskb.sources.add_btn", zh: "测试并注册" },
              perm_ref: "SourceRegister",
              feedback: { success: { key: "naskb.sources.add_ok", zh: "来源已注册" }, error: { key: "naskb.sources.add_fail", zh: "注册失败" } },
              api_ref: "POST /api/sources", sends: ["alias", "protocol", "access_mode", "root_path|url", "username", "password", "verify_ssl", "label", "scan_auto", "scan_interval_min", "deep"] },
            { type: "component", name: "[button] 取消", componentType: "button",
              label: { key: "naskb.sources.cancel", zh: "取消" }, perm_ref: "login_required" }
          ]
        },
        {
          type: "zone", name: "功能区：来源表格",
          desc: "别名/协议与根/模式/知识统计（文件/最新/待更新/消失/已分析/条款）/最近扫描/操作列",
          perm_ref: "SourceList",
          children: [
            { type: "component", name: "[button] 测试连通", componentType: "button",
              label: { key: "naskb.sources.test", zh: "测试" }, perm_ref: "SourceTest",
              api_ref: "POST /api/sources/{sid}/test", sends: ["source_id"] },
            { type: "component", name: "[button] 扫描", componentType: "button",
              label: { key: "naskb.sources.scan", zh: "扫描" }, perm_ref: "SourceScan",
              feedback: { success: { key: "naskb.sources.scan_ok", zh: "扫描已提交" } },
              api_ref: "POST /api/sources/{sid}/scan", sends: ["source_id"] },
            { type: "component", name: "[button] AI 分析", componentType: "button",
              label: { key: "naskb.sources.analyze", zh: "AI 分析" }, perm_ref: "SourceAnalyze",
              feedback: { success: { key: "naskb.sources.analyze_ok", zh: "AI 分析已提交（可在任务页查看进度）" } },
              api_ref: "POST /api/sources/{sid}/analyze", sends: ["source_id"] },
            { type: "component", name: "[button] 变更（确认清单）", componentType: "button",
              label: { key: "naskb.sources.changes", zh: "变更" }, perm_ref: "SourceChangesView",
              api_ref: "GET /api/sources/{sid}/changes", sends: ["source_id"] },
            { type: "component", name: "[button] 确认同步并分析", componentType: "button",
              label: { key: "naskb.sources.confirm_btn", zh: "确认同步并分析" }, perm_ref: "SourceChangeConfirm",
              feedback: { success: { key: "naskb.sources.confirm_ok", zh: "确认同步已提交" } },
              api_ref: "POST /api/sources/{sid}/confirm", sends: ["source_id", "rel_paths"] },
            { type: "component", name: "[button] 深度开关（关闭需确认：清理存量条款 chunk）", componentType: "button",
              label: { key: "naskb.sources.deep_toggle", zh: "深度开/关" }, perm_ref: "SourceDeepToggle",
              feedback: { confirm: { key: "naskb.sources.deep_confirm", zh: "关闭深度分析将清理该来源存量条款级 chunk（不可逆），确认？" } },
              api_ref: "PATCH /api/sources/{sid}", sends: ["source_id", "deep"] },
            { type: "component", name: "[button] 收编", componentType: "button",
              label: { key: "naskb.sources.adopt", zh: "收编" }, perm_ref: "SourceAdopt",
              api_ref: "POST /api/sources/{sid}/adopt", sends: ["source_id"] },
            { type: "component", name: "[button] 停用/启用", componentType: "button",
              label: { key: "naskb.sources.toggle", zh: "停用/启用" }, perm_ref: "SourceEnable",
              api_ref: "PATCH /api/sources/{sid}", sends: ["source_id", "enabled"] },
            { type: "component", name: "[button] 删除来源", componentType: "button",
              label: { key: "naskb.sources.delete", zh: "删除" }, perm_ref: "SourceDelete",
              feedback: { error: { key: "naskb.sources.delete_confirm", zh: "删除来源？ro 源入库知识将一并清除" } },
              api_ref: "DELETE /api/sources/{sid}", sends: ["source_id"] }
          ]
        },
        {
          type: "zone", name: "功能区：变更确认清单",
          desc: "差异分组（新增/变更/消失）+ 勾选确认（消失仅标记 missing 不物理删除）",
          perm_ref: "SourceChangesView",
          children: [
            { type: "component", name: "[display] 变更清单展示", componentType: "display",
              text: { key: "naskb.sources.changes_list", zh: "选中项将触发对账 + AI 分析入库（幂等）" },
              refEntity: "01-source-management:Source", refFields: ["rel_paths"] }
          ]
        }
      ]
    },

    /* ===== 页面四：任务中心 ===== */
    {
      name: "页面：任务中心",
      desc: "任务表格（ID/类型/状态/进度条/信息/时间；每 2 秒自动刷新；结果可展开）",
      perm_ref: "JobsView",
      page_input: { from: "page:知识来源", params: ["job_id"] },
      page_output: { to: "page:知识来源", params: [] },
      children: [
        {
          type: "zone", name: "功能区：任务表格",
          perm_ref: "JobsView",
          children: [
            { type: "component", name: "[display] 任务行状态", componentType: "display",
              text: { key: "naskb.jobs.status", zh: "pending/running/completed/failed" },
              refEntity: "06-platform-console:Job", refFields: ["id", "kind", "status", "progress", "message", "result", "error", "created_at"],
              api_ref: "GET /api/jobs/{job_id}", sends: ["job_id"] }
          ]
        }
      ]
    }
  ],

  shared_pages: [],

  shared_components: [
    {
      name: "公共组件：文件详情模态",
      desc: "全站复用的文件详情浮层：知识元数据（路径/分类/标签/摘要/内容描述/指纹/大小时间/分析时间）+ 预览 + 下载",
      refs: ["检索问答→检索结果行", "浏览→文件行", "浏览→目录行（预览目录描述）"],
      perm_ref: "login_required",
      children: [
        { type: "component", name: "[display] 知识元数据区", componentType: "display",
          text: { key: "naskb.modal.meta_title", zh: "知识元数据" },
          refEntity: "02-ingestion-analysis:Resource", refFields: ["rel_path", "category", "tags", "summary", "content_description", "hash_algorithm", "file_hash", "size_bytes", "mtime", "analyzed_at"],
          api_ref: "GET /api/files/{rid}", sends: ["resource_id", "src"] },
        { type: "component", name: "[display] 预览区", componentType: "display",
          text: { key: "naskb.modal.preview_title", zh: "预览" },
          perm_ref: "FilePreview",
          refEntity: "06-platform-console:PreviewKind", refFields: ["viewable", "url|content", "parsed_url|reason"],
          api_ref: "GET /api/files/{rid}/preview", sends: ["resource_id", "src"] },
        { type: "component", name: "[button] 下载", componentType: "button",
          label: { key: "naskb.modal.download", zh: "下载" }, perm_ref: "FileDownload",
          api_ref: "GET /api/files/{rid}/download", sends: ["resource_id", "src", "disposition"] },
        { type: "component", name: "[button] 关闭", componentType: "button",
          label: { key: "naskb.modal.close", zh: "关闭 ✕" }, perm_ref: "login_required" }
      ]
    }
  ],

  flows: [
    {
      name: "浏览与预览流程",
      steps: [
        "步骤1：检索结果命中行/浏览文件行 → 打开文件详情模态",
        "步骤2：模态加载元数据（GET /api/files/{rid}）",
        "步骤3：预览区按 viewable 渲染（image/pdf/video/audio/text/html/office/parsed/none）",
        "步骤4：点击下载 → 下载代理流式响应（Range 断点续传）"
      ]
    },
    {
      name: "来源注册与扫描流程",
      steps: [
        "步骤1：来源页填写表单（local/WebDAV、ro/rw）",
        "步骤2：测试并注册（POST /api/sources?test=true 先连通后入库）",
        "步骤3：扫描（POST /api/sources/{sid}/scan → 任务中心轮询 /api/jobs/{id}）",
        "步骤4：变更（GET /api/sources/{sid}/changes）→ 勾选 → 确认同步并分析（/confirm）"
      ]
    },
    {
      name: "任务观察流程",
      steps: [
        "步骤1：从来源页扫描/AI 分析/收编/确认 提交任务",
        "步骤2：Toast 提示 job_id → 自动进入任务中心视图",
        "步骤3：任务表格每 2 秒刷新；completed 后查看 result（含 deep.chunks 统计）"
      ]
    }
  ]

};
