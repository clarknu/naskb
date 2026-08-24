#!/usr/bin/env python3
"""
NASKB 架构契约探针（static 类）——naskb 包事实采集
规范：.agents/skills/sfds/_shared/arch-contract-spec.md §2 事实模式
输出：scripts/probes/out/facts.json（中性 schema）
技术栈：Python（AST 静态扫描）；范围：naskb/scripts/naskb/**/*.py（排除 __pycache__）

facts 内容：
  units[]      —— 每个 .py 模块一个 unit（path = 点分模块名）
  dependency[] —— import 边（仅 naskb 包内，kind=import）
  reference[]  —— 同上（供 reference-whitelist 用，via=导入名列表逗号分隔）
  assetRef[]   —— 表名常量出现在字符串常量中（SQL 引用；assetKind=table）
  literal[]    —— 值域 access_mode 的裸字面量（"ro"/"rw"）
  registry[]   —— FastAPI 路由注册（set=routes，key='METHOD /path' 小写）
"""
from __future__ import annotations

import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent.parent / "naskb" / "scripts" / "naskb"
OUT = Path(__file__).resolve().parent / "out" / "facts.json"

MODULES = {
    m.relative_to(PKG_ROOT).with_suffix("").as_posix().replace("/", ".")
    for m in PKG_ROOT.rglob("*.py")
    if "__pycache__" not in m.parts
}  # 相对点分模块名（如 common.pgstore）

TABLE_NAMES = ["sources", "nas_registry", "resources", "vectors", "folders", "termbase"]
ACCESS_VALUES = {"ro", "rw"}
ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def module_name(path: Path) -> str:
    rel = path.relative_to(PKG_ROOT)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] == "__init__":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return "naskb." + ".".join(parts) if parts else "naskb"


def resolve_import(node: ast.Import | ast.ImportFrom, module: str) -> list[str]:
    """返回本文件绝对导入目标模块列表（仅 naskb 包内；模块级精度）。"""
    targets: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.startswith("naskb"):
                targets.append(alias.name)
        return targets

    base = node.module or ""
    level = node.level or 0
    if base.startswith("naskb"):
        base_mod = base
    elif level:
        segs = module.split(".")
        pkg = segs[: len(segs) - (level - 1) - 1] if base else segs[: len(segs) - level]
        base_mod = ".".join(pkg + ([base] if base else []))
    else:
        return []

    for alias in node.names:
        sym = alias.name
        candidate = f"{base_mod}.{sym}" if base_mod else sym
        # 符号是已知子模块 → 模块级精确边；否则依赖 base 包（包级边）
        if candidate.split(".", 1)[0] == "naskb" and ".".join(candidate.split(".")[1:]) in MODULES:
            targets.append(candidate)
        elif base_mod.startswith("naskb") or (sym.startswith("naskb") and sym.split(".", 1)[0] in ("naskb",)):
            targets.append(sym if sym.startswith("naskb") else base_mod)
        elif base_mod.startswith("naskb"):
            targets.append(base_mod)
    return [t for t in targets if t.startswith("naskb")]


def extract_strings_constants(node: ast.AST) -> list[tuple[str, int]]:
    """文件内字符串常量（含 f-string 拼接伪文本，供 SQL 表名识别）。"""
    out: list[tuple[str, int]] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append((n.value, n.lineno))
        elif isinstance(n, ast.JoinedStr):
            parts = []
            for v in n.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                elif isinstance(v, ast.FormattedValue) and isinstance(v.value, ast.Name):
                    parts.append("{" + v.value.id + "}")
                else:
                    parts.append("{}")
            if parts:
                out.append(("".join(parts), n.lineno))
    return out


def path_has_sql_table(text: str) -> bool:
    # 近似：SQL 关键字上下文中的表名
    return re.search(r"\b(?:from|join|into|update|delete\s+from)\s+[`\"'\w.]*(" + "|".join(TABLE_NAMES) + r")\b", text, re.I)


