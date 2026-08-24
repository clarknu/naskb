# TDD 设计（API）：知识整理

> 基于 API 设计 v1 | 工作流 v1 | 后端架构 v1（L3）
> 日期：2026-08-24 | Stage: API TDD
> 反向记录说明（DD-004）：既有套件映射 + 追溯链补齐。本域无独立 REST（CLI/MCP 驱动）；
> 用例 = 方案生成/校验/级联的领域验证。

## 测试范围

| 验证对象 | 涉及工作流 | 涉及实体 | 既有测试（tests/unit/） |
|----------|-----------|---------|------------------------|
| 方案生成/持久化 | section: main-flow | PlanRecord | test_plan_store.py |
| apply 三重校验 | section: apply-flow | — | test_reorganizer.py |
| 级联更新/空目录 | section: apply-flow（cascade） | MoveOp | test_reorganizer.py |
| 快照复检 | section: apply-flow（P0-3） | SnapshotFp | test_reorganizer.py |
| root 互斥锁 | section: rules（R005） | — | test_reorganizer.py（并发用例） |

## 追溯矩阵

| 测试用例 | 正向链 | 反向链 | 用户旅程 |
|---------|--------|--------|---------|
| TC-O02 | workflow:snapshot.outputs.plan_id → save_plan → ER:PlanRecord | ER:PlanRecord ← save_plan ← workflow:snapshot | 生成→预览→确认→apply |

## 用户旅程覆盖矩阵

| 旅程 | 覆盖测试用例 | 状态 |
|------|-------------|------|
| 生成 → 预览 → 确认 → apply（含冲突/失败分支） | TC-O01~TC-O07 | ✅ |

## 测试用例

### TC-O01: 方案生成两阶段
- **类型**: 正常流程 ｜ **前置条件**: tmp 仓库 + 桩 DeepSeek
- **断言清单**: ✅ Plan{plan_name/rationale/new_folders/moves/rejected/total} 完整；✅ 400 截断缺陷不再现

### TC-O02: 方案持久化与快照
- **类型**: 正常流程 ｜ **断言清单**: ✅ plan_id 稳定；✅ snapshot 指纹 {源路径: file_hash}

### TC-O03: 越界校验（P0-1）
- **类型**: 异常流程 ｜ **断言清单**: ✅ 路径逃逸/跨根移动 → 拒绝

### TC-O04: 快照复检（P0-3）
- **类型**: 异常流程 ｜ **断言清单**: ✅ plan 后源文件变化 → stale_source 拒绝执行（防 TOCTOU）

### TC-O05: 冲突三档（P0-2）
- **类型**: 边界条件 ｜ **断言清单**: ✅ noop/meta_only/rename(1) 递增逐一验证

### TC-O06: 级联更新
- **类型**: 正常流程 ｜ **断言清单**: ✅ 整仓跟随（artifacts/folder/meta 随迁）；✅ 祖先链 folder.json 刷新；✅ 空目录树清理；✅ 子路径先移

### TC-O07: root 互斥锁
- **类型**: 并发 ｜ **断言清单**: ✅ 同 root 并发 apply 被拒；✅ STALE_AFTER 过期可接管
