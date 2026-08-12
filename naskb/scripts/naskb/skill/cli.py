"""Command-line interface for NASKB (v2).

Usage:
    naskb desc scan <root>
    naskb desc analyze <file>
    naskb desc analyze-tree <root> [--llm] [--workers N]
    naskb desc plan-reorganize <root> [--apply]
    naskb desc search <query>
"""
import os
import sys
from pathlib import Path
from typing import Optional

import click

# Resolve NASKB_WORK from env or current directory
def _default_work_path() -> str:
    """默认工作区：NASKB_WORK 环境变量 > CWD/NASKB_data > 代码仓库旁 NASKB_data。

    避免从任意目录运行 CLI 时误把 CWD/NASKB_data（不存在则被 Config 自动
    创建为空配置）当成工作区，导致 LLM key 为空。
    """
    env = os.environ.get("NASKB_WORK")
    if env:
        return env
    cwd_candidate = str(Path.cwd() / "NASKB_data")
    if os.path.isdir(cwd_candidate):
        return cwd_candidate
    repo_candidate = str(
        Path(__file__).resolve().parent.parent.parent / "NASKB_data")
    if os.path.isdir(repo_candidate):
        return repo_candidate
    return cwd_candidate


_DEFAULT_WORK = _default_work_path()


def _get_work_path(work_path: Optional[str]) -> str:
    return work_path or _DEFAULT_WORK




# ═══════════════════════════════════════════════════════════════════
# CLI Group
# ═══════════════════════════════════════════════════════════════════

@click.group()
@click.option("--work-path", "-w", envvar="NASKB_WORK",
              default=_DEFAULT_WORK, show_default=True,
              help="Path to NASKB work directory")
@click.pass_context
def main(ctx, work_path):
    """NASKB — 智能 NAS 知识库（目录描述仓库 + AI 分析）。"""
    ctx.ensure_object(dict)
    ctx.obj["work_path"] = str(Path(work_path).resolve())



# ═══════════════════════════════════════════════════════════════════
# desc — v2 目录隐藏描述仓库 (.naskb/)
# ═══════════════════════════════════════════════════════════════════

@main.group()
@click.option("--webdav-url", "webdav_url", default=None,
              help="WebDAV 根地址（如 https://host:5006）；给出后 desc 命令以 WebDAV 模式运行（也可在 config.toml [webdav] 配置后省略）")
@click.option("--webdav-user", "webdav_user", default=None)
@click.option("--webdav-pass", "webdav_pass", default=None)
@click.pass_context
def desc(ctx, webdav_url, webdav_user, webdav_pass):
    """目录隐藏描述仓库 (.naskb/ 读写/校验/跟随移动/迁移)。

    默认操作本地目录；加 --webdav-url 或配置 [webdav] 后操作 NAS。
    """
    ctx.obj = ctx.obj or {}
    if webdav_url:
        ctx.obj["desc_webdav"] = {
            "url": webdav_url,
            "user": webdav_user or "",
            "password": webdav_pass or "",
        }
    else:
        ctx.obj["desc_webdav"] = None


def _make_desc_store(ctx, fs_type="local", url=None, auth=None, path_hint=None):
    """创建 NaskbStore。

    连接来源优先级：命令行 --webdav-* 选项 > config.toml [webdav] 段（仅当
    path_hint 是服务器路径风格，即以 / 开头且非 Windows 盘符）> 本地模式。
    """
    from ..common.config import Config
    from ..common.desc_store import NaskbStore
    from ..common.fs.base import FileSystemAdapter

    wp = _get_work_path(ctx.obj.get("work_path"))
    config = Config.from_work_path(wp)
    # 命令行 WebDAV 选项优先
    wd = (ctx.obj or {}).get("desc_webdav")
    if not wd and config.webdav_url:
        hint = path_hint or url or ""
        looks_remote = hint.startswith("/") and not hint.startswith("//")
        if looks_remote:
            wd = {"url": config.webdav_url, "user": config.webdav_user,
                  "password": config.webdav_password}
    if wd and wd.get("url"):
        fs_type = "webdav"
        url = wd["url"]
        auth = {"username": wd.get("user") or "",
                "password": wd.get("password") or "",
                "verify_ssl": config.webdav_verify_ssl}
    if fs_type == "local" and not url:
        # 默认以当前目录为根（与命令行传入的相对路径基准一致）
        url = str(Path.cwd())
    fs = FileSystemAdapter.create(fs_type, url, auth or {})
    store = NaskbStore(
        fs,
        analyzer_version=config.desc_analyzer_version,
        hash_max_bytes=config.desc_hash_max_bytes,
    )
    return store, fs, config


@desc.command("check")
@click.argument("path")
@click.pass_context
def desc_check(ctx, path):
    """检查单个文件的描述状态 (valid/stale/missing)。"""
    store, fs, _ = _make_desc_store(ctx, path_hint=path)
    try:
        status = store.check(path)
        print(f"[naskb] {status}: {path}")
        if status == "valid":
            e = store.get_entry(path)
            print(f"  分类: {e.category or '(未分类)'}")
            print(f"  摘要: {e.summary or '(无摘要)'}")
            print(f"  Hash: {e.file_hash}")
            print(f"  策略: {e.processing_policy}")
    finally:
        fs.close()


