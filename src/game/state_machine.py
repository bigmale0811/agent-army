"""百家樂遊戲狀態機"""

import asyncio
import logging
from enum import Enum, auto
from typing import Callable, Awaitable, Optional

logger = logging.getLogger(__name__)


class GameState(Enum):
    """遊戲狀態"""
    IDLE = "IDLE"
    BETTING = "BETTING"
    DEALING = "DEALING"
    PLAYER_DRAW = "PLAYER_DRAW"
    BANKER_DRAW = "BANKER_DRAW"
    RESULT = "RESULT"
    SETTLE = "SETTLE"


# 合法的狀態轉換
_VALID_TRANSITIONS = {
    GameState.IDLE: {GameState.BETTING},
    GameState.BETTING: {GameState.DEALING},
    GameState.DEALING: {GameState.PLAYER_DRAW, GameState.RESULT},
    GameState.PLAYER_DRAW: {GameState.BANKER_DRAW, GameState.RESULT},
    GameState.BANKER_DRAW: {GameState.RESULT},
    GameState.RESULT: {GameState.SETTLE},
    GameState.SETTLE: {GameState.BETTING, GameState.IDLE},
}


class InvalidTransition(Exception):
    """無效的狀態轉換"""
    pass


class BaccaratStateMachine:
    """百家樂遊戲狀態機"""

    def __init__(
        self,
        on_state_change: Optional[Callable[[GameState], Awaitable[None]]] = None,
    ) -> None:
        self._state = GameState.IDLE
        self._on_state_change = on_state_change

    @property
    def state(self) -> GameState:
        return self._state

    async def transition(self, new_state: GameState) -> None:
        """轉換到新狀態"""
        valid_next = _VALID_TRANSITIONS.get(self._state, set())
        if new_state not in valid_next:
            raise InvalidTransition(
                f"無法從 {self._state.value} 轉換到 {new_state.value}"
            )

        old_state = self._state
        self._state = new_state
        logger.info("狀態轉換: %s → %s", old_state.value, new_state.value)

        if self._on_state_change:
            await self._on_state_change(new_state)

    async def reset_to_idle(self) -> None:
        """透過正常狀態轉換回到 IDLE（僅限 SETTLE 狀態下呼叫）

        保留舊的 reset() 只供緊急情況（如遊戲循環異常退出）使用。
        正常流程請使用 transition(IDLE) 或此方法。
        """
        if self._state == GameState.SETTLE:
            await self.transition(GameState.IDLE)
        elif self._state != GameState.IDLE:
            # 非正常路徑：直接靜默重置，避免觸發廣播
            logger.warning("強制重置狀態: %s → IDLE", self._state.value)
            self._state = GameState.IDLE

    def reset(self) -> None:
        """緊急重置為初始狀態（不觸發回呼，不廣播）

        警告：此方法會靜默跳過狀態機廣播，僅於遊戲循環異常終止時使用。
        正常局間過渡請使用 transition(GameState.IDLE)。
        """
        self._state = GameState.IDLE
