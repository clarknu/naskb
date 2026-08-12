"""目录级分析（folder.json）：软件/代码/发布包目录不逐文件分析，只分析结构。

流程：统计目录树（子目录名/文件数/扩展名分布/大小/样例文件）→ 交 DeepSeek
生成结构摘要 → 写入 .naskb/folder.json。LLM 成本 ≈ 1 次调用/目录，极低。
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Any, Optional

from ..desc_store import FolderEntry


def _fmt_size(n: int) -> str:
    """字节 → 可读大小。"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"


class FolderAnalyzer:
    """目录级分析器：只读目录树结构，不下载/不解析文件内容。"""

    def __init__(self, llm_client: Optional[Any] = None,
                 max_sample_files: int = 60,
                 max_subdirs: int = 40,
                 excluded_folders: Optional[list[str]] = None):
        self._llm = llm_client
        self._max_sample_files = max_sample_files
        self._max_subdirs = max_subdirs
        # 统计时跳过这些目录段（node_modules 等；隐藏目录段始终跳过）
        self._excluded_folders = list(excluded_folders or [])

    def collect_structure(self, fs, dir_path: str,
                          repo_name: str = ".naskb") -> dict:
        """列出目录树结构统计（PROPFIND 级别，不读文件内容）。

        排除描述仓库自身（.naskb/ 内部文件不算目录内容），也排除隐藏目录
        （.git 等）与 excluded_folders 目录段内的文件。
        """
        files = [f for f in fs.list_files(dir_path, recursive=True)
                 if f"/{repo_name}/" not in f.path.replace("\\", "/")]
        base = fs.resolve_path(dir_path) if hasattr(fs, "resolve_path") else dir_path
        return self.build_structure(files, base, repo_name=repo_name,
                                    excluded_folders=self._excluded_folders)

    @staticmethod
    def build_structure(files, base_dir: str, repo_name: str = ".naskb",
                        max_sample_files: int = 60,
                        max_subdirs: int = 40,
                        excluded_folders: Optional[list[str]] = None) -> dict:
        """从全量文件列表构建单个目录的结构统计（复用一次递归扫描结果）。

        与 collect_structure 输出一致；batch 分析时避免对每个目录重复
        递归列目录（WebDAV 下开销大）。

        过滤规则：.naskb 仓库内部、相对 base 的路径中任何段为隐藏目录
        （. 开头）或在 excluded_folders（大小写不敏感）内的文件不计入。
        """
        import posixpath

        excl = {f.lower() for f in (excluded_folders or [])}
        base = base_dir.replace("\\", "/").rstrip("/") or "/"
        prefix = "/" if base == "/" else base + "/"  # WebDAV 挂载根边界
        sub = []
        for f in files:
            p = f.path.replace("\\", "/")
            if f"/{repo_name}/" in p:
                continue
            if p == base:
                rel = ""
            elif p.startswith(prefix):
                rel = p[len(prefix):]
            else:
                continue
            if any(seg.startswith(".") or seg.lower() in excl
                   for seg in rel.split("/") if seg):
                continue
            sub.append(f)
        ext_counter: Counter = Counter()
        subdirs: set[str] = set()
        total_size = 0
        max_depth = 0
        for f in sub:
            ext_counter[f.ext or "(无扩展名)"] += 1
            total_size += f.size_bytes
            p = f.path.replace("\\", "/")
            try:
                rel = posixpath.relpath(p, base)
            except ValueError:
                rel = p
            depth = 0 if rel == "." else rel.count("/")
            max_depth = max(max_depth, depth)
            if "/" in rel:
                subdirs.add(rel.split("/", 1)[0])
        names = sorted(f.name for f in sub)
        return {
            "dir": base_dir,
            "file_count": len(sub),
            "total_size_bytes": total_size,
            "total_size": _fmt_size(total_size),
            "max_depth": max_depth,
            "ext_distribution": dict(ext_counter.most_common(20)),
            "subdirs": sorted(subdirs)[: max_subdirs],
            "sample_files": names[: max_sample_files],
        }

    def analyze(self, fs, dir_path: str,
                prebuilt: Optional[dict] = None) -> FolderEntry:
        """收集结构 → 生成 FolderEntry（有 LLM 时生成结构摘要，否则仅统计）。

        prebuilt: 可选的预收集结构（build_structure 的输出），避免重复递归扫描。
        """
        struct = prebuilt if prebuilt is not None \
            else self.collect_structure(fs, dir_path)
        entry = FolderEntry()
        entry.file_type_distribution = struct["ext_distribution"]

        if self._llm is None:
            entry.summary = (f"目录 {struct['dir']}：{struct['file_count']} 个文件，"
                             f"共 {struct['total_size']}，最深 {struct['max_depth']} 层")
            entry.description = entry.summary
            return entry

        ext_lines = "\n".join(f"  {k}: {v}" for k, v in struct["ext_distribution"].items())
        sub_lines = "\n".join(f"  {s}/" for s in struct["subdirs"]) or "  （无子目录）"
        sample_lines = "\n".join(f"  {s}" for s in struct["sample_files"][:30])
        prompt = (
            f"这是一个 NAS 上的目录（可能是软件/代码/库/发布包，不逐文件分析）。\n"
            f"目录: {struct['dir']}\n"
            f"文件数: {struct['file_count']}，总大小: {struct['total_size']}，"
            f"目录深度: {struct['max_depth']}\n"
            f"扩展名分布:\n{ext_lines}\n"
            f"子目录:\n{sub_lines}\n"
            f"文件样例（前 30）:\n{sample_lines}\n\n"
            "输出 JSON: {\"description\": \"该目录是什么/用途的一句话说明\", "
            "\"structure\": [{\"name\": \"子目录或文件\", \"type\": \"dir|file\", "
            "\"summary\": \"作用说明\"}], "
            "\"tags\": [3-6个中文标签], \"summary\": \"一句话中文摘要\", "
            "\"language\": \"zh\", \"confidence\": 0-1}"
        )
        data = self._llm.complete_json(prompt)
        entry.description = str(data.get("description", ""))
        entry.structure = [
            {"name": str(s.get("name", "")), "type": str(s.get("type", "file")),
             "summary": str(s.get("summary", ""))}
            for s in (data.get("structure") or [])
            if isinstance(s, dict) and s.get("name")
        ][:20]
        entry.tags = [str(t) for t in (data.get("tags") or []) if t]
        entry.summary = str(data.get("summary", "")) or entry.description
        entry.language = str(data.get("language", "zh"))
        entry.confidence = float(data.get("confidence") or 0.0)
        return entry
