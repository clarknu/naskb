# 知识整理（重组）

> 文档 ID: REQ-knowledge-reorganize | 最后更新：2026-08-24 | 从 2 个存量文档整合（original-logs/）
> 本文档为整合后的当前设计结论。原始讨论记录见 `original-logs/`。

## 一、核心决策

> **[R1-14]** 整理两段式：方案生成（只输出不动）→ 用户确认 → apply 执行（凭 plan_id 复校验，防 TOCTOU）。

> **[R1-14]** 仅 rw 源可整理（ro 只读源不写源端，故禁止移动）。

> **[R1-15]** 移动不删除；`.naskb` 整仓跟随（artifacts/folder/meta 随迁，index 保留目标）；源/目标/上层 folder.json 自动级联更新；搬空的源目录自动删除（只删空目录树）；子路径先移（防"先移整目录后抽子目录"失败）。

> **[核心安全]** apply 三重校验：P0-1 越界硬校验（validate_move 路径不出根）、P0-3 快照复检（snapshot 指纹比对，不一致 → 拒绝）、P0-2 冲突三档（noop | meta_only | rename(1) 递增）。

> **[并发]** root 互斥锁（整理期间禁止并行整理）；整理后同步：remap_paths + PG 增量同步（保留 resource_id；失败记录不阻断——尽力而为）。

## 二、详细设计

### 2.1 方案模型

Plan = {plan_name, rationale, new_folders[], moves[{src, dst, reason}], rejected[], snapshot（指纹）}；持久化 plan_id（plan_store）。

### 2.2 执行语义

1. 生成：全量收集 + 分片两阶段（DeepSeek 方案）；修复过 400 截断缺陷。
2. 预览：moves 清单 + 冲突预判（同目标冲突、目录循环、跨源拒绝）。
3. apply：校验 → 逐个 move（子路径先移、整仓跟随）→ 级联刷新 folder.json 祖先链 → 空目录 _remove_empty_chain → 同步向量/PG。
4. 说明：同步失败不阻断（记日志）；PG 侧保留 resource_id（移动不改身份）。

### 2.3 与下游的关系

- ER：PlanRecord（plan_store 行）、MoveOp（派生）——见 05-knowledge-reorganize.js。
- API：MCP kb_plan_reorganize/kb_preview_reorganize/kb_apply_reorganize（ai-tools 文件）；无独立 REST（CLI 为主入口）。
- 与 02 域级联规则共享（.naskb 原语）。

## 三、仍待决策

- ⚠️ 待定：Plan 预览的 Web 入口（当前 CLI/MCP；来源工作流中"整理"未接入 Web UI）。

## 四、来源索引

| 原始文件 | 主要贡献内容 |
|---------|-------------|
| reorganize-refactor-plan.md | plan/apply 全规则 |
| requirement.md | R1-14/15 整理安全需求 |
