"""File system adapters for NASKB."""
from .base import FileSystemAdapter, FileStat, _FsspecAdapter
from .local import LocalAdapter

__all__ = ["FileSystemAdapter", "FileStat", "LocalAdapter"]
