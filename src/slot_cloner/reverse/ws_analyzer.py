"""WebSocket 分析器 — 攔截並解析遊戲 WS 訊息"""
from __future__ import annotations
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class WSAnalyzer:
    """WebSocket 訊息分析器

    解析攔截到的 WS 訊息，提取遊戲配置和 spin 結果。
    Layer 2 逆向策略的核心。
    """

    # 安全限制
    MAX_MESSAGES = 500
    MAX_RAW_BYTES = 64 * 1024  # 64 KB per message

    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []

    def add_message(self, data: str | bytes, direction: str = "received") -> None:
        """添加一則 WS 訊息（含數量和大小限制）"""
        if len(self._messages) >= self.MAX_MESSAGES:
            return
        raw = data if isinstance(data, str) else data.hex()
        if len(raw) > self.MAX_RAW_BYTES * 2:
            raw = raw[: self.MAX_RAW_BYTES * 2] + "...[truncated]"
        parsed = self._try_parse(data)
        self._messages.append({
            "direction": direction,
            "raw": raw,
            "parsed": parsed,
        })

    def find_game_config(self) -> dict[str, Any] | None:
        """從已收集的 WS 訊息中搜尋遊戲配置

        搜尋策略：找包含 paytable/symbol/reel 等關鍵字的訊息
        """
        config_keywords = {"paytable", "symbol", "reel", "payline", "scatter", "wild", "bonus", "multiplier"}

        for msg in self._messages:
            parsed = msg.get("parsed")
            if not isinstance(parsed, dict):
                continue

            # 遞迴搜尋關鍵字
            text = json.dumps(parsed, default=str).lower()
            matches = sum(1 for kw in config_keywords if kw in text)
            if matches >= 3:
                logger.info("找到疑似遊戲配置（匹配 %d 個關鍵字）", matches)
                return parsed

        return None

    def find_spin_results(self) -> list[dict[str, Any]]:
        """從 WS 訊息中搜尋 spin 結果"""
        results = []
        spin_keywords = {"result", "win", "grid", "board", "symbol", "payout"}

        for msg in self._messages:
            parsed = msg.get("parsed")
            if not isinstance(parsed, dict):
                continue

            text = json.dumps(parsed, default=str).lower()
            matches = sum(1 for kw in spin_keywords if kw in text)
            if matches >= 2:
                results.append(parsed)

        logger.info("找到 %d 則疑似 spin 結果", len(results))
        return results

    def extract_symbols(self) -> list[dict[str, Any]]:
        """從 WS 訊息提取符號定義"""
        config = self.find_game_config()
        if not config:
            return []

        # 搜尋 symbols 相關的巢狀結構
        return self._deep_find(config, "symbol")

    @property
    def messages(self) -> list[dict[str, Any]]:
        """已收集的所有 WS 訊息"""
        return list(self._messages)

    @staticmethod
    def _try_parse(data: str | bytes) -> Any:
        """嘗試解析訊息為 JSON"""
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                return {"type": "binary", "size": len(data)}

        try:
            return json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return {"type": "text", "content": data[:500]}

    @staticmethod
    def _deep_find(obj: Any, key: str, _depth: int = 0, max_depth: int = 20) -> list[Any]:
        """遞迴搜尋包含指定 key 的值（含深度限制防止 stack overflow）"""
        if _depth > max_depth:
            return []
        results = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if key.lower() in k.lower():
                    results.append(v)
                results.extend(WSAnalyzer._deep_find(v, key, _depth + 1, max_depth))
        elif isinstance(obj, list):
            for item in obj:
                results.extend(WSAnalyzer._deep_find(item, key, _depth + 1, max_depth))
        return results
