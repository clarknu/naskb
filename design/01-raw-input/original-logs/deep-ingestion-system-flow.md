# 深度分析纳入系统级同步流程 + MCP 深析接线（实施计划）

> 版本: v0.1（计划草案，待用户评审）
> 创建: 2026-08-23
> 问题: D' 的 chunk 入库目前是 CLI 两步（`desc sync-vectors` + `desc sync-chunks`），
>       与「把 NASKB 做成完整知识库系统」的定位不符——真正的同步应走系统界面/定时，
>       让用户看到差异、选择确认、再分析入库。本计划把 deep 分析作为**系统同步/分析流程
>       的一等能力**接入，并补 MCP `kb_ask` 深度接线。
> 依据: [requirement.md](./requirement.md)（REQ-R7-01/09/12、REQ-R5-06）、
>       [platform-v3-design.md](./platform-v3-design.md)、[deep-analysis-roadmap.md](./deep-analysis-roadmap.md)
> 相关实现: `server/routes_sources.py`、`server/scheduler.py`、`common/enrich.py`、
>           `common/source_registry.py`、`common/pgstore.sync_chunks`、`mcp/server.py`

---

## 0. 现状确认（先算清家底，避免重复造）

平台已经具备你描述的系统级闭环（UI + 定时），只差 deep 这一层没接进去：

| 环节 | 现状 | 与「系统」定位 |
|---|---|---|
| 来源注册 | `/api/sources` CRUD + 来源页 | ✅ 已有 |
| 同步检测 | `/api/sources/{sid}/scan`（reconcile）+ 调度器按 `scan_interval_min` 周期扫 | ✅ 已有（**自动 reconcile，无“确认清单”步**） |
| 分析入库 | `/api/sources/{sid}/analyze` → `enrich_source` → `sync_vectors` | ✅ 已有（**未调 chunk**） |
| 任务中心 | `/api/jobs` + 进度 | ✅ 已有 |
| 深析（chunk）入库 | ❌ 仅 CLI `sync-vectors` + `sync-chunks` | ⚠️ **缺口** |

**结论**：不需要重做同步系统；要做的是把 chunk 生成**挂进 `enrich_source` 这条既有流水线**，
作为来源级“深度分析”开关，并通过后台任务 + 进度 + 状态呈现；同时把“确认清单”补进
scan→analyze 之间（若你要）。

---

## 1. 目标

1. **系统级 deep 入库**：来源页/定时触发的 扫描→分析 自动带上 chunk；内容/分析版本变化时
   chunk 行随之重建（幂等）；任务报告与来源状态展示 chunk 数。
2. **MCP 深析**：`kb_ask` 走条款级（两级引用），`kb_search` 支持 `level` 参数——与
   `/api/kb/ask`、`/api/kb/search` 能力对齐。
3. **只读源缺口消除**：不再依赖源端持久 md，chunk 在分析窗口内用**暂存 md** 生成（符合
   REQ-R7-02 中间产物不残留）。
4. CLI `sync-chunks` 保留为高级/回退通道（不删除）。

---

## 2. 设计

### 2.1 来源级「深度分析」开关
- `SourceRecord` 增字段 `deep: bool = False`（标注该来源要走条款级 chunk；仅对含 MinerU md
  的来源有意义，rw/ro 皆可）。
- 来源 CRUD 白名单加入 `deep`；来源页加开关 + 提示文案（“需先能产生 MinerU md；开启后
  每次分析自动建条款级 chunk 行”）。
- 与 `[deep].roots` 目录级圈定的关系：**来源级开关优先，`[deep].roots` 作为目录级补充**
  （二者叠加；均在 sync_chunks 的 `_is_deep` 匹配内）。

### 2.2 chunk 生成钩子（核心，挂进 `enrich_source`）
位置：`enrich.py` 的 `sync_vectors(...)` 之后、`cleanup_artifacts(...)` 之前（此时暂存 md 尚在）。

