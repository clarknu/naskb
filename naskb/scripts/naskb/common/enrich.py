"""来源知识富化（REQ-R7-05，ArtifactSink 内部模式·v3）。

对注册来源执行 AI 分析并把结果**直接入库 PG**（resources/vectors/folders），
不在源端写任何东西——包括只读源也一个字节不写。

实现取"暂存仓库 sink"形态（platform-v3-design §3.2 的落地变体）：
- 读：来源适配器（相对根路径视图）；
- 写：工作区 store/tmp/repos/<source_id>/ 下的本地暂存 .naskb；
  完整复用 batch.analyze_tree 增量幂等管线（L1/L2/L3、MinerU、MiMo、并发纪律）；
- 同步：从暂存仓库收集 Doc（保留相对路径语义）→ pgstore.sync_vectors(source_id=…)；
- 清理：每次成功同步后删除暂存 artifacts/（MinerU html/middle.json/images 等
  重产物，用户拍板不持久保留）；仅保留 index.json/files/*.json 轻量元数据
  作为增量幂等的状态基础。

rw 源的源端 .naskb 双写仍走既有 CLI 流程（原始仲裁端语义不变，
ADR-20260818-1 决策 5）；平台富化统一走本模块。
"""
from __future__ import annotations

import json
import os
import shutil
from typing import Callable, Optional

from .batch import analyze_tree
from .desc_store import REPO_DIR_NAME, FileEntry, FolderEntry, _fs_read_json
from .fs.base import FileSystemAdapter
from .fs.local import LocalAdapter
from .pgstore import PgStore
from .retrieval import Doc
from .source_registry import SourceRecord

ProgressFn = Optional[Callable[[float, str], None]]


def staging_repo_dir(work_path: str, source_id: str) -> str:
    return os.path.join(work_path, "store", "tmp", "repos", source_id)


def _doc_from_entry(rel: str, entry: FileEntry, data_full: Optional[FileEntry]) -> Doc:
    if data_full is not None:
        entry = data_full
    text = "\n".join(x for x in (
        rel, entry.summary, entry.category, " ".join(entry.tags),
        entry.content_description) if x)
    context = "\n".join(x for x in (
        rel, entry.summary, entry.category, " ".join(entry.tags),
        entry.content_description, entry.transcription, entry.ocr_text) if x)
    return Doc(
        path=rel, kind="file", text=text,
        summary=entry.summary, category=entry.category, tags=entry.tags,
        content_description=entry.content_description,
        file_type=entry.file_type or "",
        context=context, file_hash=entry.file_hash,
        hash_algorithm=entry.hash_algorithm, size_bytes=entry.size_bytes,
        mtime=entry.mtime, ctime=entry.ctime,
        analyzed_at=entry.analyzed_at)


def collect_staging_docs(staging_adapter: FileSystemAdapter,
                         staging_root: str) -> tuple[list[Doc], list[Doc]]:
    """收集暂存仓库的文件/目录 Doc（路径保持**相对**语义）。"""
    file_docs: list[Doc] = []
    folder_docs: list[Doc] = []
    for f in staging_adapter.list_files(staging_root, recursive=True):
        if f.name not in ("index.json", "folder.json"):
            continue
        rel_parts = f.path.replace("\\", "/").split("/")
        if REPO_DIR_NAME not in rel_parts:
            continue
        try:
            raw_bytes = staging_adapter.read_bytes(f.path, max_bytes=4_000_000)
            data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if f.name == "index.json":
            for raw in data.get("files") or []:
                entry = FileEntry.from_dict(raw)
                full = None
                df = raw.get("data_file")
                if df:
                    repo_dir = os.path.dirname(os.path.dirname(f.path))
                    df_path = os.path.join(repo_dir, REPO_DIR_NAME,
                                           "files", df).replace("\\", "/")
                    if staging_adapter.exists(df_path):
                        full_raw = _fs_read_json(staging_adapter, df_path)
                        if full_raw is not None:
                            full = FileEntry.from_dict(full_raw)
                rel = raw.get("path") or ""
                if not rel or not text_nonempty(entry):
                    continue
                file_docs.append(_doc_from_entry(rel, entry, full))
        else:
            fe = FolderEntry.from_dict(data)
            rel_dir = os.path.dirname(os.path.dirname(f.path))
            rel_norm = _rel_under(staging_root, rel_dir)
            if rel_norm is None:
                continue
            folder_docs.append(Doc(
                path=rel_norm, kind="folder",
                text="\n".join(x for x in (
                    fe.summary, fe.description,
                    " ".join(fe.tags)) if x),
                summary=fe.summary, category="目录", tags=fe.tags))
    return file_docs, folder_docs


