# 采集与分析

> 文档 ID: REQ-ingestion-analysis | 最后更新：2026-08-24 | 从 4 个存量文档整合（original-logs/）
> 本文档为整合后的当前设计结论。原始讨论记录见 `original-logs/`。

## 一、核心决策

> **[R1]** 采集分析：扫描对账（inventory）+ AI 富化（enrich）分离；分析产物一律写入被分析目录的 `.naskb/` 隐藏仓库（meta.json / index.json 轻量索引 / folder.json / files/<rel>.json 大字段 / artifacts/）。

> **[R1-10]** 增量幂等：三级判定链——L1 免检（path+文件名+size+mtime+ctime 一致即跳过）、L2 采样 hash 复合（8×64KB，ADR-20260816-4）、L3 重析；变更重分析、删除清孤儿；hash 一致跳过。**可反复跑、可中断重跑**。

> **[R1]** 模型分工：DeepSeek（文本分类/摘要/标签/方案）并发 4-6（上限 8）；MiMo（图片/音频）、MinerU、ffmpeg、Word COM **严格串行**（并发会触发平台风控冻结 key）；401 停止重试并提示检查 key。

> **[R1-09?]** 文档双路径：PyMuPDF 快速提取 + 文本不足 30% 阈值 → MinerU 复杂路径；docx 档位 1（XML 流式图文 + MiMo 结构识别）/ 档位 2（Word 转 PDF → MinerU）。

> **[REQ-R5-02]** 干净导出：`.naskb` 分析产物 → 干净 Markdown/ZIP（供外部引擎），`export-clean`。

> **[R1-14/15]** 整理原则（见 05 域）：移动不删除、整仓跟随、级联更新、空目录清理、子路径先移。

## 二、详细设计

### 2.1 管线

1. 扫描对账：读源（fs base：local/webdav）→ 与 .naskb/index 比对 → valid/stale/missing；被忽略文件（exclusions）记"可能含义"轻量条目。
2. 分析：单文件（文档/图片/音频/视频）→ 分类/摘要/标签（DeepSeek）/视觉/转写（MiMo）；目录级只析结构 → folder.json。
3. 富化入库：desc_store 双写（files/ 大字段 + index.json 轻量条目）；PG 侧（若配 [pg]）同步 resources/vectors/termbase。
4. 导出：export-clean（Markdown/ZIP）。

### 2.2 关键业务规则

- .naskb 原语：`set_entry`（完整原数据+轻量索引双写,原子）、`move_entry`（先移文件后迁条目）、`remove_entry`（删文件+原子写）、`check` → valid|stale|missing。
- 视频分级：路径/关键词/时长兜底 → metadata_only / keyframes_only / full。
- 术语表：jieba 自定义词典 `termbase-add/list`（关键词通道二期用）。
- CLI 28 个 `desc` 命令与平台共用同一核心（CLI 裸路径 vs API resource_id 边界差异见 design-code-gap）。

### 2.3 与下游的关系

- Job 维度归属 06 域（任务中心）；本章定义 job 的业务内容。
- ER：Resource / FolderEntry / NaskbRepo 元数据（见 03-entity-relationship/data/02-ingestion-analysis.js）。
- API：`{sid}/scan|analyze|adopt` 属来源入口（01 域文件），管线内部无独立 REST（服务端驱动）。

## 三、仍待决策

- ⚠️ 待定：`exts.DOC_EXTS` 与 `document.TEXT_EXTS` 双集合并存（统一性）；老版 .doc/.xls（Word COM / olefile 兜底，MinerU 不支持）。
- ⚠️ 待定：批次进度回传口径（progress/message 语义）。

## 四、来源索引

| 原始文件 | 主要贡献内容 |
|---------|-------------|
| analysis-engine-v2.md | 管线/幂等/并发约束 |
| platform-v3-design.md | 入库链路、folders 表 |
| reorganize-refactor-plan.md | 整理原则与级联（归属 05，本文引用） |
| requirement.md | R1 采集分析需求组 |
