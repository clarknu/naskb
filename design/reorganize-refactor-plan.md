# NASKB 整理功能 P0+P1 重构计划

> 版本: v0.2
> 状态: **P0+P1 已实施（2026-08-11，44 用例绿 + 全量回归通过）**
> 最后更新: 2026-08-11
> 依赖: [requirement.md](./requirement.md), [agent-interface-design.md](./agent-interface-design.md), [analysis-engine-v2.md](./analysis-engine-v2.md)
> 范围: 整理/重组功能（`Reorganizer` + `desc plan-reorganize`）的安全加固（P0）与功能闭环（P1）。
> 目标: 让整理功能达到"AI 可安全调用"的服务级：不越界、不冲突、不按过期方案执行、整理后检索不丢。

## 实施记录（v0.2 追加）

| 项 | 状态 | 说明 |
|----|------|------|
| P0-1 越界硬校验 | ✅ | `validate_move`（本地 normcase / WebDAV posix 双风格）+ `_finalize_plan` 过滤进 `rejected` + `apply` 开头复校验；plan 携带 `root` |
| P1-1 plan 持久化 | ✅ | `plan_store.py`（save/load/list/mark_applied + RootLock）；`collect` 加 hash；`plan` 附 `snapshot`；CLI 打印 plan_id |
| P0-3 apply 复检 | ✅ | `apply(store, plan, snapshot=None)`；文件级 hash 对比 → `stale_source` / `not_found`（snapshot 缺失时兼容旧调用） |
| P0-2 冲突三档 | ✅ | `_decide_conflict`：同 hash→`noop`；目标无分析→`meta_only`（`_copy_meta`，指纹按目标重算）；否则→`rename`（` (1)` 递增）；目录合并逐文件三档；文件 vs 目录→`conflict` |
| P1-3 向量索引 remap | ✅ | `VectorIndex.remap_paths`（仅重写 paths，无需重嵌入） |
| P1-2 服务方法 | ✅ | `apply_with_housekeeping`：RootLock 互斥 → apply → 级联 folder.json → 本地索引 remap + PG 增量同步；同步失败只记录不阻断 |
| P1-4 失败分类 | ✅ | `failed` 条目结构化为 `{src, dst, reason, detail?}`，reason 枚举 `conflict/stale_source/not_found/entry/io`；CLI 打印分类汇总 |

**实现偏差（相对 v0.1 计划）**：① `copy_analysis_meta` 未放 `desc_store.py`，实现在 `reorganizer._copy_meta`（用公开 API get_entry/set_entry/stat，不动 desc_store）；② `_refresh_folders` 从 `cli.py` 迁入 `reorganizer._refresh_folders`（静默失败不打印，级联尽力而为）；③ `apply` 的 `failed` 从三元组改为 dict（含 reason 枚举 + detail），CLI 与测试已同步。

---

## 1. 现状差距（已评审，见会话记录）

| # | 缺口 | 位置 | 后果 |
|---|------|------|------|
| A1 | `to` 越界无硬校验 | `reorganizer.py` `_finalize_plan` / `apply` | LLM 幻觉路径可把文件移出 root |
| A2 | 目标同名冲突无策略 | `desc_store.move_entry` | 静默覆盖/失败看运气，违反"移动不删除" |
| A3 | plan→apply 漂移（TOCTOU） | `apply()` 直接按旧方案执行 | 文件已被改动时按旧路径移动出错 |
| B1 | plan 不持久化 | `plan()` 进程内对象 | MCP 工具无状态，无法凭 plan_id 复取方案 |
| B2 | 整理后检索不同步 | 无（`serve` 只判陈旧降级） | 移动后向量索引/PG 路径失效，整理完反而搜不到 |
| B3 | 级联刷新在 CLI 层 | `cli.py` `_refresh_folders` | MCP server 直调 `apply` 会漏级联更新 |
| B6 | 失败原因无分类 | `apply` failed 为字符串 | Agent 无法自动决定跳过/重试/放弃 |

> B4（taxonomy 可配置）、B5（dry-run/预览）、B7（scope 分批）、C1~C5（MCP 协议适配）列入后续阶段，不在本次范围，但本次设计为其预留接口。

---

## 2. 改造点清单

### P0-1 越界硬校验（A1）

**文件**: `naskb/scripts/naskb/common/reorganizer.py`

**新增**:

```python
def validate_move(src: str, dst: str, root: str) -> tuple[bool, str]:
    """返回 (ok, reason)。dst 必须位于 root 之下（含 root 本身），
    src 必须位于 root 之下；二者均不得落在 .naskb 仓库内部。
    路径统一 normpath + normcase 后前缀判定（Windows 大小写不敏感）。
    """
```

