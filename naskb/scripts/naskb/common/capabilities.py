"""能力注册表（单一事实源）：MCP 工具从这里注册。

每个能力定义一次（名称/描述/类型/权限/是否长任务），handler 为
服务对象（naskb.mcp.server.NasKbService）上的同名方法。
阶段 C 的 function-calling schema 导出与 REST 适配从本表生成。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    kind: str         # read | write | plan | apply | admin
    scope: str        # read | write | admin（Phase B 认证用）
    job: bool = False  # 长任务（返回 job_id）


CAPABILITIES: list[Capability] = [
    # ── A 组：检索与问答（read，同步）──
    Capability("kb_search",
               "语义检索知识库（向量 → BM25 自动降级；nas 指定时走 PG 向量库）。"
               "返回命中文件的路径/摘要/分类/标签/分数。",
               "read", "read"),
    Capability("kb_ask",
               "RAG 问答：召回 top-k 后由 DeepSeek 生成回答，带来源路径。",
               "read", "read"),
    Capability("kb_get_doc",
               "取单文件完整元数据（摘要/分类/标签/EXIF/转录/OCR；"
               "include_fulltext=true 才带全文）。",
               "read", "read"),
    Capability("kb_fetch_file",
               "取原始资源内容（base64，≤8MB；大文件请直接访问 NAS 或用 kb_get_doc）。",
               "read", "read"),
    # ── B 组：入库与索引（write，job 模式）──
    Capability("kb_ingest",
               "增量幂等批量分析目录树（hash 对比跳过已分析，可反复调用）。"
               "长任务：返回 job_id，用 kb_job_status 查询。",
               "write", "write", job=True),
    Capability("kb_sync_vectors",
               "把 .naskb 描述同步进 PG 多 NAS 向量库（增量：增/改/删/移）。"
               "长任务。",
               "write", "write", job=True),
    Capability("kb_index_vectors",
               "构建本地语义向量索引（bge-small-zh 嵌入全部描述，首次较慢）。"
               "长任务。",
               "write", "write", job=True),
    Capability("kb_job_status",
               "查询长任务进度（进度 0~1/阶段消息/结果/错误）。",
               "read", "read"),
    Capability("kb_list_jobs",
               "列出长任务（可按状态过滤）。",
               "read", "read"),
    # ── C 组：整理与重组（plan → apply 两段式）──
    Capability("kb_plan_reorganize",
               "AI 生成目录重组方案并持久化，返回 plan_id（只规划不移动；"
               "越界/幻觉路径自动过滤）。长任务。",
               "plan", "write", job=True),
    Capability("kb_preview_reorganize",
               "对已生成方案 dry-run：逐条判定 move/noop/meta_only/rename/"
               "conflict/越界/过期，不移动任何文件。",
               "read", "read"),
    Capability("kb_apply_reorganize",
               "执行方案（凭 plan_id；服务端复校验：越界拦截/快照复检/冲突"
               "三档；整理后自动同步本地索引与 PG）。长任务。",
               "apply", "admin", job=True),
    # ── D 组：管理与状态 ──
    Capability("kb_status",
               "知识库一致性报告（valid/stale/missing + PG 差异，只读）。",
               "read", "read"),
    Capability("kb_stats",
               "全局状态：引擎/文档数/向量索引状态/PG 注册 NAS。",
               "read", "read"),
]