@desc.command("scan")
@click.argument("root", required=False, default=".")
@click.pass_context
def desc_scan(ctx, root):
    """扫描目录，报告所有文件的描述状态（口径与 analyze-tree 一致）。"""
    store, fs, _ = _make_desc_store(ctx, path_hint=root)
    try:
        report = store.scan(root)
        print(f"[naskb] 描述仓库扫描报告: {root}")
        print(f"  文件总数: {report['total']}")
        print(f"  valid:   {report['valid']}  (可复用，跳过分析)")
        print(f"  missing: {report['missing']}  (需要分析)")
        print(f"  stale:   {report['stale']}  (文件已变更，需重新分析)")
        print(f"  ignored: {report['ignored']}  (不支持类型，仅记录名称推断)")
        print(f"  孤儿条目: {report['orphans']}  (index.json 有记录但文件不存在)")
        for d in report["details"]:
            if d["status"] != "valid":
                print(f"  {d['status']:8s} {d['path']}")
    finally:
        fs.close()


@desc.command("analyze")
@click.argument("path")
@click.option("--llm/--no-llm", default=False,
              help="调用大模型生成摘要/标签/分类（文本走 DeepSeek）")
@click.pass_context
def desc_analyze(ctx, path, llm):
    """分析文件并写入 .naskb/index.json（按类型分发：文档/图片/音频/视频）。"""
    from ..common.analyzer import (
        AudioAnalyzer,
        DocumentAnalyzer,
        ImageAnalyzer,
        VideoAnalyzer,
        VideoClassifier,
    )
    from ..common.desc_store import FileEntry
    from ..common.exts import (DOC_EXTS, IMAGE_EXTS, AUDIO_EXTS, VIDEO_EXTS,
                               meaning_of, guess_mime)
    from ..common.llm import LLMConfig, create_llm_client

    config = _make_desc_store(ctx, path_hint=path)[2]
    store, fs, _ = _make_desc_store(ctx, path_hint=path)
    try:
        ext = Path(path).suffix.lower()
        llm_client = None
        vision_client = None
        word_app = None
        try:
            entry = FileEntry()
            entry.original_path = path
            entry.processing_policy = "full"

            if ext in DOC_EXTS:
                # ── 文档：快速路径提取 + MinerU 双路径 ──
                from ..common.analyzer.mineru import MinerUAnalyzer

                analyzer = DocumentAnalyzer(
                    max_chars=config.analyzer_max_chars,
                    max_file_bytes=config.analyzer_max_file_mb * 1024 * 1024,
                )
                result = analyzer.extract_remote(fs, path, config.analyzer_tmp_dir)
                entry.file_type = result.metadata.file_type
                entry.size_bytes = result.metadata.file_size
                if result.text:
                    entry.ocr_text = result.text[: config.analyzer_max_chars]
                if result.error and "MinerU" in result.error:
                    print(f"[naskb] 提示: {result.error}")

                # MinerU 分析器（docx 档位 2 与通用双路径共用）
                mineru = MinerUAnalyzer(
                    enabled=config.mineru_enabled,
                    extra_formats=config.mineru_extra_formats,
                    return_middle_json=config.mineru_return_middle_json,
                    model_source=config.mineru_model_source,
                    mineru_bin=config.mineru_bin,
                    backend="pipeline",  # 本机 CPU：传统布局+OCR 后端
                )

                flow_text = ""   # docx 图文流（非 docx 恒为空）
                if ext == ".docx":
                    # ── 档位 1：XML 流式图文解析（本地）+ 图内结构识别
                    #    （MiMo 视觉，严格串行）── 与批量 analyze-tree 一致
                    from ..common.batch import _docx_to_pdf, _extract_docx_images

                    tmp = _download_to_tmp(fs, path, config.analyzer_tmp_dir)
                    if tmp:
                        try:
                            if vision_client is None:
                                vision_client = create_llm_client(
                                    LLMConfig.from_dict(config.llm_vision))
                            flow_text = _extract_docx_images(tmp, vision_client)
                        except Exception:
                            flow_text = ""
                        if flow_text and not result.text:
                            # 图片型 docx（扫描件放入 Word，无文本层）
                            entry.ocr_text = flow_text[: config.analyzer_max_chars]
                            entry.content_description = flow_text[:2000]
                            entry.category = "扫描件"
                        elif result.text and flow_text:
                            # 有文本层：正文在 ocr_text，图文流单独存
                            entry.content_description = flow_text[:2000]

                        # ── 档位 2：图片型 docx → Word 渲染 PDF →
                        #    MinerU 版面 + OCR 全文（与批量一致）──
                        pdf_path = None
                        if (not (result.text or "").strip()
                                and config.mineru_enabled
                                and mineru.available()):
                            if word_app is None:
                                from ..common.batch import _make_word_app
                                word_app = _make_word_app()
                            if word_app:
                                try:
                                    pdf_path = _docx_to_pdf(word_app, tmp)
                                    if pdf_path:
                                        out_dir = os.path.join(
                                            os.path.dirname(path),
                                            config.desc_repo_name,
                                            "artifacts", Path(path).stem)
                                        r = mineru.parse(pdf_path, out_dir)
                                        if r["ok"] and r.get("md_path"):
                                            with open(r["md_path"],
                                                      encoding="utf-8") as mf:
                                                md_text = mf.read()
                                            if md_text:
                                                entry.ocr_text = md_text[: config.analyzer_max_chars]
                                                entry.content_description = flow_text[:2000]
                                                entry.category = "扫描件"
                                            repo_dir = os.path.join(
                                                os.path.dirname(path),
                                                config.desc_repo_name)
                                            entry.exif["mineru_artifacts"] = {
                                                k: (os.path.relpath(v, repo_dir)
                                                     if v else None)
                                                for k, v in r.items()
                                                if k in ("md_path", "html_path",
                                                         "middle_json", "images_dir")
                                            }
                                            print(f"[naskb] MinerU 解析完成 → {r['md_path']}")
                                except Exception:
                                    pass
                        _rm_tmp(pdf_path)
                        _rm_tmp(tmp)
                size = entry.size_bytes or 0
                ratio = (len(result.text or "") / size) if size else 0.0
                # 扫描件（图片页 + 文本稀薄）→ 强制 MinerU 重新 OCR；
                # 其余按双路径判定（文本量/占比）
                scan_like = bool((result.metadata.exif or {}).get("scan_like"))
                if (config.mineru_enabled
                        and ext != ".docx"   # docx 已由档位 1/2 全权处理
                        and (scan_like
                             or mineru.needs_mineru(
                                 ratio, config.mineru_fast_text_ratio,
                                 text_len=len(result.text or ""),
                                 min_text_chars=config.mineru_min_text_chars))
                        and ext not in {".txt", ".md", ".km", ".mmap", ".doc", ".xls"}):
                    if mineru.available():
                        tmp = _download_to_tmp(fs, path, config.analyzer_tmp_dir)
                        if tmp:
                            out_dir = os.path.join(
                                os.path.dirname(path), config.desc_repo_name,
                                "artifacts", Path(path).stem)
                            r = mineru.parse(tmp, out_dir)
                            if r["ok"]:
                                md_text = ""
                                if r.get("md_path"):
                                    with open(r["md_path"], encoding="utf-8") as f:
                                        md_text = f.read()
                                if md_text:
                                    entry.ocr_text = md_text[: config.analyzer_max_chars]
                                    if not llm:
                                        entry.summary = md_text[:200]
                                # 记录产物（相对 .naskb 目录的路径）
                                repo_dir = os.path.join(
                                    os.path.dirname(path), config.desc_repo_name)
                                entry.exif["mineru_artifacts"] = {
                                    k: (os.path.relpath(v, repo_dir)
                                         if v else None)
                                    for k, v in r.items()
                                    if k in ("md_path", "html_path",
                                             "middle_json", "images_dir")
                                }
                                print(f"[naskb] MinerU 解析完成 → {r['md_path']}")
                            else:
                                print(f"[naskb] MinerU 解析失败（降级保留快速提取）: "
                                      f"{r['error']}")
                            _rm_tmp(tmp)
                    else:
                        print("[naskb] 检测到扫描件/复杂版面，但 MinerU 未安装 "
                              "（pip install mineru，需 Python<3.14）；"
                              "降级使用快速提取结果")
                text_for_llm = entry.ocr_text or ""
                if flow_text and result.text and ext == ".docx":
                    # 有文本层的 docx：摘要输入拼上图文流（图结构+位置），
                    # 正文仍完整保留在 ocr_text（与批量一致）
                    text_for_llm = (result.text + "\n\n[图文结构]\n" + flow_text)[
                        : config.analyzer_max_chars]
                if llm and text_for_llm:
                    llm_client = create_llm_client(
                        LLMConfig.from_dict(config.llm_text))
                    try:
                        data = llm_client.complete_json(
                            f"这是文件内容:\n{text_for_llm[:4000]}\n\n"
                            "输出 JSON: {\"summary\": 一句话中文摘要, \"tags\": [3-6个中文标签], "
                            "\"category\": 建议分类目录, \"confidence\": 0-1}")
                        entry.summary = str(data.get("summary", ""))
                        entry.tags = [str(t) for t in (data.get("tags") or []) if t]
                        entry.category = str(data.get("category", ""))
                        entry.confidence = _safe_float(data.get("confidence"), 0.5)
                    except Exception as e:
                        # LLM 失败降级：保留提取文本，不中断分析
                        print(f"[naskb] LLM 摘要失败（降级使用提取文本）: {e}")
                        entry.summary = text_for_llm[:200]
                if not llm and text_for_llm:
                    entry.summary = text_for_llm[:200]

            elif ext in IMAGE_EXTS:
                # ── 图片：EXIF + MiMo 视觉（全走大模型）──
                tmp = _download_to_tmp(fs, path, config.analyzer_tmp_dir)
                if tmp:
                    llm_client = create_llm_client(
                        LLMConfig.from_dict(config.llm_vision))
                    ia = ImageAnalyzer(llm_client)
                    desc_text, meta = ia.analyze(tmp)
                    entry.summary = desc_text[:200]
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
                tmp = _download_to_tmp(fs, path, config.analyzer_tmp_dir)
                if tmp:
                    llm_client = create_llm_client(
                        LLMConfig.from_dict(config.llm_audio))
                    aa = AudioAnalyzer(
                        llm_client,
                        split_seconds=config.llm_audio_split_minutes * 60,
                        diarization=config.llm_audio_diarization,
                    )
                    entry.transcription = aa.transcribe(tmp)
                    entry.summary = (entry.transcription or "")[:200]
                    entry.category = "音频"
                    _rm_tmp(tmp)

            elif ext in VIDEO_EXTS:
                # ── 视频：ffprobe + 分级（影视仅元数据，个人录像全量）──
                llm_client = create_llm_client(
                    LLMConfig.from_dict(config.llm_audio))
                aa = AudioAnalyzer(
                    llm_client,
                    split_seconds=config.llm_audio_split_minutes * 60,
                    diarization=config.llm_audio_diarization,
                )
                classifier = VideoClassifier(
                    category_paths=config.video_category_paths,
                    category_keywords=config.video_category_keywords,
                    duration_threshold_min=config.video_duration_threshold_min,
                )
                va = VideoAnalyzer(
                    llm_client, classifier,
                    keyframes_max=config.video_keyframes_max,
                    keyframe_interval_sec=config.video_keyframe_interval_sec,
                    audio_analyzer=aa,
                )
                tmp = _download_to_tmp(fs, path, config.analyzer_tmp_dir)
                if tmp:
                    result = va.analyze(tmp)
                    meta = result["meta"]
                    entry.category = result["category"]
                    entry.processing_policy = result["policy"]
                    entry.transcription = result["transcription"]
                    entry.duration_seconds = meta.get("duration_seconds")
                    entry.width = meta.get("width")
                    entry.height = meta.get("height")
                    entry.exif = {"codec": meta.get("codec") or "",
                                  "container": meta.get("container") or ""}
                    entry.file_type = f"video/{meta.get('container') or 'x-unknown'}"
                    entry.summary = (entry.transcription or "")[:200] or \
                        f"视频 {result['category']}（{result['policy']}）"
                    _rm_tmp(tmp)

            else:
                # 被忽略文件：不分析内容，仅按文件名记录可能的意义
                st = fs.stat(path)
                entry = FileEntry()
                entry.original_path = path
                entry.processing_policy = "metadata_only"
                entry.file_type = guess_mime(os.path.basename(path))
                if st:
                    entry.size_bytes = st.size_bytes
                    entry.mtime = st.mtime
                entry.summary = (f"可能为{meaning_of(os.path.basename(path))}："
                                 f"{os.path.basename(path)}"
                                 f"（未分析内容，仅按文件名记录）")
                if store.set_entry(path, entry):
                    print(f"[naskb] 忽略文件已记录（仅名称推断，未分析内容）: {path}")
                    print(f"  摘要: {entry.summary[:80]}")
                else:
                    print(f"[naskb] 忽略文件记录失败: {path}")
                return

            ok = store.set_entry(path, entry)
            repo = store.repo_dir(store.dir_of(path))
            if ok:
                print(f"[naskb] 描述已写入: {repo}/index.json")
                print(f"  分类: {entry.category or '(未分类)'}")
                print(f"  摘要: {(entry.summary or '')[:80]}")
                if entry.transcription:
                    print(f"  转写: {entry.transcription[:80]}...")
                if entry.processing_policy != "full":
                    print(f"  策略: {entry.processing_policy}")
                # 级联更新该目录及上层 folder.json（内容已变化，上层同样受影响）
                try:
                    from ..common.analyzer.folder import FolderAnalyzer
                    fa = FolderAnalyzer(
                        llm_client if llm else None,
                        excluded_folders=config.exclusions.get("folder", []))
                    t = os.path.dirname(os.path.abspath(path))
                    updated = 0
                    while fs.is_dir(t):
                        if f"/{config.desc_repo_name}/" in t.replace("\\", "/"):
                            break
                        if fs.is_dir(store.repo_dir(t)):
                            try:
                                e2 = fa.analyze(fs, t)
                                if store.write_folder(t, e2):
                                    updated += 1
                            except Exception:
                                pass
                        parent = os.path.dirname(t)
                        if parent == t:
                            break
                        t = parent
                    if updated:
                        print(f"[naskb] 目录级描述级联更新: {updated} 个目录")
                except Exception:
                    pass
            else:
                print(f"[naskb] 描述写入失败: {path}")
        finally:
            if llm_client:
                llm_client.close()
            if vision_client:
                vision_client.close()
            if word_app:
                try:
                    word_app.Quit()
                except Exception:
                    pass
    finally:
        fs.close()


