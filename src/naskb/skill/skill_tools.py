"""Copilot Skill tool functions for NASKB."""
import os
from pathlib import Path


def _get_work_path() -> str:
    return os.environ.get("NASKB_WORK", str(Path.home() / "NASKB_data"))


def naskb_search(query: str, top_k: int = 10,
                 threshold: float = 0.5) -> str:
    """Semantic search over the NASKB knowledge base.

    Args:
        query: Natural language search query (Chinese or English)
        top_k: Maximum number of results to return
        threshold: Minimum similarity score (0.0 to 1.0)

    Returns:
        Formatted search results with file paths, scores, and snippets.
    """
    wp = _get_work_path()

    from ..common.config import Config
    from ..common.embedder import Embedder
    from .indexer import Indexer
    from ..common.model_manager import ModelManager
    from ..common.sources import SourceManager
    from ..common.state import StateManager
    from ..common.vector_store import VectorStore

    config = Config.from_work_path(wp)
    model_path, tokenizer_path = ModelManager.ensure_model(
        wp, config.model_name
    )
    embedder = Embedder(model_path, tokenizer_path, config.execution_provider)
    vector_store = VectorStore(config.db_path, config.model_dim)
    state = StateManager(config.state_path)
    source_manager = SourceManager(config)
    indexer = Indexer(config, embedder, vector_store, state, source_manager)

    results = indexer.search(query, top_k=top_k, threshold=threshold)

    if not results:
        return "未找到相关结果。"

    lines = [f"找到 {len(results)} 条相关结果：\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r.score:.2f}] **{r.name}**")
        lines.append(f"   路径: `{r.path}`")
        if r.orig_file:
            lines.append(f"   原始文件: `{r.orig_file}`")
        if r.snippet:
            lines.append(f"   摘要: {r.snippet[:200]}")
        lines.append("")

    return "\n".join(lines)


def naskb_status() -> str:
    """Get NASKB indexing status report.

    Returns:
        Summary of indexed files, missing descriptions, and source stats.
    """
    wp = _get_work_path()
    config = __import__("naskb.config", fromlist=["Config"]).Config.from_work_path(wp)

    try:
        from ..common.state import StateManager
        from ..common.vector_store import VectorStore

        state = StateManager(config.state_path)
        vector_store = VectorStore(config.db_path, config.model_dim)
        stats = state.get_stats()

        lines = [
            f"**NASKB 状态报告**",
            f"- 模型: {config.model_name} ({config.model_dim}维)",
            f"- 已索引文件: {vector_store.count('files')}",
            f"- 已索引文件夹: {vector_store.count('folders')}",
            f"- 索引状态: 已索引 {stats['indexed']} | 待更新 {stats['outdated']} | 缺失描述 {stats['missing_desc']}",
        ]
        return "\n".join(lines)
    except Exception:
        return "NASKB 尚未初始化。请先运行 `naskb init --work-path <path>`。"


def naskb_index() -> str:
    """Trigger incremental index update.

    Returns:
        Summary of indexing operation.
    """
    wp = _get_work_path()
    try:
        config = __import__("naskb.config", fromlist=["Config"]).Config.from_work_path(wp)
        from ..common.embedder import Embedder
        from .indexer import Indexer
        from ..common.model_manager import ModelManager
        from ..common.sources import SourceManager
        from ..common.state import StateManager
        from ..common.vector_store import VectorStore

        model_path, tokenizer_path = ModelManager.ensure_model(
            wp, config.model_name
        )
        embedder = Embedder(model_path, tokenizer_path, config.execution_provider)
        vector_store = VectorStore(config.db_path, config.model_dim)
        state = StateManager(config.state_path)
        source_manager = SourceManager(config)
        indexer = Indexer(config, embedder, vector_store, state, source_manager)

        stats = indexer.index_incremental()
        return f"增量索引完成。更新了 {stats['total_updated']} 个文件。"
    except Exception as e:
        return f"索引失败: {e}"
