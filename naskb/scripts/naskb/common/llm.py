"""LLM 调用框架 — 支持 OpenAI / Anthropic / Ollama 切换。

架构文档 3.2「大模型调用策略」：
- 云端主模型（GPT-4o / Claude）：复杂内容分析，Structured Output
- 本地模型（Ollama）：简单分类，隐私内容，零成本
- 统一接口：complete() 自由文本，complete_json() 结构化输出

协议实现：
- OpenAI 兼容（openai / deepseek / ollama /v1/chat/completions 等）
- Anthropic /v1/messages（system 独立字段）

依赖：httpx（Python 3.10+ 标准 HTTP 客户端）。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


class LLMError(Exception):
    """LLM 调用失败。"""


@dataclass
class LLMConfig:
    """单个 LLM 端点配置。

    provider: "openai" / "anthropic" / "ollama"（openai 与 ollama 均走 OpenAI 兼容协议）
    base_url: 自定义端点；ollama 默认 http://localhost:11434/v1
    """
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    timeout: float = 120.0
    temperature: float = 0.2
    max_tokens: int = 2048

    def __post_init__(self) -> None:
        if httpx is None:
            raise ImportError("LLM 支持需要 httpx: pip install httpx")
        if self.provider == "ollama" and not self.base_url:
            self.base_url = "http://localhost:11434/v1"
        if self.provider == "openai" and not self.base_url:
            self.base_url = "https://api.openai.com/v1"
        if self.provider == "anthropic" and not self.base_url:
            self.base_url = "https://api.anthropic.com/v1"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMConfig":
        return cls(
            provider=str(data.get("provider", "openai")),
            model=str(data.get("model", "gpt-4o-mini")),
            api_key=str(data.get("api_key", "")),
            base_url=str(data.get("base_url", "")),
            timeout=float(data.get("timeout", 120.0)),
            temperature=float(data.get("temperature", 0.2)),
            max_tokens=int(data.get("max_tokens", 2048)),
        )


class BaseLLMClient:
    """LLM 客户端基类。"""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._client = httpx.Client(timeout=config.timeout)  # type: ignore[union-attr]

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """自由文本补全。"""
        raise NotImplementedError

    def complete_json(self, prompt: str, system: Optional[str] = None,
                      schema: Optional[dict] = None) -> dict:
        """结构化输出：请求 JSON 并解析。解析失败抛 LLMError。"""
        raise NotImplementedError

    def close(self) -> None:
        try:
            self._client.close()  # type: ignore[union-attr]
        except Exception:
            pass

    # ── 工具 ──

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从模型输出中提取 JSON 对象（容忍 markdown 代码块包裹）。"""
        t = text.strip()
        # 去掉 ```json ... ``` 代码块
        fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.DOTALL)
        if fence:
            t = fence.group(1)
        else:
            # 取第一个 { 到最后一个 }
            start, end = t.find("{"), t.rfind("}")
            if start != -1 and end > start:
                t = t[start:end + 1]
        try:
            return json.loads(t)
        except json.JSONDecodeError as e:
            raise LLMError(f"模型输出不是合法 JSON: {e} — {text[:200]}")


