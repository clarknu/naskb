# NASKB 分析引擎 v2 — 目录隐藏仓库 + MinerU 全格式解析

> 版本: v0.1
> 日期: 2026-08-10
> 状态: 已拍板（用户决策）
> 依赖: [requirement.md](./requirement.md), [implementation-plan.md](./implementation-plan.md)
> 变更: **废弃 sidecar 同行机制，全面改目录隐藏仓库 `.naskb/`**

---

## 1. 背景与决策记录

在 [架构文档（2026-08-10 粘贴版）](../../.reasonix/attachments/clipboard-20260810-104227.869972-000001.md) 的"文件自描述"原则（`.sidecar.json` 同行）基础上，经多轮讨论，用户拍板以下变更：

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 描述存储位置 | **废弃 sidecar 同行**，全面改**目录隐藏仓库** `.naskb/`（每 NAS 目录一个） |
| 2 | 隐藏目录命名 | `.naskb/` |
| 3 | 文档描述载体 | 全部统一进 `.naskb/`（index.json），不再用 `.sidecar.json` |
| 4 | 现有 sidecar | 废弃，改造为 `.naskb/` 写入（Phase 1 的 sidecar.py → NaskbStore） |
| 5 | 文档解析 | **MinerU 全格式统一**（PDF/DOCX/PPTX/XLSX），双路径（PyMuPDF 快速 + MinerU 复杂） |
| 6 | MinerU 加速 | DirectML 不支持；AMD 加速仅 Linux ROCm；**Windows+AMD 用 CPU 跑，接受稍慢** |
| 7 | MinerU 产物 | HTML **既给人看也给大模型看**（`extra_formats=["html"]`），md 用于轻量场景，JSON 保留结构 |
| 8 | 文本 LLM | **DeepSeek**（更便宜），OpenAI 兼容协议 |
| 9 | 多模态（图片/音频） | **小米 MiMo V2.5**（`mimo-v2.5`，OpenAI 兼容，key 已内置可用） |
| 10 | 图片识别 | **全部走大模型**（不用纯 OCR）；描述集中进 `.naskb/index.json` 的 files 条目 |
| 11 | 音频转写 | MiMo `input_audio`，ffmpeg 分段（20-30min/段）→ 拼接；说话人分离尽力尝试（config 开关） |
| 12 | 视频分级 | 关键词 + 路径双规则 → `processing_policy`（metadata_only / keyframes_only / full） |
| 13 | 目录级分析 | 代码/软件/发布包目录**不逐文件**，只分析目录结构 → `.naskb/folder.json` |
| 14 | 敏感性 | 不做隐私过滤，统一处理 |

---

## 2. 描述存储：`.naskb/` 目录隐藏仓库

### 2.1 目录结构

```
NAS 任意目录/
├── IMG_001.jpg
├── IMG_002.jpg
├── 合同.pdf
├── 会议录音.m4a
├── 项目代码/                  ← 目录级分析对象（软件/代码/发布包）
│   ├── src/
│   └── README.md
└── .naskb/                    ← 隐藏描述仓库（每目录一个）
    ├── meta.json              ← 仓库元数据（schema 版本/更新时间/模型快照）
    ├── index.json             ← 文件级描述：该目录所有文件的描述索引
    ├── folder.json            ← 目录级描述：目录结构说明（仅软件/代码/项目类）
    └── artifacts/             ← 文档解析产物集中存放
        ├── 合同.pdf.html              ← MinerU HTML（人看 + 大模型看）
        ├── 合同.pdf.middle.json       ← MinerU 版面结构（bbox/类别）
        ├── 合同.pdf.md                ← MinerU Markdown（轻量 LLM 输入）
        └── 合同.pdf.images/           ← MinerU 抽取的图片（送大模型识别）
```

**设计动机**（用户原话要点）：
- 图片量多，逐图旁放描述文件会让目录很乱 → 描述集中到隐藏目录，不进去看感受不到存在
- 打开目录浏览时，工具把 `.naskb/index.json` 内容列出来，展示每个文件的分析结果
- 代码/软件/发布包目录文件五花八门，不需要逐文件识别 → 只分析路径/结构 → folder.json

