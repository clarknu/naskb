""".kbdes 描述文件管理器。

管理隐藏文件夹 .kbdes/ 下的自描述描述文件 (.kbdesc)。
每个 .kbdesc 文件包含 YAML 元数据头 + Markdown 内容体，
用于描述同级目录下的媒体文件。
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── YAML frontmatter 解析 (零依赖) ──
# 使用内置解析器，避免引入 PyYAML 依赖


@dataclass
class MediaInfo:
    """媒体文件的元信息（嵌入在 .kbdesc 中）。"""
    size_bytes: int = 0
    mtime: float = 0.0
    sha256: str = ""
    mime_type: str = ""
    media_type: str = ""       # image / video / audio / document / other
    width: int = 0
    height: int = 0
    duration_seconds: float = 0.0


@dataclass
class KbDesc:
    """一个 .kbdesc 描述文件的内存表示。"""
    # ── 文件路径 ──
    desc_path: str              # .kbdesc 文件绝对路径
    media_path: str             # 对应媒体文件的绝对路径

    # ── 元数据 ──
    kbdesc_version: str = "1.0"
    generated_at: str = ""      # ISO 8601
    generated_by: str = "naskb-mcp"
    media_info: MediaInfo = field(default_factory=MediaInfo)
    description_type: str = "auto_generated"  # auto_generated | manual | hybrid
    description_hash: str = ""

    # ── 内容 ──
    content: str = ""           # Markdown 正文

    # ── 状态 ──
    is_stale: bool = False      # 描述是否过期
    stale_reason: str = ""      # 过期原因


class DescManager:
    """.kbdes 描述文件管理器。

    在每个文件夹下创建/管理隐藏的 .kbdes/ 子文件夹，
    其中存放对应媒体文件的 .kbdesc 描述文件。
    """

    KBDES_DIR = ".kbdes"
    KBDESC_EXT = ".kbdesc"
    VERSION = "1.0"

    # ── 路径计算 ──

    @classmethod
    def get_desc_path(cls, media_path: str) -> str:
        """给定媒体文件路径，返回其 .kbdesc 描述文件路径。

        Example:
            /photos/IMG_001.jpg → /photos/.kbdes/IMG_001.jpg.kbdesc
        """
        media = Path(media_path)
        kbdes_dir = media.parent / cls.KBDES_DIR
        desc_name = media.name + cls.KBDESC_EXT
        return str(kbdes_dir / desc_name)

    @classmethod
    def get_media_path(cls, desc_path: str) -> Optional[str]:
        """从 .kbdesc 路径反推媒体文件路径。

        Example:
            /photos/.kbdes/IMG_001.jpg.kbdesc → /photos/IMG_001.jpg
        """
        desc = Path(desc_path)
        if desc.suffix != cls.KBDESC_EXT:
            return None
        # 去掉 .kbdesc 后缀，得到 media 文件名
        media_name = desc.name[:-len(cls.KBDESC_EXT)]
        media_path = desc.parent.parent / media_name
        if media_path.exists():
            return str(media_path.resolve())
        return None

    @classmethod
    def list_desc_files(cls, folder: str) -> list[str]:
        """列出文件夹下 .kbdes/ 中的所有 .kbdesc 文件。"""
        kbdes_dir = Path(folder) / cls.KBDES_DIR
        if not kbdes_dir.exists() or not kbdes_dir.is_dir():
            return []
        return sorted([
            str(p.resolve()) for p in kbdes_dir.glob(f"*{cls.KBDESC_EXT}")
            if p.is_file()
        ])

    @classmethod
    def list_media_without_desc(cls, folder: str,
                                 media_exts: set[str] | None = None) -> list[str]:
        """列出文件夹中没有对应 .kbdesc 的媒体文件。"""
        if media_exts is None:
            media_exts = _DEFAULT_MEDIA_EXTS

        kbdes_dir = Path(folder) / cls.KBDES_DIR
        has_desc: set[str] = set()
        if kbdes_dir.exists():
            for desc_file in kbdes_dir.glob(f"*{cls.KBDESC_EXT}"):
                media_name = desc_file.name[:-len(cls.KBDESC_EXT)]
                has_desc.add(media_name)

        missing = []
        try:
            for entry in Path(folder).iterdir():
                if entry.is_file() and entry.suffix.lower() in media_exts:
                    if entry.name not in has_desc:
                        missing.append(str(entry.resolve()))
        except (OSError, PermissionError):
            pass

        return sorted(missing)

    # ── 读取 ──

    @classmethod
    def read(cls, desc_path: str) -> Optional[KbDesc]:
        """读取一个 .kbdesc 文件，解析为 KbDesc 对象。"""
        try:
            raw = Path(desc_path).read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            return None

        metadata, content = _parse_frontmatter(raw)
        if metadata is None:
            return None

        # 构建 MediaInfo
        mi_data = metadata.get("media_info", {})
        media_info = MediaInfo(
            size_bytes=int(mi_data.get("size_bytes", 0)),
            mtime=float(mi_data.get("mtime", 0.0)),
            sha256=mi_data.get("sha256", ""),
            mime_type=mi_data.get("mime_type", ""),
            media_type=mi_data.get("media_type", ""),
            width=int(mi_data.get("width", 0)),
            height=int(mi_data.get("height", 0)),
            duration_seconds=float(mi_data.get("duration_seconds", 0.0)),
        )

        kbdesc = KbDesc(
            desc_path=desc_path,
            media_path=metadata.get("media_file", ""),
            kbdesc_version=metadata.get("kbdesc_version", "1.0"),
            generated_at=metadata.get("generated_at", ""),
            generated_by=metadata.get("generated_by", "naskb-mcp"),
            media_info=media_info,
            description_type=metadata.get("description_type", "auto_generated"),
            description_hash=metadata.get("description_hash", ""),
            content=content.strip(),
        )

        # 检测过期
        kbdesc.is_stale, kbdesc.stale_reason = cls.check_stale(kbdesc)

        return kbdesc

    @classmethod
    def read_for_media(cls, media_path: str) -> Optional[KbDesc]:
        """根据媒体文件路径，读取其对应的 .kbdesc。"""
        desc_path = cls.get_desc_path(media_path)
        if not Path(desc_path).exists():
            return None
        return cls.read(desc_path)

    # ── 写入 ──

    @classmethod
    def write(cls, kbdesc: KbDesc) -> str:
        """将 KbDesc 写入 .kbdesc 文件。返回写入的路径。"""
        desc_path = kbdesc.desc_path or cls.get_desc_path(kbdesc.media_path)
        kbdesc.desc_path = desc_path

        # 确保目录存在
        Path(desc_path).parent.mkdir(parents=True, exist_ok=True)

        # 设置隐藏属性 (Windows)
        _set_hidden(Path(desc_path).parent)

        # 更新哈希
        kbdesc.description_hash = hashlib.md5(
            kbdesc.content.encode("utf-8")
        ).hexdigest()

        if not kbdesc.generated_at:
            kbdesc.generated_at = datetime.now(timezone.utc).isoformat()

        # 序列化
        lines = [
            f"# NASKB Description File v{kbdesc.kbdesc_version}",
            "# ═══════════════════════════════════════",
            "# 元数据区 (YAML frontmatter)",
            "# ═══════════════════════════════════════",
            "---",
            f"kbdesc_version: \"{kbdesc.kbdesc_version}\"",
            f"generated_at: \"{kbdesc.generated_at}\"",
            f"generated_by: \"{kbdesc.generated_by}\"",
            f"media_file: \"{str(Path(kbdesc.media_path).resolve())}\"",
            "media_info:",
            f"  size_bytes: {kbdesc.media_info.size_bytes}",
            f"  mtime: {kbdesc.media_info.mtime}",
            f"  sha256: \"{kbdesc.media_info.sha256}\"",
            f"  mime_type: \"{kbdesc.media_info.mime_type}\"",
            f"  media_type: \"{kbdesc.media_info.media_type}\"",
        ]

        if kbdesc.media_info.width:
            lines.append(f"  width: {kbdesc.media_info.width}")
        if kbdesc.media_info.height:
            lines.append(f"  height: {kbdesc.media_info.height}")
        if kbdesc.media_info.duration_seconds:
            lines.append(f"  duration_seconds: {kbdesc.media_info.duration_seconds}")

        lines.extend([
            f"description_type: \"{kbdesc.description_type}\"",
            f"description_hash: \"{kbdesc.description_hash}\"",
            "# ═══════════════════════════════════════",
            "# 内容区 (Markdown)",
            "# ═══════════════════════════════════════",
            "---",
            "",
            kbdesc.content.strip(),
            "",
        ])

        Path(desc_path).write_text("\n".join(lines), encoding="utf-8")
        return desc_path

    @classmethod
    def write_auto(cls, media_path: str, content: str,
                   mime_type: str = "") -> str:
        """为媒体文件自动生成 .kbdesc 描述文件。"""
        media = Path(media_path)
        if not media.exists():
            raise FileNotFoundError(f"Media file not found: {media_path}")

        st = media.stat()
        sha256 = _hash_file(media_path)
        mime = mime_type or _guess_mime(media.suffix)
        media_type = _guess_media_type(media.suffix)

        kbdesc = KbDesc(
            desc_path=cls.get_desc_path(media_path),
            media_path=str(media.resolve()),
            kbdesc_version=cls.VERSION,
            generated_at=datetime.now(timezone.utc).isoformat(),
            generated_by="naskb-mcp",
            media_info=MediaInfo(
                size_bytes=st.st_size,
                mtime=st.st_mtime,
                sha256=sha256,
                mime_type=mime,
                media_type=media_type,
            ),
            description_type="auto_generated",
            content=content.strip(),
        )

        return cls.write(kbdesc)

    # ── 过期检测 ──

    @classmethod
    def check_stale(cls, kbdesc: KbDesc) -> tuple[bool, str]:
        """检查描述文件是否过期。

        Returns:
            (is_stale, reason)
        """
        media_path = kbdesc.media_path
        if not media_path:
            # 尝试从 desc_path 反推
            media_path = cls.get_media_path(kbdesc.desc_path)
            if media_path:
                kbdesc.media_path = media_path
            else:
                return True, "media_file_not_found"

        media = Path(media_path)
        if not media.exists():
            return True, "media_file_missing"

        try:
            st = media.stat()
        except OSError:
            return True, "media_file_unreadable"

        mi = kbdesc.media_info

        # 比较 mtime
        if abs(mi.mtime - st.st_mtime) > 0.001:
            return True, "mtime_mismatch"

        # 比较 size
        if mi.size_bytes != st.st_size:
            return True, "size_mismatch"

        # 比较版本
        if str(kbdesc.kbdesc_version) != cls.VERSION:
            return True, "kbdesc_version_outdated"

        # 可选：深度哈希比较（较昂贵）
        # 仅在前述检查通过但用户要求严格校验时触发
        # current_hash = _hash_file(media_path)
        # if mi.sha256 and current_hash != mi.sha256:
        #     return True, "content_hash_mismatch"

        return False, ""

    @classmethod
    def find_stale(cls, folder: str) -> list[KbDesc]:
        """在文件夹中查找所有过期的 .kbdesc 文件。"""
        stale = []
        for desc_path in cls.list_desc_files(folder):
            kbdesc = cls.read(desc_path)
            if kbdesc and kbdesc.is_stale:
                stale.append(kbdesc)
        return stale


# ── 辅助函数 ──

_DEFAULT_MEDIA_EXTS: set[str] = {
    # 图片
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif",
    ".svg", ".ico", ".heic", ".heif", ".raw", ".cr2", ".nef", ".arw",
    # 视频
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    ".3gp", ".mts", ".m2ts",
    # 音频
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus",
    # 文档
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp",
    # 压缩包
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
    # 其他二进制
    ".exe", ".dll", ".so", ".dylib", ".bin", ".dat",
    ".psd", ".ai", ".eps", ".sketch",
    ".iso", ".img", ".dmg",
}


_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".rar": "application/vnd.rar",
    ".7z": "application/x-7z-compressed",
}


def _guess_mime(ext: str) -> str:
    return _MIME_MAP.get(ext.lower(), "application/octet-stream")


def _guess_media_type(ext: str) -> str:
    ext = ext.lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",
               ".tif", ".svg", ".ico", ".heic", ".heif", ".raw", ".cr2",
               ".nef", ".arw", ".psd", ".ai", ".eps"):
        return "image"
    if ext in (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
               ".m4v", ".3gp", ".mts", ".m2ts"):
        return "video"
    if ext in (".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"):
        return "audio"
    if ext in (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
               ".odt", ".ods", ".odp"):
        return "document"
    if ext in (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"):
        return "archive"
    return "other"


def _hash_file(file_path: str, algorithm: str = "sha256",
               chunk_size: int = 65536) -> str:
    """计算文件哈希（仅前 1MB 用于快速校验）。"""
    h = hashlib.new(algorithm)
    max_bytes = 1024 * 1024  # 1MB
    try:
        with open(file_path, "rb") as f:
            read_bytes = 0
            while read_bytes < max_bytes:
                chunk = f.read(min(chunk_size, max_bytes - read_bytes))
                if not chunk:
                    break
                h.update(chunk)
                read_bytes += len(chunk)
    except (OSError, PermissionError):
        return ""
    return h.hexdigest()


def _parse_frontmatter(raw: str) -> tuple[Optional[dict], str]:
    """解析 YAML frontmatter (---...---) + Markdown 内容。

    零外部依赖的简化解析器。
    """
    # 查找第一个 ---
    lines = raw.split("\n")
    start = -1
    for i, line in enumerate(lines):
        if line.strip() == "---":
            start = i
            break
    if start < 0:
        return None, raw

    # 查找第二个 ---
    end = -1
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end < 0:
        return None, raw

    frontmatter_lines = lines[start + 1:end]
    content = "\n".join(lines[end + 1:])

    # 解析简单的 YAML 键值对 (不支持嵌套列表等高级特性)
    metadata: dict[str, Any] = {}
    # 缩进栈: (dict, parent_indent)
    indent_stack: list[tuple[dict, int]] = [(metadata, -1)]

    for line in frontmatter_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # 计算缩进（空格数）
        indent = len(line) - len(line.lstrip())

        # 回退到合适的深度
        while len(indent_stack) > 1 and indent <= indent_stack[-1][1]:
            indent_stack.pop()

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if value == "":
                # 嵌套对象的开始
                new_dict: dict[str, Any] = {}
                indent_stack[-1][0][key] = new_dict
                indent_stack.append((new_dict, indent))
            else:
                # 简单键值对
                # 类型转换
                if value.isdigit():
                    value = int(value)
                elif _is_float(value):
                    value = float(value)
                elif value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                indent_stack[-1][0][key] = value

    # Debug: print what we parsed
    # print(f"[DEBUG] _parse_frontmatter: metadata={metadata}")

    return metadata, content


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _set_hidden(path: Path) -> None:
    """在 Windows 上设置隐藏属性。"""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(
                str(path), 2  # FILE_ATTRIBUTE_HIDDEN
            )
        except Exception:
            pass
