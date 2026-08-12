"""Sidecar 数据类 — v1 旧格式兼容（仅 desc migrate 迁移时使用）。

v2 已改用 .naskb/ 目录隐藏仓库；这里保留 Schema 数据类
（Analysis/Metadata/Provenance/SidecarData）用于把旧 .sidecar.json
迁移到新格式。
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from .fs.base import FileSystemAdapter, FileStat

SIDECAR_SUFFIX = ".sidecar.json"
SIDECAR_VERSION = 1
ANALYZER_VERSION = "0.1.0"


# ═══════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════


@dataclass
class Analysis:
    """LLM 分析结果（analysis 字段）。"""
    content_description: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    language: str = "zh"
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "content_description": self.content_description,
            "category": self.category,
            "tags": list(self.tags),
            "summary": self.summary,
            "language": self.language,
            "confidence": float(self.confidence),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Analysis":
        if not isinstance(data, dict):
            return cls()
        return cls(
            content_description=str(data.get("content_description", "")),
            category=str(data.get("category", "")),
            tags=[str(t) for t in (data.get("tags") or [])],
            summary=str(data.get("summary", "")),
            language=str(data.get("language", "zh")),
            confidence=float(data.get("confidence", 0.0) or 0.0),
        )


@dataclass
class Metadata:
    """文件元数据（metadata 字段）。"""
    exif: dict[str, Any] = field(default_factory=dict)
    file_type: str = ""
    file_size: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "exif": dict(self.exif),
            "file_type": self.file_type,
            "file_size": int(self.file_size),
            "width": self.width,
            "height": self.height,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Metadata":
        if not isinstance(data, dict):
            return cls()
        return cls(
            exif=dict(data.get("exif") or {}),
            file_type=str(data.get("file_type", "")),
            file_size=int(data.get("file_size", 0) or 0),
            width=_opt_int(data.get("width")),
            height=_opt_int(data.get("height")),
            duration_seconds=_opt_float(data.get("duration_seconds")),
        )


@dataclass
class Provenance:
    """来源追踪（provenance 字段）。"""
    original_path: str = ""
    moved_from: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "original_path": self.original_path,
            "moved_from": list(self.moved_from),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Provenance":
        if not isinstance(data, dict):
            return cls()
        return cls(
            original_path=str(data.get("original_path", "")),
            moved_from=[str(p) for p in (data.get("moved_from") or [])],
        )


@dataclass
class SidecarData:
    """一个完整的 .sidecar.json 内容。"""
    version: int = SIDECAR_VERSION
    file_hash: str = ""
    analyzed_at: str = ""
    analyzer_version: str = ANALYZER_VERSION
    analysis: Analysis = field(default_factory=Analysis)
    metadata: Metadata = field(default_factory=Metadata)
    transcription: Optional[str] = None
    ocr_text: Optional[str] = None
    provenance: Provenance = field(default_factory=Provenance)

    # ── 序列化 ──

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "file_hash": self.file_hash,
            "analyzed_at": self.analyzed_at,
            "analyzer_version": self.analyzer_version,
            "analysis": self.analysis.to_dict(),
            "metadata": self.metadata.to_dict(),
            "transcription": self.transcription,
            "ocr_text": self.ocr_text,
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "SidecarData":
        """解析 sidecar dict。容错：字段缺失/类型错误时使用默认值。"""
        if not isinstance(data, dict):
            raise ValueError("sidecar 内容不是 JSON 对象")
        return cls(
            version=int(data.get("version", SIDECAR_VERSION)),
            file_hash=str(data.get("file_hash", "")),
            analyzed_at=str(data.get("analyzed_at", "")),
            analyzer_version=str(data.get("analyzer_version", ANALYZER_VERSION)),
            analysis=Analysis.from_dict(data.get("analysis")),
            metadata=Metadata.from_dict(data.get("metadata")),
            transcription=_opt_str(data.get("transcription")),
            ocr_text=_opt_str(data.get("ocr_text")),
            provenance=Provenance.from_dict(data.get("provenance")),
        )

    def to_json(self, pretty: bool = True) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        )




def _now_iso() -> str:
    """当前 UTC 时间，ISO8601 格式。"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _opt_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _opt_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _opt_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    return str(v)
