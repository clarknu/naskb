# 全局设计决策（跨领域）

> 文档 ID: REQ-global | 最后更新：2026-08-24 | 从 14 个存量设计文档整合（original-logs/）
> 本文档为整合后的当前设计结论。原始讨论记录见 `original-logs/`。
> 编号沿用项目既有 REQ-R{x}-{nn} / ADR-{date}-{n} 体系（追溯锚点稳定性优先）。

## 一、核心决策

> **[ADR-20260818-1]** 平台化重定位：工具 → 自持知识的知识库系统（v0.1 平台版）。八项拍板：FastAPI；Vue3+Vite 静态包（运行时零 Node）；中间产物不入库（store/tmp 即清）；单管理员 Bearer；rw 源双写、源端 .naskb 为原始仲裁端；folder 入独立 folders 表；resources.source_id 区分多来源；v0.1 重新起版。

> **[REQ-R6]** 非功能：UTF-8 全链路（Windows 控制台 GBK 需显式处理）、密钥不入库、模型风控（MiMo 严格串行防冻结 key）、NO_PROXY 支持、自包含部署（拷贝 naskb/ + workdir 即可）、开源纪律（零拷贝）。

> **[REQ-R6-07]** 法律纪律：设计学习自开源项目（只读源码），实现零拷贝；自部署/HTTP 调用/改源码自用安全，仅"抄源码入库再分发"违规（GPL 红线=是否分发+是否衍生作品）。

> **[REQ-R2]** 检索索引只用文件的摘要+描述（用户拍板：全文不参与向量/关键词检索，避免高频词稀释主题）；全文（ocr_text 等）保留为元数据，仅 RAG 生成阶段作为上下文。既有拍板，反向补全时保持（DD-007）。

> **[ADR-20260811-1]** 向量检索采用本地嵌入（bge-small-zh-v1.5 ONNX，512 维）+ numpy 余弦；重型向量库（LanceDB 等）不引入。

> **[ADR-20260816-1/2/3]** MaxKB 分期（远期可插拔深度引擎）；API 契约恒定（`/api/search` `/api/ask` 为后端抽象边界，换实现不换接口）；多 NAS 向量库设计（R4）。

> **[ADR-20260816-4]** 指纹体系：ctime + mtime + size + 8×64KB 采样 hash（start_i = i*(S-65536)//7）五元组；三级判定链 L1 免检（path+size+mtime+ctime）→ L2 采样 hash → L3 重析。

> **[ADR-20260823-1]** 深度分析主线 = 自研 chunk 级检索增强（D'，REQ-R5-06），不搬 MaxKB 代码、不买专业版；MaxKB 社区版/RAGFlow/FastGPT 仅作远期可插拔深度引擎（路线 A，Backend B 同契约）。

> **[R7-13]** PG 用宿主化独立实例（如 192.168.5.2:25432），不在业务进程/容器内自建（全局部署原则变体）。

> **[中间产物不入库]** .naskb 之外的中间产物（临时 md、缩略图源件）存 store/tmp 即清；知识主库 = PG（可重建，派生根），源端 .naskb（rw 源）= 原始仲裁端。

> **[四出口同源]** MCP / REST / CLI+Skill / function schema 四出口共用同一定义（common/capabilities.py 为工具清单单一事实源）。

## 二、详细设计

### 2.1 演进史（只读参考，选型不采信）

- v0.2 工具形态（LanceDB/bge-large/fsspec 选型、sidecar v1）已在 `requirement-v0.2-archived.md`，已过时。
- v2 描述仓库（.naskb + MinerU + DeepSeek/MiMo 分工）仍在役（CLI 形态）。
- 多份专题文档（pg-vector-multi-nas、implementation-plan）含大量已被 v3 承接/替换的选型（LanceDB/DirectML/bge-large/sidecar），仅作历史。

### 2.2 复杂度与部署形态

- 单进程模块化单体（FastAPI + 进程内 JobManager + daemon 调度线程），复杂度判定 L3（外部 LLM 依赖 + 异步任务 + 6 域，见 design/05-backend-architecture/data/system-topology.js）。
- 部署：本机/内网 `python run.py`；可选项：外置 PG 实例（独立 schema 多 NAS 向量库）、MCP（stdio）供外部 Agent。

## 三、仍待决策

- ⚠️ 待定：R5-01/03/04/07（外部深度引擎/Backend B/分级检索/兜底）规划中未实现；R5-05 混合检索（草案）；R7-01 MCP 出口（部分）；R7-04 SMB/NFS/iSCSI（SMB 直连 V2 规划）；R7-15 二级知识库；多用户/角色（单管理员为现状）。
- ⚠️ 待定：`GET /api/sources/{sid}/report` 装饰器未生效（代码死点）、`/api/folder` 孤儿匿名前缀、`/api/jobs` 匿名口径不一致、多 token 仅首个有效等——列入 design/review/design-code-gap.md 待 review 仲裁。
- ⚠️ 待定：MinerU 不支持 .doc/.xls（老格式兜底策略）；Office 预览 V1"提示下载"与 V2"零依赖简版"表述差异。

## 四、来源索引

| 原始文件 | 主要贡献内容 |
|---------|-------------|
| requirement.md | R1~R7 需求编码体系与全部锚点 |
| platform-v3-design.md | ADR-20260818-1 拍板、来源模型、实体设计 |
| mcp-kb-design.md / mcp-tech-reassessment.md | MCP 六原则、四出口同源、工具清单 |
| analysis-engine-v2.md | 分析管线/幂等/并发 |
| pg-vector-multi-nas.md | R4 多 NAS 向量库（过时点已标注） |
| deep-analysis-roadmap.md / chunk-retrieval-design.md / deep-ingestion-system-flow.md | D' 深度分析链路与自研拍板 |
| reorganize-refactor-plan.md | 整理重组规则 |
| agent-interface-design.md | 四出口同源 |
| implementation-plan.md | 阶段划分（历史） |
| maxkb-integration-analysis.md | 远期路线 A 与许可结论 |
| requirement-v0.2-archived.md | v0.2 选型（历史） |
