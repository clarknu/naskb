"""采样 hash 规则（ADR-20260816-4）与三级判定链测试。"""
import hashlib
import os

import pytest

from naskb.common.batch import _stat_unchanged, _upgrade_fingerprint
from naskb.common.desc_store import FileEntry, NaskbStore
from naskb.common.fs.local import LocalAdapter
from naskb.common.hashing import (HASH_ALG_FULL, HASH_ALG_SAMPLE,
                                  SAMPLE_SEGMENTS, SAMPLE_SEG_SIZE,
                                  sample_ranges)


class TestSampleRanges:
    def test_small_file_full(self):
        assert sample_ranges(100) is None
        assert sample_ranges(512 * 1024) is None  # 边界：=512KB 全量

    def test_large_file_segments(self):
        size = 4 * 1024 * 1024 * 1024  # 4GB
        spans = sample_ranges(size)
        assert spans is not None
        assert len(spans) == SAMPLE_SEGMENTS
        assert spans[0][0] == 0                    # 首段含文件头
        assert spans[-1][0] + spans[-1][1] == size  # 末段含文件尾
        assert all(l == SAMPLE_SEG_SIZE for _, l in spans)

    def test_positions_deterministic(self):
        """同大小文件永远取相同位置；不同大小位置不同。"""
        assert sample_ranges(10_000_000) == sample_ranges(10_000_000)
        assert sample_ranges(10_000_000) != sample_ranges(20_000_000)

    def test_positions_uniformly_spread(self):
        size = 8 * 1024 * 1024
        starts = [s for s, _ in sample_ranges(size)]
        # 8 段应覆盖文件头/中/尾而非堆在头部
        assert starts[0] == 0
        assert starts[-1] == size - SAMPLE_SEG_SIZE
        assert starts[3] > size // 4   # 中间段已越过 1/4 处

    def test_barely_large_file(self):
        """刚超过 512KB 的文件：段可能重叠/缩短，但不越界且确定。"""
        size = 512 * 1024 + 1
        spans = sample_ranges(size)
        assert spans is not None
        for start, length in spans:
            assert start >= 0
            assert start + length <= size
            assert length > 0


class TestComputeHash:
    def _store(self, tmp_path):
        fs = LocalAdapter(str(tmp_path))
        return NaskbStore(fs), fs

    def test_small_file_full_hash(self, tmp_path):
        store, fs = self._store(tmp_path)
        p = tmp_path / "a.txt"
        p.write_bytes(b"hello world")
        alg, h = store.compute_hash(str(p))
        assert alg == HASH_ALG_FULL
        assert h == "sha256:" + hashlib.sha256(b"hello world").hexdigest()

    def test_large_file_sampled_hash(self, tmp_path):
        """大文件：采样 hash 与手工按 sample_ranges 计算一致。"""
        store, fs = self._store(tmp_path)
        p = tmp_path / "big.bin"
        data = os.urandom(3 * 1024 * 1024)
        p.write_bytes(data)
        alg, h = store.compute_hash(str(p))
        assert alg == HASH_ALG_SAMPLE
        # 手工复算
        hh = hashlib.sha256()
        for start, length in sample_ranges(len(data)):
            hh.update(data[start:start + length])
        assert h == "sha256:" + hh.hexdigest()

    def test_head_only_difference_detected(self, tmp_path):
        """采样 hash 能区分'头相同、尾部不同'的文件（防伪装）。"""
        store, fs = self._store(tmp_path)
        head = b"A" * (2 * 1024 * 1024)   # 2MB 相同头部
        p1 = tmp_path / "f1.bin"
        p2 = tmp_path / "f2.bin"
        p1.write_bytes(head + b"X" * (2 * 1024 * 1024))
        p2.write_bytes(head + b"Y" * (2 * 1024 * 1024))
        _, h1 = store.compute_hash(str(p1))
        _, h2 = store.compute_hash(str(p2))
        assert h1 != h2

    def test_file_shrunk_raises(self, tmp_path):
        """读取量与 size 不符（文件在变化）→ 抛异常，不静默降级。"""
        store, fs = self._store(tmp_path)
        p = tmp_path / "f.bin"
        p.write_bytes(b"short")
        with pytest.raises(Exception):
            store.compute_hash(str(p), size=10 * 1024 * 1024)  # 谎报大尺寸


class TestStatUnchanged:
    def test_all_fields_match(self):
        f = type("F", (), {"size_bytes": 100, "mtime": 1.5, "ctime": 2.5})()
        e = FileEntry(size_bytes=100, mtime=1.5, ctime=2.5)
        assert _stat_unchanged(e, f)

    def test_missing_ctime_never_exempt(self):
        """ctime 任一侧缺失 → 不得免检（ADR-20260816-4 必要条件）。"""
        f = type("F", (), {"size_bytes": 100, "mtime": 1.5, "ctime": 2.5})()
        e = FileEntry(size_bytes=100, mtime=1.5, ctime=0.0)   # 条目无 ctime
        assert not _stat_unchanged(e, f)
        f2 = type("F", (), {"size_bytes": 100, "mtime": 1.5, "ctime": 0.0})()
        e2 = FileEntry(size_bytes=100, mtime=1.5, ctime=2.5)  # 文件无 ctime
        assert not _stat_unchanged(e2, f2)

    def test_mtime_or_size_diff(self):
        f = type("F", (), {"size_bytes": 100, "mtime": 1.5, "ctime": 2.5})()
        assert not _stat_unchanged(
            FileEntry(size_bytes=99, mtime=1.5, ctime=2.5), f)
        assert not _stat_unchanged(
            FileEntry(size_bytes=100, mtime=1.6, ctime=2.5), f)


class TestUpgradeFingerprint:
    def test_upgrade_legacy_entry(self, tmp_path):
        """旧条目（无 hash_algorithm/ctime）补算新指纹，不重析。"""
        p = tmp_path / "旧文件.pdf"
        p.write_bytes(b"%PDF content " * 100)
        fs = LocalAdapter(str(tmp_path))
        store = NaskbStore(fs)
        store.set_entry(str(p), FileEntry(
            original_path="旧文件.pdf", summary="旧摘要", category="文档",
            file_hash="sha256:deadbeef0000000000000000000000000000000000",
            size_bytes=p.stat().st_size, mtime=p.stat().st_mtime))
        old = store.get_entry(str(p))
        assert old and old.hash_algorithm == ""
        f = type("F", (), {"path": str(p), "size_bytes": p.stat().st_size,
                           "mtime": p.stat().st_mtime,
                           "ctime": p.stat().st_ctime})()
        assert _upgrade_fingerprint(store, f, old)
        upgraded = store.get_entry(str(p))
        # 算法取决于大小：≤512KB 为 FULL，否则 SAMPLE
        expected = HASH_ALG_FULL if p.stat().st_size <= 512 * 1024 \
            else HASH_ALG_SAMPLE
        assert upgraded.hash_algorithm == expected
        assert upgraded.file_hash.startswith("sha256:")
        assert upgraded.ctime == f.ctime
        # 分析内容保留（不重析）
        assert upgraded.summary == "旧摘要"
