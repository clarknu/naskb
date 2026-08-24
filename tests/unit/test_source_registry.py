"""来源注册表测试（JSON 后端；source_registry，REQ-R7-03）。"""
import json

import pytest

from naskb.common.source_registry import SourceRecord, SourceRegistry


class _Cfg:
    def __init__(self, work_path):
        self.work_path = work_path
        self.pg_enabled = False


@pytest.fixture
def reg(tmp_path):
    return SourceRegistry(_Cfg(str(tmp_path)))


def _local(**kw):
    base = dict(alias="docs", protocol="local", root_path="C:/tmp/docs",
                access_mode="ro")
    base.update(kw)
    return SourceRecord(**base)


def test_create_get_roundtrip(reg):
    rec = reg.create(_local())
    assert rec.schema_name.startswith("nas_local_")
    got = reg.get(rec.source_id)
    assert got is not None and got.alias == "docs"
    by_alias = reg.get("docs")
    assert by_alias.source_id == rec.source_id


def test_alias_conflict_rejected(reg):
    reg.create(_local())
    with pytest.raises(ValueError, match="alias 已存在"):
        reg.create(_local(root_path="C:/other"))


def test_deep_field_roundtrip_and_update(reg):
    rec = reg.create(_local(deep=True))
    got = reg.get(rec.source_id)
    assert got.deep is True
    assert got.to_api()["deep"] is True    # API 输出带 deep
    upd = reg.update(rec.source_id, deep=False)
    assert upd.deep is False
    assert reg.get(rec.source_id).deep is False


@pytest.mark.parametrize("bad", [
    {"alias": "非法 别名"},
    {"protocol": "ftp"},
    {"access_mode": "rw2"},
])
def test_validation(reg, bad):
    with pytest.raises(ValueError):
        reg.create(_local(**bad))


def test_json_persistence_and_mask(tmp_path, reg):
    rec = reg.create(_local(password="secret"))
    raw = json.loads(
        (tmp_path / "sources.json").read_text(encoding="utf-8"))
    stored = [s for s in raw["sources"] if s["alias"] == "docs"]
    assert stored and stored[0]["password"] == "secret"      # 落盘明文（与 config 同策略）
    api = reg.get(rec.source_id).to_api()
    assert api["password"] == "******"                       # API 输出脱敏
    assert SourceRecord(**{**api, "password": ""}).password == ""


def test_update_and_delete(reg):
    rec = reg.create(_local(access_mode="ro"))
    upd = reg.update(rec.source_id, access_mode="rw", label="主库")
    assert upd.access_mode == "rw" and upd.label == "主库"
    assert reg.update(rec.source_id, scan_interval_min=5).scan_interval_min == 5
    assert reg.delete(rec.source_id) is True
    assert reg.get(rec.source_id) is None
    assert reg.delete(rec.source_id) is False


def test_webdav_identity_schema_name(reg):
    rec = reg.create(SourceRecord(
        alias="nas1", protocol="webdav",
        url="https://192.168.5.2:5006/home/docs",
        host="192.168.5.2", port=5006, username="alice",
        access_mode="ro"))
    assert rec.identity() == ("webdav", "192.168.5.2", 5006, "alice")
    assert "_u" in rec.schema_name
