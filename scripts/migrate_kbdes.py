"""迁移脚本：将老版本 .kbdes/*.md 的 OCR 文字合并进新版本 .naskb/files/*.json。

用法：
  python migrate_kbdes.py --dry-run     # 只预览，不动 NAS
  python migrate_kbdes.py --apply        # 真正写入 NAS
  python migrate_kbdes.py --dry-run -d 2 # 只看第 2 个月

工作原理：
  1. 遍历 Album/2026/1~8 下的 .kbdes/*.md
  2. 按基础名匹配 .naskb/files/*.json（如 IMG_20260208_090534.md → IMG_20260208_090534.png.json）
  3. 把 md 正文写入 json 的 ocr_text 字段（已有则跳过）
  4. 标记 ocr_source = "kbdes_migration"
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# 配置
NAS_HOST = "192.168.5.2"
NAS_PORT = 5006
NAS_USER = "clarknu"
NAS_PASS = "qwer4321!@#$REWQ"
BASE = "/Album/2026"

MONTHS = ["1", "2", "3", "4", "5", "6", "7", "8"]


def _cred() -> str:
    return base64.b64encode(f"{NAS_USER}:{NAS_PASS}".encode()).decode()


def _ctx() -> ssl.SSLContext:
    ctx = ssl._create_unverified_context()
    return ctx


def _propfind(path: str, depth: str = "1") -> str:
    url = f"https://{NAS_HOST}:{NAS_PORT}" + urllib.parse.quote(path)
    req = urllib.request.Request(url, method="PROPFIND")
    req.add_header("Authorization", f"Basic {_cred()}")
    req.add_header("Depth", depth)
    req.add_header("User-Agent", "naskb-migrate")
    with urllib.request.urlopen(req, timeout=60, context=_ctx()) as r:
        return r.read().decode("utf-8", "replace")


def _get(path: str) -> str:
    url = f"https://{NAS_HOST}:{NAS_PORT}" + urllib.parse.quote(path)
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {_cred()}")
    req.add_header("User-Agent", "naskb-migrate")
    with urllib.request.urlopen(req, timeout=60, context=_ctx()) as r:
        return r.read().decode("utf-8", "replace")


def _put(path: str, data: bytes) -> None:
    url = f"https://{NAS_HOST}:{NAS_PORT}" + urllib.parse.quote(path)
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Authorization", f"Basic {_cred()}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("User-Agent", "naskb-migrate")
    with urllib.request.urlopen(req, timeout=60, context=_ctx()) as r:
        pass


def safe_print(s: str) -> None:
    """控制台输出容错（Windows GBK 编码无法打印某些 Unicode 字符时自动替换）。"""
    try:
        print(s)
    except UnicodeEncodeError:
        # 用 bytes 直接写 stdout，绕过 print 的二次编码
        sys.stdout.buffer.write(s.encode("utf-8", errors="replace") + b"\n")


def _hrefs(xml: str) -> list[str]:
    return re.findall(r"<D:href>(.*?)</D:href>", xml)


def _norm(h: str) -> str:
    return urllib.parse.unquote(h)


def list_md_files(month: str) -> list[str]:
    """列出某月 .kbdes/ 下所有 .md 文件路径。"""
    kbdes_dir = f"{BASE}/{month}/.kbdes/"
    try:
        xml = _propfind(kbdes_dir, "infinity")
    except Exception as e:
        safe_print(f"  [SKIP] {kbdes_dir} 访问失败: {e}")
        return []
    out = []
    for h in _hrefs(xml):
        p = _norm(h)
        if p.endswith(".md") and "/.kbdes/" in p:
            out.append(p)
    return out


def list_naskb_jsons(month: str) -> dict[str, str]:
    """列出某月 .naskb/files/ 下所有 .json 文件，返回 {基础名前缀: 完整路径}。"""
    naskb_dir = f"{BASE}/{month}/.naskb/files/"
    try:
        xml = _propfind(naskb_dir, "1")
    except Exception as e:
        safe_print(f"  [SKIP] {naskb_dir} 访问失败: {e}")
        return {}
    out = {}
    for h in _hrefs(xml):
        p = _norm(h)
        if p.endswith(".json") and "/.naskb/files/" in p:
            # IMG_20260208_090534.png.json → IMG_20260208_090534
            fname = Path(p).stem  # 去掉 .json → IMG_20260208_090534.png
            prefix = fname.rsplit(".", 1)[0] if "." in fname else fname
            out[prefix] = p
    return out


def extract_base_name(md_path: str) -> str:
    """从 .kbdes/xxx.md 路径提取基础名（不含扩展名）。"""
    fname = Path(md_path).name  # IMG_20260208_090534.md
    return fname.rsplit(".", 1)[0]  # IMG_20260208_090534


def migrate_month(month: str, dry_run: bool = True) -> dict:
    """迁移某月的 .kbdes → .naskb，返回统计。"""
    stats = {"matched": 0, "already_has": 0, "migrated": 0, "skipped_no_match": 0, "errors": 0}
    md_files = list_md_files(month)
    naskb_map = list_naskb_jsons(month)

    if not md_files:
        safe_print(f"  月份 {month}: 无 .kbdes/*.md 文件，跳过")
        return stats
    if not naskb_map:
        safe_print(f"  月份 {month}: 无 .naskb/files/*.json 文件，跳过")
        return stats

    safe_print(f"  月份 {month}: {len(md_files)} 个 .md 文件, {len(naskb_map)} 个 .json 文件")

    for md_path in sorted(md_files):
        base = extract_base_name(md_path)
        json_path = naskb_map.get(base)

        if not json_path:
            stats["skipped_no_match"] += 1
            continue

        stats["matched"] += 1

        # 读取 .naskb json
        try:
            json_text = _get(json_path)
            data = json.loads(json_text)
        except Exception as e:
            safe_print(f"    [ERR] 读取 {json_path} 失败: {e}")
            stats["errors"] += 1
            continue

        # 检查是否已有 ocr_text
        if data.get("ocr_text") and data.get("ocr_source") == "kbdes_migration":
            stats["already_has"] += 1
            continue

        # 读取 .md 正文
        try:
            md_text = _get(md_path)
        except Exception as e:
            safe_print(f"    [ERR] 读取 {md_path} 失败: {e}")
            stats["errors"] += 1
            continue

        # 清理 md：去掉第一行的 <!-- 源文件: ... --> 注释和标题行
        lines = md_text.strip().split("\n")
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("<!--") and stripped.endswith("-->"):
                continue
            if stripped.startswith("# ") and not clean_lines:
                continue
            clean_lines.append(line)
        ocr_text = "\n".join(clean_lines).strip()

        if not ocr_text:
            stats["skipped_no_match"] += 1
            continue

        # 写入
        data["ocr_text"] = ocr_text
        data["ocr_source"] = "kbdes_migration"

        if dry_run:
            preview = ocr_text[:120].replace("\n", "\\n")
            safe_print(f"    [DRY] {base}: 会写入 {len(ocr_text)} 字 → {json_path}")
            safe_print(f"           内容预览: {preview}...")
            stats["migrated"] += 1
        else:
            try:
                new_json = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
                _put(json_path, new_json)
                safe_print(f"    [OK]  {base}: 已写入 {len(ocr_text)} 字")
                stats["migrated"] += 1
            except Exception as e:
                safe_print(f"    [ERR] 写入 {json_path} 失败: {e}")
                stats["errors"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="迁移 .kbdes/*.md → .naskb ocr_text")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="只预览，不写入 NAS（默认）")
    parser.add_argument("--apply", action="store_true", default=False,
                        help="真正写入 NAS")
    parser.add_argument("-d", "--month", type=str, default="",
                        help="只处理指定月份（1-8），留空处理全部")
    args = parser.parse_args()

    dry_run = not args.apply
    if dry_run:
        safe_print("=== DRY-RUN 模式（不会写入 NAS） ===\n")
    else:
        safe_print("=== APPLY 模式（将写入 NAS） ===\n")

    months = [args.month] if args.month else MONTHS
    total = {"matched": 0, "already_has": 0, "migrated": 0, "skipped_no_match": 0, "errors": 0}

    for m in months:
        stats = migrate_month(m, dry_run=dry_run)
        for k in total:
            total[k] += stats[k]
        safe_print("")

    safe_print("=" * 60)
    safe_print(f"匹配成功: {total['matched']}")
    safe_print(f"已迁移（跳过）: {total['already_has']}")
    safe_print(f"本次{'预览' if dry_run else '迁移'}: {total['migrated']}")
    safe_print(f"未匹配: {total['skipped_no_match']}")
    safe_print(f"错误: {total['errors']}")
    safe_print("=" * 60)


if __name__ == "__main__":
    main()
