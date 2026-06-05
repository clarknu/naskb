"""NASKB MCP 服务器入口。

启动一个持续运行的 MCP (Model Context Protocol) 服务，
通过 stdio 或 HTTP/SSE 传输与 AI 客户端通信。

启动方式:
    # stdio 模式 (IDE 集成)
    python -m naskb.mcp.server

    # HTTP/SSE 模式 (外部网络调用)
    python -m naskb.mcp.server --transport sse --port 8765

环境变量:
    NASKB_WORK: 知识库工作路径
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# ── 确保 naskb 包在 Python 路径中 ──
_skill_home = os.environ.get("NASKB_HOME", "")
if not _skill_home:
    _file_dir = Path(__file__).resolve().parent.parent.parent
    if (_file_dir / "pyproject.toml").exists():
        _skill_home = str(_file_dir)
if _skill_home and _skill_home not in sys.path:
    sys.path.insert(0, _skill_home)

from .tools import (
    kb_search, kb_index_full, kb_index_incremental,
    kb_index_file, kb_status, kb_list_sources,
    kb_list_missing, kb_add_source, kb_remove_source,
    kb_describe_media, kb_get_job_status, kb_list_jobs,
    kb_start_watcher, kb_stop_watcher, kb_check_stale,
)


def _resolve_work_path(work_path: Optional[str] = None) -> str:
    """解析工作路径。"""
    if work_path:
        return str(Path(work_path).resolve())
    env_path = os.environ.get("NASKB_WORK", "")
    if env_path:
        return str(Path(env_path).resolve())
    # 默认: 当前目录下的 NASKB_data
    return str(Path.cwd() / "NASKB_data")


# ═══════════════════════════════════════════════════════════════════
# MCP Server 工厂
# ═══════════════════════════════════════════════════════════════════

def create_mcp_server(work_path: str = "", name: str = "NASKB") -> "FastMCP":
    """创建并配置 MCP 服务器。

    Args:
        work_path: NASKB 工作路径
        name: 服务器名称

    Returns:
        配置好的 FastMCP 实例
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        try:
            from fastmcp import FastMCP
        except ImportError:
            print("[naskb] MCP SDK not installed. Install with: pip install mcp")
            print("[naskb] or: pip install fastmcp")
            raise

    wp = _resolve_work_path(work_path)

    # 确保工作路径环境变量已设置
    os.environ["NASKB_WORK"] = wp

    mcp = FastMCP(
        name=name,
        description=(
            "NASKB — NAS Knowledge Base MCP Server. "
            "本地向量知识库服务，支持语义检索、文件索引、"
            "媒体描述管理 (.kbdes) 和实时文件监控。"
        ),
    )

    # ── 注册 Tools ──

    mcp.tool()(kb_search)
    mcp.tool()(kb_index_full)
    mcp.tool()(kb_index_incremental)
    mcp.tool()(kb_index_file)
    mcp.tool()(kb_status)
    mcp.tool()(kb_list_sources)
    mcp.tool()(kb_list_missing)
    mcp.tool()(kb_add_source)
    mcp.tool()(kb_remove_source)
    mcp.tool()(kb_describe_media)
    mcp.tool()(kb_get_job_status)
    mcp.tool()(kb_list_jobs)
    mcp.tool()(kb_start_watcher)
    mcp.tool()(kb_stop_watcher)
    mcp.tool()(kb_check_stale)

    # ── 注册 Resources ──

    @mcp.resource("naskb://config")
    def get_config_resource() -> str:
        """获取 NASKB 当前配置摘要。"""
        from .tools import get_components
        comp = get_components(wp)
        config = comp["config"]
        lines = [
            f"# NASKB Configuration",
            f"work_path: {config.work_path}",
            f"model: {config.model_name} ({config.model_dim}d)",
            f"execution_provider: {config.execution_provider}",
            f"db_path: {config.db_path}",
            f"state_path: {config.state_path}",
            f"batch_size: {config.batch_size}",
            f"sources: {len([s for s in config.sources if s.get('enabled', True)])} enabled",
        ]
        return "\n".join(lines)

    @mcp.resource("naskb://stats")
    def get_stats_resource() -> str:
        """获取 NASKB 运行统计。"""
        from .tools import get_components
        comp = get_components(wp)
        state = comp["state"]
        vector_store = comp["vector_store"]
        job_queue = comp["job_queue"]

        file_count = vector_store.count("files")
        folder_count = vector_store.count("folders")
        state_stats = state.get_stats()
        job_stats = job_queue.get_stats()

        lines = [
            f"# NASKB Runtime Statistics",
            f"indexed_files: {file_count}",
            f"indexed_folders: {folder_count}",
            f"indexed_total: {state_stats.get('indexed', 0)}",
            f"outdated: {state_stats.get('outdated', 0)}",
            f"missing_desc: {state_stats.get('missing_desc', 0)}",
            f"active_jobs: {job_stats.get('running', 0)}",
            f"pending_jobs: {job_stats.get('pending', 0)}",
        ]
        return "\n".join(lines)

    # ── 注册 Prompts ──

    @mcp.prompt()
    def search_prompt(query: str) -> str:
        """生成用于知识库搜索的提示。"""
        return (
            f"请在 NASKB 知识库中搜索关于「{query}」的相关内容。"
            f"使用 kb_search 工具进行语义检索，返回最相关的结果。"
        )

    @mcp.prompt()
    def organize_knowledge_prompt() -> str:
        """生成用于知识库整理的提示。"""
        return (
            "请帮我整理 NASKB 知识库：\n"
            "1. 使用 kb_check_stale 检查过期的描述文件\n"
            "2. 使用 kb_list_missing 查看缺失描述的媒体文件\n"
            "3. 使用 kb_index_incremental 更新索引\n"
            "4. 使用 kb_status 确认最终的索引状态"
        )

    return mcp


