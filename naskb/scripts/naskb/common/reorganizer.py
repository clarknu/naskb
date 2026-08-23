"""文件夹结构重组规划：分析现状 → DeepSeek 生成重组方案。

默认只输出方案不执行；--apply 时按方案移动文件（fs.move + desc_store 跟随）。

分片策略：文件多时（> max_files）按目录聚合后分片，每片独立让 LLM
输出归类建议（阶段 A），再汇总全部归类由 LLM 生成最终方案（阶段 B）——
保证所有文件的信息都进入规划，不遗漏（不再截断前 N 个文件）。
"""
from __future__ import annotations

import os
import posixpath
from typing import Any, Optional

from .desc_store import NaskbStore, REPO_DIR_NAME

# ── 失败原因分类（P1-4）：apply 结果 failed[] 的 reason 枚举 ──
REASON_CONFLICT = "conflict"        # 文件 vs 目录等无法处理的冲突
REASON_STALE = "stale_source"       # 源在 plan 后被改动（快照不符，P0-3）
REASON_NOT_FOUND = "not_found"      # 源已消失（P0-3）
REASON_ENTRY = "entry"              # 条目移动/元数据迁移失败
REASON_IO = "io"                    # 底层文件系统错误


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


# ── 路径规范化与越界校验（P0-1）──

def _norm_compare(p: str) -> str:
    """规范化路径用于包含关系判定：统一 / 分隔、折叠 //、解析 ..、去尾斜杠。

    本地路径（盘符）按 Windows 大小写不敏感处理（normcase）；
    WebDAV/posix 路径（/ 开头）按原样大小写敏感。
    """
    p = p.replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    if len(p) >= 2 and p[1] == ":":
        p = os.path.normcase(os.path.normpath(p)).replace("\\", "/")
    else:
        p = posixpath.normpath(p)
    return p.rstrip("/")


def _is_under(base: str, target: str, strict: bool = False) -> bool:
    """target 是否位于 base 之下（含 base 本身；strict=True 时不含 base）。"""
    if target == base:
        return not strict
    if not base:
        return True
    return target.startswith(base + "/")


def validate_move(src: str, dst: str, root: str) -> tuple[bool, str]:
    """校验一条 move 是否合法：(ok, reason)。

    - dst 必须位于 root 之下（含 root 本身，允许移到根目录）；
    - src 必须严格位于 root 之下（src == root 拒绝，防整库移入子目录）；
    - 两者均不得落在 .naskb 仓库内部路径。
    用于 plan 生成后（_finalize_plan）与 apply 执行前（apply 开头）双重校验。
    """
    r, s, d = _norm_compare(root), _norm_compare(src), _norm_compare(dst)
    if not s or not d:
        return False, "空路径"
    if not r:
        return False, "root 为空"
    if not _is_under(r, s, strict=True):
        return False, f"源路径越界（不在 root 下）: {src}"
    if not _is_under(r, d):
        return False, f"目标路径越界（不在 root 下）: {dst}"
    for p in (s, d):
        if "/.naskb/" in p or p.endswith("/.naskb"):
            return False, "涉及 .naskb 仓库内部路径"
    return True, ""


