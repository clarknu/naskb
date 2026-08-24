# Web 控制台设计变更说明 v0 → v1

> 存量项目 SFDS 方法论接入：按 app.js 实际视图建立桌面端功能树/流程/风格/多语言方案。
> 日期：2026-08-24

---

## 变更 1：建立 06-web-console 设计资产

**类型**：新增功能结构（存量接入）
**来源**：SFDS 方法论补全（naskb/web/public/app.js 视图事实基线）

### 变更内容

| 之前 | 之后 |
|------|------|
| 无前端功能设计资产 | tree.js（4 页面 + 文件详情模态公共组件 + 3 流程）+ processes.js（4 流程）+ style.js + i18n.js |

- 页面：检索问答（public/KbSearch/KbAsk + api_ref 绑定）、浏览知识库（SourceList）、知识来源（9 个操作按钮权限点映射）、任务中心（JobsView）
- 公共组件：文件详情模态（元数据 display + 预览区 + 下载/关闭）
- 权限标注：全层级 perm_ref（OR 聚合规则遵守）；文本精确化（text/label/placeholder/feedback 带 i18n key + zh）

### 理由

- desktop-ui-design 规则 1/4/7（refEntity/refFields、全层级权限、文本精确化）落地；
- 与 02 域 workflow actions 一一映射（来源页 9 按钮 ↔ 01 域 9 权限点）。

---

## 未变更部分（确认已对齐）

| 设计项 | 状态 |
|--------|------|
| Api 端点引用（tree/api_ref vs 04 域 REST 契约） | ✅ 已验证无需变更 |

---

## 变更 2：身份口径 + deep 确认（DD-009 拍板批次）

**类型**：功能精简/描述修正｜**来源**：用户拍板（2026-08-24）

| 之前 | 之后 |
|------|------|
| 检索/浏览/模态等 perm_ref=public | 全部 login_required（6 处） |
| 深度开关直接 toggle | 关闭需确认提示（清理存量条款 chunk，不可逆）——i18n 增 deep_confirm 键 |