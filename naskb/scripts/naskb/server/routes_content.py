"""内容访问路由（REQ-R7-06/07/08）：目录浏览、文件元数据、下载代理、预览。

安全边界：一切寻址凭 source（alias/id）+ resource_id，不接受裸路径；
资源行必须属于该来源（source_id 校验），防跨库串取。
"""
from __future__ import annotations

import mimetypes
import os
import urllib.parse
from typing import Optional

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .ranges import content_range, parse_range

# 预览分类（REQ-R7-08 V1 档）
_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "ico"}
_VIDEO_EXTS = {"mp4", "webm", "m4v", "ogv"}          # 浏览器原生可播容器
_AUDIO_EXTS = {"mp3", "wav", "m4a", "flac", "aac", "ogg", "oga", "opus"}
_PDF_EXTS = {"pdf"}
_TEXT_EXTS = {"txt", "md", "markdown", "json", "xml", "yml", "yaml", "toml",
              "ini", "csv", "log", "py", "js", "ts", "css", "html", "htm",
              "c", "h", "cpp", "java", "go", "rs", "sh", "bat", "ps1",
              "sql", "conf"}
_OFFICE_EXTS = {"docx", "xlsx", "pptx"}
_TEXT_CAP = 512 * 1024


def _artifact_stream_url(row: dict, record) -> str:
    artifacts = row.get("artifacts") or {}
    if artifacts.get("html_path") or artifacts.get("md_path"):
        return (f"/api/files/{row['resource_id']}/parsed?src="
                f"{urllib.parse.quote(record.alias)}")
    return ""