- 目录级、文件级 move 统一走该校验；
- `_finalize_plan()` 内对每条 move 校验，**不合法 → 移入 `plan["rejected"]`**（带 reason，不静默丢弃，供审计/展示）；
- `apply()` 开头对 plan 全部 moves **再次校验**（双保险，防 plan 被外部篡改）；
- `new_folders` 同样校验（必须位于 root 之下）。

**测试**: 构造 `to` 为 root 之外 / `..` 穿越 / `.naskb` 内部的 plan → `apply` 拒绝且文件未移动；`rejected` 带原因。

### P1-1 plan 持久化（B1）

**文件**: 新增 `naskb/scripts/naskb/common/plan_store.py`（工作区 `plans/` 目录，JSON 原子写，复用 desc_store 的原子写模式）

**数据结构**:

```python
# plans/<plan_id>.json
{
  "plan_id": "uuid",
  "root": "C:/NAS/xxx",
  "created_at": "iso",
  "status": "pending",          # pending | applied | expired
  "plan": {plan_name, rationale, new_folders, moves, total},
  "snapshot": {"<src_path>": "<file_hash>"},   # collect 时指纹，P0-3 复检用
  "applied_at": null,
  "result": null,               # apply 返回的完整结果（含 sync）
  "audit": []                   # 追加式审计记录
}
```

**API**: `save_plan(plan, snapshot, root) -> plan_id` / `load_plan(plan_id) -> Plan|None` / `list_plans(root, status=None)` / `mark_applied(plan_id, result)`。

**配套**: `Reorganizer.collect()` 的 item 增加 `"hash": e.file_hash if e else ""`（数据已存在，只加字段）；plan 生成后由调用方（CLI/将来 MCP）调 `save_plan`。

**测试**: save/load/list/mark_applied 往返；plan_id 不存在返回 None；原子写（中断不留半文件）。

### P0-3 apply 复检（A3，依赖 P1-1）

**文件**: `reorganizer.py` `apply()` 改造

- 签名改为 `apply(store, plan, snapshot: dict, ...)`——**不再接受裸 moves**；
- 每条 move 执行前复检：
  - 文件级: `store.check(src)` —— `missing` → 记 `not_found` 跳过；`stale`（hash 与 snapshot 不符）→ 记 `stale_source` 跳过，**不移动**；
  - 目录级: 目录存在 + 直接子项数不变（轻量；文件级 hash 全查对目录太大，避免过度设计）；
- 复检不过的条目进 `failed`，带 `reason` 分类（见 P1-4）。

**测试**: plan 生成后改动源文件 → apply 时该条 `stale_source` 且未移动；删除源文件 → `not_found`。

### P0-2 目标冲突检测（A2，用户拍板三档策略）

**文件**: `reorganizer.py`（apply 内新增预检阶段）+ `desc_store.py`（新增 meta_only 元数据迁移 helper）

- `apply` 执行前 **dry-run 冲突扫描**（不移动，只枚举），逐条判定处理方式：
  - `dst` 是目录且 `src` 是文件 → `conflict`（文件 vs 目录）：记 `failed[reason=conflict]`，跳过；
  - `dst` 是目录且 `src` 是目录 → **合法合并**（文件并进目标目录，目录级 move 的常见场景，始终允许，继续走 move）；
  - `dst` 是文件 → **三档判定**：
    1. **内容相同**（hash 一致）→ `noop`：**啥也不干**（不移动、不覆盖、不删源），记入结果 `noops`；
    2. **内容不同且目标无有效元数据** → `meta_only`：把源条目的分析元数据（analysis/images/transcription/ocr_text 等）**迁移到目标条目，文件不移动**；目标条目的指纹字段（file_hash/hash_algorithm/size/mtime/ctime）用目标文件实际值重算（否则 `check()` 误报 stale），provenance 记录元数据来源；记入结果 `meta_onlys`；
    3. **内容不同且目标已有有效元数据** → `rename`：目标追加 ` (1)`、` (2)`…（先检查再递增），走正常 move。
  - "目标无有效元数据"判定：目标无 `.naskb` 条目，或条目 `has_analysis()` 为 False（复用 `FileEntry.has_analysis()`）。
- 执行顺序：先扫全部冲突并分类汇总进结果（`conflicts` / `noops` / `meta_onlys`），再执行 move/rename 类；
- **单一失败不推导任务失败**：任意条目失败只进 `failed` 分类并继续，任务结果含完整失败清单，由上层决定整体成败。