def text_nonempty(entry: FileEntry) -> bool:
    return bool((entry.summary or "").strip()
                or (entry.content_description or "").strip())


def _rel_under(staging_root: str, abs_dir: str) -> Optional[str]:
    root_norm = os.path.abspath(staging_root).replace("\\", "/").rstrip("/")
    d = abs_dir.replace("\\", "/")
    if d.startswith(root_norm + "/"):
        return d[len(root_norm) + 1:]
    if d == root_norm:
        return ""
    return None


def cleanup_artifacts(work_path: str, source_id: str) -> int:
    """删除暂存仓库内的 artifacts 重产物（决策 3：中间产物不持久保留）。

    返回删除的目录数。index.json 与 files/*.json 保留（增量幂等状态）。
    """
    base = staging_repo_dir(work_path, source_id)
    removed = 0
    if not os.path.isdir(base):
        return removed
    for root, dirs, files in os.walk(base):
        for d in list(dirs):
            if d == "artifacts":
                target = os.path.join(root, d)
                shutil.rmtree(target, ignore_errors=True)
                dirs.remove(d)
                removed += 1
    return removed


def enrich_source(source: SourceRecord, pg: PgStore, config,
                  *, llm: bool = True, workers: int = 4,
                  mineru: bool = True, limit: Optional[int] = None,
                  force: bool = False,
                  on_progress: ProgressFn = None,
                  clients: Optional[dict] = None) -> dict:
    """对单个来源执行"扫描级分析→入库"。可反复调用（增量幂等）。

    返回 {analyze: BatchResult 字段, sync: sync 统计, folders: n,
          artifacts_removed: n}
    """
    from .embeddings import Embedder, ensure_model

    report: dict = {}
    read_fs = source.open_adapter()

    def prog(p: float, msg: str) -> None:
        if on_progress:
            on_progress(min(p * 0.85, 0.85), msg)

    # 暂存仓库（持久以获得增量幂等；重产物在同步后清理）
    stage_dir = staging_repo_dir(config.work_path, source.source_id)
    os.makedirs(stage_dir, exist_ok=True)
    staging_store_fs = LocalAdapter(stage_dir)
    from .desc_store import NaskbStore
    staging_store = NaskbStore(staging_store_fs)

    result = analyze_tree(
        read_fs, staging_store, config, root="",
        llm=llm, workers=workers, mineru=mineru,
        limit=limit, force=force,
        on_progress=prog, clients=clients)
    report["analyze"] = {
        "total": getattr(result, "total", 0),
        "analyzed": getattr(result, "analyzed", 0),
        "skipped": getattr(result, "skipped", 0),
        "failed": getattr(result, "failed", 0),
        "unsupported": getattr(result, "unsupported", 0),
    }

    if on_progress:
        on_progress(0.88, "收集描述并同步向量库…")

    # 向量模型：显式管理动作允许触发下载（~24MB，一次性）
    ensure_model(config.work_path)
    embedder = Embedder(config.work_path)
    try:
        file_docs, folder_docs = collect_staging_docs(
            staging_store_fs, stage_dir)
        schema = source.schema_name or ""
        if schema:
            sync = pg.sync_vectors(schema, [d for d in file_docs
                                            if d.text.strip()],
                                   embedder, source_id=source.source_id)
            report["sync"] = {k: v for k, v in sync.items() if k != "errors"}
            report["sync_errors"] = sync.get("errors", [])[:20]
            for fd in folder_docs:
                if fd.text.strip():
                    pg.upsert_folder_meta(
                        schema, source.source_id, fd.path,
                        summary=fd.summary, description=fd.context,
                        tags=fd.tags)
            report["folders"] = len(folder_docs)
        else:
            report["sync"] = {"skipped": "schema 未派生（来源未完成注册校验）"}
            report["folders"] = 0
    finally:
        embedder.close()

    report["artifacts_removed"] = cleanup_artifacts(
        config.work_path, source.source_id)
    if on_progress:
        on_progress(1.0, "完成")
    return report
