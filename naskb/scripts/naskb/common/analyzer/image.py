"""图片分析器 — EXIF 元数据 + 大模型视觉理解（v2）。

用户拍板：所有图片都经过大模型识别，不做纯 OCR。
- 独立图片 → MiMo 视觉描述 → FileEntry.analysis
- 文档/视频抽取的图 → MiMo 视觉理解结构（箭头/方块/布局）→ FileEntry.images[]
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from ..llm import BaseLLMClient, LLMError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".avif"}

# 独立图片的描述 prompt（紧凑版：控制输出长度，MiMo 生成速度与输出 token 强相关）
IMAGE_DESCRIBE_PROMPT = (
    "用中文简述这张图片，总长度不超过120字，包含："
    "1) 主体内容（是什么文件/场景/物品，涉及谁） "
    "2) 图中关键文字（若有） "
    "3) 一句话总结。直接输出，不要编号外的解释。"
)

# 文档/视频抽取图的 prompt：重点是结构理解
IMAGE_STRUCTURE_PROMPT = (
    "这是从文档中抽取的一张图。请分析：\n"
    "1. 图的类型（架构图/流程图/表格截图/照片/示意图）\n"
    "2. 结构关系：箭头、方框、连线表达的逻辑关系\n"
    "3. 图中的文字内容（若有）\n"
    "4. 一句话总结这张图说明什么\n"
    "直接输出分析结果。"
)


def extract_exif(path: str) -> dict:
    """提取图片 EXIF 元数据（依赖 Pillow，缺失时返回空）。"""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
    except ImportError:
        return {}

    exif: dict[str, Any] = {}
    try:
        img = Image.open(path)
        if hasattr(img, "width"):
            exif["width"] = img.width
            exif["height"] = img.height
        raw = img._getexif()
        if not raw:
            return exif
        for tag_id, value in raw.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                gps = {}
                for k, v in value.items():
                    gps[GPSTS.get(k, k)] = str(v)
                exif["gps"] = gps
            elif tag in ("DateTimeOriginal", "DateTime", "Model", "Make",
                         "Software", "ExposureTime", "FNumber", "ISOSpeedRatings"):
                exif[tag] = str(value)
    except Exception:
        pass
    return exif


class ImageAnalyzer:
    """图片内容分析：EXIF（本地）+ 视觉大模型（云端 MiMo）。"""

    def __init__(self, llm: BaseLLMClient):
        self._llm = llm

    def analyze(self, image_path: str,
                prompt: str = IMAGE_DESCRIBE_PROMPT) -> tuple[str, dict]:
        """分析一张独立图片，返回 (描述文本, 元数据 dict)。

        Raises:
            LLMError: 图片不存在或大模型调用失败
        """
        if not os.path.exists(image_path):
            raise LLMError(f"图片文件不存在: {image_path}")
        meta = extract_exif(image_path)
        st = os.stat(image_path)
        meta.setdefault("size_bytes", st.st_size)
        description = self._llm.complete_image(image_path, prompt)
        return description, meta

    def describe_structure(self, image_path: str) -> str:
        """理解文档/视频抽取图的结构（箭头/方框/布局），返回描述文本。"""
        return self._llm.complete_image(image_path, IMAGE_STRUCTURE_PROMPT)