def register_content_routes(app) -> None:

    def st(request: Request):
        return request.app.state

    def resolve(request: Request, src: str, rid: str):
        """来源 + 资源行 + 适配器三元组（统一校验）。"""
        s = st(request)
        if s.pg is None:
            raise HTTPException(400, detail="内容访问需要配置 [pg] 知识主库")
        record = s.registry.get(src)
        if record is None:
            raise HTTPException(404, detail=f"来源不存在: {src}")
        row = s.pg.get_resource(record.schema_name, rid)
        if row is None:
            raise HTTPException(404, detail="资源不存在")
        row_sid = (row.get("source_id") or "").lower()
        if row_sid and row_sid != str(record.source_id).lower():
            raise HTTPException(404, detail="资源不属于该来源")
        return record, row, record.open_adapter()

    @staticmethod
    def _ext(name: str) -> str:
        return name.rsplit(".", 1)[-1].lower() if "." in name else ""

    # ── 目录浏览（罗列检索，REQ-R7-09）──

    @app.get("/api/tree")
    async def tree(request: Request, src: str = Query(""),
                   dir: str = Query("")):
        s = st(request)
        if s.pg is None:
            raise HTTPException(400, detail="浏览需要配置 [pg] 知识主库")
        record = s.registry.get(src)
        if record is None:
            raise HTTPException(404, detail=f"来源不存在: {src}")
        rel = dir.strip().strip("/")
        dirs, files = s.pg.list_dir(record.schema_name, record.source_id, rel)
        return {"source": record.to_api(), "dir": rel,
                "dirs": dirs, "files": files}

    # ── 文件元数据 ──

    @app.get("/api/files/{rid}")
    async def file_meta(request: Request, rid: str, src: str = Query("")):
        record, row, _fs = resolve(request, src, rid)
        ext = _ext(row["name"])
        return {
            "resource": {k: v for k, v in row.items()
                         if k not in ("source_id",)},
            "source": record.to_api(),
            "ext": ext,
            "viewable": _view_kind(ext),
            "download_url": (f"/api/files/{rid}/download?src="
                             f"{urllib.parse.quote(record.alias)}"),
            "preview_url": (f"/api/files/{rid}/preview?src="
                            f"{urllib.parse.quote(record.alias)}"),
        }

    # ── 下载代理（流式 + Range，REQ-R7-07）──

    @app.get("/api/files/{rid}/download")
    async def download(request: Request, rid: str, src: str = Query(""),
                       disposition: str = Query("attachment")):
        record, row, fs = resolve(request, src, rid)
        rel = row["rel_path"]
        try:
            fstat = fs.stat(rel)
        except Exception:
            fstat = None
        if fstat is None:
            raise HTTPException(
                503, detail={"error": "source_unreachable",
                             "hint": "来源不可达或文件已消失；"
                                     "可运行一次扫描对账"})
        size = int(fstat.size_bytes or row.get("size_bytes") or 0)
        etag = f'"{row["file_hash"]}"' if row.get("file_hash") else \
            f'W/"{size}-{int(fstat.mtime or 0)}"'
        headers = {
            "Accept-Ranges": "bytes",
            "ETag": etag,
            "X-NASKB-Status": row.get("status") or "ok",
        }
        # 新鲜度提示（不阻断：浏览器场景仍要能拿到内容）
        if (row.get("status") not in ("", "ok")) or \
                int(fstat.size_bytes or 0) != int(row.get("size_bytes") or 0) or \
                abs(float(fstat.mtime or 0) - float(row.get("mtime") or 0)) > 1e-6:
            headers["X-NASKB-Stale"] = "1"
        inm = (request.headers.get("if-none-match") or "").strip()
        if inm and inm == etag:
            return JSONResponse({}, status_code=304, headers=headers)

        rng, valid = parse_range(request.headers.get("range"), size)
        if not valid:
            return JSONResponse(
                {"error": "range_not_satisfiable"},
                status_code=416,
                headers={"Content-Range": f"bytes */{size}", **headers})

        media, _ = mimetypes.guess_type(row["name"])
        media = media or "application/octet-stream"
        fname = urllib.parse.quote(row["name"])
        disp = "inline" if disposition == "inline" else "attachment"
        headers["Content-Disposition"] = (
            f"{disp}; filename*=UTF-8''{fname}")

        if rng is None:
            headers["Content-Length"] = str(size)
            return StreamingResponse(
                fs.open_stream(rel), status_code=200,
                media_type=media, headers=headers)
        start, end = rng
        headers["Content-Range"] = content_range(start, end, size)
        headers["Content-Length"] = str(end - start + 1)
        return StreamingResponse(
            fs.open_stream(rel, start=start, end=end), status_code=206,
            media_type=media, headers=headers)

    # ── 预览（V1 档矩阵 + V2 增强：Office 简版 / 解析视图），REQ-R7-08 ──

    @app.get("/api/files/{rid}/preview")
    async def preview(request: Request, rid: str, src: str = Query("")):
        record, row, fs = resolve(request, src, rid)
        name = row["name"]
        ext = _ext(name)
        kind = _view_kind(ext)
        base = {"resource_id": rid, "name": name, "ext": ext,
                "status": row.get("status") or "ok",
                "size_bytes": row.get("size_bytes") or 0}
        if kind:
            base.update({
                "viewable": kind,
                "url": (f"/api/files/{rid}/download?src="
                        f"{urllib.parse.quote(record.alias)}"
                        f"&disposition=inline")})
            if kind == "text":
                try:
                    raw = fs.read_bytes(row["rel_path"],
                                        max_bytes=_TEXT_CAP)
                    base["content"] = raw.decode("utf-8", errors="replace")
                    base["truncated"] = (row.get("size_bytes") or 0) > _TEXT_CAP
                except Exception as e:
                    base["viewable"] = False
                    base["reason"] = f"text_read_failed: {e}"
            elif kind == "html":
                # 解析视图可用时优先展示（rw 源 MinerU HTML）
                parsed = _artifact_stream_url(row, record)
                if parsed:
                    base["viewable"] = "parsed"
                    base["parsed_url"] = (
                        f"/api/files/{rid}/parsed?src="
                        f"{urllib.parse.quote(record.alias)}")
                    base.pop("url", None)
                elif row["status"] == "missing_source":
                    base["viewable"] = False
                    base["reason"] = "missing_source"
            return base
        # 不支持类型：先尝试 Office 零依赖简版，再兜底提示+下载
        if kind == "office" and ext in ("docx", "xlsx") and \
                (row.get("size_bytes") or 0) <= 30 * 1024 * 1024:
            from ..common.batch import _download_to_tmp, _rm_tmp
            from .office import render
            config = st(request).config
            tmp = _download_to_tmp(fs, row["rel_path"],
                                   config.analyzer_tmp_dir)
            if tmp:
                try:
                    html = render(config, tmp, ext)
                    if html:
                        return {**base, "viewable": "html",
                                "content": html}
                finally:
                    _rm_tmp(tmp)
        return {**base, "viewable": False,
                "reason": "unsupported_type",
                "hint": "该类型暂不支持在线查看，可下载后本地打开",
                "download_url": (
                    f"/api/files/{rid}/download?src="
                    f"{urllib.parse.quote(record.alias)}")}

    # ── 解析视图（rw 源 MinerU HTML/md，复用源端产物）──

    @app.get("/api/files/{rid}/parsed")
    async def parsed(request: Request, rid: str, src: str = Query("")):
        record, row, fs = resolve(request, src, rid)
        artifacts = row.get("artifacts") or {}
        rel_artifact = artifacts.get("html_path") or artifacts.get("md_path")
        if not rel_artifact:
            raise HTTPException(404, detail="该文件未登记解析产物")
        parent = row.get("parent_dir") or ""
        repo_dir = f"{parent}/.naskb" if parent else ".naskb"
        full_rel = f"{repo_dir}/{str(rel_artifact).lstrip('/')}"
        if not fs.exists(full_rel):
            raise HTTPException(404, detail="解析产物已不存在（源端未保留）")
        is_html = bool(str(rel_artifact).endswith((".html", ".htm")))
        media = "text/html; charset=utf-8" if is_html else "text/plain; charset=utf-8"
        return StreamingResponse(fs.open_stream(full_rel),
                                 media_type=media)

    # ── 缩略图（图片/视频海报，store/thumbs 小缓存）──

    @app.get("/api/files/{rid}/thumbnail")
    async def thumbnail(request: Request, rid: str, src: str = Query(""),
                        w: int = Query(320)):
        record, row, fs = resolve(request, src, rid)
        from .thumb import thumbnail as _thumb
        w = max(64, min(int(w or 320), 1024))
        data = _thumb(st(request).pg, st(request).config, row, fs, w=w)
        if not data:
            raise HTTPException(404, detail="无法生成缩略图")
        return StreamingResponse(iter([data]),
                                 media_type="image/jpeg")


def _view_kind(ext: str):
    e = (ext or "").lower()
    if e in _IMAGE_EXTS:
        return "image"
    if e in _VIDEO_EXTS:
        return "video"
    if e in _AUDIO_EXTS:
        return "audio"
    if e in _PDF_EXTS:
        return "pdf"
    if e in _TEXT_EXTS:
        return "text"
    if e in _OFFICE_EXTS:
        return "office"
    return False
