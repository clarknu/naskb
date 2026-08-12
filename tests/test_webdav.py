"""WebDAV 适配器测试：路径映射、时间戳转换、list/stat 解析。

覆盖真实群晖 WebDAV 发现的问题：
- webdav4 返回的 modified 是 datetime 对象（非 float）
- name 是相对请求路径、href 是服务器绝对路径
- size 字段在 detail=True 下是 content_length
- 根路径为 / 时 _to_remote_path 不能产生 // 双斜杠
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from naskb.common.fs.webdav import (
    WebDAVAdapter,
    _norm_path,
    _to_timestamp,
)


class TestHelpers:
    def test_to_timestamp_datetime(self):
        """datetime 对象（webdav4 实际返回）转 epoch 秒。"""
        dt = datetime.datetime(2025, 8, 30, 11, 4, 49, tzinfo=datetime.timezone.utc)
        ts = _to_timestamp(dt)
        assert ts == pytest.approx(1756551889.0)

    def test_to_timestamp_none_and_float(self):
        assert _to_timestamp(None) == 0.0
        assert _to_timestamp(123.5) == 123.5
        assert _to_timestamp("42") == 42.0
        assert _to_timestamp("garbage") == 0.0

    def test_norm_path(self):
        assert _norm_path("//Unclassified") == "/Unclassified"
        assert _norm_path("/MediaLib/") == "/MediaLib"
        assert _norm_path("/") == "/"
        assert _norm_path("/a//b/") == "/a/b"


class FakeClient:
    """模拟 webdav4.Client 的 ls/info 返回（群晖真实结构）。"""

    def __init__(self, entries, info):
        self._entries = entries
        self._info = info
        self.last_ls = None
        self.last_info = None

    def ls(self, path, detail=True):
        self.last_ls = path
        return self._entries

    def info(self, path):
        self.last_info = path
        return self._info

    def close(self):
        pass


def _make_adapter(fake):
    """构造已注入 fake client 的 WebDAVAdapter。"""
    adapter = WebDAVAdapter.__new__(WebDAVAdapter)
    adapter._root_url = "https://nas.example.com:5006/"
    adapter._base_url = "https://nas.example.com:5006"
    adapter._root_path = "/"
    adapter._client = fake
    return adapter


class TestPathMapping:
    def test_root_path_no_double_slash(self):
        """根路径为 / 时映射不能产生 //（真实 NAS 根路径 bug）。"""
        adapter = _make_adapter(FakeClient([], {}))
        assert adapter._to_remote_path("/Unclassified") == "/Unclassified"
        assert adapter._to_remote_path("/") == "/"
        assert adapter._to_remote_path("Unclassified/wg.conf") == "/Unclassified/wg.conf"

    def test_subpath_root(self):
        adapter = _make_adapter(FakeClient([], {}))
        adapter._root_path = "/DriveShare"
        assert adapter._to_remote_path("/DriveShare/Photos") == "/DriveShare/Photos"
        assert adapter._to_remote_path("/Photos") == "/DriveShare/Photos"


class TestListFiles:
    def test_list_files_parses_real_webdav4_structure(self):
        """群晖真实返回：name 相对路径、href 绝对路径、modified 为 datetime。"""
        entries = [
            {
                "name": "Unclassified/wg.conf",
                "href": "/Unclassified/wg.conf",
                "content_length": 335,
                "modified": datetime.datetime(2025, 8, 30, 11, 4, 49,
                                              tzinfo=datetime.timezone.utc),
                "type": "file",
                "display_name": "wg.conf",
            },
            {
                "name": "Unclassified/IMG_1.jpg",
                "href": "/Unclassified/IMG_1.jpg",
                "content_length": 491155,
                "modified": datetime.datetime(2025, 8, 30, 11, 5, 15,
                                              tzinfo=datetime.timezone.utc),
                "type": "file",
                "display_name": "IMG_1.jpg",
            },
        ]
        adapter = _make_adapter(FakeClient(entries, {}))
        files = adapter.list_files("/Unclassified", recursive=False)

        assert len(files) == 2
        assert files[0].path == "/Unclassified/wg.conf"
        assert files[0].name == "wg.conf"
        assert files[0].size_bytes == 335
        assert files[0].mtime == pytest.approx(1756551889.0)
        assert files[0].ext == ".conf"
        assert files[1].ext == ".jpg"

    def test_list_files_recursive_uses_href(self):
        """递归时子目录用 href 完整路径，不再拼接出 //RegularSync/RegularSync。"""
        subdir = {
            "name": "RegularSync/my-ai-consult",
            "href": "/RegularSync/my-ai-consult/",
            "type": "directory",
            "display_name": "my-ai-consult",
        }
        subfile = {
            "name": "RegularSync/my-ai-consult/notes.md",
            "href": "/RegularSync/my-ai-consult/notes.md",
            "content_length": 100,
            "type": "file",
            "display_name": "notes.md",
        }

        class RecursiveClient(FakeClient):
            def ls(self, path, detail=True):
                self.last_ls = path
                if path == "/RegularSync":
                    return [subdir]
                if path == "/RegularSync/my-ai-consult":
                    return [subfile]
                return []

        adapter = _make_adapter(RecursiveClient([], {}))
        files = adapter.list_files("/RegularSync", recursive=True)
        assert len(files) == 1
        assert files[0].path == "/RegularSync/my-ai-consult/notes.md"


class TestStat:
    def test_stat_parses_real_structure(self):
        info = {
            "name": "Unclassified",
            "href": "/Unclassified/",
            "content_length": None,
            "modified": datetime.datetime(2026, 8, 8, 12, 47, 38,
                                          tzinfo=datetime.timezone.utc),
            "type": "directory",
            "display_name": "Unclassified",
        }
        adapter = _make_adapter(FakeClient([], info))
        st = adapter.stat("/Unclassified")
        assert st is not None
        assert st.is_dir is True
        assert st.path == "/Unclassified"
        assert st.name == "Unclassified"