@desc.command("move")
@click.argument("src")
@click.argument("dst")
@click.pass_context
def desc_move(ctx, src, dst):
    """移动文件并同步其描述条目（跨目录时旧仓库删条目、新仓库加条目）。"""
    store, fs, _ = _make_desc_store(ctx, path_hint=src)
    try:
        ok = store.move_entry(src, dst)
        print(f"[naskb] 已移动: {src} -> {dst} {'✓' if ok else '✗'}")
        e = store.get_entry(dst)
        if e is not None:
            print(f"[naskb] 描述已跟随（original: {e.original_path}）")
    finally:
        fs.close()


@desc.command("orphans")
@click.argument("root", required=False, default=".")
@click.option("--delete", "do_delete", is_flag=True, default=False,
              help="从 index.json 移除孤儿条目")
@click.pass_context
def desc_orphans(ctx, root, do_delete):
    """查找 index.json 中有记录但文件已不存在的孤儿条目。"""
    store, fs, _ = _make_desc_store(ctx, path_hint=root)
    try:
        orphans = store.find_orphans(root)
        if not orphans:
            print("[naskb] 没有孤儿条目。")
            return
        print(f"[naskb] 发现 {len(orphans)} 个孤儿条目:")
        for o in orphans:
            print(f"  {o}")
        if do_delete:
            for o in orphans:
                store.remove_entry(os.path.join(root, o))
            print(f"[naskb] 已移除 {len(orphans)} 个孤儿条目。")
    finally:
        fs.close()


