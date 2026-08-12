"""v2 分析器测试：图片/音频/视频 + 视频分级规则引擎。

- VideoClassifier：路径规则/关键词规则/时长兜底/默认策略
- VideoAnalyzer：ffprobe 元数据（真实 ffmpeg 合成素材）、分级后不解析影视
- ImageAnalyzer/AudioAnalyzer：依赖降级与 LLM mock
"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from naskb.common.analyzer.audio import AudioAnalyzer
from naskb.common.analyzer.image import ImageAnalyzer, extract_exif
from naskb.common.analyzer.video import (
    POLICY_FULL,
    POLICY_KEYFRAMES_ONLY,
    POLICY_METADATA_ONLY,
    VideoAnalyzer,
    VideoClassifier,
)
from naskb.common.llm import LLMError


# ═══════════════════════════════════════════════════════════════════
# 视频分级规则引擎
# ═══════════════════════════════════════════════════════════════════

class TestVideoClassifier:
    def test_path_rule_wins(self):
        c = VideoClassifier(
            category_paths=[{"category": "媒体/影视", "path": "/XVideo"}],
        )
        r = c.classify("/XVideo/复仇者联盟.mp4", duration_seconds=7200)
        assert r["category"] == "媒体/影视"
        assert r["policy"] == POLICY_METADATA_ONLY

    def test_keyword_rule_movie(self):
        c = VideoClassifier()
        r = c.classify("/home/电影/星际穿越.2014.1080p.BluRay.mkv")
        assert r["policy"] == POLICY_METADATA_ONLY
        assert "电影" in r["category"]

    def test_keyword_rule_course(self):
        c = VideoClassifier()
        r = c.classify("/learn/Python教程-第3讲.mp4")
        assert r["category"] == "媒体/教学视频"
        assert r["policy"] == POLICY_KEYFRAMES_ONLY

    def test_keyword_case_insensitive(self):
        c = VideoClassifier()
        r = c.classify("/videos/MyHomeVideo.MOV")
        assert r["policy"] == POLICY_FULL  # 无关键词命中 → 个人录像

    def test_duration_fallback(self):
        """无规则命中但时长 > 90min → 判为影视。"""
        c = VideoClassifier(duration_threshold_min=90)
        r = c.classify("/home/camera/2025-08-10_23-45.mkv", duration_seconds=7200)
        assert r["category"] == "媒体/影视"
        assert r["policy"] == POLICY_METADATA_ONLY

    def test_short_default_full(self):
        c = VideoClassifier()
        r = c.classify("/home/camera/IMG_0001.mp4", duration_seconds=120)
        assert r["category"] == "媒体/个人录像"
        assert r["policy"] == POLICY_FULL

    def test_custom_keywords(self):
        c = VideoClassifier(category_keywords=[
            {"category": "媒体/影视/综艺", "keywords": ["综艺", "variety"]},
        ])
        r = c.classify("奔跑吧-综艺第2期.mp4")
        assert r["category"] == "媒体/影视/综艺"
        assert r["policy"] == POLICY_METADATA_ONLY


# ═══════════════════════════════════════════════════════════════════
# 视频分析器（ffmpeg 合成真实素材）
# ═══════════════════════════════════════════════════════════════════

FFMPEG = subprocess.run(["where", "ffmpeg"], capture_output=True,
                        text=True).returncode == 0


def _make_test_video(tmp_path: Path, seconds: int = 3) -> Path:
    """用 ffmpeg 合成一个测试视频（testsrc 模式）。"""
    v = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-f", "lavfi", "-i",
         f"testsrc=duration={seconds}:size=320x240:rate=10",
         "-pix_fmt", "yuv420p", str(v)],
        capture_output=True, text=True, check=True)
    return v


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg 不可用")
class TestVideoAnalyzer:
    def test_probe_metadata(self, tmp_path):
        v = _make_test_video(tmp_path, seconds=2)
        a = VideoAnalyzer(llm=None, classifier=VideoClassifier())
        meta = a.probe(str(v))
        assert meta["duration_seconds"] is not None
        assert meta["width"] == 320
        assert meta["height"] == 240
        assert meta["codec"]

    def test_movie_policy_no_content_parsing(self, tmp_path):
        """影视类：仅元数据，不抽帧不转写（llm=None 也不会崩）。"""
        v = _make_test_video(tmp_path, seconds=2)
        a = VideoAnalyzer(llm=None, classifier=VideoClassifier(
            category_paths=[{"category": "媒体/影视", "path": str(tmp_path)}]))
        r = a.analyze(str(v))
        assert r["policy"] == POLICY_METADATA_ONLY
        assert r["keyframes"] == []
        assert r["transcription"] is None

    def test_full_policy_extracts_keyframes(self, tmp_path):
        v = _make_test_video(tmp_path, seconds=3)
        a = VideoAnalyzer(llm=None, classifier=VideoClassifier(),
                          keyframes_max=3, keyframe_interval_sec=1)
        r = a.analyze(str(v))
        assert r["policy"] == POLICY_FULL
        # 关键帧为本地临时文件（不写 NAS）；analyze 后已清理
        assert r["keyframes"] == [] or all(
            not Path(k["path"]).exists() for k in r["keyframes"])


# ═══════════════════════════════════════════════════════════════════
# 图片分析器
# ═══════════════════════════════════════════════════════════════════

class TestImageAnalyzer:
    def test_extract_exif_no_pillow_or_missing(self, tmp_path):
        """非图片文件/无 EXIF → 返回空 dict，不抛异常。"""
        f = tmp_path / "plain.txt"
        f.write_text("x", encoding="utf-8")
        assert extract_exif(str(f)) == {}

    def test_analyze_missing_file_raises(self, tmp_path):
        """不存在的图片 → LLMError（文件检查在调用大模型之前）。"""
        a = ImageAnalyzer(llm=None)
        with pytest.raises(LLMError, match="图片文件不存在"):
            a.analyze(str(tmp_path / "nope.jpg"))


# ═══════════════════════════════════════════════════════════════════
# 音频分析器
# ═══════════════════════════════════════════════════════════════════

class TestAudioAnalyzer:
    def test_missing_file_raises(self, tmp_path):
        a = AudioAnalyzer(llm=None)
        with pytest.raises(LLMError, match="音频文件不存在"):
            a.transcribe(str(tmp_path / "nope.wav"))

    def test_no_ffmpeg_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "clip.wav"
        f.write_bytes(b"RIFF")
        a = AudioAnalyzer(llm=None)
        monkeypatch.setattr(a, "_ffmpeg", None)
        with pytest.raises(LLMError, match="ffmpeg"):
            a.transcribe(str(f))
