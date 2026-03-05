"""Shoe 牌靴模組測試"""

import random
import pytest
from src.game.shoe import Shoe, ShoeEmpty
from src.game.card import Card


class TestShoe:
    """牌靴測試"""

    def test_initial_card_count(self):
        """8 副牌 = 416 張，扣除燒牌後應少於 416"""
        shoe = Shoe(decks=8, rng=random.Random(42))
        assert shoe.remaining < 416
        assert shoe.remaining > 400  # 燒牌最多 10 張 + 1

    def test_single_deck(self):
        """單副牌 52 張"""
        shoe = Shoe(decks=1, rng=random.Random(42))
        assert shoe.remaining < 52

    def test_deal_returns_card(self):
        shoe = Shoe(rng=random.Random(42))
        card = shoe.deal()
        assert isinstance(card, Card)

    def test_deal_decreases_remaining(self):
        shoe = Shoe(rng=random.Random(42))
        before = shoe.remaining
        shoe.deal()
        assert shoe.remaining == before - 1

    def test_deterministic_with_seed(self):
        """相同種子應產生相同序列"""
        shoe1 = Shoe(rng=random.Random(123))
        shoe2 = Shoe(rng=random.Random(123))
        for _ in range(10):
            c1 = shoe1.deal()
            c2 = shoe2.deal()
            assert c1 == c2

    def test_shuffle_resets_cards(self):
        shoe = Shoe(rng=random.Random(42))
        # 發一些牌
        for _ in range(50):
            shoe.deal()
        before_shuffle = shoe.remaining
        shoe.shuffle()
        assert shoe.remaining > before_shuffle

    def test_auto_reshuffle_on_low_cards(self):
        """剩餘牌數低於門檻時自動重新洗牌"""
        shoe = Shoe(decks=1, rng=random.Random(42))
        # 發到接近空為止，應觸發自動重洗而非拋出異常
        for _ in range(100):
            shoe.deal()  # 單副牌 52 張，發 100 次會觸發至少一次重洗
        assert shoe.remaining > 0

    def test_all_suits_and_ranks_present(self):
        """完整牌靴應包含所有花色和點數"""
        shoe = Shoe(decks=1, rng=random.Random(42))
        # 收集所有牌（不觸發自動重洗，手動收集）
        shoe._cards  # 直接檢查內部
        suits = {c.suit for c in shoe._cards}
        ranks = {c.rank for c in shoe._cards}
        from src.game.card import Suit, Rank
        # 燒牌可能移除某些牌，但花色和點數種類應該都在
        assert len(suits) == 4
        assert len(ranks) == 13