### 2.2 `meta.json`

```json
{
  "schema": 2,
  "created_at": "2026-08-10T03:15:22Z",
  "updated_at": "2026-08-10T03:15:22Z",
  "analyzer_version": "0.2.0",
  "model_snapshot": {
    "llm_text": "deepseek-chat",
    "llm_vision": "mimo-v2.5",
    "llm_audio": "mimo-v2.5"
  }
}
```

### 2.3 `index.json`（文件级描述）

```json
{
  "schema": 2,
  "updated_at": "2026-08-10T03:15:22Z",
  "files": [
    {
      "path": "IMG_001.jpg",              // 相对 .naskb 所在目录
      "file_hash": "sha256:abc123…",
      "analyzed_at": "2026-08-10T03:15:22Z",
      "analyzer_version": "0.2.0",
      "file_type": "image/jpeg",
      "size_bytes": 4281600,
      "mtime": 1692090000,
      "processing_policy": "full",        // full | metadata_only | keyframes_only
      "analysis": {
        "content_description": "青岛海边日落风景照，沙滩上有行人剪影",
        "category": "相册/按年份/2023/旅行",
        "tags": ["海边", "日落", "旅行", "2023"],
        "summary": "2023年8月青岛海边日落风景照",
        "language": "zh",
        "confidence": 0.92
      },
      "images": [                          // 文档/视频抽取的图（方案 A 集中式）
        {
          "path": "artifacts/合同.pdf.images/img_3.png",
          "description": "系统架构图：3 个模块由箭头串联，数据流从 A 到 B 再到 C",
          "region": "page2-bottom"
        }
      ],
      "transcription": null,               // 音频/视频音轨转写全文
      "ocr_text": null,                    // 文档 OCR 全文（MinerU 文本）
      "exif": {                            // 媒体元数据
        "date_taken": "2023-08-15T18:42:10",
        "camera": "iPhone 14 Pro",
        "gps": {"lat": 36.067, "lng": 120.382}
      },
      "duration_seconds": null,
      "width": 4032, "height": 3024,
      "provenance": {"original_path": "/home/DriveShare/乱七八糟/IMG_1.jpg", "moved_from": []}
    }
  ]
}
```

### 2.4 `folder.json`（目录级描述）

仅当目录被判定为"结构型目录"（代码/软件/发布包/项目）时生成；图片相册类目录不需要。

```json
{
  "schema": 2,
  "updated_at": "2026-08-10T03:15:22Z",
  "description": "公司内部软件发布目录：包含 3 个项目源码、2 个安装包、1 份部署说明",
  "structure": [
    {"name": "charge-admin-web", "type": "dir",  "summary": "计费管理 Web 前端（Vue3）"},
    {"name": "nas-tools",        "type": "dir",  "summary": "NAS 辅助工具集（Python）"},
    {"name": "setup.exe",        "type": "file", "summary": "客户端安装包 v2.3.1"},
    {"name": "README.md",        "type": "file", "summary": "部署说明"}
  ],
  "file_type_distribution": {"py": 128, "js": 342, "exe": 2, "md": 5},
  "tags": ["软件发布", "内部项目"],
  "summary": "公司软件发布与项目源码目录",
  "language": "zh",
  "confidence": 0.88
}
```

**目录级分析流程**：不下载/解析每个文件 → 只统计目录树结构（文件名/扩展名分布/子目录名）→ 交 DeepSeek 生成结构摘要 → 写入 folder.json。LLM 成本 ≈ 1 次调用/目录，极低。

### 2.5 生命周期

```
写入: 分析完成 → 更新 .naskb/index.json（原子写：tmp + rename，目录级文件锁）
校验: 扫描时读 index.json，比对 file_hash → valid 复用 / stale 重分析 / missing 新文件
跟随: 目录内移动 → 只改 index.json 中 path 字段（原子更新）
      跨目录移动 → 旧目录 index.json 删条目 + 新目录 index.json 加条目（顺序执行 + 操作日志）
删除: 删除文件 → 从 index.json 移除条目（不留孤儿）
清理: index.json 有条目但文件不存在 → 孤儿条目，可一键清理
重建: 遍历所有 .naskb/index.json → 重建本地 SQLite + 向量库（无需 LLM）
```

