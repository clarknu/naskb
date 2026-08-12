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
| 检索文件 | `naskb desc search "关键词"`（有向量索引 → 语义检索；无 → BM25 自动降级；`--no-vector` 强制 BM25） |
| 问答（RAG） | `naskb desc ask "问题"`（语义/BM25 召回 top-k → DeepSeek 生成，带来源） |
| 目录整理规划 | `naskb desc plan-reorganize <root>`（DeepSeek 出方案，只输出不动） |
| 执行整理 | 确认方案后 `naskb desc plan-reorganize <root> --apply` |
| 更新（手工增删改后） | `naskb desc analyze-tree <root> --llm`（hash 对比：一致跳过/变更重分析/删除清孤儿） |
| 目录级描述刷新 | `naskb desc analyze-folder <root> --recursive` |

NAS 场景：`naskb desc --webdav-url <url> [--webdav-user <u> --webdav-pass <p>] analyze-tree /path`（config.toml 配好 [webdav] 后可省略）。

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

## 配置（工作区 config.toml）

- `[llm.text]` DeepSeek：分类/摘要/标签/重组方案
- `[llm.vision]` / `[llm.audio]` MiMo：图片识别/音频转写
- `[analyzer.mineru]`：扫描件 OCR（本机 CPU，MINERU_MODEL_SOURCE=modelscope）
- `[webdav]`：NAS 连接（verify_ssl=false 群晖自签）

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