```
在 enrich_source 内，若 source.deep 且 deep_cfg.enabled:
    deep_docs = [d for d in file_docs if d.text.strip() and _is_deep(d.path, deep_roots)]
    read_md = lambda d: 读取暂存 .naskb/artifacts/<stem>.md（staging，ro 也读得到）
    chunk_stats = pg.sync_chunks(schema, deep_docs, deep_cfg,
                                 source_id=source.source_id, read_md=read_md)
    进度并入 job；report["deep"] = {documents, chunks, skipped_*}
```

- **幂等**：`sync_vectors` 已据 hash 判增/改/删/移；chunk 行先删后建（`sync_chunks` 已实现），
  内容变化时自动重建。
- **只读源**：md 来自 staging（`cleanup_artifacts` 在 chunk 之后才跑），不再依赖源端 `.naskb`。

### 2.3 触发与「确认清单」
- 手动：来源页「扫描 / 分析」按钮 → 后台任务（自动带 deep）。
- 定时：`scheduler` 周期 scan→analyze，`deep` 来源自动建 chunk。
- **确认清单（建议本期加）**：`scan` 只产出**差异报告**（新增/变更/删除/缺失），来源页列出
  「待确认」清单，用户勾选后点「确定同步」→ 触发 `analyze`。这与你“用户去确认选哪些新东西”
  一致；现有 scan 是“自动 reconcile”，需要加这一“确认”层。

### 2.4 任务与状态呈现
- `job` 报告含 `deep: {documents, chunks, skipped_*}`；`/api/sources/{sid}` 与来源页显示
  “深析: 开/关 · chunk 行数”。
- 检索层已支持 `level='chunk'`；deep 来源在 `/api/kb/search|ask` 可通过 `level`/`deep` 过滤，
  无需新检索路径。

### 2.5 MCP 深析接线
- `mcp/server.py`：`kb_ask` 改为/新增 deep 路径（复用 `ask_deep` + chunk 检索，返回
  `citations` 两级引用）；`kb_search` 加 `level`（summary|chunk，默认 summary）。
- 与 REST 契约一致，前端/Agent 无感。

---

## 3. 分步落地（每步可测，走真实 PG/桩）

| 步 | 内容 | 验收 |
|---|---|---|
| 1 | `SourceRecord` + 来源 CRUD/UI 加 `deep` 开关（registry 持久化、白名单、来源页） | 来源可开关 deep；接口/页面反映 |
| 2 | `enrich_source` 挂 `sync_chunks`（staging md 读取 + 进度 + `report["deep"]`） | 集成测试：deep 来源 analyze 后 chunk 行存在；非 deep 0 行；只读源也可建 chunk |
| 3 | scan 差异报告 + 「确认清单」交互（scan 只出报告 → 勾选 → 触发 analyze） | 来源页可看到待确认项；勾选后 analyze 只处理勾选项（或全部） |
| 4 | `/api/sources/{sid}` 状态 + 来源页展示 chunk 数；job 报告含 deep | 状态/报告含 deep 统计 |
| 5 | `mcp/server.py` `kb_ask` 深析 + `kb_search level` | 单测/集成：MCP kb_ask 返回 citations；kb_search level 生效 |
| 6 | 只读源回归确认（用 staging md，不留存） | 集成测试通过 |
| 7 | 文档（requirement REQ-R5-06 更新、SKILL/README、roadmap）+ 全量测试 | 345+ 全绿 |

---

## 4. 范围说明
- 不动既有 sources/scan/analyze 的**语义**（自动 reconcile 仍成立），只在其上叠加 deep 层与
  确认层；不做多用户/引擎集成（仍是 D' 自研，无外部引擎）。
- CLI `sync-vectors/sync-chunks` 保留为高级/回退通道，不进正常路径。
- 不引入新依赖；仍走 PG + bge 本地嵌入；GPL 纪律不变（零拷贝）。

## 5. 变更历史
| 日期 | 变更 |
|---|---|
| 2026-08-23 | v0.1 计划草案：deep 纳入系统级同步流程 + MCP 深析接线；含现状确认、设计、分步落地、范围、3 个待拍板点 |
