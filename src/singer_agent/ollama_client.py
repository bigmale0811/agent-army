# -*- coding: utf-8 -*-
"""
DEV-4: Ollama HTTP 客戶端。

封裝 Ollama REST API，提供：
- is_available()：快速檢查服務是否在線
- generate()：POST /api/generate，回傳 LLM 回應文字

所有 HTTP 呼叫使用 requests 套件，超時與連線錯誤
統一轉換為 OllamaUnavailableError。
"""
import logging

import requests

from src.singer_agent import config

_logger = logging.getLogger(__name__)


class OllamaUnavailableError(RuntimeError):
    """Ollama 服務無法連線時拋出的例外。繼承自 RuntimeError。"""


class OllamaClient:
    """
    Ollama REST API 客戶端。

    Args:
        base_url: Ollama 服務 URL，預設從 config.OLLAMA_URL 讀取
        model: 模型名稱，預設 "qwen3:14b"
        timeout: HTTP 請求超時秒數，預設 120
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str = "qwen3:14b",
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url or config.OLLAMA_URL
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        """
        快速檢查 Ollama 服務是否在線。

        使用較短的 timeout（最多 10 秒），
        連線失敗或 HTTP 非 200 均回傳 False，不拋例外。
        """
        # 健康檢查使用短 timeout，不超過 10 秒
        check_timeout = min(self.timeout, 10)
        try:
            resp = requests.get(self.base_url, timeout=check_timeout)
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def generate(self, prompt: str, **kwargs) -> str:
        """
        呼叫 Ollama /api/generate API，回傳 LLM 回應文字。

        Args:
            prompt: 提示詞
            **kwargs: 額外參數（如 temperature），會傳入請求 body

        Returns:
            LLM 回應文字

        Raises:
            OllamaUnavailableError: 連線失敗或超時
        """
        url = f"{self.base_url}/api/generate"
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            **kwargs,
        }
        try:
            resp = requests.post(url, json=body, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()["response"]
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            raise OllamaUnavailableError(
                f"Ollama 服務無法連線 ({self.base_url}): {e}"
            ) from e
        except requests.exceptions.HTTPError as e:
            raise OllamaUnavailableError(
                f"Ollama 回傳 HTTP 錯誤: {e}"
            ) from e
        except (ValueError, KeyError) as e:
            # JSON 解碼失敗或回應中缺少 "response" 欄位
            raise OllamaUnavailableError(
                f"Ollama 回應格式無效: {e}"
            ) from e
