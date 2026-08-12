"""批量分析引擎 — 单进程内串行提取 + DeepSeek 并发摘要。

并发策略（用户 2026-08-10 拍板，必须遵守）：
- DeepSeek 文本摘要：ThreadPool 并发（默认 4~6 请求，官方允许）
- MinerU：严格串行（模型大、吃内存，多进程会内存爆炸）
- ffmpeg：单进程（内部已充分利用 CPU 多线程，不包多进程）
- MiMo（图片/音频/视频）：严格串行（并行会触发风控冻结 key）
- Word COM：单实例复用（批量 .doc 只启动一次 Word）

相比逐文件 subprocess 调用 CLI，本引擎还消除了解释器启动、
库导入、store/LLM client 重复创建等纯开销。
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .analyzer.document import DocumentAnalyzer
from .analyzer.folder import FolderAnalyzer
from .desc_store import FileEntry, NaskbStore
from .exts import (SUPPORTED_EXTS, DOC_EXTS, IMAGE_EXTS, AUDIO_EXTS, VIDEO_EXTS,
                   is_system_file, is_word_lock, meaning_of, guess_mime)
from .fs.base import FileSystemAdapter

@dataclass
class BatchResult:
    """批量分析汇总。"""
    total: int = 0            # 扫描到的文件总数（含不支持类型）
    supported: int = 0        # 支持的类型
    analyzed: int = 0         # 新分析（写入描述）
    skipped: int = 0          # 增量跳过（hash 未变且已有摘要）
    failed: int = 0           # 分析失败
    llm_failed: int = 0       # LLM 摘要失败（已降级，不算 failed）
    unsupported: int = 0      # 不支持的类型
    ignored_recorded: int = 0 # 被忽略文件仅记录名称推断（未分析内容）
    folder_updated: int = 0   # 目录级描述 folder.json 更新数
    orphans_removed: int = 0  # 文件已删除，清理的孤儿条目数
    elapsed: float = 0.0
    detail: list[dict] = field(default_factory=list)  # 每文件结果


ProgressFn = Optional[Callable[[int, int, str, str], None]]
# on_progress(done_count, total_count, filename, status)


def _download_to_tmp(fs: FileSystemAdapter, remote_path: str,
                     tmp_dir: str) -> Optional[str]:
    """下载远端文件到本地临时目录，返回本地路径。"""
    os.makedirs(tmp_dir, exist_ok=True)
    name = Path(remote_path).name
    local = os.path.join(tmp_dir, f"{os.getpid()}-{name}")
    try:
        with open(local, "wb") as f:
            for chunk in fs.read_chunks(remote_path):
                f.write(chunk)
        return local
    except Exception:
        try:
            os.remove(local)
        except OSError:
            pass
        return None


def _rm_tmp(path: Optional[str]) -> None:
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


def _docx_flow_items(docx_path: str) -> list[dict]:
    """解析 docx 内部 XML，按文档流顺序返回条目（本地、零依赖）。

    条目 dict:
      {"kind": "text",  "content": 段落文本, "para": 段落序号}
      {"kind": "table", "content": 表格文本, "tbl": 表格序号}
      {"kind": "image", "media": "media/image1.jpeg", "anchor": 位置锚点描述}

    docx 是流式文档：图文关系（图片嵌在哪个段落/表格、inline/浮动）就
    在 document.xml 的流式结构里，无需渲染即可还原。
    """
    import zipfile
    from lxml import etree

    try:
        with zipfile.ZipFile(docx_path) as z:
            doc_xml = z.read("word/document.xml")
            rels_xml = z.read("word/_rels/document.xml.rels")
    except Exception:
        return []
    try:
        root = etree.fromstring(doc_xml)
        rels_root = etree.fromstring(rels_xml)
    except Exception:
        return []

    # rId → 媒体路径（Target 相对 word/ 目录，可能带 ../ 前缀）
    rels: dict[str, str] = {}
    for r in rels_root:
        rid = r.get("Id")
        tgt = r.get("Target")
        if rid and tgt:
            rels[rid] = tgt

    R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

    def media_name(rid: str) -> str:
        """rId → media 相对路径（如 media/image1.jpg，读取时拼 word/ 前缀）。"""
        tgt = rels.get(rid, "")
        if not tgt:
            return ""
        norm = os.path.normpath(tgt.replace("/", os.sep)).replace(os.sep, "/")
        if norm.startswith("../"):       # 跨目录引用（如 ../media/...）
            norm = norm[3:]
        if norm.startswith("word/"):     # 部分文档 Target 直接含 word/ 前缀
            norm = norm[5:]
        return norm if norm.endswith((".png", ".jpeg", ".jpg", ".gif",
                                      ".bmp", ".webp", ".tif", ".tiff",
                                      ".emf", ".wmf", ".svg")) else ""

    def image_rid(draw_el) -> str:
        """从 w:drawing（a:blip r:embed）或 w:pict（v:imagedata）取 rId。"""
        for d in draw_el.iter():
            ln = etree.QName(d).localname
            if ln == "blip":
                rid = d.get(R_NS + "embed")
                if rid:
                    return rid
            elif ln == "imagedata":
                rid = (d.get("{urn:schemas-microsoft-com:office:office}relid")
                       or d.get(R_NS + "id"))
                if rid:
                    return rid
        return ""

    def anchor_desc(draw_el, default: str) -> str:
        for d in draw_el.iter():
            ln = etree.QName(d).localname
            if ln == "inline":
                return "inline 嵌入"
            if ln == "anchor":
                return "浮动定位"
        return default

    def collect(el, text_parts: list, images: list, ctx: str):
        """收集子树中的文本与图片元素（图片记锚点上下文）。"""
        for ch in el:
            ln = etree.QName(ch).localname
            if ln == "t":
                text_parts.append(ch.text or "")
            elif ln == "br":
                text_parts.append("\n")
            elif ln == "tab":
                text_parts.append("\t")
            elif ln in ("drawing", "pict"):
                images.append((ch, ctx))
            else:
                collect(ch, text_parts, images, ctx)

    W_BODY = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body"
    W_TR = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"
    W_TC = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"

    body = root.find(W_BODY)
    if body is None:
        return []

    items: list[dict] = []
    para_no = 0
    tbl_no = 0
    for child in body:
        ln = etree.QName(child).localname
        if ln == "p":
            para_no += 1
            text_parts: list[str] = []
            images: list = []
            collect(child, text_parts, images, f"段落 {para_no}")
            txt = "".join(text_parts).strip()
            if txt:
                items.append({"kind": "text", "content": txt, "para": para_no})
            for img_el, ctx in images:
                media = media_name(image_rid(img_el))
                if media:
                    items.append({"kind": "image", "media": media,
                                  "anchor": f"{ctx}，{anchor_desc(img_el, 'inline 嵌入')}"})
        elif ln == "tbl":
            tbl_no += 1
            rows: list[str] = []
            cell_images: list[tuple[str, str]] = []
            for tr in child.iter(W_TR):
                row_parts: list[str] = []
                for tc in tr.iter(W_TC):
                    text_parts = []
                    images = []
                    collect(tc, text_parts, images, f"表格 {tbl_no} 单元格")
                    row_parts.append("".join(text_parts).strip())
                    for img_el, ctx in images:
                        media = media_name(image_rid(img_el))
                        if media:
                            cell_images.append(
                                (media, f"表格 {tbl_no}，{anchor_desc(img_el, 'inline 嵌入')}"))
                if any(row_parts):
                    rows.append(" | ".join(row_parts))
            txt = "\n".join(rows).strip()
            if txt:
                items.append({"kind": "table", "content": txt, "tbl": tbl_no})
            for media, ctx in cell_images:
                items.append({"kind": "image", "media": media, "anchor": ctx})
    return items


def _extract_docx_images(docx_path: str, vision_client) -> str:
    """含图 docx：XML 流式图文解析（本地）+ 图内结构识别（MiMo 视觉）。

    返回按文档流顺序的文本：段落/表格文本 + 每张图的结构描述（图类型/
    箭头/方框/布局）与位置锚点（第几段、inline/浮动）。无嵌入图或全部
    失败时返回空串。
    """
    import tempfile
    import zipfile

    items = _docx_flow_items(docx_path)
    images = [it for it in items if it["kind"] == "image"]
    if not images:
        return ""
    from .analyzer import ImageAnalyzer

    ia = ImageAnalyzer(vision_client)
    tmp_dir = tempfile.mkdtemp(prefix="naskb-docx-img-")
    try:
        for it in images:
            media = it["media"]
            out = os.path.join(tmp_dir, os.path.basename(media))
            try:
                with zipfile.ZipFile(docx_path) as z:
                    with open(out, "wb") as f:
                        f.write(z.read("word/" + media))
                # 结构识别：图类型/箭头/方框/连线/布局（非纯简述）
                d = ia.describe_structure(out)
                it["desc"] = (d or "").strip()
            except Exception:
                it["desc"] = ""
    finally:
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    lines: list[str] = []
    img_no = 0
    for it in items:
        if it["kind"] == "text":
            lines.append(f"[段落 {it['para']}] {it['content']}")
        elif it["kind"] == "table":
            lines.append(f"[表格 {it['tbl']}] {it['content']}")
        else:
            img_no += 1
            d = it.get("desc") or "（图片内容未识别）"
            lines.append(f"[图片 {img_no}] {d}（{it['media']}，{it['anchor']}）")
    return "\n".join(lines)


def _docx_to_pdf(word_app, docx_path: str) -> Optional[str]:
    """用 Word COM 把 docx 渲染成 PDF（保真，供 MinerU 版面分析）。

    返回 PDF 路径（与 docx 同目录，调用方随临时目录一起清理）；
    渲染失败返回 None。
    """
    try:
        doc = word_app.Documents.Open(docx_path, ReadOnly=True)
    except Exception:
        return None
    try:
        pdf_path = os.path.join(
            os.path.dirname(docx_path),
            os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
        doc.SaveAs2(pdf_path, FileFormat=17)   # wdFormatPDF
        return pdf_path if os.path.exists(pdf_path) else None
    except Exception:
        return None
    finally:
        try:
            doc.Close(False)
        except Exception:
            pass


def _make_word_app():
    """创建可复用的 Word.Application（批量 .doc 只启动一次）。"""
    try:
        import win32com.client
        app = win32com.client.Dispatch("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        return app
    except Exception:
        return None


def analyze_tree(fs: FileSystemAdapter, store: NaskbStore, config,
                 root: str, *, llm: bool = False, workers: int = 4,
                 mineru: bool = True, limit: Optional[int] = None,
                 force: bool = False,
                 on_progress: ProgressFn = None,
                 clients: Optional[dict] = None) -> BatchResult:
    """批量分析目录树，写入 .naskb/index.json。

    增量幂等：已有条目且 hash 一致且有摘要（或 !llm 时 has ocr_text）
    则跳过；--force 强制重跑。

    workers: DeepSeek 并发数（建议 4~6，官方允许）。
    limit: 只处理前 N 个文件（测试/试跑用）。
    clients: 可选注入 {"text": .., "vision": .., "audio": ..} LLM 客户端
    （测试用 mock；缺省按 config 创建）。
    """
    from .llm import LLMConfig, create_llm_client

    t0 = time.time()
    result = BatchResult()
    clients = clients or {}

    # ── 收集文件：分类统计 ──
    # 隐藏目录（.git 等）与系统垃圾文件完全跳过；排除目录（node_modules 等）
    # 不记录文件条目但保留目录级统计（用户拍板：被忽略目录也要有目录元数据）；
    # 超过大小上限的支持类型文件不下载不分析，仅记录"文件过大"。
    repo_name = config.desc_repo_name
    excl_folders_orig = set(config.exclusions.get("folder", []))
    excl_folders_lower = {f.lower() for f in excl_folders_orig}
    max_file_bytes = config.analyzer_max_file_mb * 1024 * 1024
    files = []                       # 支持类型且未超大小：进入完整分析
    ignored_files = []               # 不支持类型：仅记录名称推断
    big_files = []                   # 支持类型但超过 max_file_mb：仅记录"文件过大"
    excluded_files = []              # 排除目录内文件：仅参与目录级统计
    dir_counts: dict[str, list[int]] = {}  # dir -> [total, supported]
    dir_rel_files: dict[str, set[str]] = {}  # dir -> 本次扫描到的直接文件名（孤儿检测）
    repo_index_dirs: set[str] = set()  # 扫描范围内存在的 .naskb 仓库目录（孤儿检测，含空目录）

    for f in fs.list_files(root, recursive=True):
        parts = f.path.replace("\\", "/").split("/")
        if f.name == "index.json" and repo_name in parts:
            # 仓库目录 = .naskb 的父目录（文件全删后目录仍存在的场景也覆盖）；
            # 用 os.path.dirname 保证与 dir_rel_files 的 key 分隔符一致
            repo_index_dirs.add(os.path.dirname(os.path.dirname(f.path)))
            continue
        if repo_name in parts:      # 跳过隐藏仓库内部文件
            continue
        hidden = excluded = False
        for p in parts[:-1]:
            if p.startswith("."):
                hidden = True
                break
            if p in excl_folders_orig or p.lower() in excl_folders_lower:
                excluded = True
        if hidden:
            continue                # 隐藏目录（.git 等）：完全跳过
        if is_system_file(f.name) or is_word_lock(f.name):
            continue                # 系统垃圾文件 / Office 锁文件：完全跳过
        d = os.path.dirname(f.path)
        dir_rel_files.setdefault(d, set()).add(f.name)
        c = dir_counts.setdefault(d, [0, 0])
        c[0] += 1
        if excluded:
            excluded_files.append(f)   # 排除目录：计总数但不算 supported
            continue
        if f.ext in SUPPORTED_EXTS:
            c[1] += 1
            if max_file_bytes and f.size_bytes > max_file_bytes:
                big_files.append(f)  # 大文件：不下载不分析，仅记录
            else:
                files.append(f)
        else:
            result.unsupported += 1
            ignored_files.append(f)
    result.total = len(files) + result.unsupported + len(big_files)
    result.supported = len(files)
    if limit is not None:
        files = files[:limit]
    # 注：files 为空（纯代码/软件目录）时不提前返回——忽略文件记录与
    # 目录级 folder.json 仍需执行（用户拍板：被忽略内容也要有元数据）

    # ── 共享资源：LLM clients / Word COM / MinerU ──
    created_clients: list = []   # 本函数创建的 client（finally 只关这些）
    llm_client = clients.get("text") or (
        create_llm_client(LLMConfig.from_dict(config.llm_text)) if llm else None)
    if llm_client is not None and "text" not in clients:
        created_clients.append(llm_client)
    vision_client = clients.get("vision") or create_llm_client(
        LLMConfig.from_dict(config.llm_vision))
    if vision_client is not None and "vision" not in clients:
        created_clients.append(vision_client)
    audio_client = clients.get("audio") or create_llm_client(
        LLMConfig.from_dict(config.llm_audio))
    if audio_client is not None and "audio" not in clients:
        created_clients.append(audio_client)
    word_app = _make_word_app()
    doc_analyzer = DocumentAnalyzer(
        max_chars=config.analyzer_max_chars,
        max_file_bytes=config.analyzer_max_file_mb * 1024 * 1024,
        com_app=word_app,
    )
    mineru_analyzer = None
    if mineru and config.mineru_enabled:
        from .analyzer.mineru import MinerUAnalyzer
        mineru_analyzer = MinerUAnalyzer(
            enabled=True,
            extra_formats=config.mineru_extra_formats,
            return_middle_json=config.mineru_return_middle_json,
            model_source=config.mineru_model_source,
            mineru_bin=config.mineru_bin,
            backend="pipeline",
        )

    executor: Optional[ThreadPoolExecutor] = None
    futures: list[tuple[str, Any]] = []   # (path, future)
    written_dirs: set[str] = set()        # 本次实际写入条目的文件所在目录

    def _set_entry(path: str, entry: FileEntry) -> None:
        ok = store.set_entry(path, entry)
        if ok:
            written_dirs.add(os.path.dirname(path))
        else:
            result.failed += 1

    try:
        # ── 主循环：串行提取 + 判定；DeepSeek 摘要提交线程池 ──
        for i, f in enumerate(files):
            ext = f.ext
            status = "analyzed"
            try:
                # 增量跳过
                if not force:
                    old = store.get_entry(f.path)
                    if old and old.file_hash == store.compute_hash(f.path):
                        has_content = bool(old.summary) or bool(old.ocr_text) \
                            or bool(old.transcription) or bool(old.content_description)
                        if has_content:
                            result.skipped += 1
                            status = "skipped"
                            if on_progress:
                                on_progress(i + 1, len(files), f.name, status)
                            continue

                entry = FileEntry()
                entry.original_path = f.path
                entry.processing_policy = "full"
                flow_text = ""   # docx 图文流（非 docx 恒为空）

                if ext in DOC_EXTS:
                    # ── 文档：快速提取（串行）→ docx 图文流（串行）
                    #    → MinerU（串行）→ DeepSeek（并发）──
                    res = doc_analyzer.extract_remote(
                        fs, f.path, config.analyzer_tmp_dir)
                    entry.file_type = res.metadata.file_type
                    entry.size_bytes = res.metadata.file_size

                    if ext == ".docx":
                        # ── 档位 1：XML 流式图文解析（本地毫秒级）+ 图内
                        #    结构识别（MiMo 视觉，严格串行）──
                        tmp = _download_to_tmp(
                            fs, f.path, config.analyzer_tmp_dir)
                        if tmp:
                            try:
                                flow_text = _extract_docx_images(tmp, vision_client)
                            except Exception:
                                flow_text = ""
                            if flow_text and not res.text:
                                # 图片型 docx（扫描件放入 Word，无文本层）
                                entry.ocr_text = flow_text[: config.analyzer_max_chars]
                                entry.content_description = flow_text[:2000]
                                entry.category = "扫描件"
                            elif res.text:
                                entry.ocr_text = res.text[: config.analyzer_max_chars]
                                if flow_text:
                                    # 图文关系单独存（正文保留在 ocr_text）
                                    entry.content_description = flow_text[:2000]

                            # ── 档位 2：图片型 docx → Word 渲染 PDF →
                            #    MinerU 版面 + OCR 全文（严格串行）──
                            pdf_path = None
                            if (not (res.text or "").strip()
                                    and mineru_analyzer is not None
                                    and mineru_analyzer.available()
                                    and word_app is not None):
                                try:
                                    pdf_path = _docx_to_pdf(word_app, tmp)
                                    if pdf_path:
                                        out_dir = os.path.join(
                                            os.path.dirname(f.path), repo_name,
                                            "artifacts", Path(f.name).stem)
                                        r = mineru_analyzer.parse(pdf_path, out_dir)
                                        if r["ok"] and r.get("md_path"):
                                            with open(r["md_path"],
                                                      encoding="utf-8") as mf:
                                                md_text = mf.read()
                                            if md_text:
                                                entry.ocr_text = md_text[: config.analyzer_max_chars]
                                                # 图文关系流保留（MinerU md 只有 OCR 全文）
                                                entry.content_description = flow_text[:2000]
                                                entry.category = "扫描件"
                                            repo_dir = os.path.join(
                                                os.path.dirname(f.path), repo_name)
                                            entry.exif["mineru_artifacts"] = {
                                                k: (os.path.relpath(v, repo_dir) if v else None)
                                                for k, v in r.items()
                                                if k in ("md_path", "html_path",
                                                         "middle_json", "images_dir")
                                            }
                                except Exception:
                                    pass
                            _rm_tmp(tmp)
                            _rm_tmp(pdf_path)   # 渲染产物 PDF 一并清理
                    elif res.text:
                        entry.ocr_text = res.text[: config.analyzer_max_chars]

                    # 双路径：扫描件/文本不足 → MinerU（严格串行）
                    # （.docx 已由档位 1/2 全权处理，不再重复走 office 后端）
                    if (ext != ".docx"
                            and mineru_analyzer is not None
                            and mineru_analyzer.available()
                            and ext not in {".txt", ".md", ".km", ".mmap",
                                            ".doc", ".xls"}
                            and (bool((res.metadata.exif or {}).get("scan_like"))
                                 or mineru_analyzer.needs_mineru(
                                     (len(res.text or "") / (entry.size_bytes or 1)),
                                     config.mineru_fast_text_ratio,
                                     text_len=len(res.text or ""),
                                     min_text_chars=config.mineru_min_text_chars))):
                        tmp = _download_to_tmp(fs, f.path, config.analyzer_tmp_dir)
                        if tmp:
                            out_dir = os.path.join(
                                os.path.dirname(f.path), repo_name,
                                "artifacts", Path(f.name).stem)
                            r = mineru_analyzer.parse(tmp, out_dir)
                            if r["ok"] and r.get("md_path"):
                                with open(r["md_path"], encoding="utf-8") as mf:
                                    md_text = mf.read()
                                if md_text:
                                    entry.ocr_text = md_text[: config.analyzer_max_chars]
                                repo_dir = os.path.join(os.path.dirname(f.path), repo_name)
                                entry.exif["mineru_artifacts"] = {
                                    k: (os.path.relpath(v, repo_dir) if v else None)
                                    for k, v in r.items()
                                    if k in ("md_path", "html_path",
                                             "middle_json", "images_dir")
                                }
                            _rm_tmp(tmp)

                    text_for_llm = entry.ocr_text or ""
                    if flow_text and res.text and ext == ".docx":
                        # 有文本层的 docx：摘要输入拼上图文流（图结构+位置），
                        # 正文仍完整保留在 ocr_text
                        text_for_llm = (res.text + "\n\n[图文结构]\n" + flow_text)[
                            : config.analyzer_max_chars]
                    if llm and text_for_llm:
                        # 先写入提取结果（ocr_text/EXIF 等），
                        # 摘要由 future 完成后合并补写
                        _set_entry(f.path, entry)
                        if executor is None:
                            executor = ThreadPoolExecutor(max_workers=workers)
                        futures.append((f.path, executor.submit(
                            _llm_summarize, llm_client, text_for_llm)))
                        result.analyzed += 1
                        if on_progress:
                            on_progress(i + 1, len(files), f.name, "llm...")
                        continue
                    if not llm and text_for_llm:
                        entry.summary = text_for_llm[:200]

                elif ext in IMAGE_EXTS:
                    # ── 图片：EXIF + MiMo 视觉（严格串行）──
                    from .analyzer import ImageAnalyzer
                    tmp = _download_to_tmp(fs, f.path, config.analyzer_tmp_dir)
                    if tmp:
                        ia = ImageAnalyzer(vision_client)
                        desc_text, meta = ia.analyze(tmp)
                        entry.summary = (desc_text or "")[:200]
                        entry.content_description = desc_text
                        entry.category = "图片"
                        entry.width = meta.get("width")
                        entry.height = meta.get("height")
                        entry.exif = {k: v for k, v in meta.items()
                                      if k not in ("width", "height")}
                        entry.file_type = meta.get("file_type", "")
                        entry.size_bytes = meta.get("size_bytes", 0)
                        _rm_tmp(tmp)

                elif ext in AUDIO_EXTS:
                    # ── 音频：ffmpeg 分段 + MiMo 串行转写 ──
                    from .analyzer import AudioAnalyzer
                    tmp = _download_to_tmp(fs, f.path, config.analyzer_tmp_dir)
                    if tmp:
                        aa = AudioAnalyzer(
                            audio_client,
                            split_seconds=config.llm_audio_split_minutes * 60,
                            diarization=config.llm_audio_diarization,
                        )
                        entry.transcription = aa.transcribe(tmp)
                        entry.summary = (entry.transcription or "")[:200]
                        entry.category = "音频"
                        _rm_tmp(tmp)

                elif ext in VIDEO_EXTS:
                    # ── 视频：ffprobe + 分级（严格串行）──
                    from .analyzer import AudioAnalyzer, VideoAnalyzer, VideoClassifier
                    aa = AudioAnalyzer(
                        audio_client,
                        split_seconds=config.llm_audio_split_minutes * 60,
                        diarization=config.llm_audio_diarization,
                    )
                    classifier = VideoClassifier(
                        category_paths=config.video_category_paths,
                        category_keywords=config.video_category_keywords,
                        duration_threshold_min=config.video_duration_threshold_min,
                    )
                    va = VideoAnalyzer(
                        audio_client, classifier,
                        keyframes_max=config.video_keyframes_max,
                        keyframe_interval_sec=config.video_keyframe_interval_sec,
                        audio_analyzer=aa,
                    )
                    tmp = _download_to_tmp(fs, f.path, config.analyzer_tmp_dir)
                    if tmp:
                        res = va.analyze(tmp)
                        meta = res["meta"]
                        entry.category = res["category"]
                        entry.processing_policy = res["policy"]
                        entry.transcription = res["transcription"]
                        entry.duration_seconds = meta.get("duration_seconds")
                        entry.width = meta.get("width")
                        entry.height = meta.get("height")
                        entry.exif = {"codec": meta.get("codec") or "",
                                      "container": meta.get("container") or ""}
                        entry.file_type = f"video/{meta.get('container') or 'x-unknown'}"
                        entry.summary = (entry.transcription or "")[:200] or \
                            f"视频 {res['category']}（{res['policy']}）"
                        _rm_tmp(tmp)

                _set_entry(f.path, entry)
                result.analyzed += 1
                status = "analyzed"
            except Exception as e:
                result.failed += 1
                status = f"FAILED: {e}"
                print(f"[naskb] 分析失败 {f.path}: {e}")
            if on_progress:
                on_progress(i + 1, len(files), f.name, status)

        # ── 等待所有 DeepSeek future，串行合并摘要写入（避免并发覆盖 index.json）──
        for path, fut in futures:
            entry = FileEntry()
            entry.original_path = path
            entry.processing_policy = "full"
            try:
                data = fut.result()
                if not data:
                    # _llm_summarize 失败降级返回空 dict
                    result.llm_failed += 1
                    print(f"[naskb] LLM 摘要失败（降级保留提取文本）: {path}")
                else:
                    entry.summary = str(data.get("summary", ""))
                    entry.tags = [str(t) for t in (data.get("tags") or []) if t]
                    entry.category = str(data.get("category", ""))
                    entry.confidence = float(data.get("confidence", 0.5) or 0.5)
            except Exception as e:
                result.llm_failed += 1
                print(f"[naskb] LLM 摘要失败 {path}: {e}")
            # 提取的文本在提交前已写入，合并旧条目补全摘要字段
            old = store.get_entry(path)
            if old:
                entry.file_type = old.file_type
                entry.size_bytes = old.size_bytes
                entry.ocr_text = old.ocr_text
                entry.content_description = old.content_description
                entry.transcription = old.transcription
                entry.exif = old.exif
                entry.file_hash = old.file_hash
                entry.analyzed_at = old.analyzed_at
                entry.analyzer_version = old.analyzer_version
            _set_entry(path, entry)

        # ── 被忽略/过大文件：仅按文件名记录可能的内容意义（不分析内容）──
        for f, big in [(x, False) for x in ignored_files] + \
                      [(x, True) for x in big_files]:
            try:
                if not force:
                    old = store.get_entry(f.path)
                    if (old and old.summary
                            and old.file_hash == store.compute_hash(f.path)):
                        result.skipped += 1
                        continue
                meaning = meaning_of(f.name)
                entry = FileEntry()
                entry.original_path = f.path
                entry.processing_policy = "metadata_only"
                entry.file_type = guess_mime(f.name)
                entry.size_bytes = f.size_bytes
                entry.mtime = f.mtime
                note = (f"（文件超过 {config.analyzer_max_file_mb}MB，未下载分析）"
                        if big else "（未分析内容，仅按文件名记录）")
                entry.summary = f"可能为{meaning}：{f.name}{note}"
                if store.set_entry(f.path, entry):
                    result.ignored_recorded += 1
                    written_dirs.add(os.path.dirname(f.path))
                else:
                    result.failed += 1
            except Exception as e:
                result.failed += 1
                print(f"[naskb] 忽略文件记录失败 {f.path}: {e}")

        # ── 文件删除检测：index.json 有条目但文件本次未出现 → 孤儿 →
        # 清理条目 + 该目录进入 folder 级联（含祖先）。
        # 覆盖：新增/修改/删除均会使目录描述保持正确。
        for d in repo_index_dirs:
            try:
                idx = store.read_index(d)
                names = dir_rel_files.get(d, set())
                gone = [f.get("path", "") for f in idx.get("files", [])
                        if f.get("path") and f["path"] not in names]
                if not gone:
                    continue
                n = store.remove_entries(d, gone)
                if n:
                    result.orphans_removed += n
                    written_dirs.add(d)  # 触发该目录及其祖先的 folder.json 重算
            except Exception as e:
                print(f"[naskb] 孤儿清理失败 {d}: {e}")

        # ── 目录级描述 folder.json：被忽略目录 + 受影响目录（含祖先级联）──
        root_abs = fs.resolve_path(root) if hasattr(fs, "resolve_path") else root
        target_dirs: set[str] = set()
        for d in written_dirs:
            target_dirs.update(_ancestor_dirs(d, root_abs))
        # 整个目录被忽略（有文件但无任何支持类型）→ 目录级元数据（名称推断用途），
        # 其祖先链同样级联。只对"顶层被忽略目录"生成 folder.json：
        # 父目录也是被忽略目录时跳过（避免 node_modules 下每个子包都生成）。
        ignored_dirs = {d for d, (total, sup) in dir_counts.items()
                        if total > 0 and sup == 0}
        top_ignored = {d for d in ignored_dirs
                       if os.path.dirname(d) not in ignored_dirs}
        for d in top_ignored:
            target_dirs.update(_ancestor_dirs(d, root_abs))
        if target_dirs:
            folder_analyzer = FolderAnalyzer(
                llm_client if llm else None,
                excluded_folders=config.exclusions.get("folder", []))
            all_files = files + ignored_files + big_files + excluded_files
            for d in sorted(target_dirs):
                try:
                    struct = FolderAnalyzer.build_structure(
                        all_files, d, repo_name=repo_name,
                        excluded_folders=config.exclusions.get("folder", []))
                    if not struct["file_count"]:
                        continue
                    entry = folder_analyzer.analyze(fs, d, prebuilt=struct)
                    if store.write_folder(d, entry):
                        result.folder_updated += 1
                except Exception as e:
                    print(f"[naskb] 目录描述更新失败 {d}: {e}")
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
        doc_analyzer.close_com()
        # 只关闭本函数创建的 client；注入的由调用方管理
        for c in created_clients:
            try:
                c.close()
            except Exception:
                pass

    result.elapsed = time.time() - t0
    return result


def _llm_summarize(llm_client, text: str) -> dict:
    """DeepSeek 摘要（在线程池中并发执行）。失败降级返回空 dict。"""
    try:
        data = llm_client.complete_json(
            f"这是文件内容:\n{text[:4000]}\n\n"
            "输出 JSON: {\"summary\": 一句话中文摘要, \"tags\": [3-6个中文标签], "
            "\"category\": 建议分类目录, \"confidence\": 0-1}")
        if not isinstance(data, dict):
            return {}
        data.setdefault("summary", "")
        data.setdefault("tags", [])
        data.setdefault("category", "")
        data.setdefault("confidence", 0.5)
        return data
    except Exception:
        return {}


def _ancestor_dirs(d: str, root: str) -> list[str]:
    """目录 d 到 root（含）的祖先链（用于 folder.json 级联更新）。"""
    out: list[str] = []
    cur = d
    root_n = os.path.normcase(os.path.normpath(root))
    while True:
        out.append(cur)
        if os.path.normcase(os.path.normpath(cur)) == root_n:
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return out
