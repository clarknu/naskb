"""NASKB MCP 端到端接口测试。

使用真实 ONNX 模型和 LanceDB 数据库，
在临时目录中创建完整的测试知识库，逐一验证所有 16 个接口。
"""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# 确保 src 路径可用
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 预先下载好的模型路径
_PRECACHED_MODEL = Path(r"c:\Sync\NASKB\NASKB_data\models\bge-base-zh-v1.5")


class TestMCPEndToEnd:
    """MCP 服务端到端测试。"""

    @classmethod
    def setup_class(cls):
        """创建临时知识库环境，复用已下载的模型。"""
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work_path = cls.tmp.name
        os.environ["NASKB_WORK"] = cls.work_path

        wp = Path(cls.work_path)

        # ── 复制已下载的模型（避免重复下载 400MB）──
        if _PRECACHED_MODEL.exists():
            dst_model = wp / "models" / "bge-base-zh-v1.5"
            dst_model.mkdir(parents=True, exist_ok=True)
            for f in _PRECACHED_MODEL.iterdir():
                if f.is_file():
                    shutil.copy2(f, dst_model / f.name)
            print(f"[SETUP] Model copied from {_PRECACHED_MODEL}")
        else:
            raise FileNotFoundError(
                f"Pre-cached model not found at {_PRECACHED_MODEL}. "
                f"Run: naskb init --work-path c:/Sync/NASKB/NASKB_data"
            )

        # 创建测试知识库来源
        cls.source_dir = wp / "test_kb"
        cls.source_dir.mkdir(parents=True)

        # 创建测试文件
        (cls.source_dir / "readme.md").write_text(
            "# 测试知识库\n\n这是一个用于端到端测试的知识库。\n\n"
            "包含向量数据库的选型对比和 Python 编程技巧。",
            encoding="utf-8"
        )
        (cls.source_dir / "database-comparison.md").write_text(
            "# 数据库对比\n\n## LanceDB\nLanceDB 是基于 Lance 列存格式的嵌入式向量数据库。\n"
            "支持语义搜索和高并发读取。\n\n## FAISS\nFacebook 开源的向量相似度搜索库。\n"
            "支持 GPU 加速，适合大规模检索。\n\n## Qdrant\n高性能向量数据库，支持嵌入模式和服务器模式。",
            encoding="utf-8"
        )
        (cls.source_dir / "python-tips.md").write_text(
            "# Python Tips\n\n## 列表推导式\n列表推导式是 Python 中创建列表的简洁方式。\n\n"
            "## 装饰器\n装饰器可以修改函数的行为而不改变其代码。\n\n"
            "## 异步编程\nasyncio 是 Python 3.4+ 引入的异步 I/O 框架。",
            encoding="utf-8"
        )

        # 创建媒体文件（无描述）
        (cls.source_dir / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        # 创建 config.toml
        config_content = f"""
[model]
name = "bge-base-zh-v1.5"
execution_provider = "cpu"
batch_size = 8
intra_op_threads = 2
inter_op_threads = 1

[db]
path = "db/"

[state]
path = "state.db"

[[sources]]
id = "test-kb"
name = "Test KB"
fs_type = "local"
root_url = "{str(cls.source_dir.resolve()).replace(chr(92), '/')}"
enabled = true
"""
        (wp / "config.toml").write_text(config_content, encoding="utf-8")

        # 初始化组件
        from naskb.mcp.tools import _init_components
        cls.components = _init_components(cls.work_path)
        cls.config = cls.components["config"]
        cls.async_indexer = cls.components["async_indexer"]
        cls.job_queue = cls.components["job_queue"]
        cls.state = cls.components["state"]
        cls.vector_store = cls.components["vector_store"]

        print(f"[SETUP] Work path: {cls.work_path}")
        print(f"[SETUP] Source dir: {cls.source_dir}")
        print(f"[SETUP] Config OK, components initialized")

    @classmethod
    def teardown_class(cls):
        """清理临时环境。"""
        import gc, time
        # 关闭微批编码器
        try:
            me = cls.components.get("micro_encoder")
            if me:
                me.shutdown()
        except Exception:
            pass
        # 关闭所有数据库连接
        for key in ("state", "vector_store"):
            try:
                obj = cls.components.get(key)
                if obj:
                    if hasattr(obj, "_conn"):
                        obj._conn.close()
                    if hasattr(obj, "_db"):
                        obj._db.close()
            except Exception:
                pass
        # 关闭线程池
        try:
            cls.components["async_indexer"].shutdown()
        except Exception:
            pass
        # 允许强制清理
        gc.collect()
        time.sleep(0.3)
        try:
            cls.tmp.cleanup()
        except PermissionError:
            pass  # Windows 文件锁偶尔延迟，忽略
        print("[TEARDOWN] Temp directory cleaned")

    # ═══════════════════════════════════════════════════════════════
    # Test 1: kb_status — 状态报告
    # ═══════════════════════════════════════════════════════════════

    def test_01_kb_status_before_index(self):
        """测试索引前的状态报告。"""
        from naskb.mcp.tools import kb_status
        result = kb_status()
        print(f"\n[kb_status]\n{result}\n")
        assert "NASKB" in result or "naskb" in result.lower()
        assert "bge-base" in result
        assert "test-kb" in result
        print("✅ kb_status (before index) PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 2: kb_list_sources — 来源列表
    # ═══════════════════════════════════════════════════════════════

    def test_02_kb_list_sources(self):
        """测试来源列表。"""
        from naskb.mcp.tools import kb_list_sources
        result = kb_list_sources()
        print(f"\n[kb_list_sources]\n{result}\n")
        assert "test-kb" in result
        assert "Test KB" in result
        print("✅ kb_list_sources PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 3: kb_index_full — 全量索引
    # ═══════════════════════════════════════════════════════════════

    def test_03_kb_index_full(self):
        """测试全量索引。"""
        from naskb.mcp.tools import kb_index_full
        print("[kb_index_full] Starting full index...")
        result = kb_index_full(force=True)
        print(f"\n[kb_index_full]\n{result}\n")
        assert "全量索引完成" in result or "Full index" in result

        # 直接打开 LanceDB 表读取行数（避免缓存问题）
        import lancedb
        db = lancedb.connect(self.vector_store._db_path)
        try:
            tbl = db.open_table("files")
            file_count = tbl.count_rows()
        except Exception:
            file_count = 0
        print(f"[kb_index_full] Files in vector store: {file_count}")
        assert file_count >= 3, f"Expected >=3 files indexed, got {file_count}"
        print("✅ kb_index_full PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 4: kb_search — 语义搜索
    # ═══════════════════════════════════════════════════════════════

    def test_04_kb_search_vector_db(self):
        """测试语义搜索 - 向量数据库相关。"""
        from naskb.mcp.tools import kb_search
        result = kb_search("向量数据库", top_k=5, threshold=0.3)
        print(f"\n[kb_search '向量数据库']\n{result}\n")
        assert "database-comparison" in result or "LanceDB" in result
        print("✅ kb_search (向量数据库) PASSED")

    def test_05_kb_search_python(self):
        """测试语义搜索 - Python 相关。"""
        from naskb.mcp.tools import kb_search
        result = kb_search("Python 异步编程", top_k=5, threshold=0.3)
        print(f"\n[kb_search 'Python 异步编程']\n{result}\n")
        assert "python-tips" in result or "asyncio" in result or "异步" in result
        print("✅ kb_search (Python) PASSED")

    def test_06_kb_search_no_result(self):
        """测试语义搜索 - 无匹配结果。"""
        from naskb.mcp.tools import kb_search
        result = kb_search("量子力学相对论黑洞", top_k=5, threshold=0.9)
        print(f"\n[kb_search '量子力学']\n{result}\n")
        # 应该返回"未找到"相关信息
        assert "未找到" in result or "no result" in result.lower() or "尝试" in result
        print("✅ kb_search (no result) PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 7: kb_list_missing — 缺失描述
    # ═══════════════════════════════════════════════════════════════

    def test_07_kb_list_missing(self):
        """测试缺失描述文件列表。"""
        from naskb.mcp.tools import kb_list_missing
        result = kb_list_missing()
        print(f"\n[kb_list_missing]\n{result}\n")
        # photo.jpg 没有 .kbdesc 所以会出现在缺失列表中
        assert "photo" in result or "缺失" in result or "所有" in result
        print("✅ kb_list_missing PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 8: kb_add_source — 添加来源
    # ═══════════════════════════════════════════════════════════════

    def test_08_kb_add_source(self):
        """测试添加知识来源。"""
        from naskb.mcp.tools import kb_add_source, kb_list_sources
        result = kb_add_source("临时来源", str(self.source_dir.resolve()), fs_type="local")
        print(f"\n[kb_add_source]\n{result}\n")
        assert "已添加" in result or "added" in result.lower()

        # 验证出现在列表中
        list_result = kb_list_sources()
        assert "临时来源" in list_result
        print("✅ kb_add_source PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 9: kb_remove_source — 移除来源
    # ═══════════════════════════════════════════════════════════════

    def test_09_kb_remove_source(self):
        """测试移除知识来源。"""
        from naskb.mcp.tools import kb_remove_source, kb_list_sources
        result = kb_remove_source("临时来源")
        print(f"\n[kb_remove_source]\n{result}\n")
        assert "已移除" in result or "removed" in result.lower()

        list_result = kb_list_sources()
        assert "临时来源" not in list_result
        print("✅ kb_remove_source PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 10: kb_index_incremental — 增量索引
    # ═══════════════════════════════════════════════════════════════

    def test_10_kb_index_incremental(self):
        """测试增量索引（无变更情况）。"""
        from naskb.mcp.tools import kb_index_incremental
        result = kb_index_incremental()
        print(f"\n[kb_index_incremental]\n{result}\n")
        assert "增量索引完成" in result or "updated" in result.lower()
        print("✅ kb_index_incremental PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 11: kb_index_file — 单文件索引
    # ═══════════════════════════════════════════════════════════════

    def test_11_kb_index_file_text(self):
        """测试索引单个文本文件。"""
        from naskb.mcp.tools import kb_index_file
        file_path = str(self.source_dir / "readme.md")
        result = kb_index_file("test-kb", file_path)
        print(f"\n[kb_index_file text]\n{result}\n")
        assert "成功" in result or "success" in result.lower()
        print("✅ kb_index_file (text) PASSED")

    def test_12_kb_index_file_media_no_desc(self):
        """测试索引无描述的媒体文件（应返回错误）。"""
        from naskb.mcp.tools import kb_index_file
        file_path = str(self.source_dir / "photo.jpg")
        result = kb_index_file("test-kb", file_path)
        print(f"\n[kb_index_file media no desc]\n{result}\n")
        assert "缺少" in result or "missing" in result.lower() or "kbdesc" in result.lower()
        print("✅ kb_index_file (media, no desc) PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 13: kb_describe_media — 媒体描述
    # ═══════════════════════════════════════════════════════════════

    def test_13_kb_describe_media(self):
        """测试为媒体文件创建描述。"""
        from naskb.mcp.tools import kb_describe_media
        file_path = str(self.source_dir / "photo.jpg")
        result = kb_describe_media(
            "test-kb",
            file_path,
            "一张测试图片，用于验证知识库的媒体描述功能。",
            tags="测试, 图片"
        )
        print(f"\n[kb_describe_media]\n{result}\n")
        assert "成功" in result or "created" in result.lower() or "更新" in result
        print("✅ kb_describe_media PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 14: kb_index_file (after describe)
    # ═══════════════════════════════════════════════════════════════

    def test_14_kb_index_file_after_describe(self):
        """测试添加描述后索引媒体文件。"""
        from naskb.mcp.tools import kb_index_file
        file_path = str(self.source_dir / "photo.jpg")
        result = kb_index_file("test-kb", file_path)
        print(f"\n[kb_index_file after describe]\n{result}\n")
        assert "成功" in result or "success" in result.lower() or "media_with_desc" in result.lower()
        print("✅ kb_index_file (after describe) PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 15: kb_check_stale — 过期检查
    # ═══════════════════════════════════════════════════════════════

    def test_15_kb_check_stale(self):
        """测试描述文件过期检查。"""
        from naskb.mcp.tools import kb_check_stale
        result = kb_check_stale()
        print(f"\n[kb_check_stale]\n{result}\n")
        assert "最新" in result or "stale" in result.lower() or "过期" in result or "所有" in result
        print("✅ kb_check_stale PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 16: Task Queue — 任务队列
    # ═══════════════════════════════════════════════════════════════

    def test_16_kb_list_jobs(self):
        """测试后台任务列表。"""
        from naskb.mcp.tools import kb_list_jobs
        result = kb_list_jobs("all")
        print(f"\n[kb_list_jobs all]\n{result}\n")
        # 即使没有任务也应该返回一条消息
        assert len(result) > 0
        print("✅ kb_list_jobs PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 17: Status after all operations
    # ═══════════════════════════════════════════════════════════════

    def test_17_kb_status_after_all(self):
        """测试全部操作后的状态报告。"""
        from naskb.mcp.tools import kb_status
        result = kb_status()
        print(f"\n[kb_status final]\n{result}\n")
        assert "已索引" in result or "indexed" in result.lower()
        print("✅ kb_status (final) PASSED")

    # ═══════════════════════════════════════════════════════════════
    # Test 18: Search media descriptions
    # ═══════════════════════════════════════════════════════════════

    def test_18_kb_search_media_desc(self):
        """测试搜索媒体描述内容。"""
        from naskb.mcp.tools import kb_search
        result = kb_search("测试图片 知识库", top_k=5, threshold=0.3)
        print(f"\n[kb_search '测试图片']\n{result}\n")
        # 应该能找到 photo.jpg 的描述
        assert "photo" in result or "图片" in result or "测试" in result
        print("✅ kb_search (media desc) PASSED")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "-s", "--tb=short"]))
