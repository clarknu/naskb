// 示例：功能结构树数据文件
// 将本文件复制为 data/tree.js，修改内容为实际设计
// 覆盖 2.1 业务功能结构、2.2 公共页面与组件、2.3 前端流程概要
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
  // 导航标签组 → 标签 → 页面 → 功能区 → 功能组件
  // ═══════════════════════════════════════════════════
  tabs: [
    /* ===== 标签一 ===== */
    {
      name: "标签：首页",
      desc: "首页一句话描述",
      children: [{
        type: "page", name: "页面：首页",
        children: [
          {
            type: "zone", name: "功能区：推荐内容",
            desc: "功能区的功能描述",
            children: [
              {
                type: "zone", name: "功能区：子功能区",
                children: [
                  { type: "component", name: "[button] 进入详情",
                    componentType: "button",
                    label: { key: "home.enter_detail", zh: "查看详情" },
                    feedback: { success: { key: "home.nav_ok", zh: "已跳转" } }
                  },
                  { type: "component", name: "[display] 标题与导语",
                    componentType: "display",
                    text: { key: "home.hero_title", zh: "精彩赛事，即将开始" }
                  },
                  { type: "component", name: "[display] 状态标签",
                    componentType: "display",
                    text: { key: "home.status_label",
                      variants: [
                        { condition: "status === 'active'", zh: "进行中" },
                        { condition: "status === 'upcoming'", zh: "即将开始" },
                        { condition: "status === 'ended'", zh: "已结束" }
                      ]
                    },
                    show_when: "competition.status !== 'draft'"
                  }
                ]
              },
              { type: "component", name: "[display] 加载提示", componentType: "display" }
            ]
          }
        ]
      }]
    },

    /* ===== 标签二 ===== */
    {
      name: "标签：列表",
      desc: "列表浏览",
      children: [{
        type: "page", name: "页面：列表页",
        children: [
          {
            type: "zone", name: "功能区：搜索与筛选",
            children: [
              { type: "component", name: "[input] 关键词搜索",
                componentType: "input",
                placeholder: { key: "list.search_placeholder", zh: "请输入关键词搜索" },
                hint: { key: "list.search_hint", zh: "支持按名称、地点模糊搜索" },
                validation: [
                  { rule: "maxlength", value: 50, error: { key: "list.search_too_long", zh: "搜索词不能超过50个字符" } }
                ]
              },
              { type: "component", name: "[button] 搜索", componentType: "button",
                label: { key: "list.search_btn", zh: "搜索" }
              }
            ]
          },
          {
            type: "zone", name: "功能区：列表",
            children: [
              {
                type: "zone", name: "功能区：卡片",
                children: [
                  { type: "component", name: "[display] 卡片标题", componentType: "display" },
                  { type: "component", name: "[button] 进入详情", componentType: "button",
                    label: { key: "list.enter_detail", zh: "查看" },
                    perm_ref: "ItemDetailView"
                  }
                ]
              }
            ]
          }
        ]
      }]
    },

    /* ===== 标签三 ===== */
    {
      name: "标签：我的",
      desc: "个人服务聚合页",
      children: [{
        type: "page", name: "页面：个人中心",
        children: [
          {
            type: "zone", name: "功能区：个人信息",
            children: [
              {
                type: "zone", name: "功能区：账号卡片",
                children: [
                  { type: "component", name: "[display] 头像与昵称",
                    componentType: "display",
                    text: { key: "me.avatar_label", zh: "用户昵称" }
                  }
                ]
              }
            ]
          }
        ]
      }]
    }
  ],

  // ═══════════════════════════════════════════════════
  // 2.2 公共页面（跨入口复用的独立页面）
  // ═══════════════════════════════════════════════════
  shared_pages: [
    {
      name: "页面：登录",
      desc: "统一登录入口，根据状态切换视图",
      refs: ["首页→未登录拦截", "我的→退出登录后"],
      children: [
        { type: "component", name: "[display] Logo与标题",
          componentType: "display",
          text: { key: "login.logo_title", zh: "{{产品名称}}" }
        },
        { type: "component", name: "[display] 引导文案",
          componentType: "display",
          text: { key: "login.guide_text", zh: "授权登录后即可使用全部功能" },
          show_when: "user_status === null"
        },
        { type: "component", name: "[button] 微信一键登录",
          componentType: "button",
          label: { key: "login.wechat_btn", zh: "微信一键登录" },
          feedback: {
            success: { key: "login.success", zh: "登录成功" },
            error: { key: "login.fail", zh: "登录失败，请重试" }
          }
        },
        {
          type: "zone", name: "功能区：身份认证表单",
          desc: "pendingregistration 状态下显示",
          show_when: "user_status === 'pendingregistration'",
          children: [
            { type: "component", name: "[input] 真实姓名",
              componentType: "input",
              placeholder: { key: "auth.name_placeholder", zh: "请输入真实姓名" },
              hint: { key: "auth.name_hint", zh: "请填写与身份证一致的中文姓名" },
              validation: [
                { rule: "required", error: { key: "auth.name_required", zh: "姓名不能为空" } },
                { rule: "pattern", value: "^[\\u4e00-\\u9fa5]{2,20}$", error: { key: "auth.name_invalid", zh: "请输入2-20位中文字符" } }
              ]
            },
            { type: "component", name: "[input] 身份证号",
              componentType: "input",
              placeholder: { key: "auth.id_placeholder", zh: "请输入18位身份证号" },
              validation: [
                { rule: "required", error: { key: "auth.id_required", zh: "身份证号不能为空" } },
                { rule: "pattern", value: "^\\d{17}[\\dXx]$", error: { key: "auth.id_invalid", zh: "请输入正确的18位身份证号" } }
              ]
            },
            { type: "component", name: "[button] 提交认证",
              componentType: "button",
              label: { key: "auth.submit_btn", zh: "提交认证" },
              feedback: {
                success: { key: "auth.submit_ok", zh: "认证信息已提交，请等待审核" },
                error: { key: "auth.submit_fail", zh: "提交失败，请检查信息后重试" }
              }
            }
          ]
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
      name: "主链路名称",
      steps: [
        "步骤1：操作描述 → 结果",
        "步骤2：操作描述 → 结果",
        "步骤3：操作描述 → 结果"
      ]
    }
  ]

};
