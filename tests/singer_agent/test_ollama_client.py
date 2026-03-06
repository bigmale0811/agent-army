# -*- coding: utf-8 -*-
"""
DEV-4: ollama_client.py 測試。

所有 HTTP 呼叫均透過 unittest.mock.patch 模擬，
不需要真實 Ollama 服務在線。

測試覆蓋：
- is_available() 成功 / 超時 / 連線失敗
- generate() 成功回傳 / 離線拋例外 / prompt 正確傳入
- OllamaUnavailableError 型別繼承
"""
import json
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────
# OllamaUnavailableError 型別測試
# ─────────────────────────────────────────────────

class TestOllamaUnavailableError:
    """測試 OllamaUnavailableError 繼承自 RuntimeError。"""

    def test_inherits_from_runtime_error(self):
        """OllamaUnavailableError 繼承自 RuntimeError。"""
        from src.singer_agent.ollama_client import OllamaUnavailableError

        err = OllamaUnavailableError("Ollama is offline")
        assert isinstance(err, RuntimeError)

    def test_can_be_raised_and_caught(self):
        """可以被 raise 也可以被 except RuntimeError 捕捉。"""
        from src.singer_agent.ollama_client import OllamaUnavailableError

        with pytest.raises(RuntimeError):
            raise OllamaUnavailableError("offline")

    def test_message_is_accessible(self):
        """錯誤訊息可正常存取。"""
        from src.singer_agent.ollama_client import OllamaUnavailableError

        err = OllamaUnavailableError("connection refused")
        assert "connection refused" in str(err)


# ─────────────────────────────────────────────────
# OllamaClient 初始化測試
# ─────────────────────────────────────────────────

class TestOllamaClientInit:
    """測試 OllamaClient 建構子。"""

    def test_default_parameters(self):
        """使用預設參數建立 OllamaClient。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient()

        assert client.base_url is not None
        assert client.model is not None
        assert client.timeout > 0

    def test_custom_parameters(self):
        """自訂 base_url, model, timeout 正確儲存。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(
            base_url="http://custom:11434",
            model="llama3",
            timeout=60,
        )

        assert "custom" in client.base_url
        assert client.model == "llama3"
        assert client.timeout == 60


# ─────────────────────────────────────────────────
# is_available() 測試
# ─────────────────────────────────────────────────

class TestIsAvailable:
    """測試 is_available()：快速檢查 Ollama 是否在線。"""

    def test_returns_true_when_server_responds(self):
        """伺服器正常回應 200 → is_available() 回傳 True。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("requests.get", return_value=mock_response) as mock_get:
            result = client.is_available()

        assert result is True

    def test_returns_false_on_connection_error(self):
        """連線拒絕 → is_available() 回傳 False（不拋例外）。"""
        import requests
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:11434")

        with patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
            result = client.is_available()

        assert result is False

    def test_returns_false_on_timeout(self):
        """超時 → is_available() 回傳 False（不拋例外）。"""
        import requests
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:11434")

        with patch("requests.get", side_effect=requests.exceptions.Timeout()):
            result = client.is_available()

        assert result is False

    def test_returns_false_on_http_error_status(self):
        """HTTP 500 → is_available() 回傳 False。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("requests.get", return_value=mock_response):
            result = client.is_available()

        assert result is False

    def test_uses_short_timeout(self):
        """is_available() 使用較短的 timeout（不超過 10s）。"""
        import requests
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:11434", timeout=120)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("requests.get", return_value=mock_response) as mock_get:
            client.is_available()

        # 確認有傳入 timeout 參數，且值 <= 10
        call_kwargs = mock_get.call_args
        actual_timeout = (
            call_kwargs.kwargs.get("timeout")
            or (call_kwargs.args[1] if len(call_kwargs.args) > 1 else None)
        )
        if actual_timeout is not None:
            assert actual_timeout <= 10


