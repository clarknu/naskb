"""HTTP Range 解析单测（server/ranges.py，REQ-R7-07）。"""
from naskb.server.ranges import content_range, parse_range


class TestParseRange:
    def test_no_header(self):
        assert parse_range(None, 100) == (None, True)

    def test_non_bytes_unit_fallback(self):
        assert parse_range("items=0-5", 100) == (None, True)

    def test_full_closed_range(self):
        assert parse_range("bytes=0-99", 100) == ((0, 99), True)
        assert parse_range("bytes=10-19", 100) == ((10, 19), True)

    def test_open_end(self):
        rng, valid = parse_range("bytes=50-", 100)
        assert valid and rng == (50, 99)

    def test_suffix_last_n(self):
        assert parse_range("bytes=-10", 100) == ((90, 99), True)
        # suffix 超过文件大小：从 0 开始
        assert parse_range("bytes=-500", 100) == ((0, 99), True)

    def test_end_clamped(self):
        assert parse_range("bytes=90-500", 100) == ((90, 99), True)

    def test_unsatisfiable_start_beyond_size(self):
        rng, valid = parse_range("bytes=100-", 100)
        assert rng is None and valid is False

    def test_inverted_range_invalid(self):
        rng, valid = parse_range("bytes=50-40", 100)
        assert rng is None and valid is False

    def test_multi_range_fallback_full(self):
        rng, valid = parse_range("bytes=0-1,5-6", 100)
        assert rng is None and valid is True

    def test_empty_file_any_range_unsatisfiable(self):
        rng, valid = parse_range("bytes=0-", 0)
        assert rng is None and valid is False

    def test_content_range_format(self):
        assert content_range(10, 19, 100) == "bytes 10-19/100"
