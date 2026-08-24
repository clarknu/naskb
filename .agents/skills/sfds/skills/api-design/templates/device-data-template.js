/**
 * 设备数据文件模板 — {设备名称}
 *
 * 使用方式：复制到 design/04-platform-api/data/iot/{device-id}.js，
 * 替换所有 {PLACEHOLDER} 并填充实际内容。
 *
 * 铁律：顶部必须初始化 window.IOT_DATA。
 */

window.IOT_DATA = window.IOT_DATA || {};
window.IOT_DATA["{device-id}"] = {

  domain: "{domain-slug}",
  name: "{设备名称}",
  description: "{设备描述与使用场景}",

  // ═══════════════════════════════════════
  // 指令定义 (endpoints)
  // ═══════════════════════════════════════
  endpoints: [
    {
      id: "{action_id}",
      protocol: "{protocol-id}",
      action: "{action_name}",
      direction: "{device-to-cloud|cloud-to-device}",
      type: "{call|call+stream}",
      method: "CALL",
      summary: "{一句话摘要}",
      description: "{详细说明}",
      envelope: {
        payload: {
          // 字段定义：type + required/optional + desc
          // 流式指令的 payload 不包含 codec 参数——参数在流自身中描述
          "{field}": { type: "{string|int|enum|...}", required: true, desc: "{字段说明}" }
        }
      },
      rpc: { timeout: "{10s}", retry: "{command|log|urgent}" },
      response: {
        action: "{action_name}_ack",
        type: "ack",
        fields: {
          // ack 响应中的额外字段，无额外字段填 null
        }
      },
      errors: [
        // [HTTP码, error_code, 触发条件, 说明]
      ],
      // 流式指令需标注 streaming 配置
      // streaming: { enabled: true, type: "device-to-cloud", streamIdSource: "platform-ack" },
      notes: "{设计注意事项、与其他指令的关系}"
    }
  ],

  // ═══════════════════════════════════════
  // 分类定义 (用于左侧导航和内容分组)
  // ═══════════════════════════════════════
  categories: {
    "{分类 key}": {
      label: "{分类显示名}",
      icon: "{emoji 图标}",
      description: "{分类描述}",
      actions: ["{action1}", "{action2}"]  // 引用 endpoints 中的 action 名称
    }
  },

  // ═══════════════════════════════════════
  // 共享枚举 (铁律 2：被信封字段 ref 引用)
  // ═══════════════════════════════════════
  sharedEnums: {
    // 消息类型 — 被 envelope.type 的 ref:"message_type" 引用
    message_type: {
      name: "message_type",
      desc: "消息类型（公共枚举）",
      values: [
        { value: "call", desc: "请求/发起" },
        { value: "ack",  desc: "响应/确认，需携带 ref_id + code" }
      ]
    },

    // 指令名称 — 被 envelope.action 的 ref:"action_name" 引用
    // 值从 endpoints 中自动汇总，此处列出全部可能的 action（含 _ack 变体）
    action_name: {
      name: "action_name",
      desc: "全部指令名称（公共枚举）",
      values: [
        { value: "{action1}",      desc: "{动作中文说明}" },
        { value: "{action1}_ack",  desc: "{动作中文说明}-响应" }
      ]
    },

    // 业务相关枚举
    "{enum_name}": {
      name: "{enum_name}",
      desc: "{枚举说明}",
      values: [
        { value: "{value}", desc: "{值说明}" }
      ]
    }
  },

  // ═══════════════════════════════════════
  // 状态定义 (可选，用于设备状态机展示)
  // ═══════════════════════════════════════
  statusDefinitions: {
    "{state_group}": {
      label: "{状态组标签}",
      description: "{状态描述}",
      field: "{字段路径，如 status_notification_call.mode.active_mode}",
      states: [
        { id: "idle", label: "空闲", desc: "初始状态", trigger: "初始化" },
        { id: "active", label: "激活中", desc: "运行状态", trigger: "{触发条件}" }
      ]
    }
  },

  // ═══════════════════════════════════════
  // 动作关联关系 (可选)
  // ═══════════════════════════════════════
  actionRelationships: {
    "{action_name}": {
      description: "{动作说明}",
      triggers: ["{被触发的下游动作}"],
      related: ["{关联动作}"],
      notes: "{关联说明}"
    }
  }
};