### 2.6 并发与原子性

- `.naskb/index.json` 是目录级单文件 → 写入用**临时文件 + rename**（原子），进程内用**线程锁**串行化
- 超大目录（万级文件）index.json 可达数 MB → 全量读写在可接受范围；若未来超限，按子目录拆分（v3 预留）

### 2.7 与旧机制的关系

| 旧机制 | 处理 |
|--------|------|
| `SidecarStore`（Phase 1 sidecar.py） | **改造为 `NaskbStore`**：读写 `.naskb/index.json`，保留 hash 校验/跟随/孤儿/重建 API 语义 |
| 已写入的 `.sidecar.json` | 提供 `naskb desc migrate` 迁移命令：读取旧 sidecar → 合并进 index.json → 删除旧文件 |
| 现有 `.kbdes/` + `.kbdesc`（DescManager） | **并存读取**（只读兼容旧数据），新写入只走 `.naskb/`；后续版本统一迁移 |
| CLI `naskb sidecar *` | 更名 `naskb desc *`（`check/scan/analyze/move/orphans` 语义保留） |

---

## 3. 文档解析：MinerU 全格式统一（双路径）

### 3.1 流程

```
PDF / DOCX / PPTX / XLSX
        │
        ▼
[快速路径] PyMuPDF / python-docx / openpyxl 直接提取
        │   提取文本量充足（如 >30% 页面有文本）→ 直接用，零成本
        │   提取文本不足（扫描件/复杂版面）→ 升级
        ▼
[复杂路径] MinerU (本地, CPU)
        │   pdf/dir 输入 → 输出:
        │     *.md              ← LLM 轻量输入
        │     *.html            ← 人看 + 大模型看（表格合并/复杂排版完整保留）★
        │     *.middle.json     ← 版面结构（bbox/类别：标题/表格/图片/公式区）
        │     *.images/         ← 抽取的图片
        ▼
图片 → 大模型（MiMo）逐图理解结构（箭头/方块/布局）→ 写入 index.json files[].images
文本 → OCR 全文 → index.json files[].ocr_text
HTML → 完整喂大模型做深度分析（可选开关）
```

### 3.2 关键决策

- **HTML 既给人看也给大模型看**（用户拍板）：Markdown 在表格合并/特殊排版时会丢失结构，导致大模型理解偏差；HTML 保留完整排版。`mineru` CLI/API 的 `extra_formats=["html"]` 直接产出
- **Word/Excel/PPT 原生支持**（已查证）：MinerU 2.x 原生支持 DOCX/PPTX/XLSX 输入，无需先转 PDF；Word 公式（OMML→LaTeX）、表格、图片均可提取。原 python-docx/openpyxl 路径保留为快速路径
- **加速现状**（已查证）：官方仅 CUDA/NPU/MPS 加速；**无 DirectML 支持**；AMD 加速只有 Linux ROCm 社区方案（RDNA2/3/4，vllm 后端）。本机 Windows+AMD → **CPU 跑**，用户已接受

### 3.3 MinerU 集成要点

- 安装：`pip install mineru`（含 torch 依赖，体积大；模型权重首次自动下载 1-3GB）
- 建议参数：
  - `return_middle_json=true`（拿版面结构）
  - `return_content_list=true`（结构化内容列表，喂 LLM 更友好）
  - `extra_formats=["html"]`（HTML 产物）
  - 语言：自动检测（中文为主）
- 任务化：MinerU 单文件耗时长（复杂 PDF 可达分钟级）→ 必须走任务队列（现有 JobQueue），且**串行/低并发**（CPU 资源争抢）

---

## 4. 模型分工（统一配置）

