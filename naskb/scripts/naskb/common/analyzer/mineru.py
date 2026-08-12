"""MinerU 文档解析后端（v2）— 全格式（PDF/DOCX/PPTX/XLSX → md + HTML + JSON）。

用户拍板：
- 文档解析尽可能用 MinerU（本地 AI 解析库），复杂 PDF 生成 HTML + 抽取图片
- 双路径：PyMuPDF 快速提取文本充足 → 直接用；不足（扫描件/复杂版面）→ MinerU
- HTML 既给人看也给大模型看（extra_formats=["html"]）
- 本机 Windows+AMD：CPU 跑（MinerU 无 DirectML 支持，AMD 加速仅 Linux ROCm）

MinerU 是可选依赖：未安装时本模块返回 error 提示安装（优雅降级）。
安装: pip install mineru（含 torch；模型权重首次自动下载，可用
      MINERU_MODEL_SOURCE=modelscope 切国内源）
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

SUPPORTED_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".jpg", ".jpeg", ".png"}

# MinerU CLI 输出结构（-o out_dir 时）：
#   out_dir/<stem>/  {stem}.md, {stem}.middle.json, {stem}.html, images/...
MD_NAME = "{stem}.md"
HTML_NAME = "{stem}.html"
MIDDLE_NAME = "{stem}.middle.json"
IMAGES_DIR = "images"


class MinerUAnalyzer:
    """MinerU 解析器封装：检测可用性 → 调用 CLI → 定位产物。"""

    def __init__(self, enabled: bool = True,
                 extra_formats: Optional[list[str]] = None,
                 return_middle_json: bool = True,
                 timeout: int = 3600,
                 model_source: str = "",
                 mineru_bin: str = "",
                 backend: str = "pipeline"):
        self.enabled = enabled
        # 注：MinerU 3.x 已移除 --extra-formats（md 默认生成），保留字段仅为
        # 2.x 兼容位；实际不再追加该参数
        self.extra_formats = extra_formats or ["html"]
        self.return_middle_json = return_middle_json
        self.timeout = timeout
        # MINERU_MODEL_SOURCE=modelscope 可切国内模型源
        self._model_source = model_source or os.environ.get("MINERU_MODEL_SOURCE", "")
        # MINERU_BIN: 独立 venv 的 mineru 可执行文件（MinerU 要求 Python<3.14，
        # 主环境 3.14 时需独立环境）；默认在 PATH 中找
        self._bin = mineru_bin or os.environ.get("MINERU_BIN", "") or "mineru"
        # 3.x 后端：pipeline（传统布局+OCR，CPU 友好）/ hybrid-engine（高精度，
        # 需 VLM 模型）/ vlm-http-client（远程服务）。CPU 机器默认 pipeline
        self._backend = backend

    # ── 可用性 ──

    def available(self) -> bool:
        """MinerU 是否可用（CLI 或 python 模块）。"""
        if not self.enabled:
            return False
        if self._bin != "mineru" and os.path.exists(self._bin):
            return True
        return shutil.which("mineru") is not None or _module_available("mineru")

    def needs_mineru(self, text_ratio: Optional[float],
                     fast_text_ratio: float = 0.3,
                     text_len: Optional[int] = None,
                     min_text_chars: int = 500) -> bool:
        """双路径判定：快速路径（PyMuPDF）文本不足 → 需要 MinerU。

        文本量充足（字符数超过 min_text_chars，默认 500）时直接信任快速
        路径，避免 PDF 结构开销导致比值永远偏低而误送 MinerU；文本过少
        （扫描件/图片型 PDF，如发票、合同扫描页常带少量零散文本层）或
        大文件中文本占比过低时才走 MinerU 做 OCR。

        text_ratio: 快速路径提取出的文本字符数 / 文件大小 的近似占比。
        None 表示无法判断（如解析失败）→ 建议走 MinerU。
        text_len: 提取出的文本字符数。与 text_ratio 同时给定且充足时
        直接返回 False（快速路径够用）。
        """
        if text_ratio is None:
            return True
        if text_len is not None and text_len >= min_text_chars:
            return False
        return text_ratio < fast_text_ratio

    # ── 解析 ──

    def parse(self, src_path: str, out_dir: str) -> dict:
        """解析文档到 out_dir，返回产物信息。

        Args:
            src_path: 本地源文件（调用方已下载到临时目录）
            out_dir: 产物输出目录（应为 .naskb/artifacts/）

        Returns:
            {"ok": bool, "error": str|None,
             "md_path": str|None, "html_path": str|None,
             "middle_json": str|None, "images_dir": str|None}
        """
        if not os.path.exists(src_path):
            return {"ok": False, "error": f"源文件不存在: {src_path}"}
        if not self.available():
            return {"ok": False,
                    "error": "MinerU 未安装 (pip install mineru，需 torch；"
                             "模型源可设 MINERU_MODEL_SOURCE=modelscope)"}

        os.makedirs(out_dir, exist_ok=True)
        cmd = [self._bin, "-p", src_path, "-o", out_dir, "-b", self._backend]
        # MinerU 3.x：--extra-formats 已移除，md 默认生成；显式声明表格/公式解析
        cmd += ["-t", "True", "-f", "True"]
        env = dict(os.environ)
        if self._model_source:
            env["MINERU_MODEL_SOURCE"] = self._model_source

        try:
            # Windows 默认 gbk 解码子进程输出，MinerU 输出 UTF-8 中文会崩；
            # 显式 utf-8 + errors=replace 容错
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=self.timeout, env=env)
            if proc.returncode != 0:
                return {"ok": False,
                        "error": f"MinerU 失败 (rc={proc.returncode}): "
                                 f"{proc.stderr[-500:] or proc.stdout[-500:]}"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"MinerU 超时 (> {self.timeout}s)"}
        except FileNotFoundError:
            return {"ok": False, "error": f"mineru CLI 未找到 ({self._bin})"}

        return self._locate_outputs(Path(src_path), out_dir)

    def _locate_outputs(self, src: Path, out_dir: str) -> dict:
        """在 MinerU 输出目录中定位产物（支持 <stem>/ 子目录或平铺）。

        MinerU 3.x 产物：<out>/<stem>/ 下 {stem}.md, {stem}.middle.json,
        images/（可选 html）；2.x 为平铺。
        """
        stem = src.stem
        base = Path(out_dir)
        # MinerU 3.x: PDF → <out>/<stem>/auto/<stem>.md；office(docx/pptx/xlsx)
        # → <out>/<stem>/office/<stem>.md；2.x 平铺；三者兼容
        candidates = [base / stem / "auto", base / stem / "office",
                      base / stem, base]
        result: dict = {"ok": True, "error": None,
                        "md_path": None, "html_path": None,
                        "middle_json": None, "images_dir": None}
        for d in candidates:
            if not d.exists():
                continue
            for name, key in ((MD_NAME.format(stem=stem), "md_path"),
                              (HTML_NAME.format(stem=stem), "html_path"),
                              (MIDDLE_NAME.format(stem=stem), "middle_json")):
                if result[key] is None:
                    p = d / name
                    if p.exists():
                        result[key] = str(p)
            imgs = d / IMAGES_DIR
            if result["images_dir"] is None and imgs.is_dir():
                result["images_dir"] = str(imgs)
            # 已找到 md 就够（html/middle 可选）
            if result["md_path"]:
                break
        # 3.x 的中间产物可能叫 {stem}_middle.json（下划线命名），兜底检查
        if result["middle_json"] is None:
            for d in candidates:
                if not d.exists():
                    continue
                alt = d / f"{stem}_middle.json"
                if alt.exists():
                    result["middle_json"] = str(alt)
                    break
        if result["md_path"] is None and result["html_path"] is None:
            result["ok"] = False
            result["error"] = "MinerU 完成但未找到产物"
        return result


def _module_available(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None
