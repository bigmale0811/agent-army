"""Card 模組測試"""

import pytest
from src.game.card import Card, Suit, Rank


class TestCard:
    """Card 資料類別測試"""

    @pytest.mark.parametrize("rank,expected", [
        (Rank.ACE, 1),
        (Rank.TWO, 2),
        (Rank.THREE, 3),
        (Rank.FOUR, 4),
        (Rank.FIVE, 5),
        (Rank.SIX, 6),
        (Rank.SEVEN, 7),
        (Rank.EIGHT, 8),
        (Rank.NINE, 9),
        (Rank.TEN, 0),
        (Rank.JACK, 0),
        (Rank.QUEEN, 0),
        (Rank.KING, 0),
    ])
    def test_baccarat_value(self, rank: Rank, expected: int):
        """百家樂點數：A=1, 2-9=面值, T/J/Q/K=0"""
        card = Card(Suit.HEARTS, rank)
        assert card.baccarat_value == expected

    def test_to_dict(self):
        card = Card(Suit.SPADES, Rank.SEVEN)
        d = card.to_dict()
        assert d == {"suit": "spades", "rank": "7", "value": 7}

    def test_frozen(self):
        """Card 應為不可變"""
        card = Card(Suit.HEARTS, Rank.ACE)
        with pytest.raises(AttributeError):
            card.suit = Suit.CLUBS

    def test_str(self):
        card = Card(Suit.DIAMONDS, Rank.KING)
        assert str(card) == "KD"