```toml
[llm]
  [llm.text]                    # 文本分类/摘要/标签/JSON
  provider = "deepseek"
  model = "deepseek-chat"
  api_key = "${DEEPSEEK_API_KEY}"

  [llm.vision]                  # 图片理解（MinerU 抽图/独立图片/视频关键帧）
  provider = "mimo"             # OpenAI 兼容多模态
  model = "mimo-v2.5"
  api_key = "${MIMO_API_KEY}"
  base_url = "https://api.xiaomimimo.com/v1"

  [llm.audio]                   # 音频转写（含视频音轨）
  provider = "mimo"
  model = "mimo-v2.5"
  api_key = "${MIMO_API_KEY}"
  base_url = "https://api.xiaomimimo.com/v1"
  split_minutes = 25            # ffmpeg 分段时长
  diarization = false           # 说话人分离（尽力尝试，模型支持则开启）
```

- MiMo key 已内置可用（用户授权）：`sk-cggxgp6s9yn4amnh9o4j0zxnq3khbunjck9mab8vhs92zggc`
  （建议改从环境变量读取，技能中已嵌入）
- DeepSeek 仅文本；图片/音频多模态统一 MiMo（OpenAI 兼容 /v1/chat/completions，`image_url` / `input_audio` 消息类型，现有 `llm.py` 的 OpenAICompatClient 扩展多模态消息即可）

### 4.1 音频转写流程

```
音频/视频音轨
  → ffmpeg 转 16kHz mono wav
  → 按 split_minutes 分段（ffmpeg -f segment）
  → 逐段 MiMo input_audio 转写（串行，避免触发平台风控）
  → 拼接全文 → index.json files[].transcription
  → （diarization=true 时）prompt 要求标注说话人
```

**注意**：多段音频必须严格串行调用同一 key（用户环境已有教训：并行触发平台风控导致 key 冻结 401）。

### 4.2 图片分析流程

```
图片（独立文件 / MinerU 抽图 / 视频关键帧）
  → MiMo image_url 逐张理解（prompt: 描述内容 + 结构：箭头/方块/布局/文字）
  → 独立图片 → index.json files[].analysis
  → 文档抽图 → index.json files[].images[]
  → 内容 hash 去重：同一张图不重复调用
```

---

## 5. 视频分级（完整配置）

### 5.1 判定规则

```
1. 路径规则（最高优先级）: category_paths 命中 → 直接标记
2. 关键词规则: 目录名/文件名命中 category_keywords → 标记
3. 兜底: 时长 > duration_threshold_min → 判为影视（仅元数据）
         其余 → 个人录像（full 处理）
```

### 5.2 配置示例

```toml
[analyzer.video]
# ── 路径规则：路径前缀命中 → 强制标记（优先于关键词）──
category_paths = [
    { category = "媒体/影视",   path = "/XVideo" },
    { category = "媒体/教学视频", path = "/LearnResource" },
]

# ── 关键词规则：目录名/文件名命中任一关键词 → 标记 ──
category_keywords = [
    { category = "媒体/影视/电影", keywords = ["电影", "movie", "BluRay", "1080p"] },
    { category = "媒体/影视/剧集", keywords = ["剧集", "season", "s01", "第1季", "TV"] },
    { category = "媒体/教学视频",  keywords = ["教程", "课程", "教学", "lecture", "course"] },
]

# ── 兜底规则 ──
duration_threshold_min = 90     # 时长 > 90min 且未命中规则 → 判为影视
keyframes_max = 20              # 个人录像抽帧上限（成本控制）
keyframe_interval_sec = 300     # 教学视频抽帧间隔（5 分钟 1 帧）
diarization = false             # 音轨转写是否尝试说话人分离
```

### 5.3 处理策略（sidecar/index.json 的 `processing_policy`）

| policy | 适用 | 处理内容 |
|--------|------|----------|
| `metadata_only` | 电影/剧集/综艺 | 仅 ffprobe 元数据（时长/分辨率/编码/字幕轨），**不解析内容** |
| `keyframes_only` | 教学视频 | 元数据 + 低密度抽帧（interval 间隔）→ 大模型生成课程大纲 |
| `full` | 个人录像/短视频 | 音轨分离 → MiMo 转写 + 场景变化抽帧（≤keyframes_max）→ 大模型识别 → 元数据 |

