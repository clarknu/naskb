"""图片分析器 — EXIF 元数据 + 大模型视觉理解（v2，增强版）。

增强点（v2.1）：
- 票据/证件/文档类图片：启用 OCR 详细模式，逐字提取关键文字（金额、日期、编号等）
- 普通照片：保持简洁摘要
- 自动分类：根据首张识别结果或文件名特征判断是否文档类
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from ..llm import BaseLLMClient, LLMError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".avif"}

# ── 通用图片描述 prompt（增强版：不再限制 120 字，要求提取图中所有文字）──
IMAGE_DESCRIBE_PROMPT = (
    "用中文描述这张图片，要求：\n"
    "1) 主体内容（是什么文件/场景/物品）\n"
    "2) 图中所有可见文字，逐字准确提取（包括：标题、正文、表格内容、数字、日期、"
    "编号、金额、水印、印章文字、签名、小字备注等，不要遗漏）\n"
    "3) 若是票据/发票/收据，列出：抬头、日期、金额、商品明细、编号等关键字段\n"
    "4) 若是证件/证书，列出：姓名、号码、日期、发证机关等关键字段\n"
    "5) 若是日历/日程，列出：日期、每天的文字内容\n"
    "6) 一句话总结\n"
    "直接输出，不要编号外的解释。"
)

# ── 票据/证件专用 OCR prompt（更严格：必须逐字提取）──
IMAGE_OCR_PROMPT = (
    "这是一张票据、证件、发票、收据、证书、或含有重要文字的文档图片。\n"
    "请逐字准确提取图中所有文字内容，要求：\n"
    "1) 列出所有可见文字，包括：标题、正文、表格、数字、日期、编号、金额、\n"
    "   水印、印章文字、签名、小字备注、页码等\n"
    "2) 用结构化格式输出（如表格用 Markdown 表格，列表用 Markdown 列表）\n"
    "3) 对关键字段加粗：金额、日期、编号、姓名等\n"
    "4) 若有表格，完整还原表格结构和内容\n"
    "5) 不要省略任何文字，即使模糊或部分遮挡也尽量识别\n"
    "直接输出提取的文字内容。"
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

# 票据/证件/文档类关键词（用于文件名/路径快速预判）
_DOC_KEYWORDS = frozenset({
    "发票", "票据", "收据", "证书", "证件", "身份证", "护照", "行驶证",
    "驾照", "营业执照", "合同", "协议", "报告", "体检", "病历", "处方",
    "保单", "保单", "缴费", "账单", "工资", "流水", "对账", "回执",
    "录取", "通知", "证明", "房产", "产权", "学位", "毕业",
    "invoice", "receipt", "certificate", "contract", "ticket", "bill",
})


def _looks_like_document(path: str, filename_hint: str = "") -> bool:
    """基于文件名/路径快速预判是否可能是票据/证件/文档类图片。"""
    check_str = (path + " " + filename_hint).lower()
    return any(kw in check_str for kw in _DOC_KEYWORDS)


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
                    gps[GPSTAGS.get(k, k)] = str(v)
                exif["gps"] = gps
            elif tag in ("DateTimeOriginal", "DateTime", "Model", "Make",
                         "Software", "ExposureTime", "FNumber", "ISOSpeedRatings"):
                exif[tag] = str(value)
    except Exception:
        pass
    return exif


class ImageAnalyzer:
    """图片内容分析：EXIF（本地）+ 视觉大模型（云端 MiMo）。

    v2.1 增强：自动选择合适 prompt（通用/OCR/结构）
    """

    def __init__(self, llm: BaseLLMClient):
        self._llm = llm

    def analyze(self, image_path: str,
                prompt: str = "",
                force_ocr: bool = False,
                filename_hint: str = "") -> tuple[str, dict]:
        """分析一张独立图片，返回 (描述文本, 元数据 dict)。

        Args:
            image_path: 图片路径
            prompt: 自定义 prompt（为空时自动选择）
            force_ocr: 强制使用 OCR 详细模式
            filename_hint: 文件名提示（用于文档类预判）

        Raises:
            LLMError: 图片不存在或大模型调用失败
        """
        if not os.path.exists(image_path):
            raise LLMError(f"图片文件不存在: {image_path}")

        # 自动选择 prompt
        if not prompt:
            if force_ocr or _looks_like_document(image_path, filename_hint):
                prompt = IMAGE_OCR_PROMPT
            else:
                prompt = IMAGE_DESCRIBE_PROMPT

        meta = extract_exif(image_path)
        st = os.stat(image_path)
        meta.setdefault("size_bytes", st.st_size)
        description = self._llm.complete_image(image_path, prompt)
        return description, meta

    def describe_structure(self, image_path: str) -> str:
        """理解文档/视频抽取图的结构（箭头/方框/布局），返回描述文本。"""
        return self._llm.complete_image(image_path, IMAGE_STRUCTURE_PROMPT)
