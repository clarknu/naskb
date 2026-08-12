"""视频分析器 — ffprobe 元数据 + 分级判定 + 音轨分离 + 关键帧抽取（v2）。

用户拍板（视频分级）：
- 电影/剧集/影视 → 仅元数据（metadata_only），不解析内容
- 教学视频 → 元数据 + 低密度抽帧（keyframes_only），大模型生成大纲
- 个人录像 → 完整处理（full）：音轨分离 → 大模型转写 + 场景抽帧 → 大模型识别

分级判定规则：
1. 路径规则（category_paths 命中 → 强制标记，优先）
2. 关键词规则（目录名/文件名命中 category_keywords）
3. 兜底：时长 > duration_threshold_min → 判为影视（metadata_only）
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..llm import BaseLLMClient, LLMError

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts", ".m4v",
              ".webm", ".mpg", ".mpeg", ".rmvb", ".3gp"}

# 处理策略（写入 FileEntry.processing_policy）
POLICY_METADATA_ONLY = "metadata_only"
POLICY_KEYFRAMES_ONLY = "keyframes_only"
POLICY_FULL = "full"

DEFAULT_CATEGORY_KEYWORDS = [
    {"category": "媒体/影视/电影", "keywords": ["电影", "movie", "BluRay", "1080p"]},
    {"category": "媒体/影视/剧集", "keywords": ["剧集", "season", "s01", "第1季", "TV"]},
    {"category": "媒体/教学视频", "keywords": ["教程", "课程", "教学", "lecture", "course"],
     "policy": POLICY_KEYFRAMES_ONLY},
]

KEYFRAME_PROMPT = (
    "这是视频中抽取的关键帧。请用中文描述画面内容：场景、主体、发生的事件，"
    "一句话总结。"
)


class VideoClassifier:
    """视频分级判定：路径规则 → 关键词规则 → 时长兜底。"""

    def __init__(self, category_paths: Optional[list[dict]] = None,
                 category_keywords: Optional[list[dict]] = None,
                 duration_threshold_min: int = 90):
        self._paths = category_paths or []
        self._keywords = category_keywords or DEFAULT_CATEGORY_KEYWORDS
        self._threshold_min = duration_threshold_min

    def classify(self, path: str, duration_seconds: Optional[float] = None) -> dict:
        """返回 {category, policy}。"""
        # 1. 路径规则（最高优先）
        norm = path.replace("\\", "/").lower()
        for rule in self._paths:
            rule_path = str(rule.get("path", "")).replace("\\", "/").lower()
            if rule_path and rule_path in norm:
                return {"category": rule.get("category", "媒体/影视"),
                        "policy": rule.get("policy", POLICY_METADATA_ONLY)}
        # 2. 关键词规则
        name = Path(path).name.lower()
        for rule in self._keywords:
            for kw in rule.get("keywords", []):
                if str(kw).lower() in name:
                    return {"category": rule.get("category", "媒体/影视"),
                            "policy": rule.get("policy", POLICY_METADATA_ONLY)}
        # 3. 时长兜底
        if duration_seconds is not None and duration_seconds > self._threshold_min * 60:
            return {"category": "媒体/影视", "policy": POLICY_METADATA_ONLY}
        # 4. 默认：个人录像 → 完整处理
        return {"category": "媒体/个人录像", "policy": POLICY_FULL}


class VideoAnalyzer:
    """视频内容分析：元数据提取 + 分级 + 音轨/关键帧处理。"""

    def __init__(self, llm: BaseLLMClient,
                 classifier: VideoClassifier,
                 keyframes_max: int = 20,
                 keyframe_interval_sec: int = 300,
                 audio_analyzer=None):
        self._llm = llm
        self._classifier = classifier
        self._keyframes_max = keyframes_max
        self._interval_sec = keyframe_interval_sec
        self._audio = audio_analyzer  # 可注入 AudioAnalyzer
        self._ffmpeg = _find_binary("ffmpeg")
        self._ffprobe = _find_binary("ffprobe")

    def probe(self, video_path: str) -> dict:
        """ffprobe 提取元数据：时长/分辨率/编码/容器。"""
        meta: dict = {"width": None, "height": None, "duration_seconds": None,
                      "codec": None, "container": Path(video_path).suffix.lower()}
        if not self._ffprobe:
            return meta
        try:
            proc = subprocess.run(
                [self._ffprobe, "-v", "error", "-print_format", "json",
                 "-show_format", "-show_streams", video_path],
                capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return meta
            data = json.loads(proc.stdout)
            fmt = data.get("format", {})
            meta["duration_seconds"] = _f(fmt.get("duration"))
            meta["container"] = str(fmt.get("format_name", meta["container"]))
            for s in data.get("streams", []):
                if s.get("codec_type") == "video":
                    meta["width"] = _i(s.get("width"))
                    meta["height"] = _i(s.get("height"))
                    meta["codec"] = str(s.get("codec_name", ""))
                    if not meta["duration_seconds"]:
                        meta["duration_seconds"] = _f(s.get("duration"))
                    break
        except Exception:
            pass
        return meta

    def analyze(self, video_path: str,
                meta: Optional[dict] = None) -> dict:
        """完整分析：probe → 分级 → 按策略处理。

        Returns:
            {"meta": {...}, "category": "...", "policy": "...",
             "transcription": str|None, "keyframes": [{"path","description"}]}
        """
        meta = meta or self.probe(video_path)
        decision = self._classifier.classify(video_path, meta.get("duration_seconds"))
        result = {"meta": meta, **decision, "transcription": None, "keyframes": []}

        if decision["policy"] == POLICY_METADATA_ONLY:
            return result  # 影视：仅元数据，不解析内容

        if decision["policy"] == POLICY_KEYFRAMES_ONLY:
            result["keyframes"] = self._extract_keyframes(
                video_path, meta, interval_sec=self._interval_sec,
                max_frames=self._keyframes_max)
            return result

        # POLICY_FULL：音轨转写 + 场景抽帧
        if self._audio is not None:
            result["transcription"] = self._extract_audio_transcript(video_path)
        result["keyframes"] = self._extract_keyframes(video_path, meta)
        return result

    def _extract_audio_transcript(self, video_path: str) -> Optional[str]:
        """分离音轨 → 交给 AudioAnalyzer 转写（需注入）。"""
        try:
            if not self._ffmpeg:
                return None
            with tempfile.TemporaryDirectory(prefix="naskb-video-") as tmp:
                audio_path = os.path.join(tmp, "track.m4a")
                proc = subprocess.run(
                    [self._ffmpeg, "-y", "-nostdin", "-i", video_path,
                     "-vn", "-acodec", "copy", audio_path],
                    capture_output=True, text=True, timeout=600)
                if proc.returncode != 0 or not os.path.exists(audio_path):
                    return None
                return self._audio.transcribe(audio_path)
        except Exception:
            return None

    def _extract_keyframes(self, video_path: str, meta: dict,
                           interval_sec: Optional[int] = None,
                           max_frames: int = 20) -> list[dict]:
        """抽取关键帧（均匀间隔），返回 [{path, description}]。

        关键帧为本地临时文件（不写 NAS）；description 由调用方后续用大模型生成。
        """
        frames: list[dict] = []
        if not self._ffmpeg:
            return frames
        duration = meta.get("duration_seconds") or 0
        interval = interval_sec or max(1, int(duration // max_frames))
        if duration <= 0:
            interval = 60
        try:
            with tempfile.TemporaryDirectory(prefix="naskb-frames-") as tmp:
                pattern = os.path.join(tmp, "frame_%03d.jpg")
                proc = subprocess.run(
                    [self._ffmpeg, "-y", "-nostdin", "-i", video_path,
                     "-vf", f"fps=1/{interval}", "-q:v", "2",
                     "-frames:v", str(max_frames), pattern],
                    capture_output=True, text=True, timeout=600)
                if proc.returncode != 0:
                    return frames
                for f in sorted(Path(tmp).glob("frame_*.jpg"))[:max_frames]:
                    frames.append({"path": str(f), "description": ""})
        except Exception:
            pass
        return frames


def _find_binary(name: str) -> Optional[str]:
    import shutil
    return shutil.which(name)


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _i(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
