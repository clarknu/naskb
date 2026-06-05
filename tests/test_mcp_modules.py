"""MCP 模块测试。

测试 DescManager（.kbdes 描述文件管理）和 JobQueue（任务队列）。
"""
import os
import sys
import tempfile
import time
from pathlib import Path

# 确保 src 路径可用
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


# ═══════════════════════════════════════════════════════════════════
# DescManager 测试
# ═══════════════════════════════════════════════════════════════════

class TestDescManager:
    """测试 .kbdes 描述文件管理器。"""

    def test_get_desc_path(self):
        """测试从媒体文件路径推导 .kbdesc 路径。"""
        from naskb.mcp.desc_manager import DescManager

        path = DescManager.get_desc_path("/photos/IMG_001.jpg")
        assert ".kbdes" in path
        assert path.endswith("IMG_001.jpg.kbdesc")

    def test_get_media_path(self):
        """测试从 .kbdesc 路径反推媒体文件路径。"""
        from naskb.mcp.desc_manager import DescManager

        # 创建临时目录结构
        with tempfile.TemporaryDirectory() as tmp:
            media_dir = Path(tmp) / "photos"
            media_dir.mkdir()
            kbdes_dir = media_dir / ".kbdes"
            kbdes_dir.mkdir()

            # 创建媒体文件和对应的 .kbdesc
            media_file = media_dir / "test.jpg"
            media_file.write_text("fake image data")

            desc_path = DescManager.get_desc_path(str(media_file))
            assert str(kbdes_dir / "test.jpg.kbdesc") == desc_path

    def test_write_and_read(self):
        """测试 .kbdesc 文件的写入和读取。"""
        from naskb.mcp.desc_manager import DescManager, KbDesc, MediaInfo

        with tempfile.TemporaryDirectory() as tmp:
            media_dir = Path(tmp) / "photos"
            media_dir.mkdir()

            # 创建媒体文件
            media_file = media_dir / "vacation.jpg"
            media_file.write_bytes(b"x" * 1024)

            # 写入描述
            kbdesc = KbDesc(
                desc_path="",
                media_path=str(media_file.resolve()),
                kbdesc_version="1.0",
                media_info=MediaInfo(
                    size_bytes=1024,
                    mtime=media_file.stat().st_mtime,
                    sha256="abc123",
                    mime_type="image/jpeg",
                    media_type="image",
                    width=1920,
                    height=1080,
                ),
                description_type="auto_generated",
                content="# Vacation Photo\n\n夏日海边的夕阳。",
            )
            written_path = DescManager.write(kbdesc)
            assert os.path.exists(written_path)
            assert ".kbdes" in written_path

            # 读取
            read_back = DescManager.read(written_path)
            assert read_back is not None
            assert read_back.media_info.size_bytes == 1024
            assert read_back.media_info.media_type == "image"
            assert read_back.content.strip() == "# Vacation Photo\n\n夏日海边的夕阳。"
            assert not read_back.is_stale  # 刚写入，不应过期

    def test_write_auto(self):
        """测试自动生成 .kbdesc 文件。"""
        from naskb.mcp.desc_manager import DescManager

        with tempfile.TemporaryDirectory() as tmp:
            media_dir = Path(tmp) / "videos"
            media_dir.mkdir()

            media_file = media_dir / "tutorial.mp4"
            media_file.write_bytes(b"y" * 5000)

            content = "# Tutorial Video\n\nThis is a Python tutorial video."
            desc_path = DescManager.write_auto(
                str(media_file), content, mime_type="video/mp4"
            )

            assert os.path.exists(desc_path)
            assert ".kbdes" in desc_path

            # 验证文件内容包含元数据
            raw = Path(desc_path).read_text(encoding="utf-8")
            assert "kbdesc_version" in raw
            assert "media_info" in raw
            assert "Python tutorial" in raw
            assert "video/mp4" in raw

    def test_stale_detection_mtime(self):
        """测试通过 mtime 检测描述过期。"""
        from naskb.mcp.desc_manager import DescManager, KbDesc, MediaInfo

        with tempfile.TemporaryDirectory() as tmp:
            media_dir = Path(tmp) / "images"
            media_dir.mkdir()

            media_file = media_dir / "photo.png"
            media_file.write_bytes(b"original content")

            # 写入描述（使用原始 mtime）
            kbdesc = KbDesc(
                desc_path="",
                media_path=str(media_file.resolve()),
                media_info=MediaInfo(
                    size_bytes=len(b"original content"),
                    mtime=media_file.stat().st_mtime,
                    sha256="hash1",
                    mime_type="image/png",
                    media_type="image",
                ),
                content="Original description.",
            )
            DescManager.write(kbdesc)

            # 修改媒体文件
            time.sleep(0.1)
            media_file.write_bytes(b"modified content - different")

            # 重新读取并检查过期
            desc_path = DescManager.get_desc_path(str(media_file))
            read_back = DescManager.read(desc_path)
            assert read_back is not None
            assert read_back.is_stale
            assert "mtime" in read_back.stale_reason or "size" in read_back.stale_reason

    def test_stale_detection_size(self):
        """测试通过 size 变化检测描述过期。"""
        from naskb.mcp.desc_manager import DescManager, KbDesc, MediaInfo

        with tempfile.TemporaryDirectory() as tmp:
            media_dir = Path(tmp) / "docs"
            media_dir.mkdir()

            media_file = media_dir / "report.pdf"
            media_file.write_bytes(b"small")

            kbdesc = KbDesc(
                desc_path="",
                media_path=str(media_file.resolve()),
                media_info=MediaInfo(
                    size_bytes=5,
                    mtime=media_file.stat().st_mtime,
                    sha256="hash_small",
                    mime_type="application/pdf",
                    media_type="document",
                ),
                content="Small report",
            )
            DescManager.write(kbdesc)

            # 改变文件大小
            time.sleep(0.1)
            media_file.write_bytes(b"much larger content for the pdf file")

            desc_path = DescManager.get_desc_path(str(media_file))
            read_back = DescManager.read(desc_path)
            assert read_back is not None
            assert read_back.is_stale

    def test_list_media_without_desc(self):
        """测试列出缺少描述的媒体文件。"""
        from naskb.mcp.desc_manager import DescManager

        with tempfile.TemporaryDirectory() as tmp:
            media_dir = Path(tmp) / "mixed"
            media_dir.mkdir()

            # 创建几个媒体文件
            (media_dir / "img1.jpg").touch()
            (media_dir / "img2.png").touch()
            (media_dir / "vid1.mp4").touch()
            (media_dir / "notes.md").touch()  # 文本文件，不算媒体

            # 只为 img1.jpg 创建描述
            DescManager.write_auto(
                str(media_dir / "img1.jpg"), "A test image"
            )

            # 检查缺失列表
            missing = DescManager.list_media_without_desc(str(media_dir))
            missing_names = [Path(m).name for m in missing]

            assert "img2.png" in missing_names
            assert "vid1.mp4" in missing_names
            assert "img1.jpg" not in missing_names  # 已有描述
            assert "notes.md" not in missing_names  # 不是媒体文件

    def test_list_desc_files(self):
        """测试列出 .kbdes 文件夹中的描述文件。"""
        from naskb.mcp.desc_manager import DescManager

        with tempfile.TemporaryDirectory() as tmp:
            media_dir = Path(tmp) / "gallery"
            media_dir.mkdir()

            (media_dir / "a.jpg").write_bytes(b"a")
            (media_dir / "b.jpg").write_bytes(b"bb")
            (media_dir / "c.jpg").write_bytes(b"ccc")

            DescManager.write_auto(str(media_dir / "a.jpg"), "Photo A")
            DescManager.write_auto(str(media_dir / "b.jpg"), "Photo B")

            descs = DescManager.list_desc_files(str(media_dir))
            assert len(descs) == 2

            # c.jpg 无描述
            missing = DescManager.list_media_without_desc(str(media_dir))
            assert len(missing) == 1
            assert "c.jpg" in Path(missing[0]).name


