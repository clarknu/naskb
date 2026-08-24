"""KM（JSON 思维导图）/ MMAP（MindManager ZIP）提取测试。"""
import json
import zipfile

import pytest

from naskb.common.analyzer.document import DocumentAnalyzer, extract_km, extract_mmap


@pytest.fixture
def km_file(tmp_path):
    f = tmp_path / "防护计划.km"
    f.write_text(json.dumps({
        "root": {
            "data": {"id": "r1", "text": "防护计划"},
            "children": [
                {"data": {"id": "c1", "text": "灭火器"}, "children": []},
                {"data": {"id": "c2", "text": "赶猪器（长）"},
                 "children": [
                     {"data": {"id": "c3", "text": "备用电池"}, "children": []},
                 ]},
            ],
        }
    }, ensure_ascii=False), encoding="utf-8")
    return str(f)


@pytest.fixture
def mmap_file(tmp_path):
    f = tmp_path / "金溪功能区.mmap"
    xml = (
        '<Map><ap:Topic OId="1">'
        '<ap:Text PlainText="金溪功能区" ReadOnly="false"><ap:Font/></ap:Text>'
        '</ap:Topic>'
        '<ap:Topic OId="2">'
        '<ap:Text PlainText="沙发 &amp; 茶几" ReadOnly="false"><ap:Font/></ap:Text>'
        '</ap:Topic>'
        '</Map>'
    )
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("Document.xml", xml)
    return str(f)


class TestKm:
    def test_extract_tree_text(self, km_file):
        r = extract_km(km_file)
        assert r.analyzer == "km"
        assert r.text is not None
        lines = r.text.splitlines()
        assert lines[0] == "防护计划"
        assert lines[1] == "  灭火器"
        assert "  赶猪器（长）" in lines
        assert "    备用电池" in lines  # 层级缩进保留

    def test_km_via_analyzer(self, km_file):
        r = DocumentAnalyzer().extract(km_file)
        assert r.analyzer == "km"
        assert "防护计划" in (r.text or "")

    def test_km_bad_json(self, tmp_path):
        f = tmp_path / "bad.km"
        f.write_text("not json", encoding="utf-8")
        r = extract_km(str(f))
        assert r.text is None
        assert r.error and "解析失败" in r.error


class TestMmap:
    def test_extract_plaintext(self, mmap_file):
        r = extract_mmap(mmap_file)
        assert r.analyzer == "mmap"
        assert r.text is not None
        assert "金溪功能区" in r.text
        assert "沙发 & 茶几" in r.text  # XML 实体解码

    def test_mmap_via_analyzer(self, mmap_file):
        r = DocumentAnalyzer().extract(mmap_file)
        assert r.analyzer == "mmap"
        assert "金溪功能区" in (r.text or "")

    def test_mmap_not_zip(self, tmp_path):
        f = tmp_path / "bad.mmap"
        f.write_bytes(b"not a zip")
        r = extract_mmap(str(f))
        assert r.text is None
        assert r.error and "打开失败" in r.error
