"""音频分析器 — ffmpeg 分段 + 大模型（MiMo）转写（v2）。

用户拍板：
- 音频转写走大模型（MiMo V2.5 input_audio），不用本地 whisper（效果差）
- 长音频 ffmpeg 分段（默认 25min/段）→ 逐段转写 → 拼接
- 多段必须严格串行调用（并行触发平台风控，key 会被冻结 401）
- 说话人分离尽力尝试（diarization 开关，prompt 要求标注）
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..llm import BaseLLMClient, LLMError

TRANSCRIBE_PROMPT = "请把这段语音的完整内容转写成文字，只输出转写结果，不要任何解释。"
DIARIZE_PROMPT = (
    "请把这段语音转写成文字，并尽可能标注说话人（如 说话人A: ... 说话人B: ...），"
    "只输出转写结果。"
)

SEGMENT_SECONDS = 25 * 60  # 默认分段 25 分钟


class AudioAnalyzer:
    """音频内容分析：ffmpeg 转换分段 → MiMo 串行转写 → 拼接全文。"""

    def __init__(self, llm: BaseLLMClient,
                 split_seconds: int = SEGMENT_SECONDS,
                 diarization: bool = False):
        self._llm = llm
        self._split_seconds = split_seconds
        self._diarization = diarization
        self._ffmpeg = _find_binary("ffmpeg")

    def transcribe(self, audio_path: str) -> str:
        """转写音频文件，返回完整文本。

        流程：ffmpeg 转 16kHz mono wav → 分段 → 逐段 MiMo（严格串行）→ 拼接。
        """
        if not os.path.exists(audio_path):
            raise LLMError(f"音频文件不存在: {audio_path}")
        if not self._ffmpeg:
            raise LLMError("ffmpeg 未安装，无法转写音频")

        with tempfile.TemporaryDirectory(prefix="naskb-audio-") as tmp:
            wav = self._to_wav(audio_path, tmp)
            segments = self._split(wav, tmp)
            prompt = DIARIZE_PROMPT if self._diarization else TRANSCRIBE_PROMPT
            parts: list[str] = []
            for seg in segments:
                # 严格串行：每段一次请求，等待完成再发下一段
                parts.append(self._llm.complete_audio(seg, prompt))
            return "\n".join(p for p in parts if p)

    def _to_wav(self, audio_path: str, tmp_dir: str) -> str:
        """任意音频 → 16kHz mono 16-bit WAV。"""
        wav_path = os.path.join(tmp_dir, "audio.wav")
        cmd = [self._ffmpeg, "-y", "-nostdin", "-i", audio_path,
               "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", wav_path]
        _run(cmd)
        return wav_path

    def _split(self, wav_path: str, tmp_dir: str) -> list[str]:
        """按固定时长分段，返回分段文件路径列表。"""
        probe = _ffprobe_duration(wav_path)
        duration = probe if probe and probe > 0 else self._split_seconds
        if duration <= self._split_seconds:
            return [wav_path]

        segments: list[str] = []
        start = 0
        idx = 0
        while start < duration:
            seg_path = os.path.join(tmp_dir, f"seg_{idx:03d}.wav")
            cmd = [self._ffmpeg, "-y", "-nostdin", "-i", wav_path,
                   "-ss", str(start), "-t", str(self._split_seconds),
                   "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", seg_path]
            _run(cmd)
            segments.append(seg_path)
            start += self._split_seconds
            idx += 1
        return segments


def _find_binary(name: str) -> Optional[str]:
    import shutil
    return shutil.which(name)


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise LLMError(f"命令失败: {' '.join(cmd[:4])}... — {proc.stderr[-300:]}")


def _ffprobe_duration(path: str) -> Optional[float]:
    ffprobe = _find_binary("ffprobe")
    if not ffprobe:
        return None
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(proc.stdout.strip()) if proc.returncode == 0 else None
    except Exception:
        return None
