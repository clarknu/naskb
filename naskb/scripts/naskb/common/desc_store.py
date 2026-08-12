"""NaskbStore — 目录隐藏描述仓库（v2 架构核心）。

取代 Phase 1 的 `.sidecar.json` 同行机制（已废弃）：
每个 NAS 目录下建一个隐藏仓库 `.naskb/`，集中存放该目录所有文件的描述。

```
NAS 目录/
├── IMG_001.jpg
├── 合同.pdf
└── .naskb/                    ← 隐藏描述仓库
    ├── meta.json              ← 仓库元数据（schema 版本/更新时间/模型快照）
    ├── index.json             ← 文件级描述索引（files[]）
    ├── folder.json            ← 目录级描述（代码/软件/项目目录）
    └── artifacts/             ← 文档解析产物（HTML/md/middle.json/images）
```

设计原则（v2 拍板）:
- 图片等媒体：描述集中在 index.json，不在每个文件旁放描述文件
- 代码/软件/发布包目录：不逐文件分析，只分析目录结构 → folder.json
- 原子写：tmp + rename，进程内锁串行化
- index.json 中 path 为相对仓库所在目录的路径；provenance 记录绝对历史路径
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from .fs.base import FileSystemAdapter

REPO_DIR_NAME = ".naskb"
FILES_DIR_NAME = "files"       # 每源文件一个独立原数据文件
INDEX_SCHEMA = 2

# 大字段：只存进独立原数据文件（files/<rel>.json），不进 index.json
# （避免文件多/全文提取后 index.json 膨胀到无法一次性读取）
_LARGE_FIELDS = ("content_description", "transcription", "ocr_text", "images")

# 全局写锁：index.json 是目录级单文件，进程内串行化写入
# 用 RLock：set_entry 外层持锁后内部 _write_json_atomic 再次获取（同一线程重入）
_write_lock = threading.RLock()


# ═══════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════


@dataclass
class FileEntry:
    """index.json 中一个文件的描述条目。"""
    path: str = ""                      # 相对 .naskb 所在目录
    file_hash: str = ""
    analyzed_at: str = ""
    analyzer_version: str = ""
    file_type: str = ""
    size_bytes: int = 0
    mtime: float = 0.0
    processing_policy: str = "full"     # full | metadata_only | keyframes_only
    # analysis
    content_description: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    language: str = "zh"
    confidence: float = 0.0
    # 媒体 / 抽取图
    images: list[dict] = field(default_factory=list)   # [{path, description, region}]
    transcription: Optional[str] = None
    ocr_text: Optional[str] = None
    # 元数据
    exif: dict = field(default_factory=dict)
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    # 溯源
    original_path: str = ""
    moved_from: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "file_hash": self.file_hash,
            "analyzed_at": self.analyzed_at,
            "analyzer_version": self.analyzer_version,
            "file_type": self.file_type,
            "size_bytes": int(self.size_bytes),
            "mtime": float(self.mtime),
            "processing_policy": self.processing_policy,
            "analysis": {
                "content_description": self.content_description,
                "category": self.category,
                "tags": list(self.tags),
                "summary": self.summary,
                "language": self.language,
                "confidence": float(self.confidence),
            },
            "images": [dict(i) for i in self.images],
            "transcription": self.transcription,
            "ocr_text": self.ocr_text,
            "exif": dict(self.exif),
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "provenance": {
                "original_path": self.original_path,
                "moved_from": list(self.moved_from),
            },
        }

    @classmethod
    def from_dict(cls, data: Any) -> "FileEntry":
        if not isinstance(data, dict):
            raise ValueError("条目不是 JSON 对象")
        analysis = data.get("analysis") or {}
        prov = data.get("provenance") or {}
        return cls(
            path=str(data.get("path", "")),
            file_hash=str(data.get("file_hash", "")),
            analyzed_at=str(data.get("analyzed_at", "")),
            analyzer_version=str(data.get("analyzer_version", "")),
            file_type=str(data.get("file_type", "")),
            size_bytes=_int(data.get("size_bytes")),
            mtime=_float(data.get("mtime")),
            processing_policy=str(data.get("processing_policy", "full")),
            content_description=str(analysis.get("content_description", "")),
            category=str(analysis.get("category", "")),
            tags=[str(t) for t in (analysis.get("tags") or [])],
            summary=str(analysis.get("summary", "")),
            language=str(analysis.get("language", "zh")),
            confidence=_float(analysis.get("confidence")),
            images=[dict(i) for i in (data.get("images") or [])],
            transcription=_opt_str(data.get("transcription")),
            ocr_text=_opt_str(data.get("ocr_text")),
            exif=dict(data.get("exif") or {}),
            duration_seconds=_opt_float(data.get("duration_seconds")),
            width=_opt_int(data.get("width")),
            height=_opt_int(data.get("height")),
            original_path=str(prov.get("original_path", "")),
            moved_from=[str(p) for p in (prov.get("moved_from") or [])],
        )

    def has_analysis(self) -> bool:
        return bool(self.summary or self.content_description or self.transcription
                    or self.ocr_text or self.images)


@dataclass
class FolderEntry:
    """folder.json 目录级描述。"""
    description: str = ""
    structure: list[dict] = field(default_factory=list)  # [{name,type,summary}]
    file_type_distribution: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    language: str = "zh"
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "structure": [dict(s) for s in self.structure],
            "file_type_distribution": dict(self.file_type_distribution),
            "tags": list(self.tags),
            "summary": self.summary,
            "language": self.language,
            "confidence": float(self.confidence),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "FolderEntry":
        if not isinstance(data, dict):
            return cls()
        return cls(
            description=str(data.get("description", "")),
            structure=[dict(s) for s in (data.get("structure") or [])],
            file_type_distribution=dict(data.get("file_type_distribution") or {}),
            tags=[str(t) for t in (data.get("tags") or [])],
            summary=str(data.get("summary", "")),
            language=str(data.get("language", "zh")),
            confidence=_float(data.get("confidence")),
        )


# ═══════════════════════════════════════════════════════════════════
# 引擎
# ═══════════════════════════════════════════════════════════════════


class NaskbStore:
    """目录隐藏描述仓库读写引擎。"""

    def __init__(self, fs: FileSystemAdapter,
                 analyzer_version: str = "0.2.0",
                 hash_max_bytes: Optional[int] = None):
        self._fs = fs
        self._analyzer_version = analyzer_version
        self._hash_max_bytes = hash_max_bytes

    # ── 路径 ──

    @staticmethod
    def dir_of(file_path: str) -> str:
        """文件路径 → 所在目录路径。"""
        p = file_path.replace("\\", "/")
        idx = p.rfind("/")
        return p[:idx] if idx > 0 else "/"

    def repo_dir(self, dir_path: str) -> str:
        return os.path.join(dir_path, REPO_DIR_NAME).replace("\\", "/")

    def index_path(self, dir_path: str) -> str:
        return os.path.join(self.repo_dir(dir_path), "index.json").replace("\\", "/")

    def folder_path(self, dir_path: str) -> str:
        return os.path.join(self.repo_dir(dir_path), "folder.json").replace("\\", "/")

    def meta_path(self, dir_path: str) -> str:
        return os.path.join(self.repo_dir(dir_path), "meta.json").replace("\\", "/")

    def artifacts_dir(self, dir_path: str) -> str:
        return os.path.join(self.repo_dir(dir_path), "artifacts").replace("\\", "/")

    def files_dir(self, dir_path: str) -> str:
        """独立原数据文件目录（镜像源文件的相对路径）。"""
        return os.path.join(self.repo_dir(dir_path), FILES_DIR_NAME).replace("\\", "/")

    def data_file_path(self, dir_path: str, rel_path: str) -> str:
        """某源文件（相对路径）对应的独立原数据文件路径。

        如 .naskb/files/慈水心境租约.pdf.json；含子目录时镜像目录结构。
        """
        rel = rel_path.replace("\\", "/").lstrip("/")
        return os.path.join(self.files_dir(dir_path), rel + ".json").replace("\\", "/")

    # ── 哈希 ──

    def compute_hash(self, file_path: str) -> str:
        """流式计算文件 sha256，返回 "sha256:<hex>"。

        未配置 hash_max_bytes 时默认截断前 16MB（大文件/WebDAV 下避免
        全量下载计算哈希；变更检测对文档/媒体足够）。
        """
        h = hashlib.sha256()
        total = 0
        limit = self._hash_max_bytes
        if limit is None:
            limit = 16 * 1024 * 1024
        for chunk in self._fs.read_chunks(file_path):
            if limit is not None:
                remaining = limit - total
                if remaining <= 0:
                    break
                chunk = chunk[:remaining]
            h.update(chunk)
            total += len(chunk)
        return f"sha256:{h.hexdigest()}"

    # ── meta ──

    def ensure_repo(self, dir_path: str) -> str:
        """确保目录下存在 .naskb 仓库（含 artifacts/ 与 files/），返回仓库路径。"""
        repo = self.repo_dir(dir_path)
        self._fs.mkdir(repo)
        self._fs.mkdir(self.artifacts_dir(dir_path))
        self._fs.mkdir(self.files_dir(dir_path))
        return repo

    def read_meta(self, dir_path: str) -> Optional[dict]:
        mp = self.meta_path(dir_path)
        if not self._fs.exists(mp):
            return None
        try:
            return json.loads(self._fs.read_text(mp))
        except Exception:
            return None

    def write_meta(self, dir_path: str, data: dict) -> bool:
        mp = self.meta_path(dir_path)
        data.setdefault("schema", INDEX_SCHEMA)
        data["updated_at"] = _now_iso()
        return self._write_json_atomic(mp, data)

    # ── index.json（文件级）──

    def read_index(self, dir_path: str) -> dict:
        """读取目录的 index.json。不存在/损坏返回空结构。"""
        ip = self.index_path(dir_path)
        if not self._fs.exists(ip):
            return {"schema": INDEX_SCHEMA, "updated_at": "", "files": []}
        try:
            data = json.loads(self._fs.read_text(ip))
            if not isinstance(data, dict):
                return {"schema": INDEX_SCHEMA, "updated_at": "", "files": []}
            if not isinstance(data.get("files"), list):
                data["files"] = []
            return data
        except Exception:
            return {"schema": INDEX_SCHEMA, "updated_at": "", "files": []}

    def _write_index(self, dir_path: str, data: dict) -> bool:
        ip = self.index_path(dir_path)
        data.setdefault("schema", INDEX_SCHEMA)
        data["updated_at"] = _now_iso()
        return self._write_json_atomic(ip, data)

    def _write_json_atomic(self, path: str, data: dict) -> bool:
        """原子写：tmp 文件 + move。进程内锁串行化。"""
        with _write_lock:
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            try:
                tmp = f"{path}.tmp-{uuid.uuid4().hex[:8]}"
                self._fs.write_bytes(tmp, payload.encode("utf-8"))
                self._fs.move(tmp, path)
                return True
            except Exception:
                try:
                    if self._fs.exists(tmp):
                        self._fs.delete(tmp)
                except Exception:
                    pass
                return False

    # ── 条目操作（文件级）──

    @staticmethod
    def _strip_large(data: dict) -> dict:
        """index 条目轻量化：去掉大字段（全文/转写/图片描述），保留摘要等。"""
        out = {k: v for k, v in data.items() if k not in _LARGE_FIELDS}
        analysis = out.get("analysis")
        if isinstance(analysis, dict):
            analysis = {k: v for k, v in analysis.items()
                        if k not in _LARGE_FIELDS}
            out["analysis"] = analysis
        return out

    def _entry_has_large(self, raw: dict) -> bool:
        if any(raw.get(k) for k in _LARGE_FIELDS):
            return True
        analysis = raw.get("analysis")
        return bool(isinstance(analysis, dict)
                    and any(analysis.get(k) for k in _LARGE_FIELDS))

    def get_entry(self, file_path: str) -> Optional[FileEntry]:
        """读取某文件的完整描述条目（含全文）。

        优先读独立原数据文件（files/<rel>.json）；旧数据（大字段仍在
        index.json 中）自动懒迁移拆分。
        """
        dir_path = self.dir_of(file_path)
        rel = _rel_path(file_path, dir_path)
        for raw in self.read_index(dir_path).get("files", []):
            if raw.get("path") != rel:
                continue
            df = raw.get("data_file")
            if df:
                df_path = os.path.join(self.files_dir(dir_path),
                                       df).replace("\\", "/")
                try:
                    if self._fs.exists(df_path):
                        return FileEntry.from_dict(
                            json.loads(self._fs.read_text(df_path)))
                except Exception:
                    pass
                return FileEntry.from_dict(raw)  # data_file 缺失，降级轻量条目
            if self._entry_has_large(raw):
                # 旧数据：index 里带全文 → 懒迁移到独立原数据文件
                self._split_entry(dir_path, rel, raw)
            return FileEntry.from_dict(raw)
        return None

    def _split_entry(self, dir_path: str, rel: str, raw: dict) -> None:
        """懒迁移：把 index.json 中携带大字段的旧条目拆到独立原数据文件。"""
        df_path = self.data_file_path(dir_path, rel)
        try:
            self._fs.mkdir(os.path.dirname(df_path))
        except Exception:
            pass
        self._write_json_atomic(df_path, dict(raw))
        light = self._strip_large(dict(raw))
        light["data_file"] = rel + ".json"
        with _write_lock:
            idx = self.read_index(dir_path)
            for r in idx["files"]:
                if r.get("path") == rel:
                    r.clear()
                    r.update(light)
                    break
            self._write_index(dir_path, idx)

    def split_index(self, dir_path: str) -> int:
        """批量拆分：把 index.json 中所有仍携带大字段的旧条目迁到独立
        原数据文件（files/<rel>.json），index.json 只留轻量索引。

        返回拆分条目数。
        """
        idx = self.read_index(dir_path)
        count = 0
        for raw in idx.get("files", []):
            if raw.get("data_file"):
                continue  # 已是新格式
            if self._entry_has_large(raw):
                self._split_entry(dir_path, raw.get("path", ""), raw)
                count += 1
        return count

    def set_entry(self, file_path: str, entry: FileEntry) -> bool:
        """写入/更新某文件的描述条目。

        完整原数据（含全文/转写/图片描述）写入独立文件
        .naskb/files/<rel>.json；index.json 只存轻量索引。
        """
        dir_path = self.dir_of(file_path)
        self.ensure_repo(dir_path)
        if not entry.path:
            entry.path = _rel_path(file_path, dir_path)
        if not entry.analyzed_at:
            entry.analyzed_at = _now_iso()
        if not entry.analyzer_version:
            entry.analyzer_version = self._analyzer_version
        if not entry.file_hash:
            entry.file_hash = self.compute_hash(file_path)

        full = entry.to_dict()
        rel = entry.path
        df_path = self.data_file_path(dir_path, rel)
        try:
            self._fs.mkdir(os.path.dirname(df_path))
        except Exception:
            pass

        with _write_lock:
            # 1) 完整原数据文件（事无巨细：全文/转写/图片描述/EXIF）
            if not self._write_json_atomic(df_path, full):
                return False
            # 2) index.json 轻量条目
            light = self._strip_large(full)
            light["data_file"] = rel + ".json"
            idx = self.read_index(dir_path)
            files = idx["files"]
            replaced = False
            for raw in files:
                if raw.get("path") == rel:
                    raw.clear()
                    raw.update(light)
                    replaced = True
                    break
            if not replaced:
                files.append(light)
            return self._write_index(dir_path, idx)

    def remove_entry(self, file_path: str) -> bool:
        """移除条目（含删除独立原数据文件）。"""
        dir_path = self.dir_of(file_path)
        rel = _rel_path(file_path, dir_path)
        self.remove_entries(dir_path, [rel])
        return True  # 条目不存在也算成功（与旧语义一致）

    def remove_entries(self, dir_path: str, rels: list[str]) -> int:
        """批量移除条目（删除独立原数据文件 + index.json 一次原子写）。

        返回实际移除的条目数；rels 中不存在的条目忽略。
        """
        rels = {r for r in rels if r}
        if not rels:
            return 0
        for rel in rels:
            df_path = self.data_file_path(dir_path, rel)
            try:
                if self._fs.exists(df_path):
                    self._fs.delete(df_path)
            except Exception:
                pass
        with _write_lock:
            idx = self.read_index(dir_path)
            before = len(idx["files"])
            idx["files"] = [f for f in idx["files"]
                            if f.get("path") not in rels]
            removed = before - len(idx["files"])
            if removed:
                self._write_index(dir_path, idx)
            return removed

    def check(self, file_path: str) -> str:
        """检查描述是否仍有效。

        Returns:
            "valid":   有条目且 hash 一致 → 复用
            "stale":   有条目但 hash 不一致 → 需重新分析
            "missing": 无条目 → 新文件
        """
        entry = self.get_entry(file_path)
        if entry is None:
            return "missing"
        try:
            current = self.compute_hash(file_path)
        except Exception:
            return "stale"
        return "valid" if current == entry.file_hash else "stale"

    # ── 跟随：移动 / 删除 ──

    def move_entry(self, src: str, dst: str) -> bool:
        """文件移动时同步移动描述条目。

        目录内移动：只改 path 字段（原子更新）。
        跨目录移动：旧目录 remove + 新目录 set（顺序执行；provenance 保留历史）。
        先移动文件，后处理条目；文件移动失败不处理条目。
        """
        try:
            self._fs.move(src, dst)
        except Exception:
            return False

        entry = self.get_entry(src)
        if entry is None:
            return True  # 无描述，仅文件移动

        src_dir, dst_dir = self.dir_of(src), self.dir_of(dst)
        # original_path 规范化为绝对路径（相对值无意义）
        orig = entry.original_path
        if not orig or ("/" not in orig and "\\" not in orig):
            entry.original_path = src
        if src not in entry.moved_from:
            entry.moved_from.append(src)
        entry.analyzed_at = _now_iso()
        entry.path = _rel_path(dst, dst_dir)

        # 新目录写入条目 + 旧目录移除条目（同目录时也按此顺序，避免残留）
        ok = self.set_entry(dst, entry)
        ok2 = self.remove_entry(src)
        return ok and ok2

    def delete_with_file(self, path: str) -> None:
        """删除文件并清理描述条目。"""
        try:
            self._fs.delete(path)
        except Exception:
            pass
        try:
            self.remove_entry(path)
        except Exception:
            pass

    # ── 扫描 / 孤儿 / 重建 ──

    def find_orphans(self, dir_path: str) -> list[str]:
        """目录下 index.json 有条目但文件已不存在的孤儿条目（相对路径列表）。"""
        idx = self.read_index(dir_path)
        orphans: list[str] = []
        for raw in idx.get("files", []):
            rel = raw.get("path", "")
            if rel and not self._fs.exists(os.path.join(dir_path, rel).replace("\\", "/")):
                orphans.append(rel)
        return orphans

    def scan(self, dir_path: str) -> dict:
        """扫描目录所有文件的描述状态报告（非递归，只看当前目录直接文件）。

        系统垃圾/锁文件完全跳过（不计入 total）；不支持类型计入 ignored
        （analyze-tree 会为它们记录名称推断，不进入 missing）。
        """
        from .exts import is_supported, is_system_file, is_word_lock

        files = [f for f in self._fs.list_files(dir_path, recursive=False)]
        stats = {"total": 0, "valid": 0, "missing": 0,
                 "stale": 0, "ignored": 0,
                 "orphans": len(self.find_orphans(dir_path)),
                 "details": []}
        for f in files:
            if f.is_dir:
                continue
            if is_system_file(f.name) or is_word_lock(f.name):
                continue
            stats["total"] += 1
            if not is_supported(f.ext):
                stats["ignored"] += 1
                stats["details"].append({"path": f.path, "status": "ignored",
                                         "size_bytes": f.size_bytes})
                continue
            status = self.check(f.path)
            stats[status] += 1
            stats["details"].append({"path": f.path, "status": status,
                                     "size_bytes": f.size_bytes})
        return stats

    def rebuild(self, root: str) -> list[FileEntry]:
        """遍历 root 下所有 .naskb/index.json，重建本地索引数据源（无需 LLM）。

        条目带独立原数据文件（files/<rel>.json）时读完整内容。
        """
        result: list[FileEntry] = []
        for f in self._fs.list_files(root, recursive=True):
            if f.name == "index.json" and REPO_DIR_NAME in f.path.replace("\\", "/"):
                try:
                    data = json.loads(self._fs.read_text(f.path))
                    for raw in data.get("files", []):
                        df = raw.get("data_file")
                        if df:
                            df_path = os.path.join(
                                os.path.dirname(f.path), FILES_DIR_NAME,
                                df).replace("\\", "/")
                            try:
                                if self._fs.exists(df_path):
                                    result.append(FileEntry.from_dict(
                                        json.loads(self._fs.read_text(df_path))))
                                    continue
                            except Exception:
                                pass
                        result.append(FileEntry.from_dict(raw))
                except Exception:
                    continue
        return result

    # ── folder.json（目录级）──

    def read_folder(self, dir_path: str) -> Optional[FolderEntry]:
        fp = self.folder_path(dir_path)
        if not self._fs.exists(fp):
            return None
        try:
            return FolderEntry.from_dict(json.loads(self._fs.read_text(fp)))
        except Exception:
            return None

    def write_folder(self, dir_path: str, entry: FolderEntry) -> bool:
        self.ensure_repo(dir_path)
        return self._write_json_atomic(self.folder_path(dir_path), entry.to_dict())


# ═══════════════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════════════


def _rel_path(path: str, base_dir: str) -> str:
    """返回 path 相对 base_dir 的路径（不含前导 /）。"""
    p = path.replace("\\", "/")
    b = base_dir.replace("\\", "/").rstrip("/")
    if b and p.startswith(b + "/"):
        return p[len(b) + 1:]
    return p.lstrip("/")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _float(v: Any) -> float:
    try:
        return float(v or 0.0)
    except (TypeError, ValueError):
        return 0.0


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
    return None if v is None else str(v)
