"""Command-line interface for NASKB.

Usage:
    naskb init --work-path <path>
    naskb index --full
    naskb index --update
    naskb search "query"
    naskb status
    naskb missing
"""
import os
import sys
from pathlib import Path
from typing import Optional

import click

# Resolve NASKB_WORK from env or current directory
_DEFAULT_WORK = os.environ.get("NASKB_WORK", str(Path.cwd() / "NASKB_data"))


def _get_work_path(work_path: Optional[str]) -> str:
    return work_path or _DEFAULT_WORK


def _make_kb(work_path: str):
    """Initialize all components and return (config, embedder, vector_store, state, source_manager, indexer)."""
    from ..common.config import Config
    from ..common.embedder import Embedder
    from .indexer import Indexer
    from ..common.model_manager import ModelManager
    from ..common.sources import SourceManager
    from ..common.state import StateManager
    from ..common.vector_store import VectorStore

    config = Config.from_work_path(work_path)
    model_path, tokenizer_path = ModelManager.ensure_model(
        work_path, config.model_name, hf_endpoint=config.hf_endpoint
    )
    embedder = Embedder(
        model_path, tokenizer_path, config.execution_provider,
        intra_op_threads=config.intra_op_threads,
        inter_op_threads=config.inter_op_threads,
    )
    vector_store = VectorStore(config.db_path, config.model_dim)
    state = StateManager(config.state_path)
    source_manager = SourceManager(config)
    indexer = Indexer(config, embedder, vector_store, state, source_manager)

    return config, embedder, vector_store, state, source_manager, indexer


# ═══════════════════════════════════════════════════════════════════
# CLI Group
# ═══════════════════════════════════════════════════════════════════

@click.group()
@click.option("--work-path", "-w", envvar="NASKB_WORK",
              default=_DEFAULT_WORK, show_default=True,
              help="Path to NASKB work directory")
@click.pass_context
def main(ctx, work_path):
    """NASKB — 本地向量知识库系统

    语义检索你的本地文档、笔记和媒体文件描述。
    """
    ctx.ensure_object(dict)
    ctx.obj["work_path"] = str(Path(work_path).resolve())


# ═══════════════════════════════════════════════════════════════════
# init
# ═══════════════════════════════════════════════════════════════════

@main.command()
@click.option("--work-path", "-w", envvar="NASKB_WORK",
              default=_DEFAULT_WORK,
              help="Work directory path")
@click.option("--model", "-m", default="bge-base-zh-v1.5",
              type=click.Choice(["bge-base-zh-v1.5", "bge-large-zh-v1.5"]),
              help="Embedding model to use")
def init(work_path, model):
    """Initialize NASKB work environment."""
    wp = str(Path(work_path).resolve())
    print(f"[naskb] Initializing work environment at: {wp}")

    from ..common.bootstrap import Bootstrap
    from ..common.model_manager import ModelManager

    # Bootstrap venv + deps
    venv_python = Bootstrap.ensure(wp)
    print(f"[naskb] Python environment: {venv_python}")

    # Create default config
    Bootstrap.create_default_config(wp, model)
    print(f"[naskb] Config created: {wp}/config.toml")

    # Download model
    try:
        model_path, tokenizer_path = ModelManager.ensure_model(wp, model)
        print(f"[naskb] Model ready: {model_path}")
    except Exception as e:
        print(f"[naskb] Model download failed: {e}")
        print(f"[naskb] You can download it later with: naskb model download")

    print(f"\n[naskb] Initialization complete!")
    print(f"  Work path:  {wp}")
    print(f"  Config:     {wp}/config.toml")
    print(f"  Database:   {wp}/db/")
    print(f"  Next step:  naskb source add <name> <path>")
    print(f"              naskb index --full")


# ═══════════════════════════════════════════════════════════════════
# source
# ═══════════════════════════════════════════════════════════════════

@main.group()
def source():
    """Manage knowledge sources."""
    pass


@source.command("add")
@click.argument("name")
@click.argument("url")
@click.option("--type", "-t", "fs_type", default="local",
              type=click.Choice(["local", "webdav"]),
              help="File system type")
