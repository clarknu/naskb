# CHANGELOG — review（仲裁版草稿）

## 2026-08-23 · arb-hub 仲裁版草稿 v1（含 R-001 裁决执行）

- 底座：zy-ai-consult 版（`7527ea01ce6d`；较 zy-iot-ai 版多「架构契约机械校验」条款，属 consult 演进，保留）。
- 新增 frontmatter `lineage` 血缘头，另加 `rulings: [R-001]`。
- **R-001（CASE-001）执行**：§2.3 中 4 条 ER→API 契约一致性检查的委托对象由 `entity-relationship` 改为 `api-design`，表后加注记「委托归属依据 CASE-001 裁决（2026-08-23）：API 契约一致性由契约所有者 api-design 执行」。其余维度（工作流→ER、ER→ORM/TDD/前端等）逐一核对后未改动。
- 回灌 2 处（boxing → 草稿，特殊指令②）：§2.1 与 §2.10 的 `_shared/consistency-check-format.md` §3 source 注册引用——consult 缺失而 boxing 有，判定通用（zy 系 mobile/desktop-code-gen 已引用同一共享规范），回灌补齐。
- 待议 4 项（未并入）：触发点路由（低风险跳过 D5/D12）、D5 覆盖率获取方式与 D8 铁律的内部张力、报告缺字段兜底核对、收敛条件计数矛盾（底座写「三个条件」实列 4 条）。详见 MERGE-NOTES.md。
- scripts/ 两个校验脚本三方哈希一致，原样保留。