def classify_domain(key: str) -> str | None:
    """路由 key → 业务域（探针静态分类；映射规则随域注册表演进——一次性生成，随技术栈维护）。"""
    path = key.split(" ", 1)[-1]
    if path.startswith("/api/sources"):
        return "source"
    if path.startswith("/api/kb/search") or path in (
        "/api/search", "/api/ask", "/api/reload", "/api/stats", "/api/pg/rebind"):
        return "retrieval"
    if path.startswith("/api/kb/ask"):
        return "deep"
    if path.startswith("/api/config") or path.startswith("/api/tree") or path.startswith("/api/folder") or path.startswith("/api/files") or path.startswith("/api/jobs"):
        return "platform"
    return None


def main() -> int:
    units: list[dict] = []
    dependency: list[dict] = []
    reference: list[dict] = []
    asset_ref: list[dict] = []
    literal: list[dict] = []
    registry: list[dict] = []

    for py in sorted(PKG_ROOT.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        mod = module_name(py)
        segs = mod.split(".")
        units.append({"path": mod, "kind": "module", "files": [py.relative_to(PKG_ROOT).as_posix()]})
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        # ── import 边 ──
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for tgt in resolve_import(node, mod):
                    dep = {
                        "from": mod, "to": tgt, "kind": "import",
                        "evidence": {"file": py.relative_to(PKG_ROOT).as_posix(), "line": node.lineno},
                    }
                    dependency.append(dep)
                    names = []
                    for alias in getattr(node, "names", []):
                        names.append(alias.asname or alias.name)
                    reference.append({**dep, "via": ",".join(names)[:80]})

        # ── 表名引用（SQL 字符串常量 / f-string 伪文本）──
        for text, lineno in extract_strings_constants(tree):
            m = re.search(
                r"\b(?:from|join|into|update|create\s+table(?:\s+if\s+not\s+exists)?)"
                r"\s+[`\"'\w{}./]*(?<![a-z0-9_])(" + "|".join(TABLE_NAMES) + r")\b",
                text, re.I,
            )
            if m:
                asset_ref.append({
                    "unit": mod, "asset": m.group(1).lower(), "assetKind": "table",
                    "evidence": {"file": py.relative_to(PKG_ROOT).as_posix(), "line": lineno},
                })

        # ── access_mode 裸字面量 ──
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in ACCESS_VALUES:
                in_comp = False
                for parent_ctx in (node.parent_ctx if hasattr(node, "parent_ctx") else []) or []:
                    pass
                literal.append({
                    "unit": mod, "domain": "access_mode", "value": node.value,
                    "inComparison": False,
                    "evidence": {"file": py.relative_to(PKG_ROOT).as_posix(), "line": node.lineno},
                })

        # ── FastAPI 路由注册 ──
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                        continue
                    meth = dec.func.attr.lower()
                    if meth not in ROUTE_METHODS:
                        continue
                    if not dec.args or not isinstance(dec.args[0], ast.Constant):
                        continue
                    p = dec.args[0].value
                    if isinstance(p, str) and p.startswith("/api/"):
                        key = f"{meth} {p}"
                        row = {"set": "routes", "key": key,
                               "evidence": {"file": py.relative_to(PKG_ROOT).as_posix(), "line": node.lineno}}
                        registry.append(row)
                        domain = classify_domain(key)
                        if domain:
                            registry.append({**row, "set": f"routes:{domain}"})

    facts = {
        "probe": {
            "name": "naskb-python-static", "tech": "python", "version": "1.0.0",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "roots": ["naskb/scripts/naskb"],
        },
        "units": units,
        "facts": {
            "dependency": dependency,
            "reference": reference,
            "assetRef": asset_ref,
            "literal": literal,
            "registry": registry,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[probe] units={len(units)} dependency={len(dependency)} reference={len(reference)} "
          f"assetRef={len(asset_ref)} literal={len(literal)} registry={len(registry)} → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
