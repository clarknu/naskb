// 04 深度分析 —— 业务工作流数据文件
// 依据：design/01-raw-input/04-deep-analysis.md（REQ-R5-06、ADR-20260823-1）
// 域注册表：04-deep-analysis

window.WF_DATA = window.WF_DATA || {};
window.WF_DATA["04-deep-analysis"] = {
  "domain": "04",
  "title": "深度分析（条款级）",
  "slug": "deep-analysis",
  "description": "条款级精细分析：MinerU 结构化 md 按标题层级分段成 chunk 向量行（kind=chunk/title + chunk_seq + title_path），两级引用问答、保真直返与无命中兜底",
  "last_updated": "2026-08-24",

  // ── 权限控制点（唯一定义源）──
  "permissions": [
    { "id": "ChunkAsk",     "name": "条款级问答",   "desc": "允许发起两级引用条款问答（/api/kb/ask）", "category": "deep_analysis", "section_refs": ["main-flow"] },
    { "id": "DeepConfigManage", "name": "深析配置", "desc": "允许配置 [deep] roots/分段参数/直返阈值", "category": "deep_analysis", "section_refs": ["rules"] }
  ],

  // ── 角色定义（2026-08-24 拍板 DD-009：移除匿名只读；权限点保留为契约）──
  "roles": [
    { "id": "PlatformAdmin", "name": "平台管理员", "desc": "拥有深析配置与条款问答权限", "client_group": "Staff",
      "permission_ids": ["ChunkAsk","DeepConfigManage"] },
    { "id": "MCPAgent", "name": "MCP 消费方 Agent", "desc": "通过 kb_ask（deep 参数）消费条款级问答", "client_group": "Agent",
      "permission_ids": ["ChunkAsk"] }
  ],

  "sections": [
    {
      "id": "overview",
      "title": "业务概述",
      "level": 1,
      "blocks": [
        { "type": "p", "text": "标准/规范/研发类文档需要条款级精细问答（'6.3.2 条怎么规定''表 4 耐压要求'）时启用深度分析：摘要级检索保持默认，深析在圈定目录叠加条款级第二层。" },
        { "type": "note", "level": "info", "text": "自研主线（D'，ADR-20260823-1）：不搬 MaxKB 代码、不买专业版；远期可插拔深度引擎（路线 A）同契约。" },
        { "type": "note", "level": "warning", "text": "法律纪律（REQ-R6-07）：设计学习自开源项目（只读源码），实现零拷贝。" }
      ]
    },
    {
      "id": "main-flow",
      "title": "主流程：条款级入库 → 问答",
      "level": 2,
      "blocks": [
        { "type": "p", "text": "圈定 → MinerU 解析 → 标题树分段 → chunk 向量行入库 → 条款级问答（两级引用 + 保真直返 + 无命中兜底）。" }
      ],
      "flowchart": {
        "layout": "topdown",
        "nodes": [
          { "id": "start",   "type": "start",    "label": "流程开始" },
          { "id": "scope",   "type": "action",   "label": "圈定\n（[deep].roots / 来源开关）", "inputs": ["roots","source_id"], "outputs": ["scope_set"], "consumers": ["parse"] },
          { "id": "parse",   "type": "action",   "label": "MinerU 解析\n（PDF/DOCX/PPTX/XLSX → md）", "inputs": ["scope_set","file_path"], "outputs": ["structured_md"], "consumers": ["split"] },
          { "id": "split",   "type": "action",   "label": "标题树分段\n（target=800/limit=1200/overlap=0.12）", "inputs": ["structured_md"], "outputs": ["chunks"], "consumers": ["store_chunk"] },
          { "id": "store_chunk","type": "action", "label": "chunk 向量行入库\n（kind + chunk_seq + title_path）", "inputs": ["chunks"], "outputs": ["chunk_rows"], "consumers": ["ask"] },
          { "id": "ask",     "type": "action",   "label": "条款级问答\n（两级引用）", "inputs": ["question","chunk_rows","direct_return"], "outputs": ["answer","citations"], "consumers": ["direct_check"] },
          { "id": "direct_check","type": "decision", "label": "命中相似度 ≥ 0.9\n（direct_return）" },
          { "id": "direct",  "type": "action",   "label": "保真直返\n（不调 LLM，防改写）", "inputs": ["citations"], "outputs": ["answer"], "consumers": ["end"] },
          { "id": "no_hit",  "type": "action",   "label": "无命中兜底\n（designated | llm_fallback）", "outputs": ["answer"], "consumers": ["end"] },
          { "id": "end",     "type": "end",      "label": "流程结束" }
        ],
        "edges": [
          { "from": "start",        "to": "scope" },
          { "from": "scope",        "to": "parse" },
          { "from": "parse",        "to": "split" },
          { "from": "split",        "to": "store_chunk" },
          { "from": "store_chunk",  "to": "ask" },
          { "from": "ask",          "to": "direct_check" },
          { "from": "direct_check", "to": "direct", "label": "≥0.9" },
          { "from": "direct_check", "to": "no_hit", "label": "无命中" },
          { "from": "direct",       "to": "end" },
          { "from": "no_hit",       "to": "end" }
        ]
      }
    },
    {
      "id": "rules",
      "title": "业务规则表",
      "level": 2,
      "blocks": [
        { "type": "table", "headers": ["规则编号", "规则内容", "优先级", "说明"],
          "rows": [
            ["R001", "分段参数 target_chars=800 / limit_chars=1200 / overlap_ratio=0.12；句末智能切分+12% 重叠", "高", "合成基准 9 题 recall@3/@5=100%"],
            ["R002", "表格随块重复表头；代码围栏掩码；ATX 六级标题树递归；空段治理", "高", "chunker 规则"],
            ["R003", "content_for_embedding = title_path + 正文", "高", "语义保留"],
            ["R004", "chunker_version 幂等（版本升级触发再分段）", "高", "幂等"],
            ["R005", "条款级仅 PG 场景；无 PG 回退文档级——**回退必须显式提示**（A' P-003：level=summary + note）", "中", "降级链，诚实性"],
            ["R006", "只读源用暂存 md（sync_vectors 后建、cleanup 前清），不留存", "高", "中间产物纪律"],
            ["R007", "变更确认清单（/changes + /confirm）驱动深析再建 chunk", "中", "与 01 域联动"],
            ["R008", "保真直返 direct_return_similarity=0.9；no_hit_mode = designated | llm_fallback", "高", "诚实性"]
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
            ["ChunkAsk", "条款级问答", "深度分析"],
            ["DeepConfigManage", "深析配置", "深度分析"]
          ]
        }
      ]
    }
  ]
};