标记结果写入 index.json（`category` + `processing_policy`），增量扫描时命中已标记类别直接跳过。

---

## 6. 对现有代码的改造清单

### 6.1 Phase 1 存量（已实现，需改造）

| 文件 | 改造 |
|------|------|
| `src/naskb/common/sidecar.py` | → `naskb/common/desc_store.py`：`SidecarStore` → `NaskbStore`（读写 `.naskb/index.json` + `folder.json` + `meta.json`；原子写 + 文件锁；保留 check/move_with_file/find_orphans/rebuild API） |
| `src/naskb/common/analyzer/document.py` | 保留快速路径；新增 MinerU 后端（`analyzer/mineru.py`：调 mineru CLI/Python API → 产物落 `.naskb/artifacts/`） |
| `src/naskb/common/llm.py` | OpenAICompatClient 支持多模态消息（image_url / input_audio）；新增 DeepSeek/MiMo provider 配置别名 |
| `src/naskb/common/config.py` | `[llm.text]/[llm.vision]/[llm.audio]`、`[analyzer.video]`、`[analyzer.mineru]` 配置段 |
| `src/naskb/skill/cli.py` | `sidecar` → `desc` 命令组（check/scan/analyze/move/orphans/migrate） |
| `src/naskb/common/scanner.py` | 排除规则默认加 `.naskb/` 目录 |
| `naskb/pyproject.toml` | 新增 `mineru`、`ffmpeg`（系统依赖）声明 |

### 6.2 Phase 2 新增（本设计覆盖范围）

| 新增 | 说明 |
|------|------|
| `analyzer/image.py` | EXIF + MiMo 视觉描述（独立图片） |
| `analyzer/audio.py` | ffmpeg 分段 + MiMo 转写 + 拼接 |
| `analyzer/video.py` | ffprobe 元数据 + 分级判定 + 音轨分离 + 关键帧抽取 |
| `classifier.py` | 视频分级规则引擎 + LLM 兜底分类 |
| `desc_store.py` | 目录隐藏仓库读写引擎 ★（替代 sidecar.py） |

---

## 7. 风险与缓解

| 风险 | 概率 | 缓解 |
|------|------|------|
| MinerU CPU 慢（复杂 PDF 分钟级） | 高 | 双路径（简单文档不经过 MinerU）；任务队列串行；未来 Linux ROCm 小主机加速 |
| torch 依赖体积大/安装慢 | 中 | MinerU 作为独立 optional extra 安装，不进核心依赖 |
| index.json 目录级并发写冲突 | 中 | 原子写 + 文件锁；进程内串行 |
| MiMo 无说话人分离能力 | 中 | config 开关；验证后不满足则换通义听悟等专用 API |
| MiMo key 并行调用触发风控 | 中 | 音频/图片严格串行（已有教训） |
| 跨目录移动部分失败（旧删新加） | 低 | 操作日志 + 一键回滚（沿用 organizer 设计） |

---

## 8. 实测记录（2026-08-11，MinerU OCR 质量评估）

用户要求实测 MinerU（`.venv-mineru`，3.x pipeline 后端）OCR 质量，评估替代/降级 MiMo 视觉的可行性。结论：**PDF/图片扫描件 OCR 质量优秀，可作 MiMo 的降级方案；docx 直入 CLI 不可用，需走 Python API。**

### 8.1 样本与结果

| 样本 | 类型 | PyMuPDF 快速提取 | MinerU OCR 结果 |
|------|------|------------------|-----------------|
| 花小猪打车行程单.pdf（224 字符文本层） | 扫描件 | 零散乱文本 | 标题/日期/手机号/金额/表格**完整还原**，表格为 HTML 结构 |
| 餐饮发票——茂力.pdf（632 字符乱排版） | 发票 | 竖向拆散乱码 | 发票代码/号码/校验码/金额大写"贰佰捌拾陆圆整"/印章内容全部正确 |
| 医疗扫描记录.docx（0 段落 + 85 内嵌图） | 图片型 docx | 无文本 | CLI 正常（产物在 `office/`，85 张图全抽出）；但 office 后端不做图内 OCR，md 仅为图片引用 |

