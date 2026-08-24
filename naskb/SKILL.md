---
name: naskb
description: >
  智能 NAS 知识库（v2）：对本地目录或 NAS（WebDAV）建立 .naskb 描述仓库——
  AI 分类/摘要/标签、图片音频视频识别、PDF/DOCX 扫描件 OCR、目录重组规划。
  AI 通过本 Skill 调用 naskb CLI 完成"扫描-分析-检索-整理-更新"闭环。
tools:
  - naskb
applyTo: "*"
---

# NASKB — 智能 NAS 知识库（Skill）

## 定位

不是传统软件，而是一个 **AI 可调用的 Skill**：确定性操作（抽取/入库/检索/移动）由代码实现，柔性判断（分类、摘要、重组方案、目录描述）由代码把现状与要求组织给 AI（DeepSeek 文本 / MiMo 多模态），AI 反馈后代码执行落地。

## AI 触发方式（自然语言 → 命令）

| 用户意图 | 命令 |
|---|---|
| 分析整个目录/库 | `naskb desc analyze-tree <root> --llm --workers 6`（增量幂等，可反复跑） |
| 分析单个文件 | `naskb desc analyze <file>` |
| 看还有哪些没描述 | `naskb desc scan <root>` |
| 构建语义向量索引 | `naskb desc index-vectors <root>`（bge-small-zh 本地嵌入，首次自动下载 ~24MB 模型） |
| 检索文件 | `naskb desc search "关键词"`（有向量索引 → 语义检索；无 → BM25 自动降级；`--no-vector` 强制 BM25；`--pg` 走 PG 多 NAS 向量库，加 `--hybrid` 为向量+关键词 RRF 混合检索） |
| 问答（RAG） | `naskb desc ask "问题"`（语义/BM25 召回 top-k → DeepSeek 生成，带来源） |
| 内部问答服务 | `naskb desc serve [--host 127.0.0.1 --port 8765 --open]`（Web UI + `/api/search` `/api/ask`，见下） |
| 同步 PG 向量库 | `naskb desc sync-vectors <root> [--nas <alias>] [--rebuild]`（.naskb → PG 多 NAS 独立 schema，增/改/删/移增量；未配 `[pg]` 自动跳过） |
| 同步条款级 chunk 行 | `naskb desc sync-chunks <root> [--nas <alias>]`（深析目录 MinerU md 分段成 chunk 向量行；需 `[deep].enabled`，REQ-R5-06） |
| 导出干净文本 | `naskb desc export-clean <out_dir> [--zip]`（.naskb 分析产物 → 干净 Markdown/ZIP，供外部引擎，REQ-R5-02） |
| 术语表管理 | `naskb desc termbase-add <词>... [--nas]` / `naskb desc termbase-list [--nas]`（jieba 自定义词典，关键词通道二期用） |
| PG 一致性报告 | `naskb desc sync-status <root> [--nas]`（只读差异清单）/ `naskb desc pg-status`（已注册 NAS 向量库统计） |
| 目录整理规划 | `naskb desc plan-reorganize <root>`（DeepSeek 出方案，只输出不动） |
| 执行整理 | 确认方案后 `naskb desc plan-reorganize <root> --apply` |
| 更新（手工增删改后） | `naskb desc analyze-tree <root> --llm`（hash 对比：一致跳过/变更重分析/删除清孤儿） |
| 目录级描述刷新 | `naskb desc analyze-folder <root> --recursive` |

NAS 场景：`naskb desc --webdav-url <url> [--webdav-user <u> --webdav-pass <p>] analyze-tree /path`（config.toml 配好 [webdav] 后可省略）。

### 挂载式接入（SMB/NFS/iSCSI，R7-04 收口）

- **一律走「OS 挂载 → 注册 local 源」**：Windows `net use Z: \\server\share /user:u p` / Linux `mount -t cifs //srv/share /mnt/nas`（NFS/iSCSI 同理），随后平台「来源」页注册 local 源（root=挂载点）→ 扫描 → AI 分析，与本地目录同权。详见 README「知识源接入」节。
- **应用层 SMB 直连**为可选未启用：代码桩在 `common/fs/base.py`（fsspec[smb]）与 `source_registry.PROTOCOLS`，不暴露到 API/UI、未测试；需要「免映射部署/凭据入 config/抗盘符掉线」时再启用。

## 工作原理

1. **存储**：每个目录一个 `.naskb/` 隐藏仓库 = `index.json`（文件级条目）+ `files/`（详情）+ `folder.json`（目录级描述）+ `artifacts/`（MinerU 产物）。
2. **分析编排**：文档（python-docx/PyMuPDF 快速提取 → 文本不足走 MinerU OCR；docx 内嵌图片走 XML 图文流 + MiMo 结构识别）→ DeepSeek 分类/摘要/标签（并发 4-6）；图片/音频走 MiMo（严格串行）；视频分级（路径/关键词/时长）。
3. **整理原则**（AI 执行 plan-reorganize --apply 时代码自动保证）：
   - 移动不删除；`.naskb` 整仓跟随（artifacts/folder/meta 随迁，index 保留目标）；
   - 源/目标/上层 folder.json 自动级联更新；
   - 搬空的源目录自动删除（只删空目录树）；
   - 子路径先移（防"先移整目录后抽子目录"失败）。
