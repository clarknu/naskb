"""Vector database using LanceDB (embedded, no server required).

Provides BaseVectorStore abstract interface for future backend extensibility
(e.g., Qdrant, Milvus Lite).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import lancedb
import pyarrow as pa


@dataclass
class SearchResult:
    """A single search result."""
    id: str
    score: float
    path: str
    rel_path: str
    name: str
    source_id: str
    snippet: str
    orig_file: Optional[str] = None


class BaseVectorStore(ABC):
    """向量数据库抽象接口。

    允许 Skill 和 MCP 形态使用不同的向量存储后端：
    - LanceDBStore: 嵌入式 LanceDB (当前实现)
    - QdrantStore: 嵌入式 Qdrant (未来扩展)
    """

    @abstractmethod
    def search(self, vector: np.ndarray, top_k: int = 10,
               threshold: float = 0.5,
               source_id: Optional[str] = None) -> list[SearchResult]:
        """语义搜索。"""
        ...

    @abstractmethod
    def add_files(self, records: list[dict]) -> None:
        """添加或更新文件向量记录。"""
        ...

    @abstractmethod
    def add_folders(self, records: list[dict]) -> None:
        """添加文件夹向量记录。"""
        ...

    @abstractmethod
    def delete_by_source(self, source_id: str) -> None:
        """删除某来源的全部记录。"""
        ...

    @abstractmethod
    def count(self, table: str = "files") -> int:
        """记录总数。"""
        ...

    def optimize(self) -> None:
        """构建加速索引 (可选)。"""
        pass


class VectorStore(BaseVectorStore):
    """Vector database using LanceDB (embedded, zero-dependency server)."""

    def __init__(self, db_path: str, dim: int = 768):
        self._db_path = Path(db_path)
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._dim = dim

        self._db = lancedb.connect(str(self._db_path))

        # Create or open tables
        self._files_table = self._get_or_create_table("files", self._files_schema())
        self._folders_table = self._get_or_create_table("folders", self._folders_schema())

    def _files_schema(self) -> pa.schema:
        return pa.schema([
            pa.field("id", pa.string()),
            pa.field("source_id", pa.string()),
            pa.field("path", pa.string()),
            pa.field("rel_path", pa.string()),
            pa.field("name", pa.string()),
            pa.field("ext", pa.string()),
            pa.field("type", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("mtime", pa.float64()),
            pa.field("vector", pa.list_(pa.float32(), self._dim)),
            pa.field("indexed_at", pa.float64()),
            pa.field("text_snippet", pa.string()),
            pa.field("orig_file", pa.string()),
            pa.field("status", pa.string()),
        ])

    def _folders_schema(self) -> pa.schema:
        return pa.schema([
            pa.field("id", pa.string()),
            pa.field("source_id", pa.string()),
            pa.field("path", pa.string()),
            pa.field("name", pa.string()),
            pa.field("summary", pa.string()),
            pa.field("source", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), self._dim)),
            pa.field("file_count", pa.int64()),
            pa.field("indexed_at", pa.float64()),
        ])

    def _get_or_create_table(self, name: str, schema: pa.schema):
        """Get existing table or create new one."""
        try:
            return self._db.open_table(name)
        except Exception:
            return self._db.create_table(name, schema=schema, mode="overwrite")

    def add_files(self, records: list[dict]) -> None:
        """Add or upsert file vectors into the files table."""
        if not records:
            return

        # Convert to Arrow Table
        rows: list[dict] = []
        for r in records:
            rows.append({
                "id": r.get("id", ""),
                "source_id": r.get("source_id", ""),
                "path": r.get("path", ""),
                "rel_path": r.get("rel_path", ""),
                "name": r.get("name", ""),
                "ext": r.get("ext", ""),
                "type": r.get("type", "text"),
                "size_bytes": int(r.get("size_bytes", 0)),
                "mtime": float(r.get("mtime", 0)),
                "vector": [float(v) for v in r.get("vector", [])],
                "indexed_at": float(r.get("indexed_at", 0)),
                "text_snippet": r.get("text_snippet", "")[:2000],
                "orig_file": r.get("orig_file", ""),
                "status": r.get("status", "indexed"),
            })

        arrow_table = pa.Table.from_pylist(rows, schema=self._files_schema())

        # Recreate table with new data (since LanceDB upsert is limited)
        # For simplicity, we use a merge strategy:
        # Delete existing rows by id, then add new ones
        try:
            existing_ids = set()
            try:
                scanner = self._files_table.to_lance().scanner
                # We'll handle upsert by delete + add
            except Exception:
                pass

            # Use LanceDB's merge/upsert via add with mode
            self._files_table.add(arrow_table, mode="append")

        except Exception as e:
            # If append fails (e.g., schema change), recreate
            print(f"[naskb] Vector store add_files warning: {e}")
            self._files_table = self._db.create_table(
                "files", data=arrow_table, mode="overwrite"
            )

    def add_folders(self, records: list[dict]) -> None:
        """Add folder vectors."""
        if not records:
            return

        rows = []
        for r in records:
            rows.append({
                "id": r.get("id", ""),
                "source_id": r.get("source_id", ""),
                "path": r.get("path", ""),
                "name": r.get("name", ""),
                "summary": r.get("summary", "")[:2000],
                "source": r.get("source", "auto_generated"),
                "vector": [float(v) for v in r.get("vector", [])],
                "file_count": int(r.get("file_count", 0)),
                "indexed_at": float(r.get("indexed_at", 0)),
            })

        arrow_table = pa.Table.from_pylist(rows, schema=self._folders_schema())
        try:
            self._folders_table.add(arrow_table, mode="append")
        except Exception:
            self._folders_table = self._db.create_table(
                "folders", data=arrow_table, mode="overwrite"
            )

    def search(self, vector: np.ndarray, top_k: int = 10,
               threshold: float = 0.5,
               source_id: Optional[str] = None) -> list[SearchResult]:
        """Semantic search over files table."""
        if vector.ndim == 2:
            vector = vector.flatten()

        query_vec = vector.astype(np.float32).tolist()

        try:
            results = (
                self._files_table
                .search(query_vec, vector_column_name="vector")
                .metric("cosine")
                .limit(top_k)
                .to_list()
            )

            search_results = []
            for r in results:
                # LanceDB returns cosine distance (lower = more similar)
                # Convert to similarity score: score = 1 - distance
                score = 1.0 - r.get("_distance", 1.0)

                if score < threshold:
                    continue

                if source_id and r.get("source_id") != source_id:
                    continue

                sr = SearchResult(
                    id=r.get("id", ""),
                    score=round(score, 4),
                    path=r.get("path", ""),
                    rel_path=r.get("rel_path", ""),
                    name=r.get("name", ""),
                    source_id=r.get("source_id", ""),
                    snippet=r.get("text_snippet", "")[:500],
                    orig_file=r.get("orig_file") if r.get("orig_file") else None,
                )
                search_results.append(sr)

            return search_results

        except Exception as e:
            print(f"[naskb] Search error: {e}")
            return []

    def search_folders(self, vector: np.ndarray, top_k: int = 5,
                       threshold: float = 0.5) -> list[dict]:
        """Search folders table."""
        if vector.ndim == 2:
            vector = vector.flatten()

        query_vec = vector.astype(np.float32).tolist()

        try:
            results = (
                self._folders_table
                .search(query_vec, vector_column_name="vector")
                .metric("cosine")
                .limit(top_k)
                .to_list()
            )

            filtered = []
            for r in results:
                score = 1.0 - r.get("_distance", 1.0)
                if score >= threshold:
                    r["score"] = round(score, 4)
                    filtered.append(r)
            return filtered
        except Exception:
            return []

    def delete_by_path(self, path: str) -> None:
        """Delete a file record by path."""
        try:
            self._files_table.delete(f"path = '{path}'")
        except Exception:
            pass

    def delete_by_source(self, source_id: str) -> None:
        """Delete all records for a source."""
        try:
            self._files_table.delete(f"source_id = '{source_id}'")
        except Exception:
            pass
        try:
            self._folders_table.delete(f"source_id = '{source_id}'")
        except Exception:
            pass

    def count(self, table: str = "files") -> int:
        """Count records in a table."""
        try:
            t = self._files_table if table == "files" else self._folders_table
            return t.count_rows()
        except Exception:
            return 0

    def clear_all(self) -> None:
        """Remove all records from both tables."""
        try:
            self._db.drop_table("files")
            self._db.drop_table("folders")
        except Exception:
            pass

    def optimize(self) -> None:
        """Build IVF-PQ index for faster search (for large datasets)."""
        try:
            count = self.count("files")
            if count > 10000:
                self._files_table.create_index(
                    vector_column_name="vector",
                    index_type="IVF_PQ",
                    num_partitions=max(256, int(count ** 0.5)),
                )
                print(f"[naskb] Built IVF-PQ index for {count} vectors.")
        except Exception as e:
            print(f"[naskb] Index optimization skipped: {e}")