# ═══════════════════════════════════════════════════════════════════
# JobQueue 测试
# ═══════════════════════════════════════════════════════════════════

class TestJobQueue:
    """测试异步任务队列。"""

    @pytest.mark.asyncio
    async def test_submit_and_process(self):
        """测试任务提交与处理。"""
        from naskb.mcp.job_queue import JobQueue, JobStatus, JobType

        queue = JobQueue(max_workers=2)
        processed = []

        async def handler(job):
            processed.append(job.job_type.value)
            await asyncio_sleep(0.01)
            return f"done_{job.job_type.value}"

        await queue.start(handler)

        job1 = await queue.submit(JobType.INDEX_FILE, source_id="src1",
                                   target_path="/test/file1.md")
        job2 = await queue.submit(JobType.INDEX_FILE, source_id="src1",
                                   target_path="/test/file2.md")

        # 等待处理完成
        await asyncio_sleep(0.1)

        await queue.stop()

        assert job1.status == JobStatus.COMPLETED
        assert job2.status == JobStatus.COMPLETED
        assert "index_file" in processed

    @pytest.mark.asyncio
    async def test_deduplication(self):
        """测试任务去重。"""
        from naskb.mcp.job_queue import JobQueue, JobType

        queue = JobQueue(max_workers=1)
        # 不启动 worker，只测试去重

        job1 = await queue.submit(
            JobType.INDEX_FILE, source_id="src1",
            target_path="/test/same.md", deduplicate=True
        )
        job2 = await queue.submit(
            JobType.INDEX_FILE, source_id="src1",
            target_path="/test/same.md", deduplicate=True
        )

        # 应该返回同一个 job
        assert job1.job_id == job2.job_id

        # 不同路径不会去重
        job3 = await queue.submit(
            JobType.INDEX_FILE, source_id="src1",
            target_path="/test/different.md", deduplicate=True
        )
        assert job1.job_id != job3.job_id

    @pytest.mark.asyncio
    async def test_list_jobs(self):
        """测试任务列表查询。"""
        from naskb.mcp.job_queue import JobQueue, JobType

        queue = JobQueue(max_workers=1)

        await queue.submit(JobType.INDEX_FILE, source_id="s1",
                           target_path="/a")
        await queue.submit(JobType.GENERATE_DESC, source_id="s2",
                           target_path="/b")

        all_jobs = queue.list_jobs("all")
        assert len(all_jobs) == 2

        pending = queue.list_jobs("pending")
        assert len(pending) == 2

        active = queue.list_jobs("active")
        assert len(active) == 2  # pending + running = active

    @pytest.mark.asyncio
    async def test_stats(self):
        """测试队列统计。"""
        from naskb.mcp.job_queue import JobQueue, JobType

        queue = JobQueue(max_workers=2)

        await queue.submit(JobType.INDEX_FILE, "s1", "/a")
        await queue.submit(JobType.INDEX_FILE, "s1", "/b")
        await queue.submit(JobType.INDEX_FILE, "s1", "/c")

        stats = queue.get_stats()
        assert stats["pending"] == 3
        assert stats["total"] == 3
        assert stats["queue_size"] == 3