# ═══════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════

def main():
    """NASKB MCP 服务器入口点。"""
    parser = argparse.ArgumentParser(
        description="NASKB MCP Server — 本地向量知识库 MCP 服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # stdio 模式 (默认，用于 IDE 集成)
  python -m naskb.mcp.server

  # HTTP/SSE 模式 (外部网络调用)
  python -m naskb.mcp.server --transport sse --port 8765

  # 自定义工作路径
  python -m naskb.mcp.server --work-path D:/MyKB
        """,
    )
    parser.add_argument(
        "--work-path", "-w",
        default="",
        help="知识库工作路径 (默认: NASKB_WORK 环境变量 或 ./NASKB_data)",
    )
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="传输方式 (默认: stdio)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="HTTP/SSE 模式下的监听端口 (默认: 8765)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP/SSE 模式下的监听地址 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--name",
        default="NASKB",
        help="MCP 服务器名称 (默认: NASKB)",
    )

    args = parser.parse_args()

    wp = _resolve_work_path(args.work_path)
    print(f"[naskb] NASKB MCP Server starting...")
    print(f"[naskb] Work path: {wp}")
    print(f"[naskb] Transport: {args.transport}")
    print(f"[naskb] Server name: {args.name}")

    # 创建工作路径目录
    Path(wp).mkdir(parents=True, exist_ok=True)

    # 检查工作环境是否初始化
    if not (Path(wp) / "config.toml").exists():
        print("[naskb] Warning: config.toml not found. Run 'naskb init' first.")
        print(f"[naskb] You can run: python -m naskb.cli init --work-path {wp}")

    # 创建 MCP 服务器
    try:
        mcp = create_mcp_server(wp, args.name)
    except ImportError as e:
        print(f"[naskb] FATAL: {e}")
        print("[naskb] Please install MCP SDK: pip install mcp")
        sys.exit(1)

    # ── 启动 ──
    if args.transport == "stdio":
        print("[naskb] Starting in stdio mode (IDE integration)...")
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        print(f"[naskb] Starting SSE server at http://{args.host}:{args.port}/sse")
        mcp.run(transport="sse", host=args.host, port=args.port)
    elif args.transport == "streamable-http":
        print(f"[naskb] Starting HTTP server at http://{args.host}:{args.port}")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
