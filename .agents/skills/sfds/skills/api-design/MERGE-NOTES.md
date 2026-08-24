# MERGE-NOTES — api-design（仲裁版草稿）

- 底座：inbox\zy-ai-consult\api-design\SKILL.md（sha256 前 12 位：aa635742c3cc）
- 三方关系：zy-iot-ai 版与 zy-ai-consult 版哈希完全相同；consult 系（23KB）较 boxing（14KB）大幅演进为协议无关设计；boxing 相对多出追溯字段、ER→API 检查、CHANGELOG 章
- 仲裁方向：内容冲突以 zy-ai-consult 为准

## 三方处置表

| 章节/内容 | boxing | zy-iot | zy-ai-consult | 处置 | 理由 |
|-----------|--------|--------|---------------|------|------|
| 技能定位/协议范围 | 仅 REST | REST、IoT（MQTT/WebSocket）、Internal、AI Tools（规划） | 同 zy-iot | 以 consult 为准 | 协议无关化是 zy 系明确演进主线 |
| §4 文件布局 | 扁平 `data/{domain}.js` + `_conventions.js` | `data/rest|iot|internal|ai-tools/` 子目录 + 各 `protocol.js` | 同 zy-iot | 以 consult 为准 | 结构性冲突，consult 为后继版本 |
| §4.4 REST 端点组织：`sections[]` 分组 vs 顶层扁平 `endpoints[]` | sections 分组，铁律 5「唯一组织方式」（论据：api-viewer 按 sections 渲染） | 顶层扁平 endpoints + `id`/`protocol` 字段 | 同 zy-iot | 以 consult 为准；分组铁律**留项目侧** | 渲染器按 sections 还是按协议 Tab 渲染属各项目 viewer 实例差异，不回灌 |
| §4.4 端点 schema 中 `consumes` / `produces` 追溯字段（引 development-standard §2.6） | 有 | 无 | 无 | ✅已裁（R-007 定案：注明成立，2026-08-23） | 经核 development-standard §2.6 数据协议表已定义 API 端点 `consumes`/`produces`，悬空引用解除；schema 不恢复字段，§8 已加注 |
| §8.2 ER→API 一致性检查 + §8.3 输出格式 | 有（field_mismatch 等 4 类 Issue，source=er-to-api） | 无（§8 收窄为工作流→API 单向） | 同 zy-iot | ✅已裁（R-007 定案：一致性检查上收 review 成立，2026-08-23） | 跨资产契约校验由 review 统一调度（其 §2.3 按 CASE-001 委托本技能一致性检查模式执行）；本技能 §8 保持工作流→API 单向，正文 §8 已加注 |
| 实战铁律集 | 5 条（①6 维度穷尽 ②错误码区间引用 ③必须渲染 ④重复 key ⑤sections 分组） | 7 条（Section 归属/枚举 ref/渲染/信封包裹/重复 key/导航锚点/发布子目录） | 同 zy-iot | 以 consult 为准 | boxing 铁律①内容已由 consult 设计规则 1 与 §6.3 清单覆盖；②已由 §6.3 清单「错误场景引用 §7.2 错误码区间」+ §7.2 覆盖；⑤见上（留项目侧）；其余为 consult 新增协议铁律 |
| §9 CHANGELOG 规范章（一行式格式+示例） | 有 | 无 | 无 | 不回灌 · 留项目侧 | consult 设计规则 6 已保留 CHANGELOG 必写要求与位置；具体格式模板属项目约定 |
| §7 REST 公共约定（错误码区间/幂等/缓存/频控/数据格式） | 有 | 有 | 有 | 基座保留 | 三方一致 |

## 清单

### 已回灌
（无——boxing 的三处独有内容中，两处进入待议、一处判定为项目侧，均未达「明显通用且无争议」标准）

### 不回灌 · 留项目侧
1. sections 分组组织方式及其铁律（boxing 项目 api-viewer 的渲染机制决定）。
2. CHANGELOG 一行式格式模板。

### 待议
1. ~~`consumes`/`produces` 端点追溯字段是否恢复进 §4.4 schema~~ ✅已裁（R-007 定案：注明成立，2026-08-23）：字段已在 development-standard §2.6 定义，§8 `untraced` 引用成立，schema 不恢复字段。
2. ~~ER→API 一致性检查归属（本技能 §8.2 / review 技能 / 废弃）~~ ✅已裁（R-007 定案：一致性检查上收 review 成立，2026-08-23）：由 review 统一调度，本技能 §8 保持工作流→API 单向口径。
3. **章节物理顺序**：正文物理排列为 …6 → 9 → 10 → 7 → 8，逻辑编号齐全但 §9/§10 物理插在 §6 与 §7 之间；L1 仅校验标题集合故通过，建议枢纽排版时归位。

## L1 相关事实
- 草稿对底座的唯一修改：frontmatter 增加 lineage 血缘头。正文零改动。
