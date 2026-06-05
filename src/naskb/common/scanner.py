"""File scanner with exclusion rules for NASKB."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .fs.base import FileSystemAdapter, FileStat


@dataclass
class ScannedFile:
    """Result of scanning a single file."""
    path: str
    rel_path: str
    name: str
    ext: str
    type: str              # "text" or "binary"
    size_bytes: int
    mtime: float
    has_desc: bool = False
    desc_path: Optional[str] = None
    is_folder_summary: bool = False


class Scanner:
    """Scans a file system tree with exclusion rule support."""

    TEXT_EXTS: set[str] = {
        ".md", ".txt", ".rst", ".org", ".markdown",
        ".textile", ".wiki", ".adoc", ".asciidoc",
        ".py", ".js", ".ts", ".html", ".css", ".json",
        ".yaml", ".yml", ".toml", ".xml", ".csv",
        ".ini", ".cfg", ".conf", ".log",
    }

    def __init__(self, fs: FileSystemAdapter, exclusions: dict):
        """
        Args:
            fs: File system adapter instance
            exclusions: {
                ext: [".exe", ".dll", ...],
                folder: [".git", "node_modules", ...],
                folder_summary: ["vendor", "libs", ...],
            }
        """
        self._fs = fs
        self._excluded_exts: set[str] = {
            e.lower() if e.startswith(".") else f".{e.lower()}"
            for e in exclusions.get("ext", [])
        }
        self._excluded_folders: set[str] = set(
            exclusions.get("folder", [])
        )
        self._summary_folders: set[str] = set(
            exclusions.get("folder_summary", [])
        )

    def scan(self, root: str) -> list[ScannedFile]:
        """Scan a directory recursively, applying exclusion rules."""
        results: list[ScannedFile] = []
        desc_files_seen: set[str] = set()  # Track desc files to avoid duplicates
        self._scan_dir(root, root, results, desc_files_seen)
        return results

    def _scan_dir(self, base_root: str, current_dir: str,
                  results: list[ScannedFile],
                  desc_files_seen: set[str]) -> None:
        """Recursively scan a directory."""
        try:
            entries = self._fs.list_files(current_dir, recursive=False)
        except Exception:
            return

        # Also get directories for recursive scan
        dirs = self._list_dirs(current_dir)

        for d in dirs:
            d_name = d.name
            rel_d = os.path.relpath(d.path, base_root).replace("\\", "/")

            # Check folder exclusion
            if self._is_folder_excluded(d_name, rel_d):
                continue

            # Check folder_summary mode
            is_summary = self._is_summary_folder(d_name, rel_d)

            if is_summary:
                # Only index description.md at folder root
                desc_path = os.path.join(d.path, "description.md")
                if self._fs.exists(desc_path):
                    st = self._fs.stat(desc_path)
                    if st:
                        results.append(ScannedFile(
                            path=desc_path,
                            rel_path=os.path.relpath(desc_path, base_root).replace("\\", "/"),
                            name="description.md",
                            ext=".md",
                            type="text",
                            size_bytes=st.size_bytes,
                            mtime=st.mtime,
                            is_folder_summary=True,
                        ))
                continue  # Don't recurse into summary folder

            # Recurse
            self._scan_dir(base_root, d.path, results, desc_files_seen)

        # Process files
        for entry in entries:
            rel_path = os.path.relpath(entry.path, base_root).replace("\\", "/")

            # Check folder exclusion
            if self._is_path_in_excluded_folder(rel_path):
                continue

            # Check summary folder
            if self._is_path_in_summary_folder(rel_path):
                continue

            # Check extension exclusion
            if self._is_ext_excluded(entry.ext):
                continue  # Silently skip excluded extensions

            # Classify file
            if self.is_text_file(entry.ext):
                # Skip if this is a description file that was (or will be) handled
                # as part of a binary file's description
                if entry.path in desc_files_seen:
                    continue
                # Directly indexable text file
                results.append(ScannedFile(
                    path=entry.path,
                    rel_path=rel_path,
                    name=entry.name,
                    ext=entry.ext,
                    type="text",
                    size_bytes=entry.size_bytes,
                    mtime=entry.mtime,
                ))
            else:
                # Binary file: look for .md description
                desc_path = self.find_desc_file(self._fs, entry.path)
                if desc_path and self._fs.exists(desc_path):
                    desc_files_seen.add(desc_path)  # Prevent duplicate text-file scan
                    st = self._fs.stat(desc_path)
                    results.append(ScannedFile(
                        path=desc_path,
                        rel_path=os.path.relpath(desc_path, base_root).replace("\\", "/"),
                        name=Path(desc_path).name,
                        ext=".md",
                        type="text",
                        size_bytes=st.size_bytes if st else 0,
                        mtime=st.mtime if st else 0,
                        has_desc=True,
                        desc_path=desc_path,
                    ))
                    # Also add the original binary as a reference
                    results.append(ScannedFile(
                        path=entry.path,
                        rel_path=rel_path,
                        name=entry.name,
                        ext=entry.ext,
                        type="binary",
                        size_bytes=entry.size_bytes,
                        mtime=entry.mtime,
                        has_desc=True,
                        desc_path=desc_path,
                    ))
                else:
                    # Binary without description
                    results.append(ScannedFile(
                        path=entry.path,
                        rel_path=rel_path,
                        name=entry.name,
                        ext=entry.ext,
                        type="binary",
                        size_bytes=entry.size_bytes,
                        mtime=entry.mtime,
                        has_desc=False,
                    ))

    def _list_dirs(self, path: str) -> list[FileStat]:
        """List subdirectories."""
        try:
            p = Path(path)
            if not p.exists():
                return []
            dirs = []
            for child in p.iterdir():
                try:
                    if child.is_dir() and not child.is_symlink():
                        dirs.append(FileStat(
                            path=str(child.resolve()),
                            name=child.name,
                            is_dir=True,
                        ))
                except OSError:
                    continue
            return dirs
        except Exception:
            return []

    def _is_folder_excluded(self, name: str, rel_path: str) -> bool:
        """Check if folder should be excluded."""
        if name in self._excluded_folders:
            return True
        # Check path components
        parts = rel_path.replace("\\", "/").split("/")
        return any(p in self._excluded_folders for p in parts)

    def _is_summary_folder(self, name: str, rel_path: str) -> bool:
        """Check if folder is in summary-only mode."""
        if name in self._summary_folders:
            return True
        parts = rel_path.replace("\\", "/").split("/")
        return any(p in self._summary_folders for p in parts)

    def _is_path_in_excluded_folder(self, rel_path: str) -> bool:
        """Check if a file path is under an excluded folder."""
        parts = rel_path.replace("\\", "/").split("/")
        return any(p in self._excluded_folders for p in parts[:-1])

    def _is_path_in_summary_folder(self, rel_path: str) -> bool:
        """Check if file is inside a summary-only folder."""
        parts = rel_path.replace("\\", "/").split("/")
        return any(p in self._summary_folders for p in parts[:-1])

    def _is_ext_excluded(self, ext: str) -> bool:
        """Check if extension is in the exclusion list."""
        return ext.lower() in self._excluded_exts

    @classmethod
    def is_text_file(cls, ext: str) -> bool:
        """Check if extension represents a text file."""
        return ext.lower() in cls.TEXT_EXTS

    @staticmethod
    def find_desc_file(fs: FileSystemAdapter, file_path: str) -> Optional[str]:
        """For a binary file, find corresponding .md description file.

        e.g. photo.jpg → photo.jpg.md in same directory.
        """
        desc_path = file_path + ".md"
        if fs.exists(desc_path):
            return desc_path
        return None