对比 MiMo 视觉（同一样本）：两者内容一致；MiMo 偶发漏字（"行程人手机号"→"行人手机号"），MinerU 无漏字且免费/本地（1 页约 4 秒）。**结论：PDF/图片扫描件场景 MinerU 可完全替代 MiMo 的"文字识别"职责；但 MinerU 只出文字，不做"图是什么"的语义理解，图片内容理解仍需视觉模型。**

### 8.2 关键事实（避免未来误判）

- **MinerU 3.x CLI `-p` 实测支持 docx**：自动走 office 后端（`office_docx_analyze`），产物在 `<out>/<stem>/office/`（md + middle.json + images/ 全部图片抽出）。日志中的 "No valid PDF or image files to process" 是 office 处理完成、PDF 列表变空后的**无害警告**，产物已生成。
- **产物路径分后端**：PDF → `<out>/<stem>/auto/`；office → `<out>/<stem>/office/`。`analyzer/mineru.py` 的 `_locate_outputs` 已兼容两处。
- **office 后端不做图内文字 OCR**：图片型 docx（扫描件放进 Word）的 md 只有图片引用，图内文字仍需视觉模型（MiMo）——`batch._extract_docx_images`（zip 解 `word/media/` → 逐张 MiMo）是正确路径，MinerU 的 office 产物价值在结构/图片落盘。
- 每任务产物含 `_layout.pdf/_span.pdf/_origin.pdf` 等调试文件，产物体积约为源文件 2-3 倍。

### 8.3 被忽略文件的元数据（2026-08-11 拍板，已实施）

用户拍板：被忽略的文件**不是没有元数据，而是不去分析其元数据，仅记录其可能的内容意义**。

判定规则（最终版，统一入口 `common/exts.py`，batch/cli/scan 共用同一集合）：

| 类别 | 判定 | 处理 |
|------|------|------|
| 支持类型（文档/图片/音频/视频白名单） | `SUPPORTED_EXTS` | 完整分析 |
| 单个被忽略文件（.py/.zip/.exe 等） | 扩展名不在白名单 | `metadata_only` 轻量条目：`可能为{含义}：{文件名}（未分析内容，仅按文件名记录）` |
| 无扩展名知名文件（Dockerfile/Makefile/go.mod/.env/.gitignore） | `FILE_NAME_MEANING` 小写匹配 | 同上（按文件名推断） |
| 整个目录被忽略（有文件但无支持类型） | 目录内 supported==0 | 自动生成 folder.json（目录名+文件名+扩展名分布→DeepSeek 结构摘要）；只对**顶层**被忽略目录生成（node_modules 下子包不逐个生成），祖先链级联更新 |
| 配置排除目录（node_modules 等 `[exclusions].folder`） | 大小写不敏感段匹配 | 不记录文件条目，但生成目录级 folder.json（目录元数据），并计入父级统计时排除 |
| 隐藏目录（.git 等点开头） | 路径段以 `.` 开头 | 完全跳过（无条目、无统计、无 folder.json） |
| 系统垃圾文件（Thumbs.db/.DS_Store/desktop.ini） | `SYSTEM_FILES` 黑名单 | 完全跳过 |
| Office 锁文件（~$xxx.docx） | `~$` 前缀 | 完全跳过 |
| 超过 max_file_mb 的支持类型文件 | 大小 > 上限 | 不下载不分析，记录 `（文件超过 NMB，未下载分析）` 条目 |
| 文件删除 | index.json 有条目但扫描未出现该文件 | 自动清理孤儿条目（批量原子写）+ 该目录及其祖先 folder.json 重算（`BatchResult.orphans_removed`） |