# ═══════════════════════════════════════════════════════════════════
# YAML Frontmatter 解析测试 (零依赖)
# ═══════════════════════════════════════════════════════════════════

class TestFrontmatterParser:
    """测试内置的 YAML frontmatter 解析器。"""

    def test_parse_simple(self):
        from naskb.mcp.desc_manager import _parse_frontmatter

        raw = """---
name: test
version: "1.0"
count: 42
---
This is the content."""

        metadata, content = _parse_frontmatter(raw)
        assert metadata is not None
        assert metadata["name"] == "test"
        assert metadata["version"] == 1.0   # Parsed as float
        assert metadata["count"] == 42
        assert content.strip() == "This is the content."

    def test_parse_nested(self):
        from naskb.mcp.desc_manager import _parse_frontmatter

        raw = """---
media_info:
  size_bytes: 2048
  mtime: 1234567890.0
  sha256: "abc123def456"
  mime_type: "image/jpeg"
  media_type: "image"
  width: 1920
  height: 1080
description_type: "auto_generated"
---
# Photo Title

Description here."""

        metadata, content = _parse_frontmatter(raw)
        assert metadata is not None
        assert isinstance(metadata["media_info"], dict)
        assert metadata["media_info"]["size_bytes"] == 2048
        assert metadata["media_info"]["mime_type"] == "image/jpeg"
        assert metadata["description_type"] == "auto_generated"
        assert "# Photo Title" in content

    def test_parse_no_frontmatter(self):
        from naskb.mcp.desc_manager import _parse_frontmatter

        raw = "Just plain text without any frontmatter."
        metadata, content = _parse_frontmatter(raw)
        assert metadata is None
        assert content == raw

    def test_parse_comment_in_frontmatter(self):
        from naskb.mcp.desc_manager import _parse_frontmatter

        raw = """---
# This is a comment
name: test
# Another comment
version: "2.0"
---
Content."""

        metadata, content = _parse_frontmatter(raw)
        assert metadata is not None
        assert metadata["name"] == "test"
        assert metadata["version"] == 2.0   # Parsed as float


# ═══════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════

def asyncio_sleep(seconds: float):
    """Async sleep helper."""
    import asyncio
    return asyncio.sleep(seconds)
