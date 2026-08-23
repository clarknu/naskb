"""存量 .naskb 仓库收编 + 反向重建（REQ-R7-13：adopt / export-repo）。

- adopt_repo：把来源端已存在的 .naskb 描述仓库（v2 时代产物）直接导入
  系统 PG 主库（复用 collect_docs + sync_vectors 富化回填），文件夹描述
  写入 folders 表。不改源端任何内容。
- export_repo：反向——把系统 PG 里的知识按 .naskb 结构重建到一个本地
  目录（可写源的便携缓存/备份），复用 NaskbStore 写入路径。

两函数都以 SourceRecord 为单位工作，source_id 作用域与 V1 一致。
"""
from __future__ import annotations

import os
from typing import Callable, Optional

from .fs.local import LocalAdapter
from .pgstore import PgStore
from .retrieval import Doc, collect_docs
from .source_registry import SourceRecord

ProgressFn = Optional[Callable[[float, str], None]]


def adopt_repo(pg: PgStore, config, source: SourceRecord,
               on_progress: ProgressFn = None,
               embedder=None) -> dict:
    """导入来源端 .naskb → PG 主库（幂等：重复执行走增量）。

    embedder: 可注入（测试用零向量假实现）；None 时自动准备真实嵌入器。
    """
    if on_progress:
        on_progress(0.1, "遍历来源端 .naskb…")
    fs = source.open_adapter()
    docs = collect_docs(fs, "")
    file_docs = [d for d in docs
                 if d.kind == "file" and d.text.strip()]
    folder_docs = [d for d in docs
                   if d.kind == "folder" and d.text.strip()]
    if not file_docs and not folder_docs:
        return {"adopted": 0, "folders": 0,
                "message": "未在该来源发现可导入的 .naskb 描述（先跑 desc analyze-tree）"}
    if on_progress:
        on_progress(0.45, f"收集到 {len(file_docs)} 文件 / {len(folder_docs)} 目录…")
    own_embedder = False
    if embedder is None:
        from .embeddings import Embedder, ensure_model
        ensure_model(config.work_path)
        embedder = Embedder(config.work_path)
        own_embedder = True
    try:
        schema = source.schema_name or ""
        if on_progress:
            on_progress(0.6, "入库（向量化）…")
        sync = pg.sync_vectors(schema, file_docs, embedder,
                               source_id=source.source_id)
        # 目录登记（folders 表 + file_count）：adopt 只灌 resources/vectors，
        # 目录清单沿 scan 语义再对账一次（幂等，未入库目录补建）
        items = [{
            "rel_path": d.path.replace("\\", "/"),
            "name": d.path.replace("\\", "/").rsplit("/", 1)[-1],
            "parent_dir": d.path.replace("\\", "/").rsplit("/", 1)[0]
            if "/" in d.path.replace("\\", "/") else "",
            "size_bytes": d.size_bytes, "mtime": d.mtime, "ctime": d.ctime,
            "file_hash": d.file_hash,
            "hash_algorithm": d.hash_algorithm,
            "file_type": d.file_type or "",
        } for d in file_docs]
        pg.reconcile_resources(schema, source.source_id, items)
        folders = 0
        for fd in folder_docs:
            pg.upsert_folder_meta(schema, source.source_id, fd.path,
                                  summary=fd.summary, description=fd.context,
                                  tags=fd.tags)
            folders += 1
        report = {k: v for k, v in sync.items() if k != "errors"}
        report["folders"] = folders
        report["adopted"] = len(file_docs)
        return report
    finally:
        embedder.close()


def export_repo(pg: PgStore, config, source: SourceRecord, out_dir: str,
                on_progress: ProgressFn = None) -> dict:
    """把 PG 知识重建为 out_dir 下的 .naskb 目录结构（便携缓存/备份）。"""
    from .desc_store import FileEntry, FolderEntry, NaskbStore

    fs_out = LocalAdapter(out_dir)
    store = NaskbStore(fs_out)
    rows = pg.all_rows(source.schema_name, source.source_id)
    written = 0
    folders_written = 0
    dirs = set()
    if on_progress:
        on_progress(0.05, f"导出 {len(rows)} 条…")
    for i, r in enumerate(rows):
        rel = r["rel_path"]
        entry = FileEntry(
            path=rel.rsplit("/", 1)[-1] if "/" in rel else rel,
            file_hash=r["file_hash"], hash_algorithm=r["hash_algorithm"],
            analyzed_at=r["analyzed_at"] or "",
            file_type=r["file_type"] or "",
            size_bytes=r["size_bytes"] or 0,
            mtime=r["mtime"] or 0.0, ctime=r["ctime"] or 0.0,
            category=r["category"] or "", tags=r["tags"] or [],
            summary=r["summary"] or "",
            content_description=r["content_description"] or "",
        )
        if r["status"] == "missing_source":
            continue
        ok = store.set_entry(rel, entry)
        if ok:
            written += 1
        dirs.add(rel.rsplit("/", 1)[0] if "/" in rel else "")
        if on_progress and i % 100 == 0:
            on_progress(min(0.05 + 0.7 * i / max(len(rows), 1), 0.75),
                        f"导出 {i}/{len(rows)}")
    if on_progress:
        on_progress(0.82, "导出目录描述…")
    for d in sorted(x for x in dirs if x):
        store.write_folder(d, FolderEntry(summary="", description="", tags=[]))
        folders_written += 1
    if on_progress:
        on_progress(1.0, "完成")
    return {"exported": written, "folders": folders_written,
            "out_dir": out_dir}
