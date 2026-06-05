"""MCP Tool 函数实现。

所有以 kb_ 为前缀的函数将被注册为 MCP Tools。
每个工具返回 str 类型的结果。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..common.config import Config


def _run_async(coro):
    """安全地运行异步协程，兼容独立运行和 pytest-asyncio。"""
    import asyncio
    import concurrent.futures
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 无运行中的循环 → 直接 asyncio.run
        return asyncio.run(coro)
    # 有运行中的循环（pytest-asyncio 等）→ 在新线程中创建独立循环
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=60)


def _get_work_path() -> str:
    return os.environ.get("NASKB_WORK", str(Path.home() / "NASKB_data"))


def _init_components(work_path: str):
    """初始化所有核心组件。"""
    from ..common.config import Config
    from ..common.embedder import Embedder, MicroBatchEncoder
    from ..common.model_manager import ModelManager
    from ..common.sources import SourceManager
    from ..common.state import StateManager
    from ..common.vector_store import VectorStore
    from ..mcp.async_indexer import AsyncIndexer
    from ..mcp.job_queue import JobQueue
    from ..mcp.watcher import FileWatcher

    config = Config.from_work_path(work_path)
    model_path, tokenizer_path = ModelManager.ensure_model(
        work_path, config.model_name, hf_endpoint=config.hf_endpoint
    )
    embedder = Embedder(
        model_path, tokenizer_path, config.execution_provider,
        intra_op_threads=config.intra_op_threads,
        inter_op_threads=config.inter_op_threads,
    )
    vector_store = VectorStore(
        config.db_path, config.model_dim,
        index_type=config.index_type,
        index_auto_threshold=config.index_auto_threshold,
        index_num_partitions=config.index_num_partitions,
        index_num_sub_vectors=config.index_num_sub_vectors,
        index_ef_construction=config.index_ef_construction,
        index_m=config.index_m,
        index_metric=config.index_metric,
    )
    state = StateManager(config.state_path)
    source_manager = SourceManager(config)

    # 微批处理编码器（用于实时查询场景）
    micro_encoder = MicroBatchEncoder(
        embedder,
        max_batch=config.mb_max_batch,
        max_wait_ms=config.mb_max_wait_ms,
        cache_size=config.mb_cache_size,
    )

    async_indexer = AsyncIndexer(config, embedder, vector_store, state,
                                 source_manager, micro_encoder=micro_encoder)
    job_queue = JobQueue()
    watcher = FileWatcher(job_queue)

    return {
        "config": config,
        "embedder": embedder,
        "micro_encoder": micro_encoder,
        "vector_store": vector_store,
        "state": state,
        "source_manager": source_manager,
        "async_indexer": async_indexer,
        "job_queue": job_queue,
        "watcher": watcher,
    }


# ── 全局组件缓存 ──
_components: dict = {}
_work_path: str = ""


def get_components(work_path: str = "") -> dict:
    """获取或初始化全局组件。"""
    global _components, _work_path
    wp = work_path or _get_work_path()
    if not _components or wp != _work_path:
        _work_path = wp
        _components = _init_components(wp)
    return _components


# ═══════════════════════════════════════════════════════════════════
# 搜索
# ═══════════════════════════════════════════════════════════════════

def kb_search(query: str, top_k: int = 10, threshold: float = 0.5,
              source_id: str | None = None) -> str:
    """语义检索知识库。

    使用自然语言查询本地知识库中的文件内容，
    返回语义相关度最高的文件列表及其摘要。

    Args:
        query: 自然语言查询，支持中文和英文
        top_k: 返回结果条数上限 (1-100)
        threshold: 相似度阈值 (0.0-1.0)，越高越严格
        source_id: 限定搜索的知识来源ID，不指定则搜索全部

    Returns:
        格式化的搜索结果文本
    """
    import asyncio
    comp = get_components()
    async_indexer = comp["async_indexer"]

    async def _search():
        return await async_indexer.search(query, top_k=top_k,
                                          threshold=threshold,
                                          source_id=source_id)

    try:
        results = _run_async(_search())
    except Exception as e:
        return f"搜索失败: {e}"

    if not results:
        return "未找到相关结果。建议：\n- 尝试更通用的关键词\n- 降低 threshold 阈值\n- 确认知识库已完成索引"

    lines = [f"找到 {len(results)} 条相关结果：\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r.score:.2f}] **{r.name}**")
        lines.append(f"   路径: `{r.path}`")
        if r.orig_file:
            lines.append(f"   原始文件: `{r.orig_file}`")
        if r.snippet:
            lines.append(f"   摘要: {r.snippet[:300]}")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# 索引
# ═══════════════════════════════════════════════════════════════════

def kb_index_full(source_ids: list[str] | None = None,
                  force: bool = False) -> str:
    """全量重建知识库索引。

    扫描所有知识来源的全部文件，清除旧索引后重建。
    适用于首次索引或索引结构变更后的完全重建。

    Args:
        source_ids: 限定重建的知识来源ID列表，不指定则重建全部
        force: 是否强制清除旧索引（否则做增量合并）

    Returns:
        索引完成统计
    """
    import asyncio
    comp = get_components()
    async_indexer = comp["async_indexer"]

    async def _run():
        return await async_indexer.index_full(source_ids, force=force)

    try:
        stats = _run_async(_run())
    except Exception as e:
        return f"全量索引失败: {e}"

    lines = [
        "**全量索引完成**",
        f"- 处理来源数: {len(stats.get('sources', {}))}",
        f"- 扫描文件总数: {stats.get('total_files', 0)}",
        f"- 成功索引: {stats.get('total_indexed', 0)}",
    ]
    return "\n".join(lines)


def kb_index_incremental(source_ids: list[str] | None = None) -> str:
    """增量更新知识库索引。

    仅处理新增或已变更的文件，跳过未变动的文件。
    适合日常维护和快速同步。

    Args:
        source_ids: 限定更新的知识来源ID列表，不指定则更新全部

    Returns:
        增量索引结果
    """
    import asyncio
    comp = get_components()
    async_indexer = comp["async_indexer"]

    async def _run():
        return await async_indexer.index_incremental(source_ids)

    try:
        stats = _run_async(_run())
    except Exception as e:
        return f"增量索引失败: {e}"

    lines = [
        "**增量索引完成**",
        f"- 更新文件数: {stats.get('total_updated', 0)}",
    ]
    if stats.get('total_desc_updated', 0) > 0:
        lines.append(f"- 描述文件更新: {stats['total_desc_updated']}")
    return "\n".join(lines)


def kb_index_file(source_id: str, file_path: str) -> str:
    """索引单个文件。

    支持文本文件和带 .kbdesc 描述文件的媒体文件。
    如果是媒体文件且无描述文件，将提示需先创建描述。

    Args:
        source_id: 知识来源ID
        file_path: 文件的绝对路径

    Returns:
        索引结果
    """
    import asyncio
    comp = get_components()
    async_indexer = comp["async_indexer"]

    async def _run():
        return await async_indexer.index_file(source_id, file_path)

    try:
        result = _run_async(_run())
    except Exception as e:
        return f"文件索引失败: {e}"

    if result.get("success"):
        return (f"文件索引成功。\n"
                f"- 类型: {result.get('type', 'unknown')}\n"
                f"- 路径: `{result.get('path', file_path)}`")
    else:
        error = result.get("error", "未知错误")
        if result.get("missing_desc"):
            return (f"文件无法索引：缺少 .kbdesc 描述文件。\n"
                    f"请使用 kb_describe_media 为媒体文件添加描述。\n"
                    f"- 路径: `{file_path}`\n"
                    f"- 错误: {error}")
        elif result.get("stale"):
            return (f"描述文件已过期：{error}\n"
                    f"请重新使用 kb_describe_media 更新描述。\n"
                    f"- 路径: `{file_path}`")
        else:
            return f"文件索引失败: {error}"


# ═══════════════════════════════════════════════════════════════════
# 状态
# ═══════════════════════════════════════════════════════════════════

def kb_status(source_id: str | None = None) -> str:
    """获取知识库状态报告。

    返回索引进度、文件统计、模型信息等。

    Args:
        source_id: 限定查询的知识来源ID，不指定则汇总全部

    Returns:
        格式化的状态报告
    """
    comp = get_components()
    config = comp["config"]
    state = comp["state"]
    vector_store = comp["vector_store"]
    job_queue = comp["job_queue"]

    stats = state.get_stats()
    job_stats = job_queue.get_stats()

    index_info = vector_store.get_index_info()
    micro_stats = comp.get("micro_encoder", None)
    mb_stats = micro_stats.get_stats() if micro_stats else {}

    lines = [
        "# NASKB MCP 状态报告",
        "",
        "## 基本信息",
        f"- 模型: {config.model_name} ({config.model_dim}维)",
        f"- 推理后端: {config.execution_provider}",
        f"- 工作路径: `{config.work_path}`",
        f"- 向量库路径: `{config.db_path}`",
        "",
        "## 索引配置",
        f"- 索引类型: {index_info['type']}",
        f"- 距离度量: {index_info['metric']}",
        f"- 自动索引阈值: {index_info['auto_threshold']:,}",
        f"- 当前记录数: {index_info['record_count']:,}",
        "",
        "## 微批处理",
        f"- 最大批量: {config.mb_max_batch}",
        f"- 最大等待: {config.mb_max_wait_ms}ms",
        f"- 缓存容量: {config.mb_cache_size:,}",
        f"- 缓存命中率: {mb_stats.get('cache_hit_rate', 0)*100:.1f}%",
        "",
        "## 索引统计",
        f"- 已索引文件: {vector_store.count('files')}",
        f"- 已索引文件夹: {vector_store.count('folders')}",
        f"- 索引状态: 已索引 {stats.get('indexed', 0)} | "
        f"待更新 {stats.get('outdated', 0)} | "
        f"缺失描述 {stats.get('missing_desc', 0)} | "
        f"已跳过 {stats.get('skipped', 0)}",
        "",
        "## 来源列表",
    ]

    from ..common.sources import SourceManager
    sources = comp["source_manager"].get_sources()
    for s in sources:
        status_icon = "✓" if s.enabled else "✗"
        lines.append(f"- [{status_icon}] `{s.id}`: {s.name} ({s.fs_type}) → {s.root_url}")

    lines.append("")
    lines.append("## 后台任务")

    if job_stats["total"] > 0:
        lines.append(f"- 待处理: {job_stats['pending']} | "
                     f"运行中: {job_stats['running']} | "
                     f"已完成: {job_stats['completed']} | "
                     f"失败: {job_stats['failed']}")
    else:
        lines.append("- 无活跃后台任务")

    return "\n".join(lines)


def kb_list_sources() -> str:
    """列出所有知识来源。

    Returns:
        知识来源列表
    """
    comp = get_components()

    sources = comp["source_manager"].get_sources()
    if not sources:
        return "暂无已配置的知识来源。使用 kb_add_source 添加。"

    lines = ["**知识来源列表**\n"]
    for i, s in enumerate(sources, 1):
        status = "✓ 启用" if s.enabled else "✗ 禁用"
        lines.append(f"{i}. [{s.id}] {s.name}")
        lines.append(f"   类型: {s.fs_type} | 路径: {s.root_url} | {status}")

    return "\n".join(lines)


def kb_list_missing(source_id: str | None = None) -> str:
    """列出缺失描述文件的媒体文件。

    Args:
        source_id: 限定查询的知识来源ID

    Returns:
        缺失描述的文件列表
    """
    comp = get_components()
    state = comp["state"]

    # 查询 missing_desc 状态的文件
    conn = state._conn
    if source_id:
        rows = conn.execute(
            "SELECT source_id, path FROM missing_descriptions "
            "WHERE source_id = ? ORDER BY path",
            (source_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT source_id, path FROM missing_descriptions ORDER BY source_id, path"
        ).fetchall()

    if not rows:
        return "所有文件均已有关联的描述信息。"

    lines = [f"**缺失描述文件: {len(rows)} 个**\n"]
    current_source = ""
    for sid, path in rows:
        if sid != current_source:
            current_source = sid
            lines.append(f"\n### [{sid}]")
        lines.append(f"- `{path}`")

    lines.append(f"\n使用 kb_describe_media 为这些文件添加描述。")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# 来源管理
# ═══════════════════════════════════════════════════════════════════

def kb_add_source(name: str, url: str, fs_type: str = "local") -> str:
    """添加知识来源。

    Args:
        name: 来源名称（用于显示和识别）
        url: 来源路径 (本地绝对路径 或 file:/// 或 webdav://)
        fs_type: 文件系统类型 (local / webdav)

    Returns:
        操作结果
    """
    comp = get_components()
    from ..common.config import Config
    from ..common.sources import SourceManager, KnowledgeSource

    config = comp["config"]
    sm = comp["source_manager"]

    source_id = name.lower().replace(" ", "-").replace("_", "-")
    ks = KnowledgeSource(
        id=source_id,
        name=name,
        fs_type=fs_type,
        root_url=url,
    )
    sm.add_source(ks)
    return f"知识来源已添加: [{source_id}] {name} → {url}"


def kb_remove_source(source_id: str) -> str:
    """移除知识来源。

    注意：不会删除实际的源文件，仅从配置中移除。

    Args:
        source_id: 要移除的知识来源ID

    Returns:
        操作结果
    """
    comp = get_components()
    sm = comp["source_manager"]

    if sm.remove_source(source_id):
        return f"知识来源已移除: {source_id}"
    else:
        return f"未找到知识来源: {source_id}"


# ═══════════════════════════════════════════════════════════════════
# 媒体描述
# ═══════════════════════════════════════════════════════════════════

def kb_describe_media(source_id: str, media_path: str,
                      description: str, tags: str = "") -> str:
    """为媒体文件创建或更新描述。

    描述将存储在媒体文件所在目录的 .kbdes/ 隐藏文件夹中。
    描述文件是自描述的（包含生成时间、文件版本等元数据）。

    Args:
        source_id: 知识来源ID
        media_path: 媒体文件的绝对路径
        description: Markdown 格式的描述内容
        tags: 逗号分隔的标签（可选）

    Returns:
        操作结果
    """
    import asyncio
    comp = get_components()
    async_indexer = comp["async_indexer"]

    async def _run():
        return await async_indexer.describe_media(
            source_id, media_path, description, tags
        )

    try:
        result = _run_async(_run())
    except Exception as e:
        return f"描述操作失败: {e}"

    if result.get("success"):
        return (f"描述文件{result.get('action', '处理')}成功。\n"
                f"- 媒体文件: `{result.get('media_path', media_path)}`\n"
                f"- 描述文件: `{result.get('desc_path', '')}`")
    else:
        return f"描述操作失败: {result.get('error', '未知错误')}"


# ═══════════════════════════════════════════════════════════════════
# 任务管理
# ═══════════════════════════════════════════════════════════════════

def kb_get_job_status(job_id: str) -> str:
    """查询后台任务状态。

    Args:
        job_id: 任务ID

    Returns:
        任务详情
    """
    comp = get_components()
    job_queue = comp["job_queue"]

    job = job_queue.get_job(job_id)
    if not job:
        return f"未找到任务: {job_id}"

    d = job.to_dict()
    lines = [
        f"**任务详情: {job_id[:8]}...**",
        f"- 类型: {d['job_type']}",
        f"- 状态: {d['status']}",
        f"- 来源: {d['source_id']}",
        f"- 目标: `{d['target_path']}`",
        f"- 进度: {d['progress']*100:.1f}%",
        f"- 耗时: {d['elapsed']:.1f}s",
    ]
    if d["eta_seconds"] > 0:
        lines.append(f"- 预估剩余: {d['eta_seconds']:.1f}s")
    if d["error"]:
        lines.append(f"- 错误: {d['error']}")
    if d["progress_message"]:
        lines.append(f"- 消息: {d['progress_message']}")

    return "\n".join(lines)


def kb_list_jobs(status_filter: str = "all") -> str:
    """列出所有后台任务。

    Args:
        status_filter: 状态过滤器
            - "all": 全部
            - "active": 活跃（待处理+运行中）
            - "pending": 待处理
            - "completed": 已完成
            - "failed": 失败

    Returns:
        任务列表
    """
    comp = get_components()
    job_queue = comp["job_queue"]

    jobs = job_queue.list_jobs(status_filter=status_filter)
    if not jobs:
        return "暂无符合条件的后台任务。"

    lines = [f"**后台任务 ({status_filter}): {len(jobs)} 个**\n"]
    for j in jobs[:20]:  # 最多显示 20 个
        status_emoji = {
            "pending": "⏳", "running": "🔄",
            "completed": "✅", "failed": "❌",
            "cancelled": "⛔",
        }.get(j.status.value, "❓")

        lines.append(
            f"{status_emoji} [{j.job_id[:8]}..] {j.job_type.value} "
            f"({j.status.value})"
        )
        if j.target_path:
            # 截断长路径
            tp = j.target_path
            if len(tp) > 60:
                tp = "..." + tp[-57:]
            lines.append(f"   → `{tp}`")

    if len(jobs) > 20:
        lines.append(f"\n... 还有 {len(jobs) - 20} 个任务未显示。")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# 文件监控
# ═══════════════════════════════════════════════════════════════════

def kb_start_watcher(source_ids: list[str] | None = None) -> str:
    """启动文件监控。

    开始实时监控指定知识来源的文件变更。
    文件变更会自动触发增量索引任务。

    Args:
        source_ids: 要监控的知识来源ID列表，不指定则监控全部启用的来源

    Returns:
        监控启动结果
    """
    import asyncio
    comp = get_components()
    watcher = comp["watcher"]

    if not watcher.is_available:
        return ("watchdog 未安装，无法启动文件监控。\n"
                "请运行: pip install watchdog")

    if watcher.is_running:
        return "文件监控已在运行中。使用 kb_stop_watcher 先停止。"

    sources = comp["source_manager"].get_sources()
    if source_ids:
        sources = [s for s in sources if s.id in source_ids]

    src_dicts = [{"id": s.id, "root_url": s.root_url} for s in sources]

    async def _start():
        await watcher.start(src_dicts)

    try:
        _run_async(_start())
    except Exception as e:
        return f"启动文件监控失败: {e}"

    if watcher.is_running:
        watched = watcher.get_watched_sources()
        lines = ["**文件监控已启动**", f"监控 {len(watched)} 个来源:"]
        for w in watched:
            lines.append(f"- [{w['source_id']}] `{w['root']}`")
        lines.append("\n文件变更将自动触发增量索引。")
        lines.append("使用 kb_list_jobs 查看索引任务。")
        return "\n".join(lines)
    else:
        return "文件监控启动失败：无可监控的有效目录。"


def kb_stop_watcher(source_ids: list[str] | None = None) -> str:
    """停止文件监控。

    Args:
        source_ids: 要停止的来源ID列表，不指定则停止全部

    Returns:
        停止结果
    """
    import asyncio
    comp = get_components()
    watcher = comp["watcher"]

    if not watcher.is_running:
        return "文件监控未在运行。"

    async def _stop():
        await watcher.stop()

    try:
        _run_async(_stop())
    except Exception as e:
        return f"停止文件监控失败: {e}"

    return "文件监控已停止。"


# ═══════════════════════════════════════════════════════════════════
# 描述文件检测
# ═══════════════════════════════════════════════════════════════════

def kb_check_stale() -> str:
    """检查所有描述文件的过期状态。

    Returns:
        过期描述文件列表
    """
    import asyncio
    comp = get_components()
    async_indexer = comp["async_indexer"]

    async def _run():
        return await async_indexer.check_stale_descs()

    try:
        stale_list = _run_async(_run())
    except Exception as e:
        return f"检查失败: {e}"

    if not stale_list:
        return "所有描述文件均为最新状态，无需更新。"

    lines = [f"**发现 {len(stale_list)} 个过期描述文件**\n"]
    for kbdesc in stale_list:
        lines.append(
            f"- `{kbdesc.media_path}` → 原因: {kbdesc.stale_reason}\n"
            f"  描述文件: `{kbdesc.desc_path}`"
        )

    lines.append("\n使用 kb_index_incremental 自动重新索引这些文件。")
    return "\n".join(lines)
