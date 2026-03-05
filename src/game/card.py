"""撲克牌資料類別定義"""

from enum import Enum
from dataclasses import dataclass


class Suit(Enum):
    """花色"""
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"
    SPADES = "spades"


class Rank(Enum):
    """點數"""
    ACE = "A"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "T"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"


# 百家樂點數對照表
_BACCARAT_VALUES = {
    Rank.ACE: 1,
    Rank.TWO: 2,
    Rank.THREE: 3,
    Rank.FOUR: 4,
    Rank.FIVE: 5,
    Rank.SIX: 6,
    Rank.SEVEN: 7,
    Rank.EIGHT: 8,
    Rank.NINE: 9,
    Rank.TEN: 0,
    Rank.JACK: 0,
    Rank.QUEEN: 0,
    Rank.KING: 0,
}


@dataclass(frozen=True)
class Card:
    """一張撲克牌"""
    suit: Suit
    rank: Rank

    @property
    def baccarat_value(self) -> int:
        """百家樂點數：A=1, 2-9=面值, T/J/Q/K=0"""
        return _BACCARAT_VALUES[self.rank]

    def to_dict(self) -> dict:
        """序列化為字典，供 WebSocket 傳送"""
        return {
            "suit": self.suit.value,
            "rank": self.rank.value,
            "value": self.baccarat_value,
        }

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value[0].upper()}"