- `desc scan` 报告口径与 analyze-tree 一致：新增 `ignored` 分类（不支持类型），垃圾/锁文件不计入 total。
- `FolderAnalyzer.collect_structure` / `desc analyze-folder --recursive` 同样排除隐藏与排除目录段（folder.json 统计不含依赖库）。
- hash 变更：`compute_hash` 未配置 `desc_hash_max_bytes` 时默认截断前 16MB（WebDAV 大文件避免全量下载；>16MB 文件后段变更不触发重分析，可配置恢复）。
- 单文件命令 `desc analyze` 对不支持类型同样写名称推断条目（与批量行为一致）；`.rtf` 已统一进 `DOC_EXTS`（此前批量支持、单文件不支持）。

### 8.4 待办（未实施）

- 档位 2（图片型 docx → Word 渲染 PDF → MinerU 版面+OCR）依赖本机 Word COM 与 `mineru`；`middle.json` 的版面框（bbox/类别）当前只落盘为 artifact，尚未解析进描述文本。
- MinerU 的 docx/pptx/xlsx office 产物仍可被 `_locate_outputs` 定位，但 analyze-tree 与 `desc analyze` 的 DOC 分支已由 docx 图文流（档位 1）与 Word→PDF→MinerU（档位 2）接管，docx 不再走 office 后端。

### 8.5 docx 版式与图文关系（2026-08-11 实施）

- **档位 1（全量 docx）**：`_docx_flow_items` 解析 `document.xml` 流式结构（段落/表格/图片顺序，inline/浮动锚点，rId→media 映射），零依赖本地毫秒级；图内结构识别用 `IMAGE_STRUCTURE_PROMPT`（图类型/箭头/方框/布局，MiMo 视觉，串行）。图片型 docx 的图文流进 `ocr_text`；有文本层的 docx 正文进 `ocr_text`、图文流进 `content_description`，DeepSeek 摘要输入拼 `正文 + [图文结构] + 图文流`。
- **档位 2（图片型 docx 自动升级）**：无文本层且 Word COM + MinerU 可用 → `_docx_to_pdf`（`SaveAs2` wdFormatPDF=17）渲染 → MinerU `auto/` 路径（版面检测 + OCR 全文）→ OCR 全文进 `ocr_text`、图文流保留在 `content_description`、产物（md/html/middle.json/images）登记 `exif.mineru_artifacts`。
- 通用 MinerU 双路径判定排除 `.docx`（已由档位 1/2 全权处理，避免重复走 office 后端）。

### 8.6 重组规划全量化与归类原则（2026-08-11）

- **前 N 文件截断缺陷修复**：`Reorganizer.collect` 原只取前 400 个文件（按路径排序）喂 LLM，根目录散文件会被漏掉。改为**全量收集 + 分片两阶段**：文件数 ≤ `max_files`（默认 400）走单阶段；超过则按目录聚合为移动单元（目录 + 根散文件）后分片（每片累计文件数 ≤ max_files，片间不重叠），阶段 A 逐片让 LLM 输出归类建议（folder→target），阶段 B 汇总全部归类由 LLM 生成最终方案（new_folders + moves）。所有文件的信息都进入规划。
- **归类原则（CATEGORY_GUIDE）**：证件与身份只放纯证件（身份证/护照/户口/港澳通行证/驾驶证/结婚证/居住证等）；含工作/经营/履历/人才类内容的目录（个体户执照、E类人才、香港高才、工牌、劳动合同、参保证明）整目录归"工作与经营"；学习/财务/房产/医疗/旅行/照片/其他各自独立。
- 特例：`医疗扫描记录.docx`（85 张内嵌扫描图，MiMo 串行识别耗时 30+ 分钟，且拖慢全量分析）按用户指示直接删除，不入逻辑。

### 8.7 迁移完整性与级联更新原则（2026-08-11 定稿）

用户拍板的原则，`Reorganizer` 与 CLI 已全部落实：

