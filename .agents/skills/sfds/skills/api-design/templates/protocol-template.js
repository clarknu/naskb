/**
 * 协议定义模板 — {协议名称}
 *
 * 使用方式：复制本文件到 design/04-platform-api/data/{category}/protocol.js（如 data/iot/protocol.js、data/rest/protocol.js），
 * 替换所有 {PLACEHOLDER} 并填充实际内容。
 *
 * 本模板展示了完整的协议定义结构，包括：
 *   - 术语表、承载层、身份认证 → 属于 protocolContent（📋 协议定义）
 *   - 流式传输、RPC 语义、状态码 → 属于 envelopeContent（📨 消息封包）
 *   - Sections 菜单结构
 */

window.API_DATA = window.API_DATA || {};
window.API_DATA["protocol-{protocol-id}"] = {

  // ═══ 元信息 ═══
  id: "{protocol-id}",
  name: "{协议简称}",
  fullName: "{协议全称}",
  description: "{协议描述}",
  version: "1.0",
  projectScoped: true,

  // ═══ 术语表 ═══
  glossary: {
    "{term}": "{术语定义}"
  },

  // ═══ 承载层 ═══
  transports: [
    {
      type: "{mqtt|websocket|http}",
      description: "{承载层说明}",
      parameters: { /* 连接参数 */ },
      topics: { /* MQTT 专用：topic 定义 */ }
    }
  ],

  // ═══ 设备身份与认证 ═══
  identity: {
    credentials: [
      { name: "{credential_name}", format: "{格式}", purpose: "{用途}" }
    ],
    signingAlgorithm: {
      name: "{算法名，如 HMAC-SHA256}",
      description: "{签名流程说明}"
    }
  },

  // ═══════════════════════════════════════
  // 消息封包定义（铁律 2：枚举字段用 ref）
  // ═══════════════════════════════════════
  envelope: {
    format: "json",
    description: "{封包格式说明}",
    fields: {
      // 铁律 2：type 引用公共枚举，不内联 values
      type:    { type: "enum",   ref: "message_type",  required: true,  desc: "消息类型：call=请求/发起，ack=响应/确认" },
      // 铁律 2：action 引用公共枚举
      action:  { type: "string", ref: "action_name",   required: true,  desc: "动作类型标识" },
      msg_id:  { type: "uint64", required: true,  desc: "消息唯一 ID。发送方全生命周期内不得重复" },
      ts:      { type: "uint64", required: true,  desc: "发送方毫秒级 Unix 时间戳" },
      ref_id:  { type: "uint64", required_if: "type==ack", desc: "引用的 call 消息 msg_id" },
      code:    { type: "int",    required_if: "type==ack", desc: "状态码。0=成功，非0=错误" },
      payload: { type: "object", optional: true,  desc: "业务数据载荷" }
    },
    // 铁律 3：去重机制必须可见
    deduplication: {
      mechanism: "msg_id LRU 缓存去重",
      window: "由接收方决定，建议 5 分钟",
      algorithm: [
        "① 接收方维护 LRU 缓存 seen_messages",
        "② 收到 call 时检查: if call.msg_id in seen_messages → 丢弃重复消息",
        "③ 否则: seen_messages.set(call.msg_id, now(), ttl=DEDUP_WINDOW)",
        "④ 正常处理消息"
      ]
    },
    maxMessageSize: "单条消息总大小（含信封）不超过 256 KB"
  },

  // ═══════════════════════════════════════
  // 协议内容（📋 协议定义菜单）
  // 铁律 1：只放协议本身的内容
  // ═══════════════════════════════════════
  protocolContent: [
    // 协议概述、术语表、承载层、身份认证、心跳、版本历史等
    // 每一项定义 type + title + data
    { type: "markdown", title: "协议概述", data: { content: "<p>{概述}</p>" } },
    { type: "table",    title: "术语表",   data: { headers: ["术语","含义"], rows: [["{term}","{定义}"]] } }
  ],

  // ═══════════════════════════════════════
  // 消息封包子内容（📨 消息封包菜单）
  // 铁律 1：放流式传输、RPC 语义、状态码、字段编码、返回约定
  // ═══════════════════════════════════════
  envelopeContent: [
    // 流式传输 — 二进制帧格式
    { type: "nested", title: "流式传输", data: { children: [
      { title: "设计原则", content: "<p>{原则说明}</p>" },
      { title: "帧格式",   content: "<table>...</table>" }
    ] } },
    // RPC 调用语义
    { type: "nested", title: "RPC 调用语义", data: { children: [
      { title: "模型", content: "call-ack 模型。每个 call 必须收到一个 ack。" }
    ] } },
    // 状态码体系 — 铁律 3：每条 code 必须完整列出
    { type: "nested", title: "状态码体系", data: { children: [
      { title: "概述", content: "状态码位于 ack 消息的 envelope.code 字段。0=成功，非0=错误。" },
      { title: "错误分类", content: "<table><tr><th>code</th><th>meaning</th><th>说明</th></tr><!-- 每一条都必须列出 --></table>" }
    ] } },
    // 字段定义与编码
    { type: "nested", title: "字段定义与编码", data: { children: [
      { title: "编码规范", content: "{编码规范说明}" },
      { title: "命名规范", content: "{命名规范说明}" }
    ] } },
    // 返回结果约定
    { type: "nested", title: "返回结果约定", data: { children: [
      { title: "code 字段", content: "call 消息无 code。ack 消息 code=0 成功；非 0 为错误。" },
      { title: "成功 ack",  content: "code=0 且 payload=null → 操作成功。" }
    ] } }
  ],

  // ═══════════════════════════════════════
  // Sections 菜单结构（铁律 1：分协议定义和消息封包两个菜单项）
  // ═══════════════════════════════════════
  sections: [
    {
      id: "protocol", label: "📋 协议定义", icon: "📋", type: "protocol"
    },
    {
      id: "envelope", label: "📨 消息封包", icon: "📨", type: "envelope"
    },
    {
      id: "{device-id}", label: "{设备名称}", icon: "{图标}", type: "device",
      device: "{device-id}",
      children: [
        { id: "{device-id}-cat1", label: "{分类1}", type: "device", device: "{device-id}", category: "{分类1}" },
        { id: "{device-id}-cat2", label: "{分类2}", type: "device", device: "{device-id}", category: "{分类2}" }
      ]
    },
    {
      id: "enums", label: "📊 公共枚举", icon: "📊", type: "sharedEnums", dataSource: "{device-id}"
    },
    {
      id: "examples", label: "📋 调用示例", icon: "📋", type: "examples", dataSource: "{device-id}"
    }
  ],

  // ═══ 渲染规则 ═══
  renderRules: {
    actions: { groupBy: "category", showCallAck: true, showRPC: true, showNotes: true },
    enums: { recursive: true, showReverseNav: true, showUsage: true },
    status: { showTriggers: true, showFieldPath: true }
  }
};