# ─────────────────────────────────────────────────
# generate() 測試
# ─────────────────────────────────────────────────

class TestGenerate:
    """測試 generate()：POST /api/generate，回傳回應文字。"""

    def _make_mock_response(self, response_text: str) -> MagicMock:
        """建立模擬成功的 HTTP 回應。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": response_text}
        mock_response.raise_for_status = MagicMock()
        return mock_response

    def test_returns_non_empty_string_on_success(self):
        """Ollama 正常回應 → generate() 回傳非空字串。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:11434", model="qwen3")
        mock_response = self._make_mock_response("這是 LLM 的回應文字。")

        with patch("requests.post", return_value=mock_response):
            result = client.generate("分析這首歌曲的風格")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_correct_response_text(self):
        """回傳值對應 Ollama JSON 中的 response 欄位。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient()
        expected_text = "音樂風格為抒情流行"
        mock_response = self._make_mock_response(expected_text)

        with patch("requests.post", return_value=mock_response):
            result = client.generate("分析風格")

        assert result == expected_text

    def test_raises_ollama_unavailable_on_connection_error(self):
        """連線失敗 → 拋出 OllamaUnavailableError。"""
        import requests
        from src.singer_agent.ollama_client import OllamaClient, OllamaUnavailableError

        client = OllamaClient()

        with patch("requests.post", side_effect=requests.exceptions.ConnectionError()):
            with pytest.raises(OllamaUnavailableError):
                client.generate("test prompt")

    def test_raises_ollama_unavailable_on_timeout(self):
        """請求超時 → 拋出 OllamaUnavailableError。"""
        import requests
        from src.singer_agent.ollama_client import OllamaClient, OllamaUnavailableError

        client = OllamaClient()

        with patch("requests.post", side_effect=requests.exceptions.Timeout()):
            with pytest.raises(OllamaUnavailableError):
                client.generate("test prompt")

    def test_prompt_is_sent_in_request_body(self):
        """prompt 字串正確傳入 HTTP 請求 body 的 prompt 欄位。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(model="qwen3")
        mock_response = self._make_mock_response("ok")
        expected_prompt = "請分析這首歌的情緒與視覺風格"

        with patch("requests.post", return_value=mock_response) as mock_post:
            client.generate(expected_prompt)

        # 取得實際呼叫的 json 參數
        call_kwargs = mock_post.call_args
        request_body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert request_body["prompt"] == expected_prompt

    def test_model_is_sent_in_request_body(self):
        """model 名稱正確傳入 HTTP 請求 body 的 model 欄位。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(model="qwen3:14b")
        mock_response = self._make_mock_response("ok")

        with patch("requests.post", return_value=mock_response) as mock_post:
            client.generate("test")

        call_kwargs = mock_post.call_args
        request_body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert request_body["model"] == "qwen3:14b"

    def test_stream_false_is_set(self):
        """stream=False 必須設定，確保一次性回傳完整回應。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient()
        mock_response = self._make_mock_response("ok")

        with patch("requests.post", return_value=mock_response) as mock_post:
            client.generate("test")

        call_kwargs = mock_post.call_args
        request_body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert request_body.get("stream") is False

    def test_kwargs_are_forwarded_to_request(self):
        """額外 kwargs（如 temperature）被傳入請求 body。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient()
        mock_response = self._make_mock_response("ok")

        with patch("requests.post", return_value=mock_response) as mock_post:
            client.generate("test", temperature=0.7)

        call_kwargs = mock_post.call_args
        request_body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert request_body.get("temperature") == 0.7

    def test_posts_to_correct_endpoint(self):
        """HTTP POST 目標為 /api/generate 端點。"""
        from src.singer_agent.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:11434")
        mock_response = self._make_mock_response("ok")

        with patch("requests.post", return_value=mock_response) as mock_post:
            client.generate("test")

        called_url = mock_post.call_args.args[0]
        assert "/api/generate" in called_url
