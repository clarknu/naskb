"""SQLite-based index state tracker for NASKB.

Tracks which files have been indexed, their metadata, and change detection.
"""
import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Optional


class StateManager:
    """Tracks file indexing state using SQLite."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS indexed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                path TEXT NOT NULL,
                rel_path TEXT,
                name TEXT,
                mtime REAL,
                size_bytes INTEGER,
                content_hash TEXT,
                status TEXT DEFAULT 'indexed',
                indexed_at REAL,
                UNIQUE(source_id, path)
            );

            CREATE TABLE IF NOT EXISTS missing_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                path TEXT NOT NULL,
                reason TEXT DEFAULT 'no_description_file',
                recorded_at REAL,
                UNIQUE(source_id, path)
            );

            CREATE INDEX IF NOT EXISTS idx_files_source
                ON indexed_files(source_id);
            CREATE INDEX IF NOT EXISTS idx_files_status
                ON indexed_files(status);
            CREATE INDEX IF NOT EXISTS idx_missing_source
                ON missing_descriptions(source_id);
        """)
        self._conn.commit()

    # ── Change Detection ──

    def has_changed(self, source_id: str, path: str,
                    mtime: float, size_bytes: int) -> bool:
        """Check if a file needs re-indexing.

        Returns True if:
        - File not in database
        - mtime differs from stored value
        - size_bytes differs from stored value
        - Status is 'deleted' or 'outdated'
        """
        row = self._conn.execute(
            "SELECT mtime, size_bytes, status FROM indexed_files "
            "WHERE source_id = ? AND path = ?",
            (source_id, path)
        ).fetchone()

        if row is None:
            return True  # New file

        stored_mtime, stored_size, status = row

        if status in ("deleted", "outdated"):
            return True

        if stored_mtime is None or stored_size is None:
            return True  # Incomplete record, re-index

        if abs(stored_mtime - mtime) > 0.001:
            return True

        if stored_size != size_bytes:
            return True

        return False

    # ── Marking Operations ──

    def mark_indexed(self, source_id: str, path: str, mtime: float,
                     size_bytes: int, content_hash: str = "",
                     rel_path: str = "", name: str = "") -> None:
        """Mark a file as successfully indexed (upsert)."""
        now = time.time()
        self._conn.execute(
            """INSERT INTO indexed_files
               (source_id, path, rel_path, name, mtime, size_bytes,
                content_hash, status, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'indexed', ?)
               ON CONFLICT(source_id, path) DO UPDATE SET
               mtime=excluded.mtime,
               size_bytes=excluded.size_bytes,
               content_hash=excluded.content_hash,
               status='indexed',
               indexed_at=excluded.indexed_at""",
            (source_id, path, rel_path, name, mtime, size_bytes,
             content_hash, now)
        )
        self._conn.commit()

    def mark_missing_desc(self, source_id: str, path: str,
                          reason: str = "no_description_file") -> None:
        """Record a file that could not be indexed (missing .md description)."""
        now = time.time()
        # Also update indexed_files status
        self._conn.execute(
            """INSERT INTO indexed_files
               (source_id, path, status, indexed_at)
               VALUES (?, ?, 'missing_desc', ?)
               ON CONFLICT(source_id, path) DO UPDATE SET
               status='missing_desc', indexed_at=?""",
            (source_id, path, now, now)
        )
        self._conn.execute(
            """INSERT OR REPLACE INTO missing_descriptions
               (source_id, path, reason, recorded_at)
               VALUES (?, ?, ?, ?)""",
            (source_id, path, reason, now)
        )
        self._conn.commit()

    def mark_skipped(self, source_id: str, path: str,
                     reason: str = "excluded") -> None:
        """Mark a file as skipped by exclusion rules."""
        now = time.time()
        self._conn.execute(
            """INSERT INTO indexed_files
               (source_id, path, status, indexed_at)
               VALUES (?, ?, 'skipped', ?)
               ON CONFLICT(source_id, path) DO UPDATE SET
               status='skipped', indexed_at=?""",
            (source_id, path, now, now)
        )
        self._conn.commit()

    def mark_deleted(self, source_id: str, path: str) -> None:
        """Mark a file as removed from disk."""
        self._conn.execute(
            "UPDATE indexed_files SET status='deleted', indexed_at=? "
            "WHERE source_id = ? AND path = ?",
            (time.time(), source_id, path)
        )
        self._conn.commit()

    def mark_outdated(self, source_id: str, path: str) -> None:
        """Explicitly mark a file as outdated."""
        self._conn.execute(
            "UPDATE indexed_files SET status='outdated', indexed_at=? "
            "WHERE source_id = ? AND path = ?",
            (time.time(), source_id, path)
        )
        self._conn.commit()

    # ── Query Operations ──

    def get_stats(self) -> dict:
        """Get indexing statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) FROM indexed_files"
        ).fetchone()[0]

        indexed = self._conn.execute(
            "SELECT COUNT(*) FROM indexed_files WHERE status='indexed'"
        ).fetchone()[0]

        outdated = self._conn.execute(
            "SELECT COUNT(*) FROM indexed_files WHERE status='outdated'"
        ).fetchone()[0]

        missing_desc = self._conn.execute(
            "SELECT COUNT(*) FROM indexed_files WHERE status='missing_desc'"
        ).fetchone()[0]

        skipped = self._conn.execute(
            "SELECT COUNT(*) FROM indexed_files WHERE status='skipped'"
        ).fetchone()[0]

        deleted = self._conn.execute(
            "SELECT COUNT(*) FROM indexed_files WHERE status='deleted'"
        ).fetchone()[0]

        # By source
        by_source_rows = self._conn.execute(
            "SELECT source_id, status, COUNT(*) FROM indexed_files "
            "GROUP BY source_id, status"
        ).fetchall()

        by_source: dict = {}
        for source_id, status, count in by_source_rows:
            if source_id not in by_source:
                by_source[source_id] = {}
            by_source[source_id][status] = count

        return {
            "total": total,
            "indexed": indexed,
            "outdated": outdated,
            "missing_desc": missing_desc,
            "skipped": skipped,
            "deleted": deleted,
            "by_source": by_source,
        }

    def get_missing_descriptions(self,
                                  source_id: Optional[str] = None) -> list[dict]:
        """Get files missing description files."""
        query = "SELECT source_id, path, reason, recorded_at FROM missing_descriptions"
        params = ()
        if source_id:
            query += " WHERE source_id = ?"
            params = (source_id,)

        rows = self._conn.execute(query, params).fetchall()
        return [
            {"source_id": r[0], "path": r[1], "reason": r[2], "recorded_at": r[3]}
            for r in rows
        ]

    def get_outdated_files(self,
                            source_id: Optional[str] = None) -> list[dict]:
        """Get files that need re-indexing."""
        query = ("SELECT source_id, path, rel_path, name, mtime, size_bytes "
                 "FROM indexed_files WHERE status = 'outdated'")
        params = ()
        if source_id:
            query += " AND source_id = ?"
            params = (source_id,)

        rows = self._conn.execute(query, params).fetchall()
        return [
            {"source_id": r[0], "path": r[1], "rel_path": r[2],
             "name": r[3], "mtime": r[4], "size_bytes": r[5]}
            for r in rows
        ]

    def get_indexed_paths(self, source_id: str) -> set[str]:
        """Get set of all indexed file paths for a source."""
        rows = self._conn.execute(
            "SELECT path FROM indexed_files WHERE source_id = ?",
            (source_id,)
        ).fetchall()
        return {r[0] for r in rows}

    def clear_source(self, source_id: str) -> None:
        """Remove all records for a source."""
        self._conn.execute(
            "DELETE FROM indexed_files WHERE source_id = ?", (source_id,)
        )
        self._conn.execute(
            "DELETE FROM missing_descriptions WHERE source_id = ?", (source_id,)
        )
        self._conn.commit()

    # ── Utilities ──

    @staticmethod
    def compute_hash(text: str, max_len: int = 65536) -> str:
        """Compute MD5 hash of text content (first max_len chars)."""
        return hashlib.md5(
            text[:max_len].encode("utf-8", errors="replace")
        ).hexdigest()

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()
