"""构建向量索引：从 NAS 的 .naskb 数据收集文档 → bge-small-zh 嵌入 → 存到 NASKB_data/db/。

用法：
  python build_vectors.py              # 从 NAS WebDAV 构建
  python build_vectors.py --root /Album/2026  # 只索引指定路径
"""
import sys
from pathlib import Path

# 注入 naskb 包路径
sys.path.insert(0, str(Path(__file__).parent.parent / "naskb" / "scripts"))

from naskb.common.config import Config
from naskb.common.fs.base import FileSystemAdapter
from naskb.common.retrieval import collect_docs
from naskb.common.vector_index import VectorIndex, index_paths
from naskb.common.embeddings import Embedder


def main():
    work_path = str(Path(__file__).parent.parent / "NASKB_data")
    config = Config.from_work_path(work_path)

    # 从 config.nas_list 取第一台 NAS
    nas = config.get_nas()
    if not nas:
        print("[ERROR] config.toml 中没有 [[nas]] 配置")
        return

    # 创建 WebDAV 文件系统
    webdav_url = config.nas_webdav_url(nas)
    auth = {
        "username": nas.get("user", ""),
        "password": nas.get("password", ""),
        "verify_ssl": nas.get("verify_ssl", False),
    }
    print(f"[info] 连接 NAS: {webdav_url} (user={auth['username']})")

    fs = FileSystemAdapter.create("webdav", webdav_url, auth)

    # 收集文档（分月扫描，避免 WebDAV 递归深度问题）
    months = ["/Album/2026/1", "/Album/2026/2", "/Album/2026/3",
              "/Album/2026/4", "/Album/2026/5", "/Album/2026/6",
              "/Album/2026/7", "/Album/2026/8"]
    all_docs = []
    for month_root in months:
        print(f"[info] 扫描 {month_root}...")
        try:
            docs = collect_docs(fs, month_root)
            print(f"  → {len(docs)} 条描述")
            all_docs.extend(docs)
        except Exception as e:
            print(f"  → 跳过: {e}")
    docs = all_docs
    fs.close()

    if not docs:
        print("[ERROR] 没有找到任何描述数据")
        return

    print(f"[info] 收集到 {len(docs)} 条描述")

    # 构建向量索引
    print("[info] 加载 bge-small-zh 嵌入模型（首次自动下载 ~24MB）...")
    emb = Embedder(work_path)
    index = VectorIndex(emb, work_path)
    n = index.build(docs)
    npz, json_path = index_paths(work_path)
    emb.close()

    print(f"[OK] 向量索引已构建: {n} 条描述 → {npz}")
    print(f"     元数据 → {json_path}")
    print("[info] 之后 desc search / desc ask 将自动使用向量检索")


if __name__ == "__main__":
    main()
