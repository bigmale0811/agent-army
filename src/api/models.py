"""Pydantic 訊息模型定義"""

import time
from typing import Dict, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

# 合法的押注類型（與 config.py PAYOUTS 保持一致）
VALID_BET_TYPES = frozenset({
    "banker",
    "player",
    "tie",
    "banker_pair",
    "player_pair",
    "golden_three",
    "treasure_six",
})


# === Client → Server ===

class PlayerJoinPayload(BaseModel):
    player_id: str
    nickname: str = "Player"


class PlaceBetPayload(BaseModel):
    bets: Dict[str, int]  # 下注金額為整數（單位：元）

    @field_validator("bets")
    @classmethod
    def validate_bets(cls, bets: Dict[str, int]) -> Dict[str, int]:
        """驗證所有押注：金額不得為負數，且押注類型必須合法（空字典表示清除押注）"""
        for bet_type, amount in bets.items():
            # 驗證押注類型是否在合法清單內
            if bet_type not in VALID_BET_TYPES:
                raise ValueError(f"無效的押注區: {bet_type}")
            # 驗證押注金額不得為負數
            if amount < 0:
                raise ValueError(f"下注金額不能為負數: {bet_type}={amount}")
        return bets


class ClientMessage(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))


# === Server → Client ===

class PlayerInitPayload(BaseModel):
    player_id: str
    balance: int  # 餘額為整數（單位：元）
    min_bet: int
    max_bet: int


class StateChangePayload(BaseModel):
    state: str
    countdown: Optional[int] = None


class CardDealtPayload(BaseModel):
    target: Literal["player", "banker"]
    card: dict
    hand_value: int
    card_index: int


class GameResultPayload(BaseModel):
    winner: str
    player_total: int
    banker_total: int
    player_pair: bool
    banker_pair: bool
    player_cards: list
    banker_cards: list


class SettleResultPayload(BaseModel):
    bets: dict
    net_change: int   # 本局淨損益（整數，單位：元）
    new_balance: int  # 結算後餘額（整數，單位：元）


class ErrorPayload(BaseModel):
    code: str
    message: str


def make_message(msg_type: str, payload: dict) -> dict:
    """建立標準 WebSocket 訊息"""
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": int(time.time() * 1000),
    }
