"""Configuration management for NASKB.

Reads and writes config.toml from the work path.
"""
import os
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore


class Config:
    """Holds all configuration for a NASKB instance."""

    def __init__(self, work_path: str, data: dict[str, Any] | None = None):
        self.work_path = str(Path(work_path).resolve())
        if data is None:
            data = {}

        # ── [model] ──
        model_cfg = data.get("model", {})
        self.model_name: str = model_cfg.get("name", "bge-base-zh-v1.5")
        self.execution_provider: str = model_cfg.get("execution_provider", "directml")
        self.batch_size: int = int(model_cfg.get("batch_size", 32))
        # 推理线程配置 (0=自动检测)
        self.intra_op_threads: int = int(model_cfg.get("intra_op_threads", 0))
        self.inter_op_threads: int = int(model_cfg.get("inter_op_threads", 0))
        # 模型下载镜像 (留空则使用 HuggingFace 官方)
        self.hf_endpoint: str = model_cfg.get("hf_endpoint", "")

        # Derive vector dimension from model name
        if "large" in self.model_name.lower():
            self.model_dim: int = 1024
        else:
            self.model_dim: int = 768

        # ONNX model path (under work_path/models/)
        self.onnx_path: str = str(Path(self.work_path) / "models" / self.model_name)

        # ── [db] ──
        db_cfg = data.get("db", {})
        self.db_path: str = self._resolve_path(db_cfg.get("path", "db/"))

        # ── [state] ──
        state_cfg = data.get("state", {})
        self.state_path: str = self._resolve_path(state_cfg.get("path", "state.db"))

        # ── [[sources]] ──
        self.sources: list[dict[str, Any]] = data.get("sources", [])
        if not self.sources:
            self.sources = [{
                "id": "default",
                "name": "Default",
                "fs_type": "local",
                "root_url": "",
                "enabled": True,
            }]

        # ── [exclusions] ──
        self.exclusions: dict[str, list[str]] = data.get("exclusions", {
            "ext": [".exe", ".dll", ".bin", ".iso", ".tmp"],
            "folder": [".git", ".svn", "__pycache__", "node_modules"],
        })

    def _resolve_path(self, rel: str) -> str:
        """Resolve a relative path against work_path; absolute paths kept as-is."""
        p = Path(rel)
        if p.is_absolute():
            return str(p)
        return str(Path(self.work_path) / p)

    @classmethod
    def from_work_path(cls, work_path: str) -> "Config":
        """Load config.toml from work_path; use defaults if not found."""
        config_file = Path(work_path) / "config.toml"
        data: dict[str, Any] = {}
        if config_file.exists():
            with open(config_file, "rb") as f:
                data = tomllib.load(f)
        return cls(str(work_path), data)

    def _format_path(self, p: str) -> str:
        """Format a path for TOML: use forward slashes and escape backslashes."""
        return p.replace("\\", "/")

    def save(self) -> None:
        """Write current configuration back to config.toml."""
        config_file = Path(self.work_path) / "config.toml"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        db_rel = self._format_path(os.path.relpath(self.db_path, self.work_path))
        state_rel = self._format_path(os.path.relpath(self.state_path, self.work_path))

        lines: list[str] = []
        lines.append("# NASKB Configuration")
        lines.append("")
        lines.append("[model]")
        lines.append(f'name = "{self.model_name}"')
        lines.append(f'execution_provider = "{self.execution_provider}"')
        lines.append(f"batch_size = {self.batch_size}")
        lines.append("")
        lines.append("[db]")
        lines.append(f'path = "{db_rel}"')
        lines.append("")
        lines.append("[state]")
        lines.append(f'path = "{state_rel}"')
        lines.append("")
        lines.append("[exclusions]")
        lines.append(f'ext = [{", ".join(f"\"{e}\"" for e in self.exclusions.get("ext", []))}]')
        lines.append(f'folder = [{", ".join(f"\"{d}\"" for d in self.exclusions.get("folder", []))}]')
        lines.append("")

        for src in self.sources:
            lines.append("[[sources]]")
            lines.append(f'id = "{src["id"]}"')
            lines.append(f'name = "{src["name"]}"')
            lines.append(f'fs_type = "{src["fs_type"]}"')
            # Format URL with forward slashes
            url = src.get("root_url", "").replace("\\", "/")
            lines.append(f'root_url = "{url}"')
            lines.append(f'enabled = {str(src.get("enabled", True)).lower()}')
            if src.get("auth"):
                lines.append("[sources.auth]")
                for k, v in src["auth"].items():
                    lines.append(f'{k} = "{v}"')
            lines.append("")

        with open(config_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def get_enabled_sources(self) -> list[dict[str, Any]]:
        """Return only enabled sources."""
        return [s for s in self.sources if s.get("enabled", True)]

    def update_source(self, source_id: str, updates: dict[str, Any]) -> bool:
        """Update a source by id. Returns True if found."""
        for src in self.sources:
            if src["id"] == source_id:
                src.update(updates)
                return True
        return False

    def remove_source(self, source_id: str) -> bool:
        """Remove a source by id. Returns True if found."""
        for i, src in enumerate(self.sources):
            if src["id"] == source_id:
                self.sources.pop(i)
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Full config as dict (for debugging / serialization)."""
        return {
            "work_path": self.work_path,
            "model_name": self.model_name,
            "model_dim": self.model_dim,
            "execution_provider": self.execution_provider,
            "batch_size": self.batch_size,
            "onnx_path": self.onnx_path,
            "db_path": self.db_path,
            "state_path": self.state_path,
            "sources": self.sources,
            "exclusions": self.exclusions,
        }
