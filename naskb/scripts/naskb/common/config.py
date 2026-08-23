"""Configuration management for NASKB.

Reads and writes config.toml from the work path.
"""
import os
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore


def _llm_endpoint(cfg: dict, default_provider: str, default_model: str,
                  default_base_url: str) -> dict:
    """构造一个 LLM 端点配置 dict（provider/model/api_key/base_url）。"""
    return {
        "provider": cfg.get("provider", default_provider),
        "model": cfg.get("model", default_model),
        "api_key": cfg.get("api_key", ""),
        "base_url": cfg.get("base_url", default_base_url),
    }


class Config:
    """Holds all configuration for a NASKB instance."""

    def __init__(self, work_path: str, data: dict[str, Any] | None = None):
        self.work_path = str(Path(work_path).resolve())
        if data is None:
            data = {}


        # ── [exclusions] ──
        self.exclusions: dict[str, list[str]] = data.get("exclusions", {
            "ext": [".exe", ".dll", ".bin", ".iso", ".tmp"],
            "folder": [".git", ".svn", "__pycache__", "node_modules"],
        })

        # ── [llm] ──
        llm_cfg = data.get("llm", {})

        # ── [llm.text] / [llm.vision] / [llm.audio]（v2 模型分工）──
        # 文本 → DeepSeek（便宜）；图片/音频多模态 → 小米 MiMo V2.5
        self.llm_text: dict = _llm_endpoint(
            llm_cfg.get("text", {}),
            default_provider="deepseek",
            default_model="deepseek-chat",
            default_base_url="https://api.deepseek.com",
        )
        self.llm_vision: dict = _llm_endpoint(
            llm_cfg.get("vision", {}),
            default_provider="mimo",
            default_model="mimo-v2.5",
            default_base_url="https://api.xiaomimimo.com/v1",
        )
        self.llm_audio: dict = _llm_endpoint(
            llm_cfg.get("audio", {}),
            default_provider="mimo",
            default_model="mimo-v2.5",
            default_base_url="https://api.xiaomimimo.com/v1",
        )
        # MiMo key 用户已授权内置（与 image-to-text / voice-to-text 技能一致）
        mimo_key = os.environ.get("MIMO_API_KEY", "")
        if mimo_key:
            self.llm_vision["api_key"] = mimo_key
            self.llm_audio["api_key"] = mimo_key
        self.llm_audio_split_minutes: int = int(
            llm_cfg.get("audio", {}).get("split_minutes", 25))
        self.llm_audio_diarization: bool = bool(
            llm_cfg.get("audio", {}).get("diarization", False))

        # ── [desc]（v2 目录隐藏仓库）──
        desc_cfg = data.get("desc", {})
        self.desc_repo_name: str = desc_cfg.get("repo_name", ".naskb")
        self.desc_analyzer_version: str = desc_cfg.get("analyzer_version", "0.2.0")
        self.desc_hash_max_bytes: Optional[int] = None
        dhmb = desc_cfg.get("hash_max_bytes")
        if dhmb:
            self.desc_hash_max_bytes = int(dhmb)

        # ── [analyzer.video]（v2 视频分级）──
        video_cfg = data.get("analyzer", {}).get("video", {})
        self.video_category_paths: list[dict] = video_cfg.get("category_paths", [])
        self.video_category_keywords: list[dict] = video_cfg.get("category_keywords", [])
        self.video_duration_threshold_min: int = int(
            video_cfg.get("duration_threshold_min", 90))
        self.video_keyframes_max: int = int(video_cfg.get("keyframes_max", 20))
        self.video_keyframe_interval_sec: int = int(
            video_cfg.get("keyframe_interval_sec", 300))

        # ── [analyzer.mineru]（v2 MinerU 后端）──
        mineru_cfg = data.get("analyzer", {}).get("mineru", {})
        self.mineru_enabled: bool = bool(mineru_cfg.get("enabled", False))
        self.mineru_extra_formats: list[str] = mineru_cfg.get(
            "extra_formats", ["html"])
        self.mineru_return_middle_json: bool = bool(
            mineru_cfg.get("return_middle_json", True))
        self.mineru_fast_text_ratio: float = float(
            mineru_cfg.get("fast_text_ratio", 0.3))
        self.mineru_min_text_chars: int = int(
            mineru_cfg.get("min_text_chars", 500))
        self.mineru_model_source: str = mineru_cfg.get("model_source", "")
        self.mineru_bin: str = mineru_cfg.get("bin", "")  # 独立 venv 的 mineru 可执行文件

        # ── [webdav]（NAS 连接信息，单台快捷方式）──
        webdav_cfg = data.get("webdav", {})
        self.webdav_url: str = webdav_cfg.get("url", "")
        self.webdav_user: str = webdav_cfg.get("user", "")
        self.webdav_password: str = webdav_cfg.get("password", "")
        self.webdav_verify_ssl: bool = bool(webdav_cfg.get("verify_ssl", True))

        # ── [pg]（PostgreSQL 向量数据库）──
        pg_cfg = data.get("pg", {})
        self.pg_host: str = pg_cfg.get("host", "")
        self.pg_port: int = int(pg_cfg.get("port", 5432))
        self.pg_user: str = pg_cfg.get("user", "")
        self.pg_password: str = pg_cfg.get("password", "")
        self.pg_database: str = pg_cfg.get("database", "naskb")
        self.pg_vector_table: str = pg_cfg.get("vector_table", "naskb_vectors")
        self.pg_vector_dim: int = int(pg_cfg.get("vector_dim", 512))

        # ── [nas]（NAS 列表：多台各自命名，主配置来源）──
        self.nas_list: list[dict[str, Any]] = []
        for entry in data.get("nas", []):
            if not isinstance(entry, dict):
                continue
            self.nas_list.append({
                "name": str(entry.get("name", "")),
                "host": str(entry.get("host", "")),
                "user": str(entry.get("user", "")),
                "password": str(entry.get("password", "")),
                "webdav_port": int(entry.get("webdav_port", 5006)),
                "webdav_https": bool(entry.get("webdav_https", True)),
                "verify_ssl": bool(entry.get("verify_ssl", False)),
            })

        # ── [analyzer] ──
        analyzer_cfg = data.get("analyzer", {})
        self.analyzer_max_chars: int = int(analyzer_cfg.get("max_chars", 100_000))
        self.analyzer_tmp_dir: str = self._resolve_path(
            analyzer_cfg.get("tmp_dir", "tmp/analyzer/")
        )
        self.analyzer_max_file_mb: int = int(analyzer_cfg.get("max_file_mb", 100))

    @property
    def pg_enabled(self) -> bool:
        """[pg] 是否已配置（host 非空即视为启用）。

        cli/mcp/test 直接访问本属性判定 PG 可用性；未配置时各调用方
        走本地引擎回退链（REQ-R4-13）。此前属性缺失会导致 AttributeError，
        pgstore/reorganizer 一直用 getattr 防御——统一收敛到这里。
        """
        return bool(self.pg_host)

    def _resolve_path(self, rel: str) -> str:
        """Resolve a relative path against work_path; absolute paths kept as-is."""
        p = Path(rel)
        if p.is_absolute():
            return str(p)
        return str(Path(self.work_path) / p)

    def get_nas(self, name: str = "") -> Optional[dict[str, Any]]:
        """按名称取 NAS 条目；name 为空时返回列表第一台；找不到返回 None。"""
        if not self.nas_list:
            return None
        if not name:
            return self.nas_list[0]
        for entry in self.nas_list:
            if entry.get("name") == name:
                return entry
        return None

    def nas_webdav_url(self, entry: Optional[dict[str, Any]] = None) -> str:
        """由 NAS 条目构造 WebDAV 基址，如 https://192.168.5.2:5006/。"""
        entry = entry or self.get_nas() or {}
        scheme = "https" if entry.get("webdav_https", True) else "http"
        return f"{scheme}://{entry.get('host', '')}:{entry.get('webdav_port', 5006)}/"

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

    @staticmethod
    def _toml_str(s: str) -> str:
        """转义 TOML 基本字符串（反斜杠与双引号）。"""
        return s.replace("\\", "\\\\").replace('"', '\\"')

    def save(self) -> None:
        """Write current configuration back to config.toml."""
        config_file = Path(self.work_path) / "config.toml"
        config_file.parent.mkdir(parents=True, exist_ok=True)


        lines: list[str] = []
        lines.append("# NASKB Configuration")
        lines.append("")
        lines.append("")
        lines.append("[exclusions]")
        lines.append(f'ext = [{", ".join(f"\"{e}\"" for e in self.exclusions.get("ext", []))}]')
        lines.append(f'folder = [{", ".join(f"\"{d}\"" for d in self.exclusions.get("folder", []))}]')
        lines.append("")


        lines.append("[llm.text]")
        lines.append(f'provider = "{self.llm_text["provider"]}"')
        lines.append(f'model = "{self.llm_text["model"]}"')
        if self.llm_text.get("api_key"):
            lines.append(f'api_key = "{self.llm_text["api_key"]}"')
        if self.llm_text.get("base_url"):
            lines.append(f'base_url = "{self.llm_text["base_url"]}"')
        lines.append("")
        lines.append("[llm.vision]")
        lines.append(f'provider = "{self.llm_vision["provider"]}"')
        lines.append(f'model = "{self.llm_vision["model"]}"')
        if self.llm_vision.get("api_key"):
            lines.append(f'api_key = "{self.llm_vision["api_key"]}"')
        if self.llm_vision.get("base_url"):
            lines.append(f'base_url = "{self.llm_vision["base_url"]}"')
        lines.append("")
        lines.append("[llm.audio]")
        lines.append(f'provider = "{self.llm_audio["provider"]}"')
        lines.append(f'model = "{self.llm_audio["model"]}"')
        if self.llm_audio.get("api_key"):
            lines.append(f'api_key = "{self.llm_audio["api_key"]}"')
        if self.llm_audio.get("base_url"):
            lines.append(f'base_url = "{self.llm_audio["base_url"]}"')
        lines.append(f"split_minutes = {self.llm_audio_split_minutes}")
        lines.append(f"diarization = {str(self.llm_audio_diarization).lower()}")
        lines.append("")

        # ── [desc]（v2 目录隐藏仓库）──
        lines.append("[desc]")
        lines.append(f'repo_name = "{self.desc_repo_name}"')
        lines.append(f'analyzer_version = "{self.desc_analyzer_version}"')
        if self.desc_hash_max_bytes is not None:
            lines.append(f"hash_max_bytes = {self.desc_hash_max_bytes}")
        lines.append("")

        # ── [analyzer.video]（v2 视频分级）──
        lines.append("[analyzer.video]")
        lines.append(f"duration_threshold_min = {self.video_duration_threshold_min}")
        lines.append(f"keyframes_max = {self.video_keyframes_max}")
        lines.append(f"keyframe_interval_sec = {self.video_keyframe_interval_sec}")
        if self.video_category_paths:
            lines.append("category_paths = [")
            for cp in self.video_category_paths:
                lines.append(f'  {{ category = "{cp.get("category", "")}", path = "{cp.get("path", "")}" }},')
            lines.append("]")
        if self.video_category_keywords:
            lines.append("category_keywords = [")
            for ck in self.video_category_keywords:
                kw = ", ".join(f'"{k}"' for k in ck.get("keywords", []))
                lines.append(f'  {{ category = "{ck.get("category", "")}", keywords = [{kw}] }},')
            lines.append("]")
        lines.append("")

        # ── [analyzer.mineru]（v2 MinerU 后端）──
        lines.append("[analyzer.mineru]")
        lines.append(f"enabled = {str(self.mineru_enabled).lower()}")
        fmts = ", ".join(f'"{f}"' for f in self.mineru_extra_formats)
        lines.append(f"extra_formats = [{fmts}]")
        lines.append(f"return_middle_json = {str(self.mineru_return_middle_json).lower()}")
        lines.append(f"fast_text_ratio = {self.mineru_fast_text_ratio}")
        lines.append(f"min_text_chars = {self.mineru_min_text_chars}")
        if self.mineru_model_source:
            lines.append(f'model_source = "{self.mineru_model_source}"')
        if self.mineru_bin:
            lines.append(f'bin = "{self._format_path(self.mineru_bin)}"')
        lines.append("")

        # ── [webdav]（NAS 连接信息）──
        lines.append("[webdav]")
        lines.append(f'url = "{self._toml_str(self.webdav_url)}"')
        lines.append(f'user = "{self._toml_str(self.webdav_user)}"')
        if self.webdav_password:
            lines.append(f'password = "{self._toml_str(self.webdav_password)}"')
        lines.append(f"verify_ssl = {str(self.webdav_verify_ssl).lower()}")
        lines.append("")

        # ── [pg]（PostgreSQL 向量数据库）──
        if self.pg_host:
            lines.append("[pg]")
            lines.append(f'host = "{self._toml_str(self.pg_host)}"')
            lines.append(f"port = {self.pg_port}")
            lines.append(f'user = "{self._toml_str(self.pg_user)}"')
            if self.pg_password:
                lines.append(f'password = "{self._toml_str(self.pg_password)}"')
            lines.append(f'database = "{self._toml_str(self.pg_database)}"')
            lines.append(f'vector_table = "{self._toml_str(self.pg_vector_table)}"')
            lines.append(f"vector_dim = {self.pg_vector_dim}")
            lines.append("")

        # ── [nas]（NAS 列表）──
        for entry in self.nas_list:
            lines.append("[[nas]]")
            lines.append(f'name = "{self._toml_str(str(entry.get("name", "")))}"')
            lines.append(f'host = "{self._toml_str(str(entry.get("host", "")))}"')
            lines.append(f'user = "{self._toml_str(str(entry.get("user", "")))}"')
            if entry.get("password"):
                lines.append(f'password = "{self._toml_str(str(entry.get("password", "")))}"')
            lines.append(f"webdav_port = {int(entry.get('webdav_port', 5006))}")
            lines.append(f"webdav_https = {str(bool(entry.get('webdav_https', True))).lower()}")
            lines.append(f"verify_ssl = {str(bool(entry.get('verify_ssl', False))).lower()}")
            lines.append("")
            lines.append("")


        # ── [analyzer] ──
        lines.append("[analyzer]")
        lines.append(f"max_chars = {self.analyzer_max_chars}")
        lines.append(f'max_file_mb = {self.analyzer_max_file_mb}')
        tmp_rel = self._format_path(
            os.path.relpath(self.analyzer_tmp_dir, self.work_path))
        lines.append(f'tmp_dir = "{tmp_rel}"')
        lines.append("")

        with open(config_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


    def to_dict(self) -> dict[str, Any]:
        """Full config as dict (for debugging / serialization)."""
        return {
            "work_path": self.work_path,
            "analyzer": {
                "max_chars": self.analyzer_max_chars,
                "tmp_dir": self.analyzer_tmp_dir,
                "max_file_mb": self.analyzer_max_file_mb,
                "video": {
                    "category_paths": self.video_category_paths,
                    "category_keywords": self.video_category_keywords,
                    "duration_threshold_min": self.video_duration_threshold_min,
                    "keyframes_max": self.video_keyframes_max,
                    "keyframe_interval_sec": self.video_keyframe_interval_sec,
                },
                "mineru": {
                    "enabled": self.mineru_enabled,
                    "extra_formats": self.mineru_extra_formats,
                    "return_middle_json": self.mineru_return_middle_json,
                    "fast_text_ratio": self.mineru_fast_text_ratio,
                    "min_text_chars": self.mineru_min_text_chars,
                    "model_source": self.mineru_model_source,
                    "bin": self.mineru_bin,
                },
            },
            "llm_text": self.llm_text,
            "llm_vision": self.llm_vision,
            "llm_audio": self.llm_audio,
            "llm_audio_split_minutes": self.llm_audio_split_minutes,
            "llm_audio_diarization": self.llm_audio_diarization,
            "desc": {
                "repo_name": self.desc_repo_name,
                "analyzer_version": self.desc_analyzer_version,
                "hash_max_bytes": self.desc_hash_max_bytes,
            },
            "nas": self.nas_list,
            "pg": {
                "host": self.pg_host,
                "port": self.pg_port,
                "user": self.pg_user,
                "database": self.pg_database,
                "vector_table": self.pg_vector_table,
                "vector_dim": self.pg_vector_dim,
            },
        }
