"""WebSocket 分析器 — 攔截並解析遊戲 WS 訊息（支援 Socket.IO 格式）"""
from __future__ import annotations
import json
import logging
import re
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

    def _extract_search_target(self, parsed: dict) -> dict[str, Any] | None:
        """從 parsed 訊息中提取實際搜尋目標（支援 Socket.IO 格式）"""
        if not isinstance(parsed, dict):
            return None
        msg_type = parsed.get("type", "")
        # Socket.IO EVENT: 搜尋 data 欄位
        if msg_type in ("socketio_event", "socketio_data"):
            data = parsed.get("data")
            return data if isinstance(data, dict) else None
        # 一般 JSON: 直接搜尋
        if msg_type not in ("binary", "text", "socketio_control"):
            return parsed
        return None

    def find_game_config(self) -> dict[str, Any] | None:
        """從已收集的 WS 訊息中搜尋遊戲配置

        搜尋策略：找包含 paytable/symbol/reel 等關鍵字的訊息
        支援 Socket.IO 格式：自動解析 42["event",{data}] 結構
        """
        config_keywords = {
            "paytable", "symbol", "reel", "payline", "scatter",
            "wild", "bonus", "multiplier", "freespin", "bet",
        }

        for msg in self._messages:
            parsed = msg.get("parsed")
            target = self._extract_search_target(parsed)
            if target is None:
                continue

            text = json.dumps(target, default=str).lower()
            matches = sum(1 for kw in config_keywords if kw in text)
            if matches >= 3:
                event_name = parsed.get("event", "") if isinstance(parsed, dict) else ""
                logger.info(
                    "找到疑似遊戲配置（匹配 %d 個關鍵字, event=%s）",
                    matches, event_name,
                )
                return target

        return None

    def find_spin_results(self) -> list[dict[str, Any]]:
        """從 WS 訊息中搜尋 spin 結果"""
        results = []
        spin_keywords = {"result", "win", "grid", "board", "symbol", "payout", "spin", "cascade"}

        for msg in self._messages:
            parsed = msg.get("parsed")
            target = self._extract_search_target(parsed)
            if target is None:
                continue

            text = json.dumps(target, default=str).lower()
            matches = sum(1 for kw in spin_keywords if kw in text)
            if matches >= 2:
                results.append(target)

        logger.info("找到 %d 則疑似 spin 結果", len(results))
        return results

    def get_all_events(self) -> list[dict[str, Any]]:
        """取得所有 Socket.IO 事件名稱和摘要（用於除錯分析）"""
        events = []
        for msg in self._messages:
            parsed = msg.get("parsed")
            if isinstance(parsed, dict) and parsed.get("type") == "socketio_event":
                events.append({
                    "event": parsed.get("event"),
                    "direction": msg.get("direction"),
                    "has_data": parsed.get("data") is not None,
                    "data_keys": list(parsed["data"].keys()) if isinstance(parsed.get("data"), dict) else [],
                })
        return events

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
        """嘗試解析訊息為 JSON（支援 Socket.IO 格式）

        Socket.IO 訊息格式：
        - '0'           → CONNECT
        - '2'           → PING
        - '3'           → PONG
        - '40'          → namespace CONNECT
        - '42["event",{...}]' → EVENT（主要解析目標）
        - '43[id,{...}]'      → ACK
        """
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                return {"type": "binary", "size": len(data)}

        # 嘗試直接 JSON 解析（排除純數字，因為可能是 Socket.IO 控制碼）
        if not re.match(r"^\d{1,3}$", data.strip()) and not re.match(r"^\d{1,3}\[", data.strip()):
            try:
                return json.loads(data)
            except (json.JSONDecodeError, ValueError):
                pass

        # Socket.IO 格式：數字前綴 + JSON payload
        match = re.match(r"^(\d{1,3})(.*)", data, re.DOTALL)
        if match:
            prefix = match.group(1)
            payload = match.group(2).strip()
            if payload:
                try:
                    parsed = json.loads(payload)
                    # Socket.IO EVENT 格式: 42["event_name", {data}]
                    if isinstance(parsed, list) and len(parsed) >= 1:
                        return {
                            "type": "socketio_event",
                            "prefix": prefix,
                            "event": str(parsed[0]) if parsed else None,
                            "data": parsed[1] if len(parsed) > 1 else None,
                        }
                    return {
                        "type": "socketio_data",
                        "prefix": prefix,
                        "data": parsed,
                    }
                except (json.JSONDecodeError, ValueError):
                    pass
            # 控制訊息（PING/PONG/CONNECT）
            return {"type": "socketio_control", "prefix": prefix}

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
