"""异步索引编排器。

在 MCP 服务环境下，以异步方式编排文件的扫描、描述解析、
向量化嵌入和存储。支持大规模并行化处理。
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from ..common.config import Config
from ..common.embedder import Embedder
from ..common.fs.base import FileSystemAdapter
from ..common.scanner import Scanner, ScannedFile
from ..common.sources import KnowledgeSource, SourceManager
from ..common.state import StateManager
from ..common.vector_store import VectorStore

from .desc_manager import DescManager, KbDesc
from .job_queue import Job, JobQueue, JobStatus, JobType


class AsyncIndexer:
    """异步知识库索引编排器。

    相比同步 Indexer 的增强：
    - 异步文件读取（asyncio + ThreadPoolExecutor）
    - 批量嵌入并行化
    - 集成 .kbdes 描述文件管理
    - 支持进度回调
    """

    def __init__(self, config: Config, embedder: Embedder,
                 vector_store: VectorStore, state: StateManager,
                 source_manager: SourceManager,
                 max_io_workers: int = 8):
        self._config = config
        self._embedder = embedder
        self._vector_store = vector_store
        self._state = state
        self._source_manager = source_manager
        self._io_executor = ThreadPoolExecutor(max_workers=max_io_workers)

    # ── 全量索引 ──

    async def index_full(self, source_ids: list[str] | None = None,
                         force: bool = False,
                         progress_callback=None) -> dict:
        """全量重建所有（或指定）来源的索引。"""
        sources = self._source_manager.get_sources()
        if source_ids:
            sources = [s for s in sources if s.id in source_ids]

        stats = {"sources": {}, "total_files": 0, "total_indexed": 0,
                 "total_desc_updated": 0}

        for source in sources:
            if progress_callback:
                progress_callback(f"Full index: [{source.id}] {source.name}")

            source_stat = await self._index_source_full(source, force)
            stats["sources"][source.id] = source_stat
            stats["total_files"] += source_stat.get("scanned", 0)
            stats["total_indexed"] += source_stat.get("indexed", 0)
            stats["total_desc_updated"] += source_stat.get("desc_updated", 0)

        self._vector_store.optimize()
        return stats

    async def _index_source_full(self, source: KnowledgeSource,
                                  force: bool) -> dict:
        """全量索引单个来源。"""
        fs = self._source_manager.get_fs(source.id)
        root = source.root_url or (fs.root if hasattr(fs, 'root') else "")

        # 清除现有记录
        if force:
            self._vector_store.delete_by_source(source.id)
            self._state.clear_source(source.id)

        # 扫描文件
        scanner = Scanner(fs, self._config.exclusions)
        scanned = scanner.scan(root)

        # 处理
        return await self._process_files(source, fs, scanned)

    # ── 增量索引 ──

    async def index_incremental(self, source_ids: list[str] | None = None,
                                 progress_callback=None) -> dict:
        """增量索引：仅处理新文件或已变更文件。"""
        sources = self._source_manager.get_sources()
        if source_ids:
            sources = [s for s in sources if s.id in source_ids]

        stats = {"sources": {}, "total_updated": 0, "total_desc_updated": 0}

        for source in sources:
            if progress_callback:
                progress_callback(f"Incremental index: [{source.id}] {source.name}")

            source_stat = await self._index_source_incremental(source)
            stats["sources"][source.id] = source_stat
            stats["total_updated"] += source_stat.get("updated", 0)
            stats["total_desc_updated"] += source_stat.get("desc_updated", 0)

        return stats

    async def _index_source_incremental(self, source: KnowledgeSource) -> dict:
        """增量索引单个来源。"""
        fs = self._source_manager.get_fs(source.id)
        root = source.root_url or (fs.root if hasattr(fs, 'root') else "")

        scanner = Scanner(fs, self._config.exclusions)
        scanned = scanner.scan(root)

        # 筛选需要更新的文件
        to_index: list[ScannedFile] = []
        for sf in scanned:
            if sf.type == "text":
                if self._state.has_changed(source.id, sf.path, sf.mtime,
                                            sf.size_bytes):
                    to_index.append(sf)
            elif sf.type == "binary":
                changed = self._state.has_changed(
                    source.id, sf.path, sf.mtime, sf.size_bytes)
                # 也检查 .kbdesc 描述文件
                desc_path = DescManager.get_desc_path(sf.path)
                if os.path.exists(desc_path):
                    ds = os.stat(desc_path)
                    changed = changed or self._state.has_changed(
                        source.id, desc_path, ds.st_mtime, ds.st_size)
                if changed:
                    to_index.append(sf)

        # 检测已删除文件
        indexed_paths = self._state.get_indexed_paths(source.id)
        scanned_paths = {sf.path for sf in scanned}
        for path in indexed_paths - scanned_paths:
            self._state.mark_deleted(source.id, path)

        if not to_index:
            print(f"  No changes detected for source [{source.id}].")
            return {"updated": 0, "scanned_total": len(scanned),
                    "desc_updated": 0}

        result = await self._process_files(source, fs, to_index)
        result["scanned_total"] = len(scanned)
        result["updated"] = result.get("indexed", 0)
        result["desc_updated"] = result.get("desc_updated", 0)
        return result

    # ── 单文件索引 ──

    async def index_file(self, source_id: str, file_path: str) -> dict:
        """索引单个文件（支持文本文件和带 .kbdesc 的媒体文件）。"""
        source = self._find_source(source_id)
        if not source:
            return {"success": False, "error": f"Source not found: {source_id}"}

        fs = self._source_manager.get_fs(source.id)
        if not fs.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        st = fs.stat(file_path)
        if not st:
            return {"success": False, "error": "Cannot stat file"}

        ext = Path(file_path).suffix.lower()

        # 文本文件：直接索引
        if Scanner.is_text_file(ext):
            sf = ScannedFile(
                path=file_path,
                rel_path=os.path.relpath(file_path, source.root_url or "").replace("\\", "/"),
                name=Path(file_path).name,
                ext=ext,
                type="text",
                size_bytes=st.size_bytes,
                mtime=st.mtime,
            )
            await self._index_text_file(source, fs, sf)
            return {"success": True, "type": "text", "path": file_path}

        # 二进制/媒体文件：通过 .kbdesc 描述
        desc_path = DescManager.get_desc_path(file_path)
        if os.path.exists(desc_path):
            # 检查描述是否过期
            kbdesc = DescManager.read(desc_path)
            if kbdesc and not kbdesc.is_stale:
                # 描述有效，索引描述内容
                ds = os.stat(desc_path)
                sf = ScannedFile(
                    path=desc_path,
                    rel_path=os.path.relpath(desc_path, source.root_url or "").replace("\\", "/"),
                    name=Path(desc_path).name,
                    ext=".kbdesc",
                    type="text",
                    size_bytes=ds.st_size,
                    mtime=ds.st_mtime,
                    has_desc=True,
                    desc_path=desc_path,
                )
                await self._index_text_file(source, fs, sf,
                                             orig_file=file_path)
                return {"success": True, "type": "media_with_desc",
                        "path": file_path, "desc_path": desc_path}
            else:
                # 描述过期，标记需更新
                return {"success": False,
                        "error": f"Description stale: {kbdesc.stale_reason if kbdesc else 'unknown'}",
                        "stale": True, "path": file_path}
        else:
            # 无描述文件，记录缺失
            self._state.mark_missing_desc(source.id, file_path)
            return {"success": False,
                    "error": "No .kbdesc description file found",
                    "missing_desc": True, "path": file_path}

    # ── 核心处理 ──

    async def _process_files(self, source: KnowledgeSource,
                              fs: FileSystemAdapter,
                              scanned: list[ScannedFile]) -> dict:
        """异步处理扫描文件列表。"""
        text_files = [sf for sf in scanned if sf.type == "text"]
        binary_no_desc = [sf for sf in scanned
                          if sf.type == "binary" and not sf.has_desc]

        print(f"  Found {len(scanned)} files: "
              f"{len(text_files)} text, {len(binary_no_desc)} missing desc")

        # 标记缺失描述
        for sf in binary_no_desc:
            self._state.mark_missing_desc(source.id, sf.path)

        # 异步批量读取文件内容
        texts_and_metas = await self._read_texts_async(fs, text_files)

        # 批量嵌入
        indexed = 0
        file_records = []
        folder_texts: dict[str, list[str]] = {}

        batch_size = self._config.batch_size
        for batch_start in range(0, len(texts_and_metas), batch_size):
            batch = texts_and_metas[batch_start:batch_start + batch_size]
            batch_texts = [t for t, _ in batch]
            batch_metas = [m for _, m in batch]

            # 通过 asyncio.to_thread 让 ONNX 推理在线程中执行
            vectors = await asyncio.to_thread(
                self._embedder.encode_batch, batch_texts
            )

            for i, (text, meta) in enumerate(zip(batch_texts, batch_metas)):
                content_hash = hashlib.md5(
                    text[:65536].encode("utf-8", errors="replace")
                ).hexdigest()

                orig_file = None
                if meta.has_desc and meta.desc_path:
                    orig_file = (meta.desc_path.rsplit(".kbdesc", 1)[0]
                                 if meta.desc_path.endswith(".kbdesc")
                                 else None)

                record = {
                    "id": hashlib.md5(
                        f"{source.id}:{meta.path}".encode()
                    ).hexdigest(),
                    "source_id": source.id,
                    "path": meta.path,
                    "rel_path": meta.rel_path,
                    "name": meta.name,
                    "ext": meta.ext,
                    "type": meta.type,
                    "size_bytes": meta.size_bytes,
                    "mtime": meta.mtime,
                    "vector": vectors[i].tolist(),
                    "indexed_at": time.time(),
                    "text_snippet": text[:1000],
                    "orig_file": orig_file or "",
                    "status": "indexed",
                }
                file_records.append(record)

                # 收集文件夹信息
                folder = str(Path(meta.path).parent)
                if folder not in folder_texts:
                    folder_texts[folder] = []
                folder_texts[folder].append(
                    f"{meta.name}: {text[:200].replace(chr(10), ' ')}"
                )

                self._state.mark_indexed(
                    source.id, meta.path, meta.mtime,
                    meta.size_bytes, content_hash,
                    rel_path=meta.rel_path, name=meta.name,
                )

            indexed += len(batch)

        # 批量写入向量库
        if file_records:
            await asyncio.to_thread(self._vector_store.add_files, file_records)

        # 索引文件夹描述
        await asyncio.to_thread(
            self._index_folders, source, fs, folder_texts, scanned
        )

        desc_updated = 0
        print(f"  Indexed {indexed} text files (including .kbdesc).")
        return {"scanned": len(scanned), "indexed": indexed,
                "desc_updated": desc_updated}

    async def _read_texts_async(self, fs: FileSystemAdapter,
                                 files: list[ScannedFile]) -> list[tuple[str, ScannedFile]]:
        """异步并发读取多个文本文件。"""
        async def read_one(sf: ScannedFile) -> tuple[str, ScannedFile]:
            try:
                content = await asyncio.to_thread(fs.read_text, sf.path)
                return (content, sf)
            except Exception as e:
                print(f"  [WARN] Cannot read {sf.path}: {e}")
                return ("", sf)

        tasks = [read_one(sf) for sf in files]
        results = await asyncio.gather(*tasks)
        return [(t, m) for t, m in results if t.strip()]

    async def _index_text_file(self, source: KnowledgeSource,
                                fs: FileSystemAdapter, sf: ScannedFile,
                                orig_file: str = "") -> None:
        """索引单个文本文件（含 .kbdesc）。"""
        try:
            content = await asyncio.to_thread(fs.read_text, sf.path)
        except Exception:
            return

        if not content.strip():
            return

        vector = await asyncio.to_thread(self._embedder.encode, content)

        content_hash = hashlib.md5(
            content[:65536].encode("utf-8", errors="replace")
        ).hexdigest()

        record = {
            "id": hashlib.md5(f"{source.id}:{sf.path}".encode()).hexdigest(),
            "source_id": source.id,
            "path": sf.path,
            "rel_path": sf.rel_path,
            "name": sf.name,
            "ext": sf.ext,
            "type": sf.type,
            "size_bytes": sf.size_bytes,
            "mtime": sf.mtime,
            "vector": vector.tolist(),
            "indexed_at": time.time(),
            "text_snippet": content[:1000],
            "orig_file": orig_file,
            "status": "indexed",
        }

        await asyncio.to_thread(self._vector_store.add_files, [record])
        self._state.mark_indexed(
            source.id, sf.path, sf.mtime, sf.size_bytes, content_hash,
            rel_path=sf.rel_path, name=sf.name,
        )

    def _index_folders(self, source: KnowledgeSource, fs: FileSystemAdapter,
                       folder_texts: dict[str, list[str]],
                       scanned: list[ScannedFile]) -> None:
        """生成并索引文件夹摘要。"""
        folder_records = []
        now = time.time()

        all_folders = set()
        for sf in scanned:
            folder = str(Path(sf.path).parent)
            all_folders.add(folder)

        for folder in all_folders:
            desc_file = os.path.join(folder, "description.md")
            summary = ""
            summary_source = "auto_generated"

            if fs.exists(desc_file):
                try:
                    summary = fs.read_text(desc_file)
                    summary_source = "manual_description_md"
                except Exception:
                    pass

            if not summary:
                children = folder_texts.get(folder, [])
                if children:
                    folder_name = Path(folder).name or folder
                    summary = f"文件夹 '{folder_name}' 的内容摘要：\n" + "\n".join(
                        children[:50]
                    )
                else:
                    continue

            try:
                vector = self._embedder.encode(summary)
            except Exception:
                continue

            record = {
                "id": hashlib.md5(f"folder:{source.id}:{folder}".encode()).hexdigest(),
                "source_id": source.id,
                "path": folder,
                "name": Path(folder).name or folder,
                "summary": summary[:2000],
                "source": summary_source,
                "vector": vector.tolist(),
                "file_count": len(folder_texts.get(folder, [])),
                "indexed_at": now,
            }
            folder_records.append(record)

        if folder_records:
            self._vector_store.add_folders(folder_records)

    # ── 搜索 ──

    async def search(self, query: str, top_k: int = 10,
                     threshold: float = 0.5,
                     source_id: Optional[str] = None) -> list:
        """异步语义搜索。"""
        query_vec = await asyncio.to_thread(self._embedder.encode, query)
        return self._vector_store.search(
            query_vec, top_k=top_k, threshold=threshold,
            source_id=source_id,
        )

    # ── 描述管理 ──

    async def describe_media(self, source_id: str, media_path: str,
                              description: str, tags: str = "",
                              mime_type: str = "") -> dict:
        """为媒体文件创建或更新 .kbdesc 描述文件。"""
        source = self._find_source(source_id)
        if not source:
            return {"success": False, "error": f"Source not found: {source_id}"}

        if not os.path.exists(media_path):
            return {"success": False, "error": f"File not found: {media_path}"}

        # 添加标签到内容
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                description += f"\n\n## 标签\n{', '.join(tag_list)}"

        # 判断是新建还是更新
        existing = DescManager.read_for_media(media_path)
        if existing:
            # 更新内容，保留元数据
            existing.content = description
            existing.description_type = "manual"
            # 刷新媒体信息
            st = os.stat(media_path)
            existing.media_info.size_bytes = st.st_size
            existing.media_info.mtime = st.st_mtime
            existing.media_info.sha256 = _hash_file(media_path)
            desc_path = DescManager.write(existing)
            action = "updated"
        else:
            desc_path = DescManager.write_auto(media_path, description, mime_type)
            action = "created"

        # 重新索引该描述文件
        await self.index_file(source_id, desc_path)

        return {"success": True, "action": action, "desc_path": desc_path,
                "media_path": media_path}

    async def check_stale_descs(self, source_id: str = "") -> list[KbDesc]:
        """检查所有已知描述文件的过期状态。"""
        stale_list = []
        sources = self._source_manager.get_sources()
        if source_id:
            sources = [s for s in sources if s.id == source_id]

        for source in sources:
            root = source.root_url or ""
            if not root:
                continue
            # 递归搜索所有 .kbdesc
            for folder, dirs, files in os.walk(root):
                if ".kbdes" in dirs:
                    kbdes_dir = os.path.join(folder, ".kbdes")
                    for desc_file in os.listdir(kbdes_dir):
                        if desc_file.endswith(".kbdesc"):
                            desc_path = os.path.join(kbdes_dir, desc_file)
                            kbdesc = DescManager.read(desc_path)
                            if kbdesc and kbdesc.is_stale:
                                stale_list.append(kbdesc)
        return stale_list

    # ── 辅助 ──

    def _find_source(self, source_id: str) -> Optional[KnowledgeSource]:
        for s in self._source_manager.get_sources():
            if s.id == source_id:
                return s
        return None

    def shutdown(self) -> None:
        """关闭线程池。"""
        self._io_executor.shutdown(wait=True)


def _hash_file(file_path: str) -> str:
    """快速哈希文件前 1MB。"""
    import hashlib
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            h.update(f.read(1024 * 1024))
    except Exception:
        return ""
    return h.hexdigest()
