"""缩略图/视频海报（V2，用户拍板：小缓存 store/thumbs）。

- 图片：Pillow 缩放到 <=w 宽，JPEG q80；
- 视频：ffmpeg 抽第 4 秒一帧做海报（需源端可读，≤100MB；无 ffmpeg 返回 None）；
- 缓存键 = sha1(source_id:resource_id:file_hash:w)，命中直接回磁盘字节，
  不重复转码/解码。缓存属于小型派生品，用户 8/23 拍板保留。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from typing import Optional

from ..common.fs.base import FileSystemAdapter
from ..common.pgstore import PgStore

IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "svg"}
VIDEO_EXTS = {"mp4", "mkv", "mov", "avi", "wmv", "webm", "flv", "ts"}
_MAX_IMAGE_MB = 12
_MAX_VIDEO_MB = 100


def _cache(config, row, w: int) -> str:
    key = hashlib.sha1(
        f"{row['source_id']}:{row['resource_id']}:{row.get('file_hash')}:{w}"
        .encode("utf-8")).hexdigest()[:24]
    d = os.path.join(config.work_path, "store", "thumbs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, key + ".jpg")


def _img_thumb(raw: bytes, w: int) -> bytes:
    from io import BytesIO
    from PIL import Image
    img = Image.open(BytesIO(raw))
    img.load()
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    if img.width > w:
        img.thumbnail((w, w * 10))
    out = BytesIO()
    img.save(out, format="JPEG", quality=80)
    return out.getvalue()


def _video_poster(local: str) -> Optional[bytes]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    out = local + ".poster.jpg"
    try:
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
             "-ss", "4", "-i", local, "-frames:v", "1", "-q:v", "3",
             out], check=True, capture_output=True, timeout=60)
        with open(out, "rb") as f:
            data = f.read()
        return data
    except Exception:
        return None
    finally:
        try:
            os.remove(out)
        except OSError:
            pass


def thumbnail(pg: PgStore, config, row: dict, fs: FileSystemAdapter,
              w: int = 320) -> Optional[bytes]:
    """按 ext 生成缩略图/海报；任何失败返回 None（前端跳过显示）。"""
    ext = (row.get("name") or "").rsplit(".", 1)[-1].lower() \
        if "." in (row.get("name") or "") else ""
    cache_path = _cache(config, row, w)
    try:
        if os.path.isfile(cache_path):
            with open(cache_path, "rb") as f:
                return f.read()
    except OSError:
        pass
    rel = row["rel_path"]
    try:
        if ext in IMAGE_EXTS:
            if (row.get("size_bytes") or 0) > _MAX_IMAGE_MB * 1024 * 1024:
                return None
            raw = fs.read_bytes(rel, max_bytes=8 * 1024 * 1024)
            data = _img_thumb(raw, w)
        elif ext in VIDEO_EXTS:
            if (row.get("size_bytes") or 0) > max(
                    _MAX_VIDEO_MB * 1024 * 1024, 1):
                return None
            tmp = _download(fs, rel, config)
            if not tmp:
                return None
            try:
                data = _video_poster(tmp)
            finally:
                _rm(tmp)
            if not data:
                return None
        else:
            return None
    except Exception:
        return None
    try:
        with open(cache_path, "wb") as f:
            f.write(data)
    except OSError:
        pass
    return data


def _download(fs: FileSystemAdapter, rel: str, config) -> Optional[str]:
    from .batch import _download_to_tmp
    return _download_to_tmp(fs, rel, config.analyzer_tmp_dir)


def _rm(path):
    if path:
        try:
            os.remove(path)
        except OSError:
            pass