**测试**: ① 目标同名且 hash 相同 → `noop`，两边文件都不动、无新条目；② 目标同名但内容不同、目标无分析 → `meta_only`，目标条目获得源元数据、文件未移动、目标指纹为实际值；③ 内容不同且目标已有分析 → `rename` 生成 ` (1)` 不覆盖；④ 文件 vs 目录冲突 → `failed[conflict]`；⑤ 目录合并成功。

### P1-3 向量索引 remap（B2 之本地索引，独立、便宜）

**文件**: `naskb/scripts/naskb/common/vector_index.py`

**新增**:

```python
def remap_paths(self, mapping: dict[str, str]) -> int:
    """仅重写 vectors.json 的 paths 字段（向量矩阵不变：移动不改 summary
    文本 → 向量不变）。返回受影响条数。索引未加载时返回 0。"""
```

- 保存后 `serve` 的陈旧判定（`set(paths) == set(docs paths)`）自然通过，无需重嵌入；
- 映射来自 apply 的 `moved` 列表 `(old, new)`。

**测试**: build 索引 → `remap_paths` → `paths()` 为新路径、`count()` 不变、`search` 仍命中（同向量矩阵）。

### P1-2 服务方法下沉（B3，整合点）

**文件**: `reorganizer.py` 新增（`_refresh_folders` 从 `cli.py` 迁入，新方法调它）

```python
def apply_with_housekeeping(self, store, plan, snapshot, *, llm_client=None,
                            config=None, sync=True, progress=None) -> dict:
    """完整整理事务：
    1) 越界复校验（P0-1）     2) 冲突三档扫描（P0-2）   3) 复检（P0-3）
    4) 执行 moves（持 root 互斥锁）  5) 级联刷新 folder.json（原 cli._refresh_folders）
    6) 整理后同步：本地向量索引 remap + PG sync_vectors（P1-3 配套）
    返回 {moved, failed, noops, meta_onlys, rejected, conflicts,
          affected_dirs, removed_dirs, sync}
    """
```

- `cli.py` `desc_plan_reorganize --apply` 改为：`save_plan` → `load_plan` → 调服务方法（行为不变，回归验证）；
- 同步策略：本地索引存在则 `remap_paths`；PG 启用则 `store.rebuild(root)` → `sync_vectors`（增量、移动检测天然处理 rel_path 变更、保留 resource_id）。**整理是主操作，同步尽力而为（用户拍板）**：同步失败**只记录**（结果 `sync: {vector_index: ok|skipped|failed, pg: ok|skipped|failed}` + 审计日志），**绝不阻断/回滚已完成的整理，也不推导任务失败**；`sync=False` 可关。
- **root 级互斥锁（用户拍板，必做）**: `plans/<root_hash>.lock`——O_EXCL 创建、内容记 pid+时间戳；带过期接管（锁 mtime 超阈值视为残留，可接管）；apply 全程持锁，防两个调用方同时整理同一 root；CLI 与将来 MCP 共用同一锁实现。

**测试（集成）**: analyze-tree → plan → save → apply（服务方法）→ 断言：folder.json 级联更新、本地索引 `paths()` 为新路径且 serve 不判陈旧、PG 行 rel_path 更新且 resource_id 保留、`desc search` 能找到移动后的文件。

### P1-4 失败原因分类（B6）

- `apply` 的 `failed` 条目改为 `{src, dst, reason}`，reason 枚举：
  `conflict` / `stale_source`（源已变） / `not_found`（源已消失） / `out_of_root`（越界，P0-1 拦截） / `io`（fs 错误） / `entry`（条目移动失败）；
- CLI 打印分类汇总；将来 MCP 工具直接返回结构化失败。

---

## 3. 实施顺序（依赖驱动）

```
1. P0-1 越界校验          ← 独立，先做（安全底线）
2. P1-1 plan 持久化       ← 独立（collect 加 hash 字段）
3. P0-3 apply 复检        ← 依赖 2（snapshot 来源）
4. P0-2 冲突检测          ← 依赖 1 的校验框架
5. P1-3 向量索引 remap    ← 独立（简单，可并行）
6. P1-2 服务方法下沉      ← 依赖 1~5，整合点
7. P1-4 失败分类          ← 随 6 一起
```

> 5 可与 1~4 并行；每步独立可测、可提交。

---

## 4. 文件改动清单

