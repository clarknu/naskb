"""Index orchestrator for NASKB.

Ties together scanning, embedding, state tracking, and vector storage.
"""
import hashlib
import os
import time
from pathlib import Path
from typing import Optional

from ..common.config import Config
from ..common.embedder import Embedder
from ..common.fs.base import FileSystemAdapter
from ..common.scanner import Scanner, ScannedFile
from ..common.sources import SourceManager, KnowledgeSource
from ..common.state import StateManager
from ..common.vector_store import VectorStore


class Indexer:
    """Orchestrates the full indexing pipeline."""

    def __init__(self, config: Config, embedder: Embedder,
                 vector_store: VectorStore, state: StateManager,
                 source_manager: SourceManager):
        self._config = config
        self._embedder = embedder
        self._vector_store = vector_store
        self._state = state
        self._source_manager = source_manager

    # ── Full Index ──

    def index_full(self, source_ids: Optional[list[str]] = None) -> dict:
        """Full index of all (or specified) sources."""
        sources = self._source_manager.get_sources()
        if source_ids:
            sources = [s for s in sources if s.id in source_ids]

        stats = {"sources": {}, "total_files": 0, "total_indexed": 0}
        for source in sources:
            print(f"\n[naskb] Full index: [{source.id}] {source.name}")
            source_stat = self._index_source_full(source)
            stats["sources"][source.id] = source_stat
            stats["total_files"] += source_stat["scanned"]
            stats["total_indexed"] += source_stat["indexed"]

        self._vector_store.optimize()
        return stats

    def _index_source_full(self, source: KnowledgeSource) -> dict:
        """Full index of a single source. Clears existing records first."""
        fs = self._source_manager.get_fs(source.id)

        # Clear existing records
        self._vector_store.delete_by_source(source.id)
        self._state.clear_source(source.id)

        # Scan
        scanner = Scanner(fs, self._config.exclusions)
        scanned = scanner.scan(source.root_url if source.root_url else fs.root)

        # Process
        return self._process_files(source, fs, scanned)

    # ── Incremental Index ──

    def index_incremental(self, source_ids: Optional[list[str]] = None) -> dict:
        """Incremental index: only process new or changed files."""
        sources = self._source_manager.get_sources()
        if source_ids:
            sources = [s for s in sources if s.id in source_ids]

        stats = {"sources": {}, "total_updated": 0}
        for source in sources:
            print(f"\n[naskb] Incremental index: [{source.id}] {source.name}")
            source_stat = self._index_source_incremental(source)
            stats["sources"][source.id] = source_stat
            stats["total_updated"] += source_stat["updated"]

        return stats

    def _index_source_incremental(self, source: KnowledgeSource) -> dict:
        """Incremental index of a single source."""
        fs = self._source_manager.get_fs(source.id)

        if not source.root_url and hasattr(fs, 'root'):
            root = fs.root
        else:
            root = source.root_url

        scanner = Scanner(fs, self._config.exclusions)
        scanned = scanner.scan(root)

        # Filter to only new/changed files
        to_index = []
        for sf in scanned:
            if sf.type == "text":
                if self._state.has_changed(source.id, sf.path, sf.mtime, sf.size_bytes):
                    to_index.append(sf)
            elif sf.type == "binary":
                # Check both the binary and its desc file
                changed = self._state.has_changed(
                    source.id, sf.path, sf.mtime, sf.size_bytes
                )
                if sf.desc_path:
                    ds = fs.stat(sf.desc_path)
                    if ds:
                        changed = changed or self._state.has_changed(
                            source.id, sf.desc_path, ds.mtime, ds.size_bytes
                        )
                if changed:
                    to_index.append(sf)

        # Also detect deleted files
        indexed_paths = self._state.get_indexed_paths(source.id)
        scanned_paths = {sf.path for sf in scanned}
        for path in indexed_paths - scanned_paths:
            if path not in scanned_paths:
                self._state.mark_deleted(source.id, path)

        if not to_index:
            print(f"  No changes detected.")
            return {"updated": 0, "scanned_total": len(scanned)}

        # Process only changed files
        result = self._process_files(source, fs, to_index)
        result["scanned_total"] = len(scanned)
        result["updated"] = result["indexed"]
        return result

    # ── Single File ──

    def index_file(self, source_id: str, file_path: str) -> bool:
        """Index a single file by path."""
        source = self._find_source(source_id)
        if not source:
            print(f"[naskb] Source not found: {source_id}")
            return False

        fs = self._source_manager.get_fs(source.id)

        if not fs.exists(file_path):
            print(f"[naskb] File not found: {file_path}")
            return False

        st = fs.stat(file_path)
        if not st:
            return False

        ext = Path(file_path).suffix.lower()
        if Scanner.is_text_file(ext):
            sf = ScannedFile(
                path=file_path,
                rel_path=os.path.relpath(file_path, source.root_url).replace("\\", "/"),
                name=Path(file_path).name,
                ext=ext,
                type="text",
                size_bytes=st.size_bytes,
                mtime=st.mtime,
            )
        else:
            desc = Scanner.find_desc_file(fs, file_path)
            if desc:
                ds = fs.stat(desc)
                sf = ScannedFile(
                    path=desc,
                    rel_path=os.path.relpath(desc, source.root_url).replace("\\", "/"),
                    name=Path(desc).name,
                    ext=".md",
                    type="text",
                    size_bytes=ds.size_bytes if ds else 0,
                    mtime=ds.mtime if ds else 0,
                    has_desc=True,
                    desc_path=desc,
                )
            else:
                self._state.mark_missing_desc(source.id, file_path)
                return False

        self._index_text_file(source, fs, sf)
        return True

    # ── Folder Index ──

    def index_folder(self, source_id: str, folder_path: str) -> int:
        """Index all files under a folder."""
        source = self._find_source(source_id)
        if not source:
            return 0

        fs = self._source_manager.get_fs(source.id)
        scanner = Scanner(fs, self._config.exclusions)
        scanned = scanner.scan(folder_path)

        text_files = [sf for sf in scanned if sf.type == "text"]
        result = self._process_files(source, fs, text_files)
        return result["indexed"]

    # ── Core Processing ──

    def _process_files(self, source: KnowledgeSource, fs: FileSystemAdapter,
                       scanned: list[ScannedFile]) -> dict:
        """Process scanned files: read, embed, store."""
        text_files = [sf for sf in scanned if sf.type == "text"]
        binary_no_desc = [sf for sf in scanned
                          if sf.type == "binary" and not sf.has_desc]

        print(f"  Found {len(scanned)} files: "
              f"{len(text_files)} text, {len(binary_no_desc)} missing desc")

        # Mark missing descriptions
        for sf in binary_no_desc:
            self._state.mark_missing_desc(source.id, sf.path)

        # Group text files into batches
        indexed = 0
        file_records = []
        folder_texts: dict[str, list[str]] = {}  # folder_path -> [text snippets]

        batch_texts = []
        batch_metas = []

        for sf in text_files:
            try:
                content = fs.read_text(sf.path)
            except Exception as e:
                print(f"  [WARN] Cannot read {sf.path}: {e}")
                continue

            if not content.strip():
                continue

            batch_texts.append(content)
            batch_metas.append(sf)

            # Collect for folder summaries
            folder = str(Path(sf.path).parent)
            if folder not in folder_texts:
                folder_texts[folder] = []
            snippet = content[:200].replace("\n", " ")
            folder_texts[folder].append(f"{sf.name}: {snippet}")

            # Process in batches
            if len(batch_texts) >= self._config.batch_size:
                self._embed_and_store(source, fs, batch_texts, batch_metas,
                                       file_records)
                indexed += len(batch_texts)
                batch_texts = []
                batch_metas = []

        # Process remaining batch
        if batch_texts:
            self._embed_and_store(source, fs, batch_texts, batch_metas,
                                   file_records)
            indexed += len(batch_texts)

        # Store file records
        if file_records:
            self._vector_store.add_files(file_records)

        # Index folder descriptions
        self._index_folders(source, fs, folder_texts, scanned)

        print(f"  Indexed {indexed} text files.")
        return {"scanned": len(scanned), "indexed": indexed}

    def _embed_and_store(self, source: KnowledgeSource, fs: FileSystemAdapter,
                         texts: list[str], metas: list[ScannedFile],
                         file_records: list[dict]) -> None:
        """Embed texts and prepare records."""
        vectors = self._embedder.encode_batch(texts)

        for i, (text, meta) in enumerate(zip(texts, metas)):
            content_hash = hashlib.md5(
                text[:65536].encode("utf-8", errors="replace")
            ).hexdigest()
            now = time.time()

            # Determine orig_file for media descriptions
            orig_file = None
            if meta.has_desc and meta.desc_path:
                # meta.path is the .md file; find the original binary
                orig_file = meta.desc_path.rsplit(".md", 1)[0] if meta.desc_path.endswith(".md") else None

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
                "indexed_at": now,
                "text_snippet": text[:1000],
                "orig_file": orig_file or "",
                "status": "indexed",
            }
            file_records.append(record)

            # Update state
            self._state.mark_indexed(
                source.id, meta.path, meta.mtime,
                meta.size_bytes, content_hash,
                rel_path=meta.rel_path, name=meta.name,
            )

    def _index_folders(self, source: KnowledgeSource, fs: FileSystemAdapter,
                       folder_texts: dict[str, list[str]],
                       scanned: list[ScannedFile]) -> None:
        """Generate and index folder-level descriptions."""
        folder_records = []
        now = time.time()

        # Collect unique folders from scanned files
        all_folders = set()
        for sf in scanned:
            folder = str(Path(sf.path).parent)
            all_folders.add(folder)

        for folder in all_folders:
            # Check for manual description.md
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
                # Auto-generate from child file snippets
                children = folder_texts.get(folder, [])
                if children:
                    folder_name = Path(folder).name or folder
                    summary = f"文件夹 '{folder_name}' 的内容摘要：\n" + "\n".join(
                        children[:50]  # Limit to 50 items
                    )
                else:
                    continue

            try:
                vector = self._embedder.encode(summary)
            except Exception:
                continue

            record = {
                "id": hashlib.md5(
                    f"folder:{source.id}:{folder}".encode()
                ).hexdigest(),
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

    # ── Helpers ──

    def _find_source(self, source_id: str) -> Optional[KnowledgeSource]:
        for s in self._source_manager.get_sources():
            if s.id == source_id:
                return s
        return None

    # ── Search ──

    def search(self, query: str, top_k: int = 10,
               threshold: float = 0.5,
               source_id: Optional[str] = None):
        """Semantic search over the knowledge base."""
        query_vec = self._embedder.encode(query)
        return self._vector_store.search(
            query_vec, top_k=top_k, threshold=threshold,
            source_id=source_id,
        )
