"""LLM 调用框架测试：OpenAI 兼容协议 + Anthropic 协议 + JSON 容错解析。

使用本地 HTTP mock server 模拟模型端点，不依赖真实 API。
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "naskb" / "scripts"))

import pytest

from naskb.common.llm import (
    AnthropicClient,
    LLMConfig,
    LLMError,
    OpenAICompatClient,
    create_llm_client,
)


class MockLLMServer:
    """模拟模型 HTTP 端点。"""

    def __init__(self):
        self.last_request = None  # 记录最后一次请求 body
        self.openai_response = {
            "choices": [{"message": {"content": "你好，我是模型"}}]
        }
        self.anthropic_response = {
            "content": [{"type": "text", "text": "你好，我是模型"}]
        }
        self.handler = None
        self._server = HTTPServer(("127.0.0.1", 0), self._make_handler())
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def _make_handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                outer.last_request = json.loads(body)
                if self.path.endswith("/messages"):
                    payload = json.dumps(outer.anthropic_response).encode()
                else:
                    payload = json.dumps(outer.openai_response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        return Handler

    def close(self):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def mock_server():
    s = MockLLMServer()
    yield s
    s.close()


class TestOpenAICompat:
    def test_complete(self, mock_server):
        cfg = LLMConfig(
            provider="openai", model="gpt-4o-mini",
            api_key="sk-test", base_url=f"http://127.0.0.1:{mock_server.port}/v1",
        )
        client = create_llm_client(cfg)
        try:
            resp = client.complete("讲个笑话")
            assert resp == "你好，我是模型"
            assert mock_server.last_request["model"] == "gpt-4o-mini"
            assert mock_server.last_request["messages"][-1]["content"] == "讲个笑话"
        finally:
            client.close()

    def test_complete_with_system(self, mock_server):
        cfg = LLMConfig(provider="openai", model="m",
                        base_url=f"http://127.0.0.1:{mock_server.port}/v1")
        client = create_llm_client(cfg)
        try:
            client.complete("q", system="你是助手")
            msgs = mock_server.last_request["messages"]
            assert msgs[0] == {"role": "system", "content": "你是助手"}
        finally:
            client.close()

    def test_complete_json_json_mode(self, mock_server):
        mock_server.openai_response = {
            "choices": [{"message": {"content": '{"summary": "海边日落", "tags": ["海"]}'}}]
        }
        cfg = LLMConfig(provider="openai", model="m",
                        base_url=f"http://127.0.0.1:{mock_server.port}/v1")
        client = OpenAICompatClient(cfg)
        try:
            result = client.complete_json("分析", schema={"type": "object"})
            assert result == {"summary": "海边日落", "tags": ["海"]}
            # json_mode 请求应带 response_format
            assert mock_server.last_request["response_format"] == {"type": "json_object"}
        finally:
            client.close()

    def test_ollama_uses_openai_protocol(self, mock_server):
        cfg = LLMConfig(provider="ollama", model="qwen2.5",
                        base_url=f"http://127.0.0.1:{mock_server.port}/v1")
        client = create_llm_client(cfg)
        assert isinstance(client, OpenAICompatClient)
        client.close()

    def test_json_extraction_from_code_fence(self):
        """容忍 ```json 代码块包裹。"""
        client = OpenAICompatClient(LLMConfig(provider="openai", model="m"))
        assert client._extract_json(
            '```json\n{"a": 1}\n```') == {"a": 1}
        assert client._extract_json('{"a": 1}') == {"a": 1}
        assert client._extract_json('前文 {"a": 1} 后文') == {"a": 1}
        with pytest.raises(LLMError):
            client._extract_json("不是 JSON")

    def test_http_error_raises_llm_error(self):
        # 无服务器监听 → 连接失败 → LLMError
        cfg = LLMConfig(provider="openai", model="m",
                        base_url="http://127.0.0.1:1/v1", timeout=2)
        client = OpenAICompatClient(cfg)
        try:
            with pytest.raises(LLMError):
                client.complete("hi")
        finally:
            client.close()


class TestAnthropic:
    def test_complete(self, mock_server):
        cfg = LLMConfig(
            provider="anthropic", model="claude-3-5-sonnet",
            api_key="sk-ant-test",
            base_url=f"http://127.0.0.1:{mock_server.port}/v1",
        )
        client = create_llm_client(cfg)
        try:
            resp = client.complete("你好")
            assert resp == "你好，我是模型"
            req = mock_server.last_request
            assert req["model"] == "claude-3-5-sonnet"
            assert req["messages"][0]["role"] == "user"
            assert req["max_tokens"] == 2048
        finally:
            client.close()

    def test_complete_with_system(self, mock_server):
        cfg = LLMConfig(provider="anthropic", model="m",
                        base_url=f"http://127.0.0.1:{mock_server.port}/v1")
        client = AnthropicClient(cfg)
        try:
            client.complete("q", system="你是助手")
            assert mock_server.last_request["system"] == "你是助手"
        finally:
            client.close()

    def test_complete_json(self, mock_server):
        mock_server.anthropic_response = {
            "content": [{"type": "text", "text": '{"ok": true}'}]
        }
        cfg = LLMConfig(provider="anthropic", model="m",
                        base_url=f"http://127.0.0.1:{mock_server.port}/v1")
        client = AnthropicClient(cfg)
        try:
            result = client.complete_json("分析")
            assert result == {"ok": True}
        finally:
            client.close()


class TestMultimodal:
    """多模态消息（image_url / input_audio）测试，mock 服务器验证请求格式。"""

    def test_complete_image(self, mock_server, tmp_path):
        mock_server.openai_response = {
            "choices": [{"message": {"content": "图片内容：日落海滩"}}]
        }
        cfg = LLMConfig(provider="mimo", model="mimo-v2.5", api_key="sk-mimo",
                        base_url=f"http://127.0.0.1:{mock_server.port}/v1")
        client = create_llm_client(cfg)
        try:
            img = tmp_path / "test.jpg"
            img.write_bytes(b"\xff\xd8\xff\xe0 fake jpeg bytes")
            resp = client.complete_image(str(img), "描述这张图片")
            assert resp == "图片内容：日落海滩"

            # 验证请求格式：content 为多模态数组
            content = mock_server.last_request["messages"][-1]["content"]
            assert isinstance(content, list)
            assert content[0]["type"] == "image_url"
            assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
            assert content[-1] == {"type": "text", "text": "描述这张图片"}
        finally:
            client.close()

    def test_complete_audio(self, mock_server, tmp_path):
        mock_server.openai_response = {
            "choices": [{"message": {"content": "转写结果：今天天气不错"}}]
        }
        cfg = LLMConfig(provider="mimo", model="mimo-v2.5", api_key="sk-mimo",
                        base_url=f"http://127.0.0.1:{mock_server.port}/v1")
        client = create_llm_client(cfg)
        try:
            wav = tmp_path / "clip.wav"
            wav.write_bytes(b"RIFF fake wav")
            resp = client.complete_audio(str(wav), "请转写这段语音")
            assert resp == "转写结果：今天天气不错"

            content = mock_server.last_request["messages"][-1]["content"]
            assert isinstance(content, list)
            assert content[0]["type"] == "input_audio"
            assert content[0]["input_audio"]["format"] == "wav"
            assert content[0]["input_audio"]["data"]
        finally:
            client.close()

    def test_complete_image_missing_file(self, mock_server, tmp_path):
        cfg = LLMConfig(provider="mimo", model="mimo-v2.5",
                        base_url=f"http://127.0.0.1:{mock_server.port}/v1")
        client = create_llm_client(cfg)
        try:
            with pytest.raises(LLMError):
                client.complete_image(str(tmp_path / "nope.jpg"), "描述")
        finally:
            client.close()


class TestFactory:
    def test_create_clients(self):
        assert isinstance(
            create_llm_client(LLMConfig(provider="openai")), OpenAICompatClient)
        assert isinstance(
            create_llm_client(LLMConfig(provider="ollama")), OpenAICompatClient)
        assert isinstance(
            create_llm_client(LLMConfig(provider="anthropic")), AnthropicClient)

    def test_unsupported_provider(self):
        with pytest.raises(ValueError):
            create_llm_client(LLMConfig(provider="unknown"))

    def test_config_defaults(self):
        cfg = LLMConfig.from_dict({})
        assert cfg.provider == "openai"
        assert cfg.base_url == "https://api.openai.com/v1"

        cfg = LLMConfig.from_dict({"provider": "ollama"})
        assert cfg.base_url == "http://localhost:11434/v1"

        cfg = LLMConfig.from_dict({"provider": "anthropic"})
        assert cfg.base_url == "https://api.anthropic.com/v1"