def _valid_sources(data: dict) -> set[str]:
    """合法源路径集合（规范化）：清单中的文件 + 其全部祖先目录（到 root 为止）。

    覆盖目录级 move（目录自身不在 items 里，但作为文件祖先必然存在）。
    """
    valid: set[str] = set()
    root_norm = _norm_compare(str(data.get("root", "")))
    for it in data.get("items") or []:
        valid.add(_norm_compare(it["path"]))
        cur = _norm_compare(it["path"])
        while cur and cur != root_norm:
            parent = cur.rsplit("/", 1)[0]
            if not parent or parent == cur:
                break
            valid.add(parent)
            cur = parent
    return valid

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
        # 相对 → 规范绝对路径（与 items 的绝对路径一致，供越界校验使用）
        root = fs.resolve_path(root)
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
                "hash": (e.file_hash if e else ""),   # P0-3 复检快照用
            })
        items.sort(key=lambda x: x["path"].lower())
        return {"root": root,
                "dirs": sorted(dirs, key=lambda d: (d.count("/"), d.lower())),
                "items": items,
                "total": len(items)}

    def plan(self, store: NaskbStore, root: str) -> dict:
        """生成重组方案：{"plan_name", "rationale", "new_folders", "moves",
        "root", "rejected", "snapshot"}。

        文件数 ≤ max_files 走单阶段（一次 LLM 调用）；
        超过则按目录分片两阶段（阶段 A 逐片归类 → 阶段 B 汇总成案），
        保证全部文件进入规划。
        snapshot（内部键，供 save_plan 持久化）：{规范化源路径: file_hash}，
        是 apply 复检（P0-3）的指纹依据。
        """
        data = self.collect(store, root)
        if self._llm is None:
            return {"plan_name": "无方案（未提供 LLM）", "rationale": "",
                    "new_folders": [], "moves": [], "total": data["total"],
                    "root": data["root"], "rejected": [],
                    "snapshot": self.snapshot_of(data)}
        if data["total"] <= self._max_files:
            return self._plan_single(data)
        return self._plan_chunked(data)

    @staticmethod
    def snapshot_of(data: dict) -> dict:
        """从 collect 数据构建复检快照：{规范化源路径: file_hash}。"""
        snap: dict[str, str] = {}
        for it in data.get("items") or []:
            h = it.get("hash") or ""
            if h:
                snap[os.path.normcase(os.path.normpath(it["path"]))] = h
        return snap

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
        return self._finalize_plan(self._llm.complete_json(prompt), data)

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
        return self._finalize_plan(self._llm.complete_json(prompt), data)

    def _finalize_plan(self, d: dict, data: dict) -> dict:
        """校验/过滤 LLM 返回的方案：no-op、越界、不在清单中的源路径剔除。

        不合法条目进 rejected（带原因），不静默丢弃；合法 moves 保留。
        """
        root = str(data.get("root", ""))
        valid = _valid_sources(data)
        moves: list[dict] = []
        rejected: list[dict] = []
        for m in d.get("moves") or []:
            if not isinstance(m, dict) or not m.get("from") or not m.get("to"):
                continue
            src, dst = str(m["from"]), str(m["to"])
            # 过滤 no-op（from == to）
            if os.path.normcase(os.path.normpath(src)) == \
                    os.path.normcase(os.path.normpath(dst)):
                continue
            # 越界 / .naskb 内部路径
            ok, reason = validate_move(src, dst, root)
            if not ok:
                rejected.append({"from": src, "to": dst, "reason": reason})
                continue
            # 源路径必须真实存在于清单（防 LLM 幻觉出不存在的路径）
            if _norm_compare(src) not in valid:
                rejected.append({"from": src, "to": dst,
                                 "reason": "源路径不在清单中"})
                continue
            moves.append({"from": src, "to": dst,
                          "reason": str(m.get("reason", ""))})
        return {
            "plan_name": str(d.get("plan_name", "")),
            "rationale": str(d.get("rationale", "")),
            "new_folders": [str(x) for x in (d.get("new_folders") or []) if x],
            "moves": moves[: self._max_move_items],
            "total": data.get("total", 0),
            "root": root,
            "rejected": rejected,
        }

    def apply(self, store: NaskbStore, plan: dict,
              snapshot: Optional[dict] = None) -> dict:
        """执行方案中的移动（store.move_entry：先移文件、后迁条目，原子）。

        支持目录级移动：from 是目录时递归移动其下所有文件（条目跟随，
        .naskb 整仓跟随）。子路径优先：moves 按 from 深度降序执行，
        避免"先移整目录、后抽子目录"时源路径已消失。
        安全：
        - P0-1：plan 携带 root 时，每条 move 执行前过 validate_move 越界
          复校验（双保险，防 plan 被外部篡改），不合法进 rejected 不执行；
        - P0-3：提供 snapshot（{规范化源路径: file_hash}，save_plan 持久化）
          时，文件级 move 执行前复检——源已消失 → not_found 跳过；
          hash 已变（plan 生成后被改动）→ stale_source 跳过，防按过期方案移动；
        - P0-2：目标已存在时三档判定（用户拍板）——内容相同 → noop 啥也不干；
          内容不同且目标无有效元数据 → meta_only 只迁元数据文件不动；
          否则 → rename（` (1)` 递增）后正常移动；文件 vs 目录 → failed[conflict]。
        移动完成后：清理被搬空的源目录（只删空目录树，绝不删有文件的）；
        返回 {"moved", "failed", "noops", "meta_onlys", "rejected",
              "affected_dirs", "removed_dirs"}——
        affected_dirs 为源/目标涉及的目录（供调用方级联更新 folder.json）。
        """
        done: list[tuple[str, str]] = []
        failed: list[dict] = []
        noops: list[dict] = []
        meta_onlys: list[dict] = []
        rejected: list[dict] = []
        fs = store._fs
        root = plan.get("root", "")
        moves = sorted(plan.get("moves") or [],
                       key=lambda m: -str(m.get("from", "")).count(
                           os.sep) - str(m.get("from", "")).count("/"))
        # ── 越界复校验（双保险；无 root 的旧 plan 跳过，兼容旧调用）──
        if root:
            keep: list[dict] = []
            for m in moves:
                src, dst = str(m.get("from", "")), str(m.get("to", ""))
                ok, reason = validate_move(src, dst, root)
                if ok:
                    keep.append(m)
                else:
                    rejected.append({"from": src, "to": dst, "reason": reason})
            moves = keep
        affected: set[str] = set()
        removed: list[str] = []
        for m in moves:
            src = os.path.normpath(m["from"])
            dst = os.path.normpath(m["to"])
            try:
                if os.path.normcase(src) == os.path.normcase(dst):
                    continue  # no-op 防御（plan 已过滤，双保险）
                # ── P0-3 快照复检（snapshot 提供时；目录级只查存在性）──
                if snapshot is not None:
                    if not fs.exists(src):
                        failed.append({"src": src, "dst": dst,
                                       "reason": REASON_NOT_FOUND})
                        continue
                    if not fs.is_dir(src):
                        want = snapshot.get(
                            os.path.normcase(os.path.normpath(src)))
                        if want:
                            try:
                                _alg, cur = store.compute_hash(src)
                            except Exception:
                                cur = ""
                            if cur != want:
                                failed.append({"src": src, "dst": dst,
                                               "reason": REASON_STALE})
                                continue
                if fs.is_dir(src):
                    moved, errs, nops, metas = self._move_dir(store, src, dst)
                    done.extend(moved)
                    failed.extend(errs)
                    noops.extend(nops)
                    meta_onlys.extend(metas)
                    if moved:
                        affected.add(src)
                        affected.add(dst)
                        affected.add(os.path.dirname(src))
                        affected.add(os.path.dirname(dst))
                        # 源目录搬空 → 清理空目录链（只删空目录树）
                        removed.extend(_remove_empty_chain(fs, src))
                    continue
                # ── P0-2 目标冲突三档判定（目标已存在时）──
                action, target = self._decide_conflict(store, src, dst)
                if action == "noop":
                    noops.append({"from": src, "to": dst,
                                  "reason": "目标内容相同，未移动"})
                    continue
                if action == "meta_only":
                    if self._copy_meta(store, src, dst):
                        meta_onlys.append(
                            {"from": src, "to": dst,
                             "reason": "目标无分析元数据，已迁移源元数据（文件未移动）"})
                    else:
                        failed.append({"src": src, "dst": dst,
                                       "reason": REASON_ENTRY,
                                       "detail": "meta_only 迁移失败（源无条目）"})
                    continue
                if action == "conflict":
                    failed.append({"src": src, "dst": dst,
                                   "reason": REASON_CONFLICT})
                    continue
                dst = target   # rename（` (1)` 递增）后走正常移动
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
                    failed.append({"src": src, "dst": dst,
                                   "reason": REASON_ENTRY,
                                   "detail": "move_entry 失败（文件或条目未移动）"})
            except Exception as e:
                failed.append({"src": src, "dst": dst,
                               "reason": REASON_IO, "detail": str(e)})
        # 被删空目录的父级同样受影响（folder.json 统计变化）
        for r in removed:
            affected.add(os.path.dirname(r))
        return {"moved": done, "failed": failed,
                "noops": noops, "meta_onlys": meta_onlys,
                "rejected": rejected,
                "affected_dirs": sorted(affected),
                "removed_dirs": removed}

    # ── P0-2 冲突三档判定（用户拍板）──

    def _same_content(self, store: NaskbStore, src: str, dst: str) -> bool:
        """两文件内容是否相同（hash 对比；任一失败按不同处理）。"""
        try:
            _a, h1 = store.compute_hash(src)
            _b, h2 = store.compute_hash(dst)
            return bool(h1 and h1 == h2)
        except Exception:
            return False

    def _has_metadata(self, store: NaskbStore, path: str) -> bool:
        """目标是否已有有效分析元数据（无条目或条目无分析 → False）。"""
        e = store.get_entry(path)
        return bool(e and e.has_analysis())

    def _unique_dst(self, store: NaskbStore, dst: str) -> str:
        """目标已存在时生成不覆盖的新名：`name (1).ext`、`name (2).ext`…"""
        if not store._fs.exists(dst):
            return dst
        d, name = os.path.dirname(dst), os.path.basename(dst)
        stem, dot, ext = name.rpartition(".")
        if not dot:
            stem, ext = name, ""
        n = 1
        while True:
            cand = os.path.join(d, f"{stem} ({n}){dot}{ext}")
            if not store._fs.exists(cand):
                return cand
            n += 1

    def _decide_conflict(self, store: NaskbStore, src: str, dst: str
                         ) -> tuple[str, str]:
        """目标已存在时的三档判定，返回 (action, final_dst)。

        - ("noop", dst)      内容相同 → 啥也不干（不移动/不覆盖/不删源）
        - ("meta_only", dst) 内容不同且目标无有效元数据 → 只迁元数据文件不动
        - ("move", new_dst)  内容不同且目标已有元数据 → rename 后正常移动
        - ("conflict", dst)  目标为目录（文件 vs 目录）→ 无法处理
        """
        fs = store._fs
        if fs.is_dir(dst):
            return ("conflict", dst)
        if not fs.exists(dst):
            return ("move", dst)
        if self._same_content(store, src, dst):
            return ("noop", dst)
        if not self._has_metadata(store, dst):
            return ("meta_only", dst)
        return ("move", self._unique_dst(store, dst))

    def _copy_meta(self, store: NaskbStore, src: str, dst: str) -> bool:
        """把源条目分析元数据迁移到目标条目（目标文件不移动）。

        指纹字段（file_hash/hash_algorithm/size/mtime/ctime）按目标文件
        实际值重算（否则 check() 误报 stale）；provenance 记录元数据来源。
        """
        from .desc_store import FileEntry
        e = store.get_entry(src)
        if e is None:
            return False
        t = store.get_entry(dst)
        if t is None:
            t = FileEntry()
        # 复制分析元数据
        t.content_description = e.content_description
        t.category = e.category
        t.tags = list(e.tags)
        t.summary = e.summary
        t.language = e.language
        t.confidence = e.confidence
        t.images = [dict(i) for i in (e.images or [])]
        t.transcription = e.transcription
        t.ocr_text = e.ocr_text
        t.file_type = e.file_type
        t.processing_policy = e.processing_policy
        t.exif = dict(e.exif)
        t.duration_seconds = e.duration_seconds
        t.width = e.width
        t.height = e.height
        # 溯源：记录元数据来源；file_hash 留空 → set_entry 按目标文件重算
        if src not in t.moved_from:
            t.moved_from.append(src)
        t.original_path = t.original_path or src
        t.file_hash = ""
        st = store._fs.stat(dst)
        if st:
            t.size_bytes = st.size_bytes
            t.mtime = st.mtime
            t.ctime = st.ctime
        return store.set_entry(dst, t)

    def _move_dir(self, store: NaskbStore, src_dir: str, dst_dir: str):
        """递归移动目录下所有文件（保持相对结构），条目跟随。

        目录合并（目标目录已存在）：逐文件过 P0-2 三档冲突判定——
        同内容 noop / 目标无元数据 meta_only / 否则 rename 后移动。
        完成后把源目录的 `.naskb/artifacts`（MinerU 解析产物）迁到目标
        目录，保证条目 `exif.mineru_artifacts` 的相对引用仍有效；目标已
        有产物时保留目标（跳过）。源 `.naskb` 的 index.json/folder.json
        留在原处（不删除）。返回 (moved, failed, noops, meta_onlys)。
        """
        fs = store._fs
        moved: list[tuple[str, str]] = []
        failed: list[dict] = []
        noops: list[dict] = []
        meta_onlys: list[dict] = []
        src_dir = os.path.normpath(src_dir).replace("\\", "/")
        dst_dir = os.path.normpath(dst_dir).replace("\\", "/")
        for f in fs.list_files(src_dir, recursive=True):
            rel = f.path.replace("\\", "/")
            if f"/{REPO_DIR_NAME}/" in rel:
                continue
            sub = rel[len(src_dir):].lstrip("/")
            dst = (dst_dir + "/" + sub) if sub else dst_dir
            # ── P0-2 目标已存在 → 三档判定 ──
            if fs.exists(dst):
                action, target = self._decide_conflict(store, f.path, dst)
                if action == "noop":
                    noops.append({"from": f.path, "to": dst,
                                  "reason": "目标内容相同，未移动"})
                    continue
                if action == "meta_only":
                    if self._copy_meta(store, f.path, dst):
                        meta_onlys.append(
                            {"from": f.path, "to": dst,
                             "reason": "目标无分析元数据，已迁移源元数据（文件未移动）"})
                    else:
                        failed.append({"src": f.path, "dst": dst,
                                       "reason": REASON_ENTRY,
                                       "detail": "meta_only 迁移失败（源无条目）"})
                    continue
                if action == "conflict":
                    failed.append({"src": f.path, "dst": dst,
                                   "reason": REASON_CONFLICT})
                    continue
                dst = target   # rename
            try:
                if store.move_entry(f.path, dst):
                    moved.append((f.path, dst))
                else:
                    failed.append({"src": f.path, "dst": dst,
                                   "reason": REASON_ENTRY,
                                   "detail": "move_entry 失败（文件或条目未移动）"})
            except Exception as e:
                failed.append({"src": f.path, "dst": dst,
                               "reason": REASON_IO, "detail": str(e)})
        # ── 整仓跟随：源 .naskb 的 artifacts/folder.json/meta.json 迁到
        #    目标目录；index.json 保留目标（新条目已由 move_entry 写入，
        #    源的已被逐个 remove 清空）。迁移完成后移除源 .naskb 空壳
        #    （仅本地；WebDAV 无 rmdir 时降级保留）。
        try:
            src_repo = os.path.join(src_dir, REPO_DIR_NAME)
            dst_repo = os.path.join(dst_dir, REPO_DIR_NAME)
            if not fs.exists(src_repo):
                return moved, failed, noops, meta_onlys
            # artifacts（ensure_repo 会在目标预建空 artifacts/，判空才迁）
            src_art = os.path.join(src_repo, "artifacts")
            dst_art = os.path.join(dst_repo, "artifacts")
            if fs.exists(src_art) and not _dir_has_files(fs, dst_art):
                if fs.exists(dst_art):
                    _remove_empty_dir(fs, dst_art)   # 空壳
                    if fs.exists(dst_art):
                        return moved, failed, noops, meta_onlys
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
        return moved, failed, noops, meta_onlys

    # ═══════════════════════════════════════════════════════════════
    # P1-2 服务方法：apply + 级联刷新 + 整理后同步（CLI 与 MCP 共用）
    # ═══════════════════════════════════════════════════════════════

    def apply_with_housekeeping(self, store: NaskbStore, plan: dict,
                                snapshot: Optional[dict] = None, *,
                                llm_client: Optional[Any] = None,
                                config: Optional[Any] = None,
                                sync: bool = True,
                                nas_alias: Optional[str] = None,
                                lock_timeout: float = 10.0) -> dict:
        """完整整理事务（P1-2，CLI 与将来 MCP 共用入口）：

        1) root 互斥锁（plans/root-<hash>.lock，过期可接管）——防两个调用
           方同时整理同一 root；
        2) self.apply（P0-1 越界 / P0-3 复检 / P0-2 冲突三档）；
        3) 级联刷新受影响目录（含祖先链）的 folder.json；
        4) 整理后同步（sync=True）：本地向量索引 remap（无需重嵌入）+
           PG 增量同步（移动识别保留 resource_id）。
        同步失败只记录（结果 sync 字段），绝不阻断/回滚已完成的整理
        （用户拍板）。返回 apply 结果 + sync 状态。
        """
        from .plan_store import RootLock
        work_path = str(getattr(config, "work_path", "") or "") if config else ""
        root = plan.get("root", "")
        lock = RootLock(work_path, root) if work_path else None
        if lock is not None and not lock.acquire(timeout=lock_timeout):
            raise RuntimeError(f"root 已被其他整理任务锁定，放弃执行: {root}")
        try:
            result = self.apply(store, plan, snapshot)
            result["sync"] = {"vector_index": "skipped", "pg": "skipped"}
            if result["moved"]:
                # 3) 级联刷新 folder.json
                if llm_client is not None and config is not None:
                    try:
                        self._refresh_folders(store, config, llm_client, root,
                                              result.get("affected_dirs") or [])
                    except Exception as e:
                        result.setdefault("sync", {})["folders"] = f"failed: {e}"
                # 4) 整理后同步
                if sync:
                    result["sync"] = self._sync_after_apply(
                        store, config, root, result, nas_alias)
            return result
        finally:
            if lock is not None:
                lock.release()

    def _refresh_folders(self, store: NaskbStore, config, llm_client,
                         root: str, dirs: list[str]) -> None:
        """对受影响目录（含祖先链，到 root 为止）级联重算 folder.json。

        用于移动/增删文件后同步目录级描述；跳过不存在与仓库内部路径。
        """
        from .analyzer.folder import FolderAnalyzer

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
        for t in sorted(targets):
            if not store._fs.is_dir(t):
                continue
            try:
                entry = fa.analyze(store._fs, t)
                store.write_folder(t, entry)
            except Exception:
                pass   # 级联刷新尽力而为，不阻断整理主流程

    def _sync_after_apply(self, store: NaskbStore, config, root: str,
                          result: dict, nas_alias: Optional[str] = None
                          ) -> dict:
        """整理后同步：本地向量索引 remap + PG 增量同步。失败只记录。"""
        status: dict = {"vector_index": "skipped", "pg": "skipped"}
        mapping = {old: new for old, new in result.get("moved", [])}
        if not mapping:
            return status
        work_path = str(getattr(config, "work_path", "") or "") if config else ""
        # 本地向量索引：移动不改 summary → 向量不变，仅重写 paths（无需嵌入模型）
        if work_path:
            try:
                from .vector_index import VectorIndex
                v = VectorIndex(None, work_path)
                if v.load():
                    n = v.remap_paths(mapping)
                    status["vector_index"] = f"ok（{n} 条路径已更新）"
                else:
                    status["vector_index"] = "skipped（无本地向量索引）"
            except Exception as e:
                status["vector_index"] = f"failed: {e}"
        # PG：增量同步（REQ-R4-08 移动识别保留 resource_id）
        try:
            if config and getattr(config, "pg_enabled", False):
                from .pgstore import PgStore
                from .retrieval import collect_docs
                pg = PgStore(config)
                protocol, host, port, username = self._resolve_nas_identity(
                    store, config, nas_alias)
                nas = pg.get_or_create_nas(protocol, host, port, username)
                docs = [d for d in collect_docs(store._fs, root)
                        if d.kind == "file"]
                if docs:
                    stats = pg.sync_vectors(nas["schema_name"], docs)
                    status["pg"] = (
                        f"ok（增{stats['added']} 改{stats['updated']} "
                        f"移{stats['moved']} 删{stats['deleted']}）")
                else:
                    status["pg"] = "skipped（无描述数据）"
        except Exception as e:
            status["pg"] = f"failed: {e}"
        return status

    @staticmethod
    def _resolve_nas_identity(store: NaskbStore, config, nas_alias=None):
        """解析 NAS 五要素身份（服务方法用，无 CLI ctx）：
        --nas 别名 > fs 实际类型（webdav）> local。"""
        from .pgstore import normalize_identity
        if nas_alias:
            for nas in config.nas_list:
                if nas.get("alias") == nas_alias:
                    return normalize_identity(
                        str(nas.get("protocol", "webdav")),
                        str(nas.get("host", "")),
                        int(nas.get("port") or 0),
                        str(nas.get("username", "")))
            raise ValueError(f"config.toml [[nas]] 中找不到别名: {nas_alias}")
        import urllib.parse
        fs = store._fs
        try:
            from .fs.webdav import WebDAVAdapter
        except ImportError:
            WebDAVAdapter = None  # type: ignore[assignment]
        if WebDAVAdapter is not None and isinstance(fs, WebDAVAdapter):
            p = urllib.parse.urlparse(fs.root)
            port = p.port or (443 if p.scheme == "https" else 80)
            return normalize_identity("webdav", p.hostname or "", port,
                                      str(getattr(config, "webdav_user", "") or ""))
        return normalize_identity("local", "local", 0, "")
