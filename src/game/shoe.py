"""8 副牌靴管理：洗牌、發牌、燒牌"""

import random
import logging
from typing import List

from .card import Card, Suit, Rank
from ..config import SHOE_DECKS, RESHUFFLE_THRESHOLD

logger = logging.getLogger(__name__)


class ShoeEmpty(Exception):
    """牌靴已空"""
    pass


class Shoe:
    """8 副牌靴"""

    def __init__(self, decks: int = SHOE_DECKS, rng: random.Random | None = None):
        self.decks = decks
        self._rng = rng or random.Random()
        self._cards: List[Card] = []
        self._dealt_count = 0
        self.shuffle()

    def shuffle(self) -> None:
        """建立完整牌靴並洗牌，執行燒牌程序"""
        self._cards = [
            Card(suit, rank)
            for _ in range(self.decks)
            for suit in Suit
            for rank in Rank
        ]
        self._rng.shuffle(self._cards)
        self._dealt_count = 0

        # 燒牌：翻開第一張，依其點數燒掉對應數量的牌
        burn_card = self._cards.pop(0)
        burn_count = burn_card.baccarat_value if burn_card.baccarat_value > 0 else 10
        for _ in range(min(burn_count, len(self._cards))):
            self._cards.pop(0)
        self._dealt_count = 1 + burn_count

        logger.info(
            "牌靴洗牌完成，燒牌 %d 張（燒牌面: %s），剩餘 %d 張",
            burn_count, burn_card, len(self._cards),
        )

    def deal(self) -> Card:
        """發一張牌，若剩餘牌數過低則自動重新洗牌"""
        if not self._cards:
            raise ShoeEmpty("牌靴已空")

        total = self.decks * 52
        if len(self._cards) / total < RESHUFFLE_THRESHOLD:
            logger.info("剩餘牌數低於 %.0f%%，自動重新洗牌", RESHUFFLE_THRESHOLD * 100)
            self.shuffle()

        card = self._cards.pop(0)
        self._dealt_count += 1
        return card

    @property
    def remaining(self) -> int:
        """剩餘牌數"""
        return len(self._cards)

    @property
    def total_cards(self) -> int:
        """總牌數（含已發出）"""
        return self.decks * 52
