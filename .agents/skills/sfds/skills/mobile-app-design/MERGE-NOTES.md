# MERGE-NOTES — mobile-app-design（仲裁版草稿）

- 底座：inbox\zy-ai-consult\mobile-app-design\SKILL.md（sha256 前 12 位：6626dcfc12e0）
- 三方关系：zy-iot-ai 版与 zy-ai-consult 版哈希完全相同；boxing（821d3d45bdc4，38632B）与 consult（38321B）同源小幅分叉，无结构性演进差异
- 仲裁方向：内容冲突以 zy-ai-consult 为准

## 三方处置表

| 章节/内容 | boxing | zy-iot | zy-ai-consult | 处置 | 理由 |
|-----------|--------|--------|---------------|------|------|
| 设计规则 6 CHANGELOG 路径 | `design/05-miniprogram-{client-slug}/data/CHANGELOG.md` | 同 consult | `design/06-{client-slug}/data/CHANGELOG.md` | 以 consult 为准 | 端目录编号属项目流水线布局；hub 共享 `_shared/pipeline-registry.js` 中 05 已被 backend-architecture 占用，06 与枢纽编号一致 |
| 输入来源表 API 设计文档路径 | `design/04-platform-api/data/{domain-slug}.js`（扁平） | 同 consult | `design/04-platform-api/data/rest/{domain-slug}.js`（REST 域端点） | 以 consult 为准 | 与 api-design v4 协议子目录结构对齐（已产出的 api-design 仲裁草稿同口径）；扁平路径为旧结构 |
| §创建设计·步骤 4 前端目录约定注（「本项目中端目录约定为 design/05-miniprogram-{customer\|fighter\|operation}」） | 有 | 无 | 无 | 不回灌 · 留项目侧 | 注文自述「本项目中」，纯项目实例约定 |
| PS_DATA 命名空间示例（正文多处 `PS_DATA.customer`） | 硬编码 `customer` | 同 boxing | `PS_DATA["{client-slug}"]` + 「示例模板中的 key 为 demo」说明 | 以 consult 为准 | consult 泛化为占位符，更通用 |
| 节点字段表 `type` 行 func 废弃注 | 无 | 同 consult | 「功能组件统一为 `"component"`（早期示例中的 `"func"` 为旧写法，已废弃）」 | 基座保留 | consult 新增澄清 |
| 节点字段表 `refEntity`/`refFields` 口径 | 「组件涉及数据展示时建议设置」，并含**实体覆盖**检查语义（实体覆盖/字段存在/描述陈旧三类比对） | 同 consult | 「规则 1：新建组件必须标注」（对应本技能规则 1「数据依赖显式化」，字段表与规则自洽） | 以 consult 为准；「实体覆盖」检查维度记**待议②** | consult 内部口径一致；boxing 为旧宽松口径 + 更丰富的检查语义，恢复与否牵动 review 汇总维度 |
| 追溯字段脚注 code-gen 补齐规则 | 无 | 同 consult | 「进入代码生成（§8.7）前应补齐；未补齐时 code-gen 以 ⚠️ 警告输出并标注 TODO，不阻塞生成」 | 基座保留 | consult 新增，与 mobile-code-gen/desktop-code-gen 衔接 |
| file:// 加载约束注（CORS / document.write / file:// 实测 0 console error） | 有 | 无 | 无 | **待议①**（不回灌正文） | 现行 loader.js 三系同哈希（1dbc9e24…），为 script 标签注入、无 fetch，注文 document.write 表述已过时；但「修改 viewer/数据文件后须以 file:// 实测验证 0 console error」是通用验证纪律，是否以修正措辞恢复待枢纽裁决 |
| 公共节点约束清单末尾 Image/Video 组件示例两行 | 有（图片展示组件 Image / 视频展示组件 Video） | 无 | 无 | 不回灌 · 留项目侧 | 示例性重复内容：consult 正文「componentType 取值」表仍完整定义 `image`/`video`，无信息损失 |
| §7 一致性检查输入路径 | `design/05-miniprogram-{端-slug}/data/tree.js` | 同 consult | `design/06-{client-slug}/data/tree.js` | 以 consult 为准 | 同首行，端目录命名留项目侧 |
| §7.3 共享规范分发位置表述 | 「位于 `.agents/skills/_shared/`，与各 skill 目录平级」 | 同 consult | 「与本 skill 同目录分发的 `_shared/` 子目录」 | 以 consult 为准 | 分发布局由枢纽打包方案决定，非方法论内容 |
| §7.3 一致性检查输出 JSON 示例字段 | 含 `source: "er-to-frontend"` + `ref_path`（上游 ER 定位），符合共享规范必填契约 | 同 boxing | 缺 `source`，以 `node_path`（下游前端节点路径数组）替代 `ref_path` | **待议③**（不回灌正文） | 两系 `_shared/consistency-check-format.md` 字段契约完全一致且明文 `source`/`ref_path` ✅ 必填，consult 示例偏离其自身引用的规范；但 `node_path` 或为面向前端 viewer 跳转的有意改造，需枢纽裁决统一（校正示例或修订规范注册 node_path） |

## 清单

### 已回灌
（无——boxing 相对底座的差异均为项目侧措辞或旧口径，无「明显通用且无争议」项）

### 不回灌 · 留项目侧
1. 端目录命名与编号约定（`design/05-miniprogram-{customer|fighter|operation}` 等，含步骤 4 前注与 §7 输入路径写法）。
2. 公共节点示例中的 Image/Video 两行（正文 componentType 取值表已有完整枚举）。
3. `PS_DATA.customer` 式硬编码端标识（consult 已泛化为 `{client-slug}` 占位符，各项目落地时自行取值）。

### 待议
1. **file:// 加载约束验证纪律是否恢复**：boxing 注文中 document.write 表述与现行 loader.js（script 注入、无 fetch）不符，但其 file:// 实测 0 console error 的验证要求是通用工程纪律；建议修正措辞后恢复，位置在渲染机制小节。
2. **`refEntity`/`refFields` 是否补充「实体覆盖」检查语义**：boxing 版含实体覆盖/字段存在/描述陈旧三类比对，consult 仅字段级语义比对——扩充将影响 review 汇总维度，需与 review 技能及共享规范 type 注册表对齐后定。
3. **一致性检查输出字段口径**：consult SKILL.md 示例缺共享规范 ✅ 必填的 `source`/`ref_path`（以 `node_path` 替代），desktop-ui-design 示例还缺 `ref_field`；需枢纽裁决「校正两技能示例回规范」或「修订规范正式注册 node_path」。desktop-ui-design 草稿同项待议联动。

## L1 相关事实
- 草稿对底座的唯一修改：frontmatter 增加 lineage 血缘头。正文零改动。