@desc.command("analyze-tree")
@click.argument("root")
@click.option("--llm/--no-llm", default=False,
              help="调用 DeepSeek 生成摘要/标签/分类（并发 4-6，其余环节严格串行）")
@click.option("--workers", type=int, default=4, show_default=True,
              help="DeepSeek 并发数（建议 4-6）")
@click.option("--no-mineru", is_flag=True, default=False,
              help="禁用 MinerU（不处理扫描件 OCR）")
@click.option("--limit", type=int, default=None,
              help="只处理前 N 个文件（试跑用）")
@click.option("--force", is_flag=True, default=False,
              help="强制重新分析（默认增量：hash 未变且已有摘要则跳过）")
@click.pass_context
def desc_analyze_tree(ctx, root, llm, workers, no_mineru, limit, force):
    """批量分析目录树（单进程 + DeepSeek 并发摘要）。

    并发策略：DeepSeek 4-6 并发；MinerU / ffmpeg / MiMo（图片音视频）
    严格串行；Word COM 单实例复用。增量幂等，可重复执行。
    """
    from ..common.batch import analyze_tree

    store, fs, config = _make_desc_store(ctx, path_hint=root)
    last = [0]

    def _progress(done, total, name, status):
        if done - last[0] >= 5 or done == total:
            print(f"[naskb] 进度 {done}/{total} | {name} ({status})", flush=True)
            last[0] = done

    try:
        result = analyze_tree(
            fs, store, config, root,
            llm=llm, workers=max(1, min(workers, 8)),
            mineru=not no_mineru, limit=limit, force=force,
            on_progress=_progress,
        )
        print("\n[naskb] ═══ 批量分析汇总 ═══")
        print(f"  文件总数: {result.total}（支持 {result.supported}，不支持 {result.unsupported}）")
        print(f"  新分析: {result.analyzed}")
        print(f"  增量跳过: {result.skipped}")
        print(f"  忽略文件记录: {result.ignored_recorded}（仅名称推断，未分析内容）")
        print(f"  目录描述更新: {result.folder_updated}")
        print(f"  孤儿条目清理: {result.orphans_removed}（文件已删除）")
        print(f"  失败: {result.failed}（LLM 降级: {result.llm_failed}）")
        print(f"  耗时: {result.elapsed / 60:.1f} 分钟")
    finally:
        fs.close()


