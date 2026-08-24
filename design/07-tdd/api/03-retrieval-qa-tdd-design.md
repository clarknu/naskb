# TDD 设计（API）：检索问答

> 基于 API 设计 v1 | 工作流 v1 | 后端架构 v1（L3）
> 日期：2026-08-24 | Stage: API TDD
> 反向记录说明（DD-004）：既有套件映射 + 追溯链补齐。

## 测试范围

| API 端点 | 方法 | 涉及工作流 | 涉及实体 | 既有测试 |
|----------|------|-----------|---------|---------|
| /api/kb/search | GET | section: main-flow（引擎链） | VectorRow/Hit | api/test_server_api.py、unit/test_retrieval.py |
| /api/ask | POST | section: main-flow（RAG） | Hit/Citation | unit/test_deep_ask.py（RAG 单元）、api/test_server_api.py |
| /api/search、/api/reload、/api/stats | GET/POST/GET | section: rules（R006 契约恒定） | — | api/test_serve.py（legacy TestHttp） |
| /api/pg/rebind | POST | section: rules | NasReg | api/test_server_api.py（rebind 用例） |
| 向量库/嵌入 | — | section: main-flow | VectorRow | unit/test_vector_index.py、test_pgstore.py（integration/） |

## 追溯矩阵

| 测试用例 | 正向链 | 反向链 | 用户旅程 |
|---------|--------|--------|---------|
| TC-R01 | workflow:query.outputs.normalized_query → GET /api/kb/search.consumes[].query → ER:VectorRow | ER:VectorRow ← kb/search ← workflow:query | 检索→预览→下载 |
| TC-R04 | workflow:rag.outputs.answer → POST /api/ask.consumes[].question → ER:Hit | ER:Hit ← /api/ask ← workflow:rag | 提问→来源→打开 |

## 用户旅程覆盖矩阵

| 旅程 | 涉及 API | 覆盖测试用例 | 状态 |
|------|---------|-------------|------|
| 检索 → 问答 → 打开结果 | GET /api/kb/search、POST /api/ask、GET /api/files/{rid} | TC-R01~TC-R06 | ✅ |

## 测试用例

### TC-R01: 检索命中结构与状态
- **类型**: 正常流程 ｜ **前置条件**: 临时 .naskb 仓库 + 桩嵌入（_FakeEmbedder）
- **断言清单**: ✅ hits[] 字段（path/score/summary/category/tags/stale）；✅ 引擎徽章 engine 值（pg|vector|bm25）

### TC-R02: 引擎链降级
- **类型**: 边界条件 ｜ **断言清单**: ✅ 无向量索引 → BM25 自动降级（不报错）；✅ PG 不可达 → 本地向量（回退链断言）

### TC-R03: 空查询
- **类型**: 异常流程 ｜ **断言清单**: ✅ 空 query → 400（legacy 契约：{error: 缺少查询参数 q}）

### TC-R04: RAG 问答（带来源）
- **类型**: 正常流程 ｜ **断言清单**: ✅ answer + sources 列表；✅ 无 LLM → 明确错误兜底

### TC-R05: 条约级问答直返/兜底
- **类型**: 边界条件 ｜ **断言清单**: ✅ 命中 ≥0.9 → 直接返回条款原文（不调 LLM）；✅ 无命中 → no_hit_mode 兜底（designated 默认）

### TC-R06: 统计与 rebind
- **类型**: 正常流程 ｜ **断言清单**: ✅ /api/stats 返回 engine/docs/vector_index；✅ pg/rebind 幂等（重复调用结果一致）