@click.pass_context
def source_add(ctx, name, url, fs_type):
    """Add a knowledge source."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    from ..common.config import Config
    from ..common.sources import SourceManager, KnowledgeSource

    config = Config.from_work_path(wp)
    sm = SourceManager(config)

    source_id = name.lower().replace(" ", "-")
    ks = KnowledgeSource(
        id=source_id,
        name=name,
        fs_type=fs_type,
        root_url=url,
    )
    sm.add_source(ks)
    print(f"[naskb] Source added: [{source_id}] {name} -> {url}")


@source.command("list")
@click.pass_context
def source_list(ctx):
    """List all sources."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    from ..common.config import Config
    from ..common.sources import SourceManager

    config = Config.from_work_path(wp)
    sm = SourceManager(config)

    for s in sm.get_sources():
        status = "✓" if s.enabled else "✗"
        print(f"  [{status}] {s.id}: {s.name} ({s.fs_type}) -> {s.root_url}")


@source.command("remove")
@click.argument("source_id")
@click.pass_context
def source_remove(ctx, source_id):
    """Remove a knowledge source."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    from ..common.config import Config
    from ..common.sources import SourceManager

    config = Config.from_work_path(wp)
    sm = SourceManager(config)

    if sm.remove_source(source_id):
        print(f"[naskb] Source removed: {source_id}")
    else:
        print(f"[naskb] Source not found: {source_id}")


# ═══════════════════════════════════════════════════════════════════
# index
# ═══════════════════════════════════════════════════════════════════

@main.group()
def index():
    """Index files into the knowledge base."""
    pass


@index.command("full")
@click.option("--source", "-s", "source_id", default=None,
              help="Limit to specific source")
@click.pass_context
def index_full(ctx, source_id):
    """Full index of all sources."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    print(f"[naskb] Full index started...")
    print(f"[naskb] Work path: {wp}")

    _, _, _, _, _, indexer = _make_kb(wp)
    source_ids = [source_id] if source_id else None
    stats = indexer.index_full(source_ids)

    print(f"\n[naskb] Full index complete!")
    print(f"  Total scanned: {stats['total_files']}")
    print(f"  Total indexed: {stats['total_indexed']}")


@index.command("update")
@click.option("--source", "-s", "source_id", default=None,
              help="Limit to specific source")
@click.pass_context
def index_update(ctx, source_id):
    """Incremental index update."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    print(f"[naskb] Incremental index update...")

    _, _, _, _, _, indexer = _make_kb(wp)
    source_ids = [source_id] if source_id else None
    stats = indexer.index_incremental(source_ids)

    print(f"\n[naskb] Incremental update complete!")
    print(f"  Updated: {stats['total_updated']}")


@index.command("file")
@click.argument("path")
@click.option("--source", "-s", "source_id", default="default",
              help="Source ID")
@click.pass_context
def index_file(ctx, path, source_id):
    """Index a single file."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    _, _, _, _, _, indexer = _make_kb(wp)

    if indexer.index_file(source_id, path):
        print(f"[naskb] File indexed: {path}")
    else:
        print(f"[naskb] Failed to index: {path}")


@index.command("folder")
@click.argument("path")
@click.option("--source", "-s", "source_id", default="default",
              help="Source ID")
@click.pass_context
def index_folder(ctx, path, source_id):
    """Index all files in a folder."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    _, _, _, _, _, indexer = _make_kb(wp)

    count = indexer.index_folder(source_id, path)
    print(f"[naskb] Folder indexed: {path} ({count} files)")


# ═══════════════════════════════════════════════════════════════════
# search
# ═══════════════════════════════════════════════════════════════════

@main.command()
@click.argument("query")
@click.option("--top-k", "-k", default=10, show_default=True,
              help="Number of results")
@click.option("--threshold", "-t", default=0.5, show_default=True,
              help="Similarity threshold (0-1)")
@click.option("--source", "-s", "source_id", default=None,
              help="Limit to specific source")
@click.pass_context
def search(ctx, query, top_k, threshold, source_id):
    """Semantic search over the knowledge base."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    _, _, _, _, _, indexer = _make_kb(wp)

    print(f"[naskb] Searching: \"{query}\"")
    results = indexer.search(query, top_k=top_k, threshold=threshold,
                              source_id=source_id)

    if not results:
        print("  No results found.")
        return

    print(f"\n  Found {len(results)} results:\n")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r.score:.3f}] {r.name}")
        print(f"     Path: {r.path}")
        if r.orig_file:
            print(f"     Original: {r.orig_file}")
        print(f"     Source: {r.source_id}")
        print(f"     {r.snippet[:120]}...")
        print()