@desc.command("split")
@click.argument("root", required=False, default=".")
@click.pass_context
def desc_split(ctx, root):
    """批量拆分：把所有仍存在 index.json 中的完整原数据迁到独立文件。

    旧格式（全文在 index.json 内）→ 新格式（.naskb/files/<源文件>.json），
    index.json 只留轻量索引。递归处理 root 下所有 .naskb 仓库。
    """
    store, fs, config = _make_desc_store(ctx, path_hint=root)
    repo_name = config.desc_repo_name
    try:
        total = 0
        for f in fs.list_files(root, recursive=True):
            if f.name != "index.json":
                continue
            if f"/{repo_name}/" not in f.path.replace("\\", "/"):
                continue
            d = os.path.dirname(os.path.dirname(f.path))
            n = store.split_index(d)
            if n:
                total += n
                print(f"[naskb] {d}: 拆分 {n} 个条目 → {repo_name}/files/")
        print(f"[naskb] 完成: 共拆分 {total} 个条目")
    finally:
        fs.close()


@desc.command("migrate")
@click.argument("root", required=False, default=".")
@click.option("--delete", "do_delete", is_flag=True, default=False,
              help="迁移后删除旧 .sidecar.json")
@click.pass_context
def desc_migrate(ctx, root, do_delete):
    """把旧 .sidecar.json 数据迁入 .naskb/index.json（v1 → v2 迁移）。"""
    import json

    from ..common.sidecar import SidecarData

    store, fs, _ = _make_desc_store(ctx, path_hint=root)
    try:
        migrated = 0
        for f in fs.list_files(root, recursive=True):
            if not f.name.endswith(".sidecar.json"):
                continue
            src = f.path[: -len(".sidecar.json")]  # 旧 sidecar 同行：源文件路径
            try:
                data = SidecarData.from_dict(
                    json.loads(fs.read_text(f.path)))
            except Exception:
                print(f"[naskb] 跳过损坏的 sidecar: {f.path}")
                continue
            if not data.file_hash:
                continue
            entry = _entry_from_sidecar(data)
            store.set_entry(src, entry)
            migrated += 1
            if do_delete:
                fs.delete(f.path)
        print(f"[naskb] 迁移完成: {migrated} 个 .sidecar.json → .naskb/index.json")
    finally:
        fs.close()


