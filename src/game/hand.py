"""百家樂手牌類別"""

from typing import List

from .card import Card


class Hand:
    """一手百家樂牌"""

    def __init__(self) -> None:
        self.cards: List[Card] = []

    def add(self, card: Card) -> None:
        """加入一張牌"""
        self.cards.append(card)

    @property
    def total(self) -> int:
        """百家樂點數（所有牌面值總和 mod 10）"""
        return sum(c.baccarat_value for c in self.cards) % 10

    @property
    def is_natural(self) -> bool:
        """天生贏家：前兩張牌合計 8 或 9"""
        if len(self.cards) < 2:
            return False
        first_two = (self.cards[0].baccarat_value + self.cards[1].baccarat_value) % 10
        return first_two >= 8

    @property
    def is_pair(self) -> bool:
        """對子：前兩張牌同 rank"""
        if len(self.cards) < 2:
            return False
        return self.cards[0].rank == self.cards[1].rank

    @property
    def card_count(self) -> int:
        return len(self.cards)

    def to_dict_list(self) -> list[dict]:
        """序列化所有牌"""
        return [c.to_dict() for c in self.cards]

    def __str__(self) -> str:
        cards_str = ", ".join(str(c) for c in self.cards)
        return f"[{cards_str}] = {self.total}"
