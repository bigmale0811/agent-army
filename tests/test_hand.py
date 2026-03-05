"""Hand 手牌模組測試"""

import pytest
from src.game.hand import Hand
from src.game.card import Card, Suit, Rank


def make_card(rank: Rank, suit: Suit = Suit.HEARTS) -> Card:
    return Card(suit, rank)


class TestHand:
    """手牌測試"""

    def test_empty_hand_total(self):
        hand = Hand()
        assert hand.total == 0

    def test_single_card(self):
        hand = Hand()
        hand.add(make_card(Rank.SEVEN))
        assert hand.total == 7

    def test_two_cards_no_mod(self):
        """兩張牌合計小於 10"""
        hand = Hand()
        hand.add(make_card(Rank.THREE))
        hand.add(make_card(Rank.FOUR))
        assert hand.total == 7

    def test_two_cards_with_mod(self):
        """兩張牌合計超過 10，取個位數"""
        hand = Hand()
        hand.add(make_card(Rank.SEVEN))
        hand.add(make_card(Rank.EIGHT))
        assert hand.total == 5  # (7+8) % 10 = 5

    def test_three_cards(self):
        hand = Hand()
        hand.add(make_card(Rank.FOUR))
        hand.add(make_card(Rank.SIX))
        hand.add(make_card(Rank.NINE))
        assert hand.total == 9  # (4+6+9) % 10 = 9

    def test_face_cards_are_zero(self):
        """T/J/Q/K 點數為 0"""
        hand = Hand()
        hand.add(make_card(Rank.KING))
        hand.add(make_card(Rank.QUEEN))
        assert hand.total == 0

    def test_natural_eight(self):
        hand = Hand()
        hand.add(make_card(Rank.THREE))
        hand.add(make_card(Rank.FIVE))
        assert hand.is_natural  # 3+5=8

    def test_natural_nine(self):
        hand = Hand()
        hand.add(make_card(Rank.FOUR))
        hand.add(make_card(Rank.FIVE))
        assert hand.is_natural  # 4+5=9

    def test_not_natural(self):
        hand = Hand()
        hand.add(make_card(Rank.THREE))
        hand.add(make_card(Rank.FOUR))
        assert not hand.is_natural  # 3+4=7

    def test_natural_only_checks_first_two(self):
        """天生贏家只看前兩張"""
        hand = Hand()
        hand.add(make_card(Rank.TWO))
        hand.add(make_card(Rank.THREE))  # 2+3=5，非天生
        hand.add(make_card(Rank.SIX))    # 加上第三張 = 1，但不算天生
        assert not hand.is_natural

    def test_pair_same_rank(self):
        hand = Hand()
        hand.add(Card(Suit.HEARTS, Rank.SEVEN))
        hand.add(Card(Suit.CLUBS, Rank.SEVEN))
        assert hand.is_pair

    def test_not_pair_different_rank(self):
        hand = Hand()
        hand.add(make_card(Rank.SEVEN))
        hand.add(make_card(Rank.EIGHT))
        assert not hand.is_pair

    def test_card_count(self):
        hand = Hand()
        assert hand.card_count == 0
        hand.add(make_card(Rank.ACE))
        assert hand.card_count == 1
        hand.add(make_card(Rank.TWO))
        assert hand.card_count == 2

    def test_to_dict_list(self):
        hand = Hand()
        hand.add(Card(Suit.SPADES, Rank.ACE))
        result = hand.to_dict_list()
        assert result == [{"suit": "spades", "rank": "A", "value": 1}]
