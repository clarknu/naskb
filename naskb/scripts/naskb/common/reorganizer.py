"""文件夹结构重组规划：分析现状 → DeepSeek 生成重组方案。

默认只输出方案不执行；--apply 时按方案移动文件（fs.move + desc_store 跟随）。

分片策略：文件多时（> max_files）按目录聚合后分片，每片独立让 LLM
输出归类建议（阶段 A），再汇总全部归类由 LLM 生成最终方案（阶段 B）——
保证所有文件的信息都进入规划，不遗漏（不再截断前 N 个文件）。
"""
from __future__ import annotations

import os
from typing import Any, Optional

from .desc_store import NaskbStore, REPO_DIR_NAME


def _dir_has_files(fs, path: str) -> bool:
    """目录下是否存在非目录项（空壳判定）。枚举失败按有内容处理（保守）。"""
    try:
        return any(not f.is_dir for f in fs.list_files(path, recursive=True))
    except Exception:
        return True


def _remove_empty_dir(fs, path: str) -> None:
    """移除空目录壳（仅本地文件系统；WebDAV 无 rmdir API 时静默跳过）。"""
    try:
        import shutil
        if hasattr(fs, "_resolve"):   # LocalAdapter 标记（本地实现）
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _tree_has_files(fs, path: str) -> bool:
    """目录树内是否存在任何文件（含 .naskb 内部）。枚举失败按有内容处理。"""
    try:
        return any(not f.is_dir for f in fs.list_files(path, recursive=True))
    except Exception:
        return True


def _remove_if_empty_tree(fs, path: str) -> bool:
    """目录树内无任何文件时删除整棵树（仅本地），返回是否删除。"""
    if not fs.is_dir(path):
        return False
    if _tree_has_files(fs, path):
        return False
    try:
        import shutil
        if hasattr(fs, "_resolve"):
            shutil.rmtree(path, ignore_errors=True)
            return not os.path.exists(path)
    except Exception:
        pass
    return False


def _remove_empty_chain(fs, start_dir: str) -> list[str]:
    """从 start_dir 向上删除连续的空目录（只删空目录树，绝不删有文件的），
    返回被删除的目录列表；驱动器根处停止。"""
    removed: list[str] = []
    cur = os.path.normpath(start_dir)
    while True:
        nxt = os.path.dirname(cur)
        if nxt == cur:              # 驱动器根
            break
        if not fs.is_dir(cur):
            cur = nxt
            continue
        if not _remove_if_empty_tree(fs, cur):
            break
        removed.append(cur)
        cur = nxt
    return removed

# 顶层分类维度与归类原则（引导 LLM，用户拍板的语义在此体现）
CATEGORY_GUIDE = """
归类原则（顶层分类名可自由拟定，以下仅供参考）：
- 证件与身份：身份证、护照、户口、港澳通行证、驾驶证、结婚证、居住证、
  独生子女证等纯证件
- 工作与经营：劳动合同、参保证明、人才认定/签证材料（如 E类人才、香港高才）、
  个体工商户营业执照、工牌、个人履历、个人作品/文章
- 学习：课程、笔记、考试资料（雅思等）；学历学位证书可归此或证件类
- 财务与交易：发票、银行流水、交易记录、银行卡、保险单、理财/存款
- 房产与装修：房产证、租赁合同、装修设计/预算/图纸、水电改造
- 医疗健康：病历、体检报告、药品说明、就诊/试管记录
- 旅行与出行：旅行计划、机票酒店、旅游签证材料
- 个人照片：生活照片、人像
- 其他：无法归入上述类的

注意：目录里只要含工作/经营/履历/人才类内容（哪怕同时有证件类文件），
整目录优先归入"工作与经营"；只有纯证件才归"证件与身份"。
"""


