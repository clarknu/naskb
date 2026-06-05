"""Multi-source manager for NASKB."""
from dataclasses import dataclass, field
from typing import Any, Optional

from .fs.base import FileSystemAdapter


@dataclass
class KnowledgeSource:
    """A configured knowledge source."""
    id: str
    name: str
    fs_type: str
    root_url: str
    auth: Optional[dict] = None
    enabled: bool = True


class SourceManager:
    """Manages multiple knowledge sources."""

    def __init__(self, config: Any):  # Config type
        self._config = config
        self._adapters: dict[str, FileSystemAdapter] = {}

    def get_sources(self) -> list[KnowledgeSource]:
        """Get all enabled sources."""
        sources = []
        for s in self._config.get_enabled_sources():
            sources.append(KnowledgeSource(
                id=s["id"],
                name=s.get("name", s["id"]),
                fs_type=s.get("fs_type", "local"),
                root_url=s.get("root_url", ""),
                auth=s.get("auth"),
                enabled=s.get("enabled", True),
            ))
        return sources

    def get_fs(self, source_id: str) -> FileSystemAdapter:
        """Get or create file system adapter for a source."""
        if source_id in self._adapters:
            return self._adapters[source_id]

        source = self._get_source_config(source_id)
        if not source:
            raise ValueError(f"Source not found: {source_id}")

        fs = FileSystemAdapter.create(
            fs_type=source.get("fs_type", "local"),
            root_url=source.get("root_url", ""),
            auth=source.get("auth"),
        )
        self._adapters[source_id] = fs
        return fs

    def _get_source_config(self, source_id: str) -> Optional[dict]:
        """Get raw source config dict by id."""
        for s in self._config.sources:
            if s.get("id") == source_id:
                return s
        return None

    def add_source(self, source: KnowledgeSource) -> None:
        """Add a new source to config."""
        self._config.sources.append({
            "id": source.id,
            "name": source.name,
            "fs_type": source.fs_type,
            "root_url": source.root_url,
            "auth": source.auth,
            "enabled": source.enabled,
        })
        self._config.save()

    def remove_source(self, source_id: str) -> bool:
        """Remove a source from config."""
        if source_id in self._adapters:
            self._adapters[source_id].close()
            del self._adapters[source_id]

        result = self._config.remove_source(source_id)
        if result:
            self._config.save()
        return result

    def close_all(self) -> None:
        """Close all file system connections."""
        for adapter in self._adapters.values():
            try:
                adapter.close()
            except Exception:
                pass
        self._adapters.clear()
