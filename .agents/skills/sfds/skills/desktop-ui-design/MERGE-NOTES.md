# MERGE-NOTES — desktop-ui-design（仲裁版草稿）

- 底座：inbox\zy-ai-consult\desktop-ui-design\SKILL.md（sha256 前 12 位：9a9299955294）
- 三方关系：zy-iot-ai 版与 zy-ai-consult 版哈希完全相同；boxing（16f6f6fca76b，36187B）与 consult（35864B）同源小幅分叉，无结构性演进差异
- 仲裁方向：内容冲突以 zy-ai-consult 为准

## 三方处置表

| 章节/内容 | boxing | zy-iot | zy-ai-consult | 处置 | 理由 |
|-----------|--------|--------|---------------|------|------|
| 设计规则 6 CHANGELOG 路径 | `design/05-{端-slug}/data/CHANGELOG.md` | 同 consult | `design/06-{client-slug}/data/CHANGELOG.md` | 以 consult 为准 | 端目录编号属项目流水线布局；hub 共享 `_shared/pipeline-registry.js` 中 05 已被 backend-architecture 占用，06 与枢纽编号一致 |
| 输入来源表 API 设计文档路径 | `design/04-platform-api/data/{domain-slug}.js`（扁平） | 同 consult | `design/04-platform-api/data/rest/{domain-slug}.js`（REST 域端点） | 以 consult 为准 | 与 api-design v4 协议子目录结构对齐（已产出的 api-design 仲裁草稿同口径）；扁平路径为旧结构 |
| PS_DATA 命名空间示例（正文 `PS_DATA.customer.tree` 等） | 硬编码 `customer` | 同 boxing | `PS_DATA["{client-slug}"]` | 以 consult 为准 | consult 泛化为占位符，更通用 |
| 节点字段表 `type` 行 func 废弃注 | 无 | 同 consult | 「功能组件统一为 `"component"`（早期示例中的 `"func"` 为旧写法，已废弃）」 | 基座保留 | consult 新增澄清 |
| 节点字段表 `refEntity`/`refFields` 口径 | 「组件涉及数据展示时建议设置」，并含**实体覆盖**检查语义（实体覆盖/字段存在/描述陈旧三类比对） | 同 consult | 「规则 1：新建组件必须标注」（对应本技能规则 1「数据依赖显式化」，字段表与规则自洽） | 以 consult 为准；「实体覆盖」检查维度记**待议②** | consult 内部口径一致；boxing 为旧宽松口径 + 更丰富的检查语义，恢复与否牵动 review 汇总维度 |
| 追溯字段脚注 code-gen 补齐规则 | 无 | 同 consult | 「进入代码生成（§8.7）前应补齐；未补齐时 code-gen 以 ⚠️ 警告输出并标注 TODO，不阻塞生成」 | 基座保留 | consult 新增，与 mobile-code-gen/desktop-code-gen 衔接 |
| file:// 加载约束注（CORS / document.write / file:// 实测 0 console error） | 有（步骤 3 后） | 无 | 无 | **待议①**（不回灌正文） | 现行 loader.js 三系同哈希（1dbc9e24…），为 script 标签注入、无 fetch，注文 document.write 表述已过时；但「修改 viewer/数据文件后须以 file:// 实测验证 0 console error」是通用验证纪律，是否以修正措辞恢复待枢纽裁决 |
| §7 一致性检查输入路径 | `design/05-{端-slug}/data/tree.js`（并注明「端 slug 用 operation-web/admin 等；不使用 miniprogram 前缀」） | 同 consult | `design/06-{client-slug}/data/tree.js` | 以 consult 为准 | 端目录命名与 boxing 括注中的实例端名均留项目侧 |
| §7.3 共享规范分发位置表述 | 「位于 `.agents/skills/_shared/`，与各 skill 目录平级」 | 同 consult | 「与本 skill 同目录分发的 `_shared/` 子目录」 | 以 consult 为准 | 分发布局由枢纽打包方案决定，非方法论内容 |
| §7.3 一致性检查输出 JSON 示例字段 | 含 `source: "er-to-frontend"` + `ref_path` + `ref_field`，符合共享规范必填契约 | 同 boxing | 缺 `source`、`ref_field`，以 `node_path`（下游前端节点路径数组）替代 `ref_path` | **待议③**（不回灌正文） | 两系 `_shared/consistency-check-format.md` 字段契约完全一致且明文 `source`/`ref_path` ✅ 必填，consult 示例偏离其自身引用的规范；但 `node_path` 或为面向 viewer 跳转的有意改造，需枢纽裁决统一。与 mobile-app-design 草稿同项待议联动 |

## 清单

### 已回灌
（无——boxing 相对底座的差异均为项目侧措辞或旧口径，无「明显通用且无争议」项）

### 不回灌 · 留项目侧
1. 端目录命名与编号约定（`design/05-{端-slug}`、端 slug 实例名 operation-web/admin 等）。
2. `PS_DATA.customer` 式硬编码端标识（consult 已泛化为 `{client-slug}` 占位符，各项目落地时自行取值）。

### 待议
1. **file:// 加载约束验证纪律是否恢复**：boxing 注文中 document.write 表述与现行 loader.js（script 注入、无 fetch）不符，但其 file:// 实测 0 console error 的验证要求是通用工程纪律；建议修正措辞后恢复，位置在创建设计·步骤 3 后。与 mobile-app-design 待议①联动。
2. **`refEntity`/`refFields` 是否补充「实体覆盖」检查语义**：boxing 版含实体覆盖/字段存在/描述陈旧三类比对，consult 仅字段级语义比对——扩充将影响 review 汇总维度，需与 review 技能及共享规范 type 注册表对齐后定。
3. **一致性检查输出字段口径**：consult SKILL.md 示例缺共享规范 ✅ 必填的 `source`/`ref_path`（以 `node_path` 替代）且缺 `ref_field`；需枢纽裁决「校正两技能示例回规范」或「修订规范正式注册 node_path」。与 mobile-app-design 待议③联动。

## L1 相关事实
- 草稿对底座的唯一修改：frontmatter 增加 lineage 血缘头。正文零改动。
