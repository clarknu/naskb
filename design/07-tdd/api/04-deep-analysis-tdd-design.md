# TDD 设计（API）：深度分析

> 基于 API 设计 v1 | 工作流 v1 | 后端架构 v1（L3）
> 日期：2026-08-24 | Stage: API TDD
> 反向记录说明（DD-004）：既有套件映射 + 追溯链补齐。

## 测试范围

| 验证对象 | 涉及工作流 | 涉及实体 | 既有测试 |
|----------|-----------|---------|---------|
| 标题树分段（md_chunker） | section: main-flow（split） | Chunk | unit/test_chunker.py |
| 条款级管道 | section: main-flow | VectorRow(level=chunk) | unit/test_deep_pipeline.py |
| 深析基准/评估 | section: rules（R001 参数） | — | unit/test_deep_bench.py、test_deep_eval.py |
| 条款级问答（/api/kb/ask） | section: main-flow | Citation | api/test_server_api.py、test_v2_features.py（PG） |

## 追溯矩阵

| 测试用例 | 正向链 | 反向链 | 用户旅程 |
|---------|--------|--------|---------|
| TC-D01 | workflow:split.outputs.chunks → md_chunker → ER:Chunk | ER:Chunk ← md_chunker ← workflow:split | 深析开关→分段→条款问答 |
| TC-D05 | workflow:ask.outputs.citations → POST /api/kb/ask → ER:Citation | ER:Citation ← kb/ask ← workflow:ask | 条款问题→两级引用 |

## 用户旅程覆盖矩阵

| 旅程 | 覆盖测试用例 | 状态 |
|------|-------------|------|
| 来源深析开关 → 扫描 → 分段 → 条款问答 | TC-D01~TC-D06 | ✅ |

## 测试用例

### TC-D01: 标题树分段参数
- **类型**: 正常流程 ｜ **前置条件**: 合成标准 md（ATX 六级）
- **断言清单**: ✅ target=800/limit=1200/overlap=0.12 命中；✅ title_path 正确；✅ 空段治理、代码围栏掩码

### TC-D02: 分段幂等
- **类型**: 正常流程 ｜ **断言清单**: ✅ chunker_version 一致 → 再跑结果不变

### TC-D03: 术语表/表格随块
- **类型**: 边界条件 ｜ **断言清单**: ✅ 表格随块重复表头；✅ 段落切割不破坏句子（句末智能切分）

### TC-D04: 条款级索引行
- **类型**: 正常流程 ｜ **断言清单**: ✅ 行含 kind/chunk_seq/title_path/search_vector；✅ 唯一约束（resource_id, model, chunk_seq）

### TC-D05: 条款级问答（两级引用）
- **类型**: 正常流程 ｜ **断言清单**: ✅ citations[{path, chunk_seq, title_path, score}]；✅ 引用到「文件+章节」两级

### TC-D06: 深析基准
- **类型**: 边界条件 ｜ **断言清单**: ✅ 合成基准 9 题 recall@3/@5=1.0（参数回归防线）
