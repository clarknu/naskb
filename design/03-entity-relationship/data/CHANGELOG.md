# ER 设计变更说明 v0 → v1

> 存量项目 SFDS 方法论接入：按 PG DDL 与 .naskb 事实基线反向建立 6 域 ER 资产。
> 日期：2026-08-24

---

## 变更 1：建立 6 域 ER 资产 + 跨域总纲

**类型**：新增实体/关系（存量接入）
**来源**：SFDS 方法论补全（project-code-domain 事实基线：pgstore DDL / desc_store / plan_store）

### 变更内容

| 之前 | 之后 |
|------|------|
| 无结构化 ER 数据 | 6 域 ER 数据文件 + core-er.js |

- `01-source-management.js`：source（public.sources 22 字段）/ nas_reg（五要素）
- `02-ingestion-analysis.js`：resource / folder_entry / naskb_index_entry + FileDetail/Doc/ArtifactRecord VO + 指纹/状态枚举
- `03-retrieval-qa.js`：vector_row / term_entry + Hit/Citation VO（level=summary|chunk|title）
- `04-deep-analysis.js`：Chunk/MineruMd VO（条款级；向量行引用 03 域，不重复定义）
- `05-knowledge-reorganize.js`：plan_record + MoveOp/SnapshotFp VO + 冲突三档枚举
- `06-platform-console.js`：Job/RangeRequest VO + 服务定义（无持久表——内存队列设计）
- `core-er.js`：6 域注册 + 4 条跨域关系（来源→资源/目录、资源→向量、条款级→资源）

### 理由

- entity-relationship §2 四数组结构（entities/value_objects/services/enums）落地；
- 不重复定义原则：vector_row 唯一归 03 域，04 域仅跨域引用（ghost 渲染）。

---

## 涉及的 Section / Flowchart

- 无 flowchart（ER 资产为实体关系图）；跨域关系见 `core-er.js` core_relations。

---

## 变更 2：派生数据集建模对齐（P-004 拍板）

**类型**：新增值对象｜**来源**：用户拍板（2026-08-24）：重复/同功能数据集设计与实现必须对齐。

- `01-source-management.js`：新增 `source_stats` VO（一致性报告 knowledge 载荷：files/ok/stale_source/missing_source/analyzed/chunks/error——PgStore.source_stats 聚合派生）
- `06-platform-console.js`：新增 `folder_entry_view` VO（/api/folder 响应载荷：rel_path/name/summary/description/tags/file_count/source(folders|generated)——与 02 域 folder_entry 实体同语义视图）
- 对齐三方：ER VO ↔ API 响应 fields（rest/01 report、rest/06 folder）↔ 实现（source_stats/list_dir 返回）

---
