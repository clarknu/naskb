# TDD 设计（API）：采集与分析

> 基于 API 设计 v1 | 工作流 v1 | 后端架构 v1（L3）
> 日期：2026-08-24 | Stage: API TDD
> 反向记录说明（DD-004）：本文档为反向记录（既有套件映射 + 追溯链补齐）。本域无独立 REST 端点（任务驱动域），用例 = 管线领域单元/集成验证。

## 测试范围

| 验证对象 | 涉及工作流 | 涉及实体 | 既有测试（tests/unit/） |
|----------|-----------|---------|------------------------|
| 分析管线（文档/图片/音频/视频/目录） | section: pipeline | FileDetail/Analysis | test_analyzer.py、test_analyzer_v2.py、test_folder_analyzer.py、test_mindmap.py |
| 批量与增量幂等 | section: main-flow（三级判定） | Doc | test_batch.py |
| .naskb 仓库服务 | section: main-flow | NaskbIndexEntry | test_desc_store.py、test_split_storage.py |
| 指纹与免检 | section: main-flow（L1/L2） | — | test_hashing.py |
| 干净导出（REQ-R5-02） | section: rules（R005） | — | test_clean_export.py |
| 扫描对账 | section: main-flow | ResourceStatus | test_inventory.py（integration/ 含 PG 用例） |
| MinerU 集成 | section: pipeline | MineruMd（VO） | test_mineru.py |

## 追溯矩阵

| 测试用例 | 正向链 | 反向链 | 用户旅程 |
|---------|--------|--------|---------|
| TC-A01 | workflow:l2_check.outputs.sampled_hash → batch → ER:Doc | ER:Doc ← batch ← workflow:l2_check | 扫描→分析→入库 |
| TC-A05 | workflow:store.outputs.entry_updated → desc_store.set_entry → ER:NaskbIndexEntry | ER:NaskbIndexEntry ← desc_store ← workflow:store | 同上 |

## 用户旅程覆盖矩阵

| 旅程 | 覆盖测试用例 | 状态 |
|------|-------------|------|
| 扫描 → 三级判定 → 分析 → .naskb 双写 → PG 同步 | TC-A01~TC-A08 | ✅（既有套件覆盖；PG 部分见 integration） |

## 测试用例

### TC-A01: 文档分析（快速路径）
- **类型**: 正常流程 ｜ **前置条件**: 临时目录 + 桩 LLM（_FakeLLM）
- **断言清单**: ✅ 提取全文 → 分类/摘要/标签；✅ 文本不足阈值 → MinerU 路径（mock）

### TC-A02: 图片/音频/视频分析
- **类型**: 正常流程
- **断言清单**: ✅ 图片 EXIF+MiMo 描述（串行 mock）；✅ 音频分段转写；✅ 视频分级（metadata_only/keyframes_only/full）

### TC-A03: 增量幂等（三级判定）
- **类型**: 正常流程
- **断言清单**: ✅ 二次分析零变化（hash 一致跳过）；✅ 变更文件重分析；✅ 删除清孤儿

### TC-A04: 批次容错
- **类型**: 异常流程
- **断言清单**: ✅ 单文件失败不阻断整批；✅ 并发窗口（DeepSeek 4-6 / MiMo 串行）语义

### TC-A05: .naskb 双写原子性
- **类型**: 正常流程
- **断言清单**: ✅ set_entry 后 files/ 与 index.json 一致；✅ move_entry 先移文件后迁条目；✅ remove_entry 原子

### TC-A06: 干净导出
- **类型**: 正常流程 ｜ **断言清单**: ✅ 产物为干净 Markdown/ZIP、不含临时字段

### TC-A07: 扫描对账
- **类型**: 正常流程 ｜ **断言清单**: ✅ valid/stale/missing 判定；✅ 消失仅标记不物理删除

### TC-A08: 指纹采样
- **类型**: 边界条件 ｜ **断言清单**: ✅ 8×64KB 采样算法（ADR-20260816-4）在临界大小文件上稳定