4. **检索**：`desc search` / `desc ask` 默认语义向量检索（bge-small-zh ONNX 本地嵌入 + numpy 余弦，索引存工作区 `db/vectors.npz`），无索引自动降级 BM25 关键词检索。**检索索引只用文件的摘要+描述（用户拍板：全文不参与向量/关键词检索，避免高频词稀释主题）；全文（ocr_text 等）保留为元数据，仅在 RAG 生成阶段作为上下文**。两者输出同构，RAG（`desc ask`）召回 top-k → DeepSeek 生成带来源回答。
5. **模型分工**：DeepSeek（文本分类/摘要/方案）并发；MiMo（图片/音频）严格串行（并行会触发平台风控冻结 key）；MinerU（扫描件 OCR）严格串行；401 时停止重试，提示检查 key。

## 内置问答服务（desc serve）

`naskb desc serve` 启动本地 Web 服务（标准库实现，零依赖），浏览器访问即用：

- **Web UI**：搜索（top-10 结果 + 摘要/标签）+ 问答（DeepSeek RAG，带来源）；`--open` 自动开浏览器，局域网用 `--host 0.0.0.0`。
- **接口**（未来 MaxKB 扩展包实现同一契约即可切换后端，换实现不换接口）：
  - `GET /api/search?q=<query>&top_k=10` → `{engine, hits, total_docs}`
  - `POST /api/ask {"question": ..., "top_k": 5}` → `{answer, sources, engine}`
  - `POST /api/reload`（analyze 之后热刷新描述数据）
  - `GET /api/stats`（引擎/文档数/向量索引状态）
- **引擎选择**：有向量索引且与当前文档集合一致 → 向量；否则 BM25 兜底（索引陈旧会提示重跑 `desc index-vectors`）。
- 多根目录：`--root` 可多次传入（如本地目录 + NAS 挂载点各自含 .naskb）。
- 建议以计划任务/开机自启常驻，本机收藏页面日常使用。

## 配置（工作区 config.toml）

- `[llm.text]` DeepSeek：分类/摘要/标签/重组方案
- `[llm.vision]` / `[llm.audio]` MiMo：图片识别/音频转写
- `[analyzer.mineru]`：扫描件 OCR（本机 CPU，MINERU_MODEL_SOURCE=modelscope）
- `[webdav]`：NAS 连接（verify_ssl=false 群晖自签）

## 深度分析（条款级，REQ-R5-06）

对**标准/规范/研发类文档**、需要条款级精细问答（如"6.3.2 条怎么规定""表 4 耐压要求"）的场景：

- 职责：文件发现级摘要检索仍是默认；深度分析在 `[deep].roots` 圈定的目录上叠加**条款级第二层**——MinerU 结构化 Markdown 按标题层级分段成 chunk 向量行（`vectors.level='chunk'`），问答可引用到「文件 + 章节」两级。
- 启用：config.toml 设 `[deep].enabled=true` 并设置 `roots`；先 `desc sync-vectors`（建摘要行/资源）再 `desc sync-chunks`（建 chunk 行）。只读源（无持久 md）会回退全文分段（已知缺口）。
- **系统级（推荐）**：平台「来源」页给来源开「深度分析」（`SourceRecord.deep`），该来源的扫描/分析/定时会自动按标题层级建条款级 chunk 行（只读源用暂存 md，不留存）；来源页可查看「变更」确认清单（新增/变更/消失），勾选后「确认同步并分析」（`/api/sources/{id}/changes`、`/confirm`）。
- 检索/问答：`desc search`/`desc ask` 走文档级；平台 `POST /api/kb/ask` 走条款级（两级引用 + 保真直返 + 无命中兜底）。保真直返：命中相似度 ≥ `direct_return_similarity` 直接返回条款原文不调 LLM（防改写）。无命中默认"未找到依据"（诚实性）。
- 参数（`[deep]`）：`target_chars`/`limit_chars`/`overlap_ratio` 分段；`direct_return`/`direct_return_similarity` 直返；`no_hit_mode`（designated|llm_fallback）；`max_context_chars`；`top_n`/`min_score`。
- 法律纪律：设计学习自开源项目（只读源码），实现零拷贝（REQ-R6-07）。

## 常用流程示例

```powershell
# 1) 全量分析（增量幂等，可中断重跑）
naskb desc analyze-tree C:\Temp\home --llm --workers 6

# 2) 检查覆盖
naskb desc scan C:\Temp\home

# 3) 整理规划（只看方案）
naskb desc plan-reorganize C:\Temp\home

# 4) 确认后执行（自动迁移元数据 + 级联更新 + 清空目录）
naskb desc plan-reorganize C:\Temp\home --apply
```
