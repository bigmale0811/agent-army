"""玩家 session 管理"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from fastapi import WebSocket

from ..config import INITIAL_BALANCE

logger = logging.getLogger(__name__)


@dataclass
class PlayerSession:
    """單一玩家的 session"""
    player_id: str
    websocket: WebSocket
    nickname: str = "Player"
    balance: int = INITIAL_BALANCE        # 餘額為整數（單位：元）
    current_bets: Dict[str, int] = field(default_factory=dict)  # 下注金額為整數
    bet_confirmed: bool = False


class SessionManager:
    """管理所有玩家 session"""

    def __init__(self) -> None:
        self._sessions: Dict[str, PlayerSession] = {}

    async def add(self, player_id: str, ws: WebSocket, nickname: str = "Player") -> PlayerSession:
        """新增或重連玩家 session

        若 player_id 已存在（重連情境），保留原有餘額，只更新 WebSocket 連線。
        避免每次重連都重置餘額的安全問題。
        """
        if player_id in self._sessions:
            # 重連：保留餘額與下注狀態，只替換 WebSocket
            old_session = self._sessions[player_id]
            old_session.websocket = ws
            logger.info("玩家 %s 重連，餘額保留: %d", player_id, old_session.balance)
            return old_session

        # 新玩家：建立全新 session
        session = PlayerSession(
            player_id=player_id,
            websocket=ws,
            nickname=nickname,
        )
        self._sessions[player_id] = session
        logger.info("玩家 %s (%s) 已加入", player_id, nickname)
        return session

    async def remove(self, player_id: str) -> None:
        """移除玩家 session"""
        if player_id in self._sessions:
            del self._sessions[player_id]
            logger.info("玩家 %s 已離開", player_id)

    def get(self, player_id: str) -> Optional[PlayerSession]:
        """取得玩家 session"""
        return self._sessions.get(player_id)

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    @property
    def all_sessions(self) -> list[PlayerSession]:
        return list(self._sessions.values())

    async def send_to(self, player_id: str, message: dict) -> None:
        """傳送訊息給指定玩家"""
        session = self._sessions.get(player_id)
        if session:
            try:
                await session.websocket.send_json(message)
            except Exception as e:
                logger.error("傳送訊息給 %s 失敗: %s", player_id, e)
                await self.remove(player_id)

    async def broadcast(self, message: dict) -> None:
        """廣播訊息給所有玩家"""
        disconnected = []
        for pid, session in self._sessions.items():
            try:
                await session.websocket.send_json(message)
            except Exception:
                disconnected.append(pid)
        for pid in disconnected:
            await self.remove(pid)

    def reset_bets(self) -> None:
        """重置所有玩家的下注"""
        for session in self._sessions.values():
            session.current_bets = {}
            session.bet_confirmed = False