| 文件 | 改动 |
|------|------|
| `naskb/scripts/naskb/common/reorganizer.py` | `validate_move`、collect 加 hash、plan 校验/rejected、apply 复检+冲突+服务方法、failed 分类 |
| `naskb/scripts/naskb/common/plan_store.py` | **新增**：plan 持久化（save/load/list/mark_applied） |
| `naskb/scripts/naskb/common/vector_index.py` | **新增** `remap_paths` |
| `naskb/scripts/naskb/common/desc_store.py` | **新增** `copy_analysis_meta(src_entry, dst_path)` helper（meta_only 用：复制分析元数据、按目标实际值重算指纹、provenance 记来源）；`move_entry` 目标存在处理（rename 场景） |
| `naskb/scripts/naskb/skill/cli.py` | `desc_plan_reorganize` 改为 plan_id 流程 + 调服务方法；`_refresh_folders` 迁出 |
| `tests/` | 新增 `test_plan_store.py`、`test_reorganize_safety.py`（P0/P1 用例），集成用例 |
| `design/agent-interface-design.md` | C 组工具重设计（见 §6） |
| `design/requirement.md` | REQ-R1-11 强化条目（见 §6） |

---

## 5. 测试计划

- 单测（无需 LLM，mock `complete_json`）：
  - 越界/`..`/`.naskb` 内部目标 → 拒绝 + rejected 带原因；
  - plan 往返持久化；snapshot 复检：stale → 跳过、missing → not_found；
  - 冲突三档：同名同 hash → `noop`（两边不动）；同名异内容+目标无分析 → `meta_only`（元数据迁移、指纹重算、文件不动）；同名异内容+目标有分析 → `rename`（` (1)` 递增不覆盖）；文件 vs 目录 → `failed[conflict]`；目录合并成功；
  - remap_paths：count 不变、search 命中、paths 更新；
- 集成（真 DeepSeek，小目录 fixture）：
  - 全闭环：analyze-tree → plan → save → apply_with_housekeeping → 断言 folder.json 级联、本地索引不陈旧、`desc search` 命中新路径；PG 环境启用时断言 rel_path 更新 + resource_id 保留；
- 回归：现有 164 用例全绿；`desc plan-reorganize --apply` 行为不变。

---

## 6. 文档同步

### 6.1 `design/agent-interface-design.md` C 组工具重设计（实施 Phase A 时更新）

| 旧 | 新 |
|----|----|
| `kb_plan_reorganize(root, nas, max_items)` | `kb_plan_reorganize(root, scope=None, taxonomy=None, max_items=None)` → 异步 job → `{plan_id, plan, summary}`；**返回 plan_id，方案持久化** |
| `kb_apply_reorganize(plan_id, sync=true)` | → 异步 job → `{moved, failed[], noops[], meta_onlys[], rejected[], affected_dirs, removed_dirs, sync{}}`；冲突三档策略服务端内置（同 hash→noop / 目标无分析→meta_only / 否则 rename）；apply 凭 plan_id 取方案+快照，服务端复检；持 root 互斥锁 |
| — | **新增** `kb_preview_reorganize(plan_id)` → 同步：dry-run 校验结果（冲突/越界/过期清单）+ 整理前后目录 diff（复用 P0-1/P0-2 的扫描器，白拿） |

- 删掉旧的裸 plan/apply 定义；plan_id 成为 apply 的唯一凭证，天然满足"确认后执行"（`approval: manual|auto` 策略留到 MCP 阶段）；
- C 组工具全部标 `kind=Job`（plan 多轮 LLM 分钟级、apply 批量移动）。

### 6.2 `design/requirement.md`

- 新增 `REQ-R1-14`（整理安全）：越界硬校验 / 目标冲突策略（skip|rename|目录合并）/ plan 快照复检（TOCTOU 防护）/ plan 持久化 plan_id；
- 新增 `REQ-R1-15`（整理闭环）：apply 后本地向量索引 remap + PG 增量同步（移动保留 resource_id），同步失败不阻断整理、状态可查；
- `REQ-R1-11` 更新备注指向 R1-14/15。

---

## 7. 风险与回退

| 风险 | 缓解 |
|------|------|
| 复检对目录级 move 过严/过松 | 目录级只复检"存在+子项数"，文件级 hash 全查；单测覆盖边界 |
| remap 后索引与其他索引文件不一致 | remap 只改 paths 字段，npz 不动；`load()` 自检长度仍成立 |
| 级联刷新下沉后 CLI 行为回归 | 服务方法默认参数与旧 CLI 语义一致；集成回归 |
| WebDAV 路径规范化差异 | `validate_move` 按 fs 层路径形态实现（本地 normcase；WebDAV 前缀判定），单测两种形态 |
| 同步失败阻塞整理 | 明确"整理为主、同步尽力而为"，失败仅置状态位，绝不回滚已移动文件 |

---

> **下一步**：按 §3 顺序从 P0-1 开始实施，每步独立提交 + 测试。确认后开工。