class Reorganizer:
    """分析目录现状，生成重组方案（JSON），可选执行。"""

    def __init__(self, llm_client: Optional[Any] = None,
                 max_files: int = 400,
                 max_move_items: int = 100):
        self._llm = llm_client
        self._max_files = max_files
        self._max_move_items = max_move_items

    def collect(self, store: NaskbStore, root: str) -> dict:
        """收集现状：全量文件清单 + 目录树（排除 .naskb 仓库），不截断。"""
        fs = store._fs
        items = []
        dirs: set[str] = set()
        for f in fs.list_files(root, recursive=True):
            rel = f.path.replace("\\", "/")
            if f"/{REPO_DIR_NAME}/" in rel:  # 排除描述仓库自身
                continue
            if not f.is_dir:
                dirs.add(rel.rsplit("/", 1)[0])
            e = store.get_entry(f.path)
            items.append({
                "path": f.path,
                "ext": f.ext,
                "size": f.size_bytes,
                "category": e.category if e else "",
                "summary": (e.summary[:60] if e and e.summary else ""),
                "policy": (e.processing_policy if e else ""),
            })
        items.sort(key=lambda x: x["path"].lower())
        return {"root": root,
                "dirs": sorted(dirs, key=lambda d: (d.count("/"), d.lower())),
                "items": items,
                "total": len(items)}

    def plan(self, store: NaskbStore, root: str) -> dict:
        """生成重组方案：{"plan_name", "rationale", "new_folders", "moves"}。

        文件数 ≤ max_files 走单阶段（一次 LLM 调用）；
        超过则按目录分片两阶段（阶段 A 逐片归类 → 阶段 B 汇总成案），
        保证全部文件进入规划。
        """
        data = self.collect(store, root)
        if self._llm is None:
            return {"plan_name": "无方案（未提供 LLM）", "rationale": "",
                    "new_folders": [], "moves": [], "total": data["total"]}
        if data["total"] <= self._max_files:
            return self._plan_single(data)
        return self._plan_chunked(data)

    # ── 单阶段（文件量少）──

    def _plan_single(self, data: dict) -> dict:
        lines = [
            f"{it['path'].replace(chr(92), '/')}  [{it['category']}] {it['summary']}"
            for it in data["items"]
        ]
        listing = "\n".join(lines) or "（空目录）"
        dirs_text = "\n".join(data["dirs"]) or "（无子目录）"
        prompt = (
            f"你是个人 NAS 文件管理规划助手。下面是目录 {data['root']} 的现状：\n"
            f"目录结构（{len(data['dirs'])} 个目录）:\n{dirs_text}\n\n"
            f"文件清单（共 {data['total']} 个）:\n{listing}\n\n"
            "请规划一个更清晰合理的目录重组方案：按类型/用途归类，避免平铺混乱。\n"
            "优先使用目录级移动（from/to 为目录路径，一条指令归并整个目录），"
            "目录结构近似或同类的目录直接归并；散落在根下的文件逐文件移动。\n"
            f"{CATEGORY_GUIDE}\n\n"
            "输出 JSON: {\"plan_name\": \"方案名称\", "
            "\"rationale\": \"重组思路说明\", "
            "\"new_folders\": [\"建议新建的目录名\"], "
            "\"moves\": [{\"from\": \"原路径\", \"to\": \"新路径\", "
            "\"reason\": \"移动理由\"}]}\n"
            f"要求：moves 的 to 都必须位于 {data['root']} 之下；最多 "
            f"{self._max_move_items} 条；from 必须是清单中的路径（目录或文件）。"
        )
        return self._finalize_plan(self._llm.complete_json(prompt), data["total"])

    # ── 分片两阶段（文件量大）──

    def _plan_chunked(self, data: dict) -> dict:
        # 1) 按目录聚合为移动单元（目录 + 根散文件），保证片间不重叠
        units: list[dict] = []
        by_dir: dict[str, list[dict]] = {}
        root_norm = os.path.normpath(data["root"])
        for it in data["items"]:
            d = os.path.dirname(it["path"])
            by_dir.setdefault(d, []).append(it)
        for d, files in by_dir.items():
            rel_dir = os.path.relpath(d, root_norm).replace("\\", "/")
            if rel_dir == ".":      # 根目录散文件：逐文件成单元
                for it in files:
                    units.append({"path": it["path"], "is_dir": False,
                                  "files": [it]})
            else:
                units.append({"path": d, "is_dir": True, "files": files})
        units.sort(key=lambda u: u["path"].lower())

        # 2) 分片：每片累计文件数 ≤ max_files
        chunks: list[list[dict]] = []
        cur: list[dict] = []
        cur_n = 0
        for u in units:
            if cur and cur_n + len(u["files"]) > self._max_files:
                chunks.append(cur)
                cur, cur_n = [], 0
            cur.append(u)
            cur_n += len(u["files"])
        if cur:
            chunks.append(cur)

        # 3) 阶段 A：逐片 LLM 输出归类建议（folder → target）
        groups: list[dict] = []
        for chunk in chunks:
            d = self._llm.complete_json(self._chunk_prompt(chunk, data["total"]))
            for g in d.get("groups") or []:
                if not isinstance(g, dict):
                    continue
                folder = str(g.get("folder") or "").strip()
                target = str(g.get("target") or "").strip()
                if folder and target:
                    groups.append({"folder": folder, "target": target,
                                   "reason": str(g.get("reason", ""))[:80]})

        # 4) 阶段 B：汇总全部归类 → 最终方案
        return self._merge_plan(data, groups)

    def _chunk_prompt(self, chunk: list[dict], total: int) -> str:
        lines = []
        for u in chunk:
            head = u["path"].replace("\\", "/")
            if u["is_dir"]:
                lines.append(f"【目录】{head}（{len(u['files'])} 个文件）:")
            else:
                lines.append(f"【文件】{head}:")
            for it in u["files"][: self._max_files]:
                lines.append(
                    f"  {os.path.basename(it['path'])}  [{it['category']}] "
                    f"{it['summary'][:40]}")
        listing = "\n".join(lines)
        prompt = (
            f"你是个人 NAS 文件管理规划助手。全库共 {total} 个文件，"
            f"这是其中一部分的清单（按目录聚合）：\n{listing}\n\n"
            "请为每个目录/文件给出建议的顶层分类名（分类名请全局统一口径，"
            "如：证件与身份/工作与经营/学习/财务与交易/房产与装修/医疗健康/"
            "旅行与出行/个人照片/其他）。\n"
            f"{CATEGORY_GUIDE}\n\n"
            "输出 JSON: {\"groups\": [{\"folder\": \"清单中的目录或文件路径\", "
            "\"target\": \"建议顶层分类名\", \"reason\": \"简短理由\"}]}\n"
            "要求：folder 必须逐字对应清单中的路径，一个目录/文件一条。"
        )
        return prompt

    def _merge_plan(self, data: dict, groups: list[dict]) -> dict:
        lines = "\n".join(
            f"{g['folder']}  →  {g['target']}  ({g['reason']})" for g in groups)
        prompt = (
            f"你是个人 NAS 文件管理规划助手。目录 {data['root']} 的归类汇总"
            f"（共 {data['total']} 个文件，{len(groups)} 个移动单元）如下：\n"
            f"{lines}\n\n"
            "请整合为最终重组方案：统一顶层分类名（同类合并，可用数字前缀如 "
            "01_证件与身份），生成目录级移动计划。\n"
            "输出 JSON: {\"plan_name\": \"方案名称\", \"rationale\": \"重组思路说明\", "
            "\"new_folders\": [\"建议新建的顶层目录\"], "
            "\"moves\": [{\"from\": \"归类汇总中的原路径\", \"to\": \"目标路径\", "
            "\"reason\": \"移动理由\"}]}\n"
            f"要求：from 必须逐字对应归类汇总中的路径；to 位于 {data['root']} 之下；"
            f"目录整体移动一条即可；最多 {self._max_move_items} 条。"
        )
        return self._finalize_plan(self._llm.complete_json(prompt), data["total"])

    def _finalize_plan(self, d: dict, total: int) -> dict:
        """校验/过滤 LLM 返回的方案：no-op 与目标越界条目剔除。"""
        moves = []
        for m in d.get("moves") or []:
            if not isinstance(m, dict) or not m.get("from") or not m.get("to"):
                continue
            src, dst = str(m["from"]), str(m["to"])
            # 过滤 no-op（from == to）
            if os.path.normcase(os.path.normpath(src)) == \
                    os.path.normcase(os.path.normpath(dst)):
                continue
            moves.append({"from": src, "to": dst,
                          "reason": str(m.get("reason", ""))})
        return {
            "plan_name": str(d.get("plan_name", "")),
            "rationale": str(d.get("rationale", "")),
            "new_folders": [str(x) for x in (d.get("new_folders") or []) if x],
            "moves": moves[: self._max_move_items],
            "total": total,
        }

    def apply(self, store: NaskbStore, plan: dict) -> dict:
        """执行方案中的移动（store.move_entry：先移文件、后迁条目，原子）。

        支持目录级移动：from 是目录时递归移动其下所有文件（条目跟随，
        .naskb 整仓跟随）。子路径优先：moves 按 from 深度降序执行，
        避免"先移整目录、后抽子目录"时源路径已消失。
        移动完成后：清理被搬空的源目录（只删空目录树，绝不删有文件的）；
        返回 {"moved", "failed", "affected_dirs", "removed_dirs"}——
        affected_dirs 为源/目标涉及的目录（供调用方级联更新 folder.json）。
        """
        done: list[tuple[str, str]] = []
        failed: list[tuple[str, str, str]] = []
        fs = store._fs
        moves = sorted(plan.get("moves") or [],
                       key=lambda m: -str(m.get("from", "")).count(
                           os.sep) - str(m.get("from", "")).count("/"))
        affected: set[str] = set()
        removed: list[str] = []
        affected: set[str] = set()
        removed: list[str] = []
        for m in moves:
            src = os.path.normpath(m["from"])
            dst = os.path.normpath(m["to"])
            try:
                if os.path.normcase(src) == os.path.normcase(dst):
                    continue  # no-op 防御（plan 已过滤，双保险）
                if fs.is_dir(src):
                    moved, errs = self._move_dir(store, src, dst)
                    done.extend(moved)
                    failed.extend(errs)
                    if moved:
                        affected.add(src)
                        affected.add(dst)
                        affected.add(os.path.dirname(src))
                        affected.add(os.path.dirname(dst))
                        # 源目录搬空 → 清理空目录链（只删空目录树）
                        removed.extend(_remove_empty_chain(fs, src))
                    continue
                # 确保目标父目录存在（已存在则忽略）
                dst_dir = os.path.dirname(dst)
                if dst_dir:
                    try:
                        fs.mkdir(dst_dir)
                    except Exception:
                        pass
                if store.move_entry(src, dst):
                    done.append((src, dst))
                    affected.add(os.path.dirname(src))
                    affected.add(os.path.dirname(dst))
                    # 源父目录搬空 → 清理空目录链
                    removed.extend(_remove_empty_chain(fs, os.path.dirname(src)))
                else:
                    failed.append((src, dst, "move_entry 失败（文件或条目未移动）"))
            except Exception as e:
                failed.append((src, dst, str(e)))
        # 被删空目录的父级同样受影响（folder.json 统计变化）
        for r in removed:
            affected.add(os.path.dirname(r))
        return {"moved": done, "failed": failed,
                "affected_dirs": sorted(affected),
                "removed_dirs": removed}

    def _move_dir(self, store: NaskbStore, src_dir: str, dst_dir: str):
        """递归移动目录下所有文件（保持相对结构），条目跟随。

        完成后把源目录的 `.naskb/artifacts`（MinerU 解析产物）迁到目标
        目录，保证条目 `exif.mineru_artifacts` 的相对引用仍有效；目标已
        有产物时保留目标（跳过）。源 `.naskb` 的 index.json/folder.json
        留在原处（不删除）。
        """
        fs = store._fs
        moved: list[tuple[str, str]] = []
        failed: list[tuple[str, str, str]] = []
        src_dir = os.path.normpath(src_dir).replace("\\", "/")
        dst_dir = os.path.normpath(dst_dir).replace("\\", "/")
        for f in fs.list_files(src_dir, recursive=True):
            rel = f.path.replace("\\", "/")
            if f"/{REPO_DIR_NAME}/" in rel:
                continue
            sub = rel[len(src_dir):].lstrip("/")
            dst = (dst_dir + "/" + sub) if sub else dst_dir
            try:
                if store.move_entry(f.path, dst):
                    moved.append((f.path, dst))
                else:
                    failed.append((f.path, dst, "move_entry 失败（文件或条目未移动）"))
            except Exception as e:
                failed.append((f.path, dst, str(e)))
        # ── 整仓跟随：源 .naskb 的 artifacts/folder.json/meta.json 迁到
        #    目标目录；index.json 保留目标（新条目已由 move_entry 写入，
        #    源的已被逐个 remove 清空）。迁移完成后移除源 .naskb 空壳
        #    （仅本地；WebDAV 无 rmdir 时降级保留）。
        try:
            src_repo = os.path.join(src_dir, REPO_DIR_NAME)
            dst_repo = os.path.join(dst_dir, REPO_DIR_NAME)
            if not fs.exists(src_repo):
                return moved, failed
            # artifacts（ensure_repo 会在目标预建空 artifacts/，判空才迁）
            src_art = os.path.join(src_repo, "artifacts")
            dst_art = os.path.join(dst_repo, "artifacts")
            if fs.exists(src_art) and not _dir_has_files(fs, dst_art):
                if fs.exists(dst_art):
                    _remove_empty_dir(fs, dst_art)   # 空壳
                    if fs.exists(dst_art):
                        return moved, failed   # 移除失败（如 WebDAV）→ 跳过
                fs.mkdir(dst_repo)
                fs.move(src_art, dst_art)
            # folder.json / meta.json：目标没有才迁（新位置优先保留新生成）
            for name in ("folder.json", "meta.json"):
                sf = os.path.join(src_repo, name)
                df = os.path.join(dst_repo, name)
                if fs.exists(sf) and not fs.exists(df):
                    fs.mkdir(dst_repo)
                    fs.move(sf, df)
            # 源 .naskb 空壳移除（本地实现；失败则保留）
            if fs.exists(src_repo):
                _remove_empty_dir(fs, src_repo)
        except Exception:
            pass
        return moved, failed