@desc.command("analyze-folder")
@click.argument("path")
@click.option("--llm/--no-llm", default=True,
              help="调用 DeepSeek 生成目录结构摘要（默认开启）")
@click.option("--recursive", "-r", is_flag=True, default=False,
              help="递归分析所有子目录（每个目录都生成 folder.json）")
@click.pass_context
def desc_analyze_folder(ctx, path, llm, recursive):
    """目录级分析：统计目录结构 → DeepSeek 摘要 → 写入 .naskb/folder.json。

    用于软件/代码/库/发布包等"文件多但不需要逐文件分析"的目录；
    --recursive 时为每个子目录也生成 folder.json。
    """
    from ..common.analyzer.folder import FolderAnalyzer
    from ..common.llm import LLMConfig, create_llm_client

    store, fs, config = _make_desc_store(ctx, path_hint=path)
    llm_client = None
    try:
        if llm:
            llm_client = create_llm_client(LLMConfig.from_dict(config.llm_text))
        fa = FolderAnalyzer(
            llm_client,
            excluded_folders=config.exclusions.get("folder", []))

        targets: list[str]
        if recursive:
            # 递归收集所有含文件的目录（含根），排除描述仓库自身与
            # 隐藏/排除目录（.git、node_modules 等不生成 folder.json）；
            # 用 realpath 归一化（Windows 8.3 短名/长名去重），保持稳定排序
            repo_name = config.desc_repo_name
            excl = {x.lower() for x in config.exclusions.get("folder", [])}
            raw: set[str] = set()
            for f in fs.list_files(path, recursive=True):
                p = f.path.replace("\\", "/")
                if f"/{repo_name}/" in p:
                    continue
                parts = p.split("/")
                if any(seg.startswith(".") or seg.lower() in excl
                       for seg in parts[:-1]):
                    continue
                raw.add(os.path.dirname(f.path))
            raw = sorted(raw)
            seen: set[str] = set()
            targets = []
            for t in raw:
                key = os.path.normcase(os.path.realpath(t))
                if key in seen:
                    continue
                seen.add(key)
                targets.append(t)
            root_p = fs.resolve_path(path) if hasattr(fs, "resolve_path") else path
            if os.path.normcase(os.path.realpath(root_p)) not in seen:
                targets.append(root_p)
        else:
            targets = [path]

        total_ok = 0
        for t in targets:
            try:
                entry = fa.analyze(fs, t)
                if store.write_folder(t, entry):
                    total_ok += 1
                    print(f"[naskb] 目录级描述已写入: {store.folder_path(t)}")
                    print(f"  摘要: {entry.summary}")
                    print(f"  标签: {', '.join(entry.tags) or '(无)'}")
            except Exception as e:
                print(f"[naskb] 目录分析失败: {t}: {e}")
        print(f"[naskb] 完成: {total_ok}/{len(targets)} 个目录写入 folder.json")
    finally:
        if llm_client:
            llm_client.close()
        fs.close()


@desc.command("search")
@click.argument("query")
@click.option("--root", required=False, default=".",
              help="扫描根目录（含 .naskb/ 描述数据）")
@click.option("--top-k", "-k", default=10, show_default=True)
@click.option("--vector/--no-vector", "vector", default=None,
              help="强制向量/BM25 检索；默认有向量索引用向量、否则 BM25")
@click.pass_context
def desc_search(ctx, query, root, top_k, vector):
    """基于 .naskb 描述数据的语义（向量）/BM25 搜索（不读文件原文）。"""
    from ..common.retrieval import BM25Index, collect_docs

    store, fs, config = _make_desc_store(ctx, path_hint=root)
    emb = None
    try:
        docs = collect_docs(fs, root)
        if not docs:
            print("[naskb] 没有找到任何描述数据（先运行 desc analyze）")
            return
        if vector is not False:
            try:
                from ..common.embeddings import Embedder
                from ..common.vector_index import VectorIndex
                emb = Embedder(config.work_path)
                index = VectorIndex(emb, config.work_path)
                if index.load():
                    hits = index.search(query, top_k=top_k)
                    print(f"[naskb] 语义搜索 \"{query}\" → {len(hits)} 条"
                          f"（向量索引 {index.count()} 条）")
                    _print_hits(hits)
                    return
                emb.close()
                emb = None
            except Exception:
                if emb:
                    emb.close()
                    emb = None
        if vector:
            print("[naskb] 未找到向量索引（先运行 desc index-vectors），降级 BM25")
        index = BM25Index()
        index.build(docs)
        hits = index.search(query, top_k=top_k)
        print(f"[naskb] 模糊搜索 \"{query}\" → {len(hits)} 条（共 {len(docs)} 条描述）")
        _print_hits(hits)
    finally:
        if emb:
            emb.close()
        fs.close()


def _print_hits(hits) -> None:
    for i, h in enumerate(hits, 1):
        print(f"  {i}. [{h['score']:.3f}] {h['path']}（{h['category'] or '未分类'}）")
        if h["summary"]:
            print(f"     {h['summary'][:100]}")
        if h.get("tags"):
            print(f"     标签: {', '.join(h['tags'][:6])}")


@desc.command("ask")
@click.argument("question")
@click.option("--root", required=False, default=".",
              help="扫描根目录（含 .naskb/ 描述数据）")
