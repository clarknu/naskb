# TDD 设计（API）：来源管理

> 基于 API 设计 v1 | 工作流 v1 | 后端架构 v1（L3）
> 日期：2026-08-24 | Stage: API TDD
> 反向记录说明（DD-004）：实现/测试先于方法论存在，本文档把既有套件映射为 TC 规格并补齐追溯链；实现状态以 tests/ 为准。

## 测试范围

| API 端点 | 方法 | 涉及工作流 | 涉及实体 | 既有测试（tests/ 重组后路径） |
|----------|------|-----------|---------|------------------------------|
| /api/sources | GET | section: overview | Source | unit/test_source_registry.py |
| /api/sources | POST | section: main-flow | Source（注册） | unit/test_source_registry.py |
| /api/sources/{sid} | PATCH/DELETE | section: main-flow | Source | unit/test_source_registry.py |
| /api/sources/{sid}/test|scan|analyze|adopt | POST | section: main-flow | Source/Job | unit/test_source_registry.py（任务入口断言） |
| /api/sources/{sid}/changes|confirm | GET/POST | section: change-confirm | Source | unit/test_source_registry.py |

## 追溯矩阵

| 测试用例 | 正向链（workflow→API→ER） | 反向链（API←ER←workflow） | 用户旅程 |
|---------|--------------------------|--------------------------|---------|
| TC-001 | workflow:register.outputs.source_id → POST /api/sources.consumes[].alias → ER:Source | ER:Source ← POST /api/sources ← workflow:register | 来源注册→扫描→分析 |
| TC-005 | workflow:scan.outputs.reconcile_diff → POST {sid}/scan.consumes[].source_id → ER:Job（VO） | ER:Job ← {sid}/scan ← workflow:scan | 同上 |

## 用户旅程覆盖矩阵

| 旅程 | 涉及 API | 覆盖测试用例 | 状态 |
|------|---------|-------------|------|
| 注册→测试→扫描→变更→确认 | POST /api/sources、{sid}/test、{sid}/scan、{sid}/changes、{sid}/confirm | TC-001~TC-006 | ✅（既有套件覆盖） |

## 测试用例

### TC-001: 来源注册（连通成功后入库）
- **类型**: 正常流程
- **前置条件**: 临时来源目录可用（tmp_path）
- **调用序列**: 1. 构造 SourceRecord（local/ro）→ 2. register → 预期 source_id 生成、alias 唯一
- **断言清单**: ✅ 注册返回条目含 source_id/alias/access_mode；✅ 重复 alias 抛错（唯一约束）
- **边界条件**: ⚠️ 非法 alias 字符 → 校验错误

### TC-002: 来源解析与脱敏
- **类型**: 正常流程
- **断言清单**: ✅ to_api() 输出不含 password 字段值（敏感字段脱敏）

### TC-003: 来源启停
- **类型**: 状态转换
- **断言清单**: ✅ enabled toggle 后状态翻转、持久化

### TC-004: 删除来源
- **类型**: 异常流程/边界
- **断言清单**: ✅ 删除后 list 不含该来源；✅ ro 源删除连带清除语义（PG 用例见 integration）

### TC-005: 连通性探测失败
- **类型**: 异常流程
- **断言清单**: ✅ 坏路径/坏 WebDAV → 返回明确错误（不静默）；✅ 失败不污染注册表

### TC-006: 变更确认清单
- **类型**: 正常流程
- **断言清单**: ✅ 扫描后 diff（added/changed/missing）三组正确分组；✅ confirm 提交 job_id

### TC-007: WebDAV 密码验证路径
- **类型**: 边界条件
- **断言清单**: ✅ verify_ssl=false 走不校验分支（mock server）
