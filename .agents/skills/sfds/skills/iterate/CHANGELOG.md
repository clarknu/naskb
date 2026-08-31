# CHANGELOG — iterate（仲裁版草稿）

## 1.1.0-arb.1（2026-08-31，CASE-015/016）

- 从 zy-iot-ai 回灌（需求方 2026-08-30 确认采纳）：**「默认执行载体」**——阶段二的执行/验证**默认进入 `pipeline-controller` 流水线模式**（登记 `T-xxx` 进 `.pipeline/PIPELINE.md` 队列、后台持锁串行、一任务一 commit、落过程留痕到 `.pipeline/journal/`），本 skill 只负责阶段一（分析+级联计划）与守卫；唯一例外=用户显式声明「一次性/直接改/不用管线」。
- **关键规则新增 #15「默认进 pipeline 模式」**（与 pipeline-controller v2.2.0-arb.1「默认激活与分层」「过程留痕」联动，两技能分层叠加：外壳/内容引擎）。
- lineage 加 reclaim 注记。iot 侧 §8.4/§8.7 的平台拆分技能名引用**不采纳**（CASE-017 已裁 client-* 合并）。

## 1.0.0-arb1（2026-08-23）

- 底座：`inbox/zy-ai-consult/iterate/SKILL.md`（37bd78e52cf1）。
- 回灌 R-002「按数量分流的细粒度分发」（源自 boxing，5 处小改）：触发词「更新」移入修正组并加不匹配派发注记；派发表新增「修复…/更新…视范围而定」行；「不匹配/遗漏/未同步/对不上/接口对不上」拆分为单点问题→B 与批量联调→C 两行（关键词枚举保留底座全集）。
- 挂起：boxing「harness 自动拉起」注记随 CASE-006 处理，本次未引入。
- 待议：boxing「前端生成验收」注记（见 MERGE-NOTES X4）。
- frontmatter 新增 lineage（三源 SHA256 前 12 位）+ `rulings: [R-002]`。