@click.option("--top-k", "-k", default=5, show_default=True,
              help="检索条数（上下文大小）")
@click.option("--vector/--no-vector", "vector", default=None,
              help="强制向量/BM25 检索；默认有向量索引用向量、否则 BM25")
@click.pass_context
def desc_ask(ctx, question, root, top_k, vector):
    """RAG 问答：语义/BM25 检索 .naskb 描述 → DeepSeek 生成回答（带来源）。"""
    from ..common.llm import LLMConfig, create_llm_client
    from ..common.retrieval import BM25Index, ask, collect_docs

    store, fs, config = _make_desc_store(ctx, path_hint=root)
    llm_client = None
    emb = None
    try:
        docs = collect_docs(fs, root)
        if not docs:
            print("[naskb] 没有找到任何描述数据（先运行 desc analyze）")
            return
        index = None
        if vector is not False:
            try:
                from ..common.embeddings import Embedder
                from ..common.vector_index import VectorIndex
                emb = Embedder(config.work_path)
                index = VectorIndex(emb, config.work_path)
                if index.load():
                    print(f"[naskb] 向量检索（索引 {index.count()} 条）")
                else:
                    index = None
                    emb.close()
                    emb = None
            except Exception:
                if emb:
                    emb.close()
                    emb = None
                index = None
        if index is None:
            if vector:
                print("[naskb] 未找到向量索引（先运行 desc index-vectors），降级 BM25")
            index = BM25Index()
            index.build(docs)
        llm_client = create_llm_client(LLMConfig.from_dict(config.llm_text))
        result = ask(llm_client, index, question, top_k=top_k)
        print(f"[naskb] 回答:\n{result['answer']}")
        if result["sources"]:
            print("\n来源:")
            for s in result["sources"]:
                print(f"  {s}")
    finally:
        if llm_client:
            llm_client.close()
        if emb:
            emb.close()
        fs.close()


@desc.command("index-vectors")
@click.option("--root", required=False, default=".",
              help="扫描根目录（含 .naskb/ 描述数据）")
@click.pass_context
def desc_index_vectors(ctx, root):
    """构建语义向量索引（bge-small-zh 本地嵌入，供 search/ask 向量检索）。

    首次运行自动下载模型（~24MB）到工作区 models/；索引存 db/vectors。
    """
    from ..common.embeddings import Embedder
    from ..common.retrieval import collect_docs
    from ..common.vector_index import VectorIndex, index_paths

    store, fs, config = _make_desc_store(ctx, path_hint=root)
    emb = None
    try:
        docs = collect_docs(fs, root)
        if not docs:
            print("[naskb] 没有找到任何描述数据（先运行 desc analyze）")
            return
        emb = Embedder(config.work_path)
        index = VectorIndex(emb, config.work_path)
        n = index.build(docs)
        npz, _ = index_paths(config.work_path)
        print(f"[naskb] 向量索引已构建: {n} 条描述 → {npz}")
        print("[naskb] 之后 desc search / desc ask 将自动使用向量检索（无索引时降级 BM25）")
    finally:
        if emb:
            emb.close()
        fs.close()


@desc.command("plan-reorganize")
@click.argument("root", required=False, default=".")
@click.option("--apply", is_flag=True, default=False,
              help="执行方案中的移动（默认只输出方案，不移动任何文件）")
@click.option("--output", "-o", "output", default=None,
              help="把方案导出为 Markdown 文件（不指定则只打印到终端）")
@click.option("--max-items", default=300, show_default=True,
              help="纳入规划的文件清单条数上限（覆盖代表性文件）")
@click.pass_context
def desc_plan_reorganize(ctx, root, apply, output, max_items):
    """文件夹结构重组规划：DeepSeek 生成重组方案。

    默认只输出方案；--apply 才实际移动文件（描述条目跟随移动）；
    --output 可把方案导出为 Markdown 文件方便保存/分享。
    文件很多时清单按 --max-items 抽样，方案覆盖代表性文件。
    """
    from ..common.llm import LLMConfig, create_llm_client
    from ..common.reorganizer import Reorganizer

    store, fs, config = _make_desc_store(ctx, path_hint=root)
    llm_client = None
    try:
        # 重组方案 moves 列表长，需要大输出上限（默认 2048 会截断坏 JSON）
        cfg = LLMConfig.from_dict(config.llm_text)
        cfg.max_tokens = 8192
        llm_client = create_llm_client(cfg)
        rz = Reorganizer(llm_client, max_files=max_items)
        plan = rz.plan(store, root)
        print(f"[naskb] 重组方案: {plan['plan_name'] or '(未命名)'}")
        print(f"  说明: {plan['rationale']}")
        if plan["new_folders"]:
            print("  建议新目录: " + ", ".join(plan["new_folders"]))
        moves = plan["moves"]
        print(f"  移动计划: {len(moves)} 条（共 {plan['total']} 个文件）")
        for m in moves:
            print(f"    {m['from']}")
            print(f"      → {m['to']}  ({m['reason']})")
        if apply:
            result = rz.apply(store, plan)
            print(f"[naskb] 已执行: 成功 {len(result['moved'])}，失败 {len(result['failed'])}")
            for src, dst, err in result["failed"]:
                print(f"  失败 {src} → {dst}: {err}")
            if result.get("removed_dirs"):
                print(f"[naskb] 已清理搬空的源目录: {len(result['removed_dirs'])} 个")
            # 级联更新源/目标及上层目录的 folder.json（必须：内容已变化）
            _refresh_folders(store, fs, config, llm_client, root,
                             result.get("affected_dirs") or [])
        else:
            print("\n[提示] 仅输出方案，未移动任何文件。确认后加 --apply 执行。")
        if output:
            _write_plan_markdown(output, plan, applied=apply)
            print(f"[naskb] 方案已导出: {os.path.abspath(output)}")
    finally:
        if llm_client:
            llm_client.close()
        fs.close()