1. **整仓跟随**：目录/文件迁移时，`artifacts`（MinerU 产物）、`folder.json`、`meta.json` 等全部连带迁移（`_move_dir` 整仓跟随；index.json 保留目标——新条目已写入）。源 `.naskb` 空壳移除（仅本地）。
2. **目录级联更新**：任何移动/增删后，源、目标及上层目录的 `folder.json` 必须同步重算——`plan-reorganize --apply` 后自动 `_refresh_folders`（受影响目录 + 祖先链到 root）；单文件 `desc analyze` 写条目后向上级联（到无仓库目录为止）；批量 `analyze-tree` 已有 written_dirs → 祖先级联。
3. **空目录删除**：目录搬空（树内无任何文件）后自动删除（`_remove_empty_chain`，只删空目录树，绝不删有文件的；驱动器根处停止）。
4. **增量更新**：`analyze-tree` 按文件名 + 内容 hash 对比——一致跳过、不一致重分析（新增/修改/删除均覆盖，删除走孤儿清理 + 目录级联）。沙盒验证：改 1 增 1 删 1 后重跑 → 新分析 2、跳过 1、孤儿 1。
5. 原则下旧位置 18 个空目录已清理；根目录仅剩 9 个顶层分类。

### 8.8 Skill 化重构与 v1 清理（2026-08-11）

用户拍板：NASKB 定位为 **Reasonix Skill**（AI 可调用的 playbook + 代码 + AI 编排），而非传统软件。结构：

```
naskb/                          ← Skill 根
├── SKILL.md                    ← AI 入口（playbook）
├── DEPLOY.md
└── scripts/naskb/              ← 代码（确定性层 common/ + AI 编排层 analyzer/ + cli）
```

pyproject `where=["naskb/scripts"]`（editable 安装）。

- **删除全部 v1 遗留**：`src/naskb/mcp/`（MCP 服务）、`skill/skill_tools.py`/`indexer.py`、`common/` 的 scanner/sources/embedder/vector_store/state/bootstrap/model_manager、`sidecar.py` 的 `SidecarStore`（保留数据类供 desc migrate）、v1 测试 4 个（test_mcp_*/test_sidecar）、`naskb/SKILL.md`/`MCP.md`/`mcp.json`（SKILL.md 按新设计重建）、`.vscode/mcp.json`、`models/`（bge 向量模型）、pyproject 的 lancedb/onnxruntime/mcp 依赖与 `naskb-mcp` 入口。
- **CLI 精简**：删除顶层 v1 命令（init/source/index/search/status/missing/model/config，其中 config 有坏引用 `__import__("naskb.config")`），只留 `desc` 命令组。
- **结构迁移**：`src/naskb` → `scripts/naskb`（pyproject `where=["scripts"]`），`src/naskb` → `scripts/naskb`。
- 验证：164 passed, 1 skipped；`naskb desc` 全命令可用。

### 8.9 语义向量检索恢复（2026-08-11）

用户拍板恢复向量 RAG（v2 原 BM25 为关键词检索，同义表述召回差）。实现轻量方案（不引入 LanceDB）：

- **嵌入**：`Xenova/bge-small-zh-v1.5` ONNX int8（~24MB，首次自动下载到工作区 `models/bge-small-zh-v1.5/`），`onnxruntime` CPU 推理 + `tokenizers` 分词，CLS 池化 + L2 归一化（`common/embeddings.py`，无 torch/transformers）。
- **索引**：`common/vector_index.py`——numpy 余弦暴力检索（数据量级毫秒），持久化工作区 `db/vectors.npz` + `vectors.json`；与 `BM25Index.search` 输出同构（score/path/kind/summary/category/tags/text），RAG（`retrieval.ask`）无需改动即可切换索引。
- **命令**：新增 `desc index-vectors <root>`；`desc search`/`desc ask` 加 `--vector/--no-vector`（默认 auto：有向量索引用向量，无则 BM25 降级）。
- 实测：HomeBuilding 2165 条描述建索引；"出行要带的证件" 语义召回港澳通行证/护照（BM25 返回混杂结果）；`desc ask` RAG 回答带来源。
- 依赖：`vectors = ["onnxruntime>=1.18", "tokenizers>=0.15"]` 可选组。
