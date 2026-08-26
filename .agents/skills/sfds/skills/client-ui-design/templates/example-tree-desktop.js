// 示例：功能结构树数据文件（桌面端版）
// 将本文件复制为 data/tree.js，修改内容为实际设计
// 桌面端使用 tree.pages[]（无固定 TabBar 层），而非移动端的 tree.tabs[]
//
// v2 新增（原则七——文本精确化）：
//   display/rich_text 组件必须设 text: {key, zh}
//   button/link 组件必须设 label: {key, zh}
//   input 组件建议设 placeholder/hint/validation
//   所有 component 可选设 show_when（显示条件）、feedback（操作反馈）

var PS_DATA = window.PS_DATA = window.PS_DATA || {};
PS_DATA.demo = PS_DATA.demo || {};
PS_DATA.demo.tree = {

  // ═══════════════════════════════════════════════════
  // 2.1 业务功能结构
  // 页面集合 → 页面 → 功能区 → 功能组件
  // ⚠️ 桌面端没有固定的 TabBar，页面直接从根节点展开
  //    导航方式（侧边栏/顶部导航/面包屑）由具体 UI 决定
  // ═══════════════════════════════════════════════════
  pages: [
    /* ===== 页面一：仪表盘 ===== */
    {
      name: "页面：仪表盘",
      desc: "数据总览与快捷操作入口",
      children: [
        {
          type: "zone", name: "功能区：数据总览",
          children: [
            { type: "component", name: "[display] 关键指标卡片",
              componentType: "display",
              text: { key: "dashboard.kpi_title", zh: "今日营收：¥12,800" },
              perm_ref: "DashboardView"
            },
            { type: "component", name: "[display] 趋势图表",
              componentType: "display",
              text: { key: "dashboard.trend_title", zh: "近7天趋势" },
              perm_ref: "DashboardView"
            }
          ]
        },
        {
          type: "zone", name: "功能区：快捷操作",
          children: [
            { type: "component", name: "[button] 创建新项目",
              componentType: "button",
              label: { key: "dashboard.create_btn", zh: "新建项目" },
              feedback: { success: { key: "dashboard.create_ok", zh: "项目已创建" } }
            },
            { type: "component", name: "[button] 查看最近操作",
              componentType: "button",
              label: { key: "dashboard.recent_btn", zh: "最近操作" }
            }
          ]
        }
      ]
    },

    /* ===== 页面二：数据列表 ===== */
    {
      name: "页面：数据列表",
      desc: "数据查询与管理",
      children: [
        {
          type: "zone", name: "功能区：筛选条件栏",
          children: [
            { type: "component", name: "[input] 关键词搜索",
              componentType: "input",
              placeholder: { key: "list.search_placeholder", zh: "请输入关键词搜索" },
              validation: [
                { rule: "maxlength", value: 100, error: { key: "list.search_too_long", zh: "搜索词不能超过100个字符" } }
              ]
            },
            { type: "component", name: "[button] 搜索",
              componentType: "button",
              label: { key: "list.search_btn", zh: "搜索" }
            },
            { type: "component", name: "[button] 重置",
              componentType: "button",
              label: { key: "list.reset_btn", zh: "重置" }
            }
          ]
        },
        {
          type: "zone", name: "功能区：数据表格",
          children: [
            { type: "component", name: "[button] 批量删除",
              componentType: "button",
              label: { key: "list.batch_delete", zh: "批量删除" },
              perm_ref: "ItemBatchEdit",
              feedback: {
                success: { key: "list.delete_ok", zh: "已删除" },
                error: { key: "list.delete_fail", zh: "删除失败" }
              }
            }
          ]
        }
      ]
    },

    /* ===== 页面三：详情编辑 ===== */
    {
      name: "页面：详情编辑",
      desc: "单条数据的详情查看与编辑",
      children: [
        {
          type: "zone", name: "功能区：基本信息",
          children: [
            { type: "component", name: "[display] 只读字段",
              componentType: "display",
              text: { key: "detail.field_label", zh: "字段内容" }
            },
            { type: "component", name: "[input] 可编辑字段",
              componentType: "input",
              placeholder: { key: "detail.edit_placeholder", zh: "请输入内容" },
              validation: [
                { rule: "required", error: { key: "detail.required", zh: "此项不能为空" } }
              ]
            }
          ]
        },
        {
          type: "zone", name: "功能区：操作区",
          perm_ref: "ItemEdit",
          children: [
            { type: "component", name: "[button] 保存",
              componentType: "button",
              label: { key: "detail.save_btn", zh: "保存" },
              feedback: {
                success: { key: "detail.save_ok", zh: "保存成功" },
                error: { key: "detail.save_fail", zh: "保存失败，请重试" }
              }
            },
            { type: "component", name: "[button] 取消",
              componentType: "button",
              label: { key: "detail.cancel_btn", zh: "取消" },
              perm_ref: "public"
            }
          ]
        }
      ]
    }
  ],

  // ═══════════════════════════════════════════════════
  // 2.2 公共页面（跨入口复用的独立页面）
  // ═══════════════════════════════════════════════════
  shared_pages: [
    {
      name: "页面：设置页",
      desc: "全局配置",
      refs: ["仪表盘→快捷操作→进入设置", "全局导航→设置"],
      children: [
        { type: "component", name: "[display] 设置页标题",
          componentType: "display",
          text: { key: "settings.title", zh: "系统设置" }
        }
      ]
    }
  ],

  // 2.2 公共组件（跨页面引用才单独列出）
  shared_components: [],

  // ═══════════════════════════════════════════════════
  // 2.3 前端流程概要（步骤序列）
  // ═══════════════════════════════════════════════════
  flows: [
    {
      name: "创建项目流程",
      steps: [
        "步骤1：从仪表盘快捷操作区点击「新建项目」",
        "步骤2：填写项目基本信息（名称/描述/负责人/截止日期）",
        "步骤3：配置项目参数（可选，可跳过）",
        "步骤4：确认创建 → 进入项目详情页"
      ]
    }
  ]

};