# ═══════════════════════════════════════════════════════════════════
# status
# ═══════════════════════════════════════════════════════════════════

@main.command()
@click.pass_context
def status(ctx):
    """Show indexing status."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    config, _, vector_store, state, source_manager, _ = _make_kb(wp)

    stats = state.get_stats()
    file_count = vector_store.count("files")
    folder_count = vector_store.count("folders")

    print(f"[naskb] Status Report")
    print(f"  Work path:     {wp}")
    print(f"  Model:         {config.model_name} ({config.model_dim}d)")
    print(f"  Provider:      {config.execution_provider}")
    print(f"  DB files:      {file_count}")
    print(f"  DB folders:    {folder_count}")
    print(f"")
    print(f"  Indexing State:")
    print(f"    Total tracked:  {stats['total']}")
    print(f"    Indexed:        {stats['indexed']} ✓")
    print(f"    Outdated:       {stats['outdated']} ⚠")
    print(f"    Missing desc:   {stats['missing_desc']} ✗")
    print(f"    Skipped:        {stats['skipped']} ⊘")
    print(f"    Deleted:        {stats['deleted']} ✕")
    print(f"")
    print(f"  Sources:")
    for s in source_manager.get_sources():
        ss = stats.get("by_source", {}).get(s.id, {})
        print(f"    [{s.id}] {s.name} "
              f"(indexed={ss.get('indexed', 0)}, "
              f"missing={ss.get('missing_desc', 0)})")


# ═══════════════════════════════════════════════════════════════════
# missing
# ═══════════════════════════════════════════════════════════════════

@main.command()
@click.option("--source", "-s", "source_id", default=None)
@click.pass_context
def missing(ctx, source_id):
    """List files missing description files."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    _, _, _, state, _, _ = _make_kb(wp)

    items = state.get_missing_descriptions(source_id)
    if not items:
        print("[naskb] No missing description files.")
        return

    print(f"[naskb] {len(items)} files missing descriptions:\n")
    for item in items:
        print(f"  [{item['source_id']}] {item['path']}")


# ═══════════════════════════════════════════════════════════════════
# model
# ═══════════════════════════════════════════════════════════════════

@main.group()
def model():
    """Manage embedding model."""
    pass


@model.command("download")
@click.argument("model_name", default="bge-base-zh-v1.5")
@click.pass_context
def model_download(ctx, model_name):
    """Download embedding model."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    from ..common.model_manager import ModelManager

    model_path, tokenizer_path = ModelManager.ensure_model(wp, model_name)
    print(f"[naskb] Model: {model_path}")
    print(f"[naskb] Tokenizer: {tokenizer_path}")


# ═══════════════════════════════════════════════════════════════════
# config
# ═══════════════════════════════════════════════════════════════════

@main.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.pass_context
def config(ctx, key, value):
    """View or set configuration."""
    wp = _get_work_path(ctx.obj.get("work_path"))
    config = __import__("naskb.config", fromlist=["Config"]).Config.from_work_path(wp)

    if key is None:
        # Print all config
        d = config.to_dict()
        for k, v in d.items():
            print(f"  {k}: {v}")
    elif value is None:
        # Get single key
        print(f"  {key}: {getattr(config, key, 'N/A')}")
    else:
        # Set key
        if hasattr(config, key):
            setattr(config, key, value)
            config.save()
            print(f"  {key} = {value} (saved)")
        else:
            print(f"  Unknown key: {key}")


# ═══════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