def _refresh_folders(store, fs, config, llm_client, root: str,
                     dirs: list[str]) -> None:
    """对受影响目录（含祖先链，到 root 为止）级联重算 folder.json。

    用于移动/增删文件后同步目录级描述；跳过不存在与仓库内部路径。
    """
    from ..common.analyzer.folder import FolderAnalyzer

    fa = FolderAnalyzer(llm_client,
                        excluded_folders=config.exclusions.get("folder", []))
    repo_name = config.desc_repo_name
    targets: set[str] = set()
    root_abs = os.path.normcase(os.path.normpath(root))
    for d in dirs or []:
        cur = os.path.normcase(os.path.normpath(d))
        while True:
            if f"/{repo_name}/" in cur.replace("\\", "/"):
                break
            targets.add(cur)
            if cur == root_abs or os.path.dirname(cur) == cur:
                break
            cur = os.path.normcase(os.path.normpath(os.path.dirname(cur)))
    ok = 0
    for t in sorted(targets):
        if not fs.is_dir(t):
            continue
        try:
            entry = fa.analyze(fs, t)
            if store.write_folder(t, entry):
                ok += 1
        except Exception as e:
            print(f"[naskb] 目录描述更新失败 {t}: {e}")
    print(f"[naskb] 目录级描述级联更新: {ok}/{len(targets)} 个目录")


def _write_plan_markdown(output: str, plan: dict, applied: bool = False) -> None:
    """把重组方案写成 Markdown 文件。"""
    lines: list[str] = []
    lines.append(f"# 重组方案: {plan.get('plan_name') or '(未命名)'}")
    lines.append("")
    lines.append(f"- 状态: {'已执行' if applied else '待确认（未移动任何文件）'}")
    lines.append(f"- 文件总数: {plan.get('total', 0)}")
    lines.append(f"- 移动计划条数: {len(plan.get('moves', []))}")
    lines.append("")
    lines.append(f"## 说明\n\n{plan.get('rationale') or ''}")
    nf = plan.get("new_folders") or []
    if nf:
        lines.append("")
        lines.append("## 建议新目录")
        for d in nf:
            lines.append(f"- {d}")
    moves = plan.get("moves") or []
    lines.append("")
    lines.append("## 移动计划")
    lines.append("")
    lines.append("| # | 原路径 | 新路径 | 理由 |")
    lines.append("|---|--------|--------|------|")
    for i, m in enumerate(moves, 1):
        lines.append(f"| {i} | `{m.get('from')}` | `{m.get('to')}` | {m.get('reason')} |")
    lines.append("")
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _entry_from_sidecar(data) -> "FileEntry":
    """把旧 SidecarData 转为新 FileEntry。"""
    from ..common.desc_store import FileEntry

    return FileEntry(
        path=data.file_hash and "" or "",  # path 由 set_entry 填充
        file_hash=data.file_hash,
        analyzed_at=data.analyzed_at,
        analyzer_version=data.analyzer_version,
        file_type=data.metadata.file_type,
        size_bytes=data.metadata.file_size,
        mtime=0.0,
        content_description=data.analysis.content_description,
        category=data.analysis.category,
        tags=data.analysis.tags,
        summary=data.analysis.summary,
        language=data.analysis.language,
        confidence=data.analysis.confidence,
        transcription=data.transcription,
        ocr_text=data.ocr_text,
        exif=data.metadata.exif,
        duration_seconds=data.metadata.duration_seconds,
        width=data.metadata.width,
        height=data.metadata.height,
        original_path=data.provenance.original_path,
        moved_from=data.provenance.moved_from,
    )


def _download_to_tmp(fs, remote_path: str, tmp_dir: str) -> str:
    """下载文件到临时目录，返回本地路径；失败返回 None。

    临时文件名用 ASCII 安全格式（uuid + 原扩展名），避免中文文件名
    在传给 MinerU 等外部 CLI 时出现 ANSI 编码乱码。
    """
    import tempfile
    import uuid

    os.makedirs(tmp_dir, exist_ok=True)
    ext = Path(remote_path).suffix.lower()
    local = os.path.join(tmp_dir, f"dl-{os.getpid()}-{uuid.uuid4().hex[:8]}{ext}")
    try:
        with open(local, "wb") as f:
            for chunk in fs.read_chunks(remote_path):
                f.write(chunk)
        return local
    except Exception as e:
        print(f"[naskb] 下载失败: {e}")
        return None


def _rm_tmp(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass




# ═══════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════

def _safe_float(v, default: float = 0.0) -> float:
    """容错转换 float；非法输入返回 default。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    main()
