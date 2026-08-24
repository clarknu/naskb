"""Config [nas] 解析单测（v3 五要素身份字段 + v2 遗留键兼容）。

覆盖：alias/protocol/host/port/username 提取；v2 老键（name/user）互认；
传统 WebDAV 键（webdav_port/webdav_https/verify_ssl）保留；多条目数组。
"""
import tomllib

from naskb.common.config import Config

TOML = """
[[nas]]
name = "home-nas"
protocol = "local"
host = ""
port = 0
username = "alice"

[[nas]]
name = "legacy-dav"
user = "bob"
host = "192.168.5.2"
webdav_port = 5006
webdav_https = true
verify_ssl = false
"""


def _cfg(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(TOML, encoding="utf-8")
    data = tomllib.loads(TOML)
    return Config(str(tmp_path), data)


def test_nas_v3_identity_fields(tmp_path):
    cfg = _cfg(tmp_path)
    assert len(cfg.nas_list) == 2
    first = cfg.nas_list[0]
    # v3 身份字段（_resolve_nas_identity 依赖）
    assert first["alias"] == "home-nas"
    assert first["protocol"] == "local"
    assert first["port"] == 0
    assert first["username"] == "alice"


def test_nas_v2_legacy_keys_compat(tmp_path):
    cfg = _cfg(tmp_path)
    legacy = cfg.nas_list[1]
    # 旧键 name/user → alias/username 互认
    assert legacy["alias"] == "legacy-dav"
    assert legacy["username"] == "bob"
    assert legacy["name"] == "legacy-dav"
    # 传统 WebDAV 键保留
    assert legacy["webdav_port"] == 5006
    assert legacy["webdav_https"] is True
    assert legacy["verify_ssl"] is False
    assert legacy["host"] == "192.168.5.2"


def test_nas_alias_via_get_nas(tmp_path):
    cfg = _cfg(tmp_path)
    assert cfg.get_nas("home-nas") is not None