class OpenAICompatClient(BaseLLMClient):
    """OpenAI 兼容协议客户端（openai / ollama / deepseek / mimo / vllm 等）。

    支持多模态消息：image_url（图片）/ input_audio（音频），
    与小米 MiMo V2.5 的 /v1/chat/completions 多模态接口兼容。
    """

    def _chat(self, prompt: str, system: Optional[str],
              json_mode: bool,
              multimodal: Optional[list[dict]] = None) -> str:
        url = self._config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        if multimodal:
            # 多模态消息：content 为 [{"type": "image_url", ...}, {"type": "text", ...}]
            messages.append({"role": "user", "content": multimodal + [
                {"type": "text", "text": prompt}]})
        else:
            messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = self._client.post(url, json=payload, headers=headers)  # type: ignore[union-attr]
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])
        except httpx.HTTPStatusError as e:  # type: ignore[union-attr]
            raise LLMError(f"LLM HTTP {e.response.status_code}: {e.response.text[:300]}")
        except httpx.HTTPError as e:  # type: ignore[union-attr]
            raise LLMError(f"LLM 请求失败: {e}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise LLMError(f"LLM 响应格式异常: {e}")

    # ── 多模态 ──

    def complete_image(self, image_path: str, prompt: str,
                       system: Optional[str] = None) -> str:
        """图片理解：压缩后 base64 以 image_url 消息发送（MiMo V2.5 等）。"""
        if not os.path.exists(image_path):
            raise LLMError(f"图片文件不存在: {image_path}")
        msg = [{
            "type": "image_url",
            "image_url": {"url": self._image_to_data_url(image_path)},
        }]
        return self._chat(prompt, system, json_mode=False, multimodal=msg)

    def _image_to_data_url(self, image_path: str,
                           max_side: int = 1568, quality: int = 82) -> str:
        """把图片压缩为 JPEG data URL（控制视觉模型输入体积，显著降低上传/推理耗时）。

        Pillow 不可用或格式不支持（如 HEIC 无 pillow-heif）时回退原图。
        """
        import base64
        import io
        import mimetypes

        try:
            from PIL import Image, ImageOps
            with Image.open(image_path) as img:
                img.load()
                img = ImageOps.exif_transpose(img)
                if max(img.size) > max_side:
                    img.thumbnail((max_side, max_side), Image.LANCZOS)
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=quality, optimize=True)
                return "data:image/jpeg;base64," + \
                    base64.b64encode(buf.getvalue()).decode()
        except Exception:
            with open(image_path, "rb") as f:
                raw = f.read()
            mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
            return f"data:{mime};base64," + base64.b64encode(raw).decode()

    def complete_audio(self, audio_path: str, prompt: str,
                       system: Optional[str] = None) -> str:
        """音频理解/转写：base64 编码后以 input_audio 消息发送（MiMo V2.5）。

        音频需为 16kHz mono 16-bit WAV（调用方先用 ffmpeg 转换）。
        """
        import base64

        if not os.path.exists(audio_path):
            raise LLMError(f"音频文件不存在: {audio_path}")
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()
        msg = [{
            "type": "input_audio",
            "input_audio": {"data": audio_b64, "format": "wav"},
        }]
        return self._chat(prompt, system, json_mode=False, multimodal=msg)

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        return self._chat(prompt, system, json_mode=False)

    def complete_json(self, prompt: str, system: Optional[str] = None,
                      schema: Optional[dict] = None) -> dict:
        sp = system or ""
        if schema:
            sp += ("\n你必须严格按以下 JSON Schema 输出，只输出 JSON，不要输出其他内容:\n"
                   + json.dumps(schema, ensure_ascii=False))
        # 重试一次：长输出时模型偶发坏 JSON（未转义引号/尾逗号等）
        for attempt in range(2):
            text = self._chat(prompt, sp, json_mode=True)
            try:
                return self._extract_json(text)
            except LLMError:
                if attempt == 0:
                    sp += ("\n注意：上次输出不是合法 JSON。请重新只输出一个"
                           "合法 JSON 对象，不要注释、不要 markdown、"
                           "字符串中的引号必须用 \\\" 转义。")
                    continue
                raise
        raise LLMError("JSON 输出重试后仍无法解析")  # pragma: no cover


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude 客户端（/v1/messages）。"""

    def _chat(self, prompt: str, system: Optional[str],
              json_hint: Optional[str]) -> str:
        url = self._config.base_url.rstrip("/") + "/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._config.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        if json_hint:
            payload["messages"].append({
                "role": "assistant",
                "content": "我会严格输出 JSON。",
            })
            payload["messages"].append({
                "role": "user",
                "content": json_hint,
            })

        try:
            resp = self._client.post(url, json=payload, headers=headers)  # type: ignore[union-attr]
            resp.raise_for_status()
            data = resp.json()
            return "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
        except httpx.HTTPStatusError as e:  # type: ignore[union-attr]
            raise LLMError(f"LLM HTTP {e.response.status_code}: {e.response.text[:300]}")
        except httpx.HTTPError as e:  # type: ignore[union-attr]
            raise LLMError(f"LLM 请求失败: {e}")

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        return self._chat(prompt, system, None)

    def complete_json(self, prompt: str, system: Optional[str] = None,
                      schema: Optional[dict] = None) -> dict:
        hint = "请只输出一个 JSON 对象（不要 markdown 代码块）。"
        if schema:
            hint += ("\n必须严格符合以下 Schema:\n"
                     + json.dumps(schema, ensure_ascii=False))
        text = self._chat(prompt, system, hint)
        return self._extract_json(text)


# ═══════════════════════════════════════════════════════════════════
# 工厂
# ═══════════════════════════════════════════════════════════════════


def create_llm_client(config: LLMConfig) -> BaseLLMClient:
    """按 provider 创建客户端。ollama 也走 OpenAI 兼容协议。"""
    if config.provider in ("openai", "ollama", "deepseek", "vllm", "mimo"):
        return OpenAICompatClient(config)
    if config.provider == "anthropic":
        return AnthropicClient(config)
    raise ValueError(f"不支持的 LLM provider: {config.provider} "
                     "(支持 openai / anthropic / ollama)")
