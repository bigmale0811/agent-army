"""百家樂引擎測試 - 涵蓋完整補牌規則表"""

import random
import pytest
from src.game.card import Card, Suit, Rank
from src.game.shoe import Shoe
from src.game.hand import Hand
from src.game.baccarat_engine import BaccaratEngine, RoundResult


def make_card(rank: Rank) -> Card:
    return Card(Suit.HEARTS, rank)


def make_hand(*ranks: Rank) -> Hand:
    hand = Hand()
    for r in ranks:
        hand.add(make_card(r))
    return hand


class TestPlayerDraw:
    """閒家補牌規則：0-5 補，6-7 不補"""

    @pytest.mark.parametrize("total,should_draw", [
        (0, True),
        (1, True),
        (2, True),
        (3, True),
        (4, True),
        (5, True),
        (6, False),
        (7, False),
    ])
    def test_player_draw_rules(self, total: int, should_draw: bool):
        # 用兩張牌組合出目標點數
        rank_map = {
            0: (Rank.TEN, Rank.KING),
            1: (Rank.ACE, Rank.TEN),
            2: (Rank.TWO, Rank.TEN),
            3: (Rank.THREE, Rank.TEN),
            4: (Rank.FOUR, Rank.TEN),
            5: (Rank.FIVE, Rank.TEN),
            6: (Rank.SIX, Rank.TEN),
            7: (Rank.SEVEN, Rank.TEN),
        }
        r1, r2 = rank_map[total]
        hand = make_hand(r1, r2)
        assert BaccaratEngine.should_player_draw(hand) == should_draw


class TestBankerDrawWithoutPlayerThird:
    """莊家補牌規則（閒家未補牌）：0-5 補，6-7 不補"""

    @pytest.mark.parametrize("total,should_draw", [
        (0, True),
        (1, True),
        (2, True),
        (3, True),
        (4, True),
        (5, True),
        (6, False),
        (7, False),
    ])
    def test_banker_draw_no_player_third(self, total: int, should_draw: bool):
        rank_map = {
            0: (Rank.TEN, Rank.KING),
            1: (Rank.ACE, Rank.TEN),
            2: (Rank.TWO, Rank.TEN),
            3: (Rank.THREE, Rank.TEN),
            4: (Rank.FOUR, Rank.TEN),
            5: (Rank.FIVE, Rank.TEN),
            6: (Rank.SIX, Rank.TEN),
            7: (Rank.SEVEN, Rank.TEN),
        }
        r1, r2 = rank_map[total]
        hand = make_hand(r1, r2)
        assert BaccaratEngine.should_banker_draw(hand, None) == should_draw


class TestBankerDrawWithPlayerThird:
    """莊家補牌規則（閒家已補牌）- 完整規則表"""

    # 莊家 0-2 點：永遠補牌
    @pytest.mark.parametrize("banker_total", [0, 1, 2])
    @pytest.mark.parametrize("p3_value", range(10))
    def test_banker_0_to_2_always_draws(self, banker_total: int, p3_value: int):
        rank_map = {
            0: (Rank.TEN, Rank.KING),
            1: (Rank.ACE, Rank.TEN),
            2: (Rank.TWO, Rank.TEN),
        }
        r1, r2 = rank_map[banker_total]
        hand = make_hand(r1, r2)
        # p3 用對應的 rank
        p3_rank_map = {
            0: Rank.TEN, 1: Rank.ACE, 2: Rank.TWO, 3: Rank.THREE,
            4: Rank.FOUR, 5: Rank.FIVE, 6: Rank.SIX, 7: Rank.SEVEN,
            8: Rank.EIGHT, 9: Rank.NINE,
        }
        p3 = make_card(p3_rank_map[p3_value])
        assert BaccaratEngine.should_banker_draw(hand, p3) is True

    # 莊家 3 點：閒家第三張非 8 時補牌
    @pytest.mark.parametrize("p3_value,should_draw", [
        (0, True), (1, True), (2, True), (3, True), (4, True),
        (5, True), (6, True), (7, True), (8, False), (9, True),
    ])
    def test_banker_3(self, p3_value: int, should_draw: bool):
        hand = make_hand(Rank.THREE, Rank.TEN)
        p3_rank_map = {
            0: Rank.TEN, 1: Rank.ACE, 2: Rank.TWO, 3: Rank.THREE,
            4: Rank.FOUR, 5: Rank.FIVE, 6: Rank.SIX, 7: Rank.SEVEN,
            8: Rank.EIGHT, 9: Rank.NINE,
        }
        p3 = make_card(p3_rank_map[p3_value])
        assert BaccaratEngine.should_banker_draw(hand, p3) == should_draw

    # 莊家 4 點：閒家第三張為 2-7 時補牌
    @pytest.mark.parametrize("p3_value,should_draw", [
        (0, False), (1, False), (2, True), (3, True), (4, True),
        (5, True), (6, True), (7, True), (8, False), (9, False),
    ])
    def test_banker_4(self, p3_value: int, should_draw: bool):
        hand = make_hand(Rank.FOUR, Rank.TEN)
        p3_rank_map = {
            0: Rank.TEN, 1: Rank.ACE, 2: Rank.TWO, 3: Rank.THREE,
            4: Rank.FOUR, 5: Rank.FIVE, 6: Rank.SIX, 7: Rank.SEVEN,
            8: Rank.EIGHT, 9: Rank.NINE,
        }
        p3 = make_card(p3_rank_map[p3_value])
        assert BaccaratEngine.should_banker_draw(hand, p3) == should_draw

    # 莊家 5 點：閒家第三張為 4-7 時補牌
    @pytest.mark.parametrize("p3_value,should_draw", [
        (0, False), (1, False), (2, False), (3, False), (4, True),
        (5, True), (6, True), (7, True), (8, False), (9, False),
    ])
    def test_banker_5(self, p3_value: int, should_draw: bool):
        hand = make_hand(Rank.FIVE, Rank.TEN)
        p3_rank_map = {
            0: Rank.TEN, 1: Rank.ACE, 2: Rank.TWO, 3: Rank.THREE,
            4: Rank.FOUR, 5: Rank.FIVE, 6: Rank.SIX, 7: Rank.SEVEN,
            8: Rank.EIGHT, 9: Rank.NINE,
        }
        p3 = make_card(p3_rank_map[p3_value])
        assert BaccaratEngine.should_banker_draw(hand, p3) == should_draw

    # 莊家 6 點：閒家第三張為 6-7 時補牌
    @pytest.mark.parametrize("p3_value,should_draw", [
        (0, False), (1, False), (2, False), (3, False), (4, False),
        (5, False), (6, True), (7, True), (8, False), (9, False),
    ])
    def test_banker_6(self, p3_value: int, should_draw: bool):
        hand = make_hand(Rank.SIX, Rank.TEN)
        p3_rank_map = {
            0: Rank.TEN, 1: Rank.ACE, 2: Rank.TWO, 3: Rank.THREE,
            4: Rank.FOUR, 5: Rank.FIVE, 6: Rank.SIX, 7: Rank.SEVEN,
            8: Rank.EIGHT, 9: Rank.NINE,
        }
        p3 = make_card(p3_rank_map[p3_value])
        assert BaccaratEngine.should_banker_draw(hand, p3) == should_draw

    # 莊家 7 點：永遠不補
    @pytest.mark.parametrize("p3_value", range(10))
    def test_banker_7_never_draws(self, p3_value: int):
        hand = make_hand(Rank.SEVEN, Rank.TEN)
        p3_rank_map = {
            0: Rank.TEN, 1: Rank.ACE, 2: Rank.TWO, 3: Rank.THREE,
            4: Rank.FOUR, 5: Rank.FIVE, 6: Rank.SIX, 7: Rank.SEVEN,
            8: Rank.EIGHT, 9: Rank.NINE,
        }
        p3 = make_card(p3_rank_map[p3_value])
        assert BaccaratEngine.should_banker_draw(hand, p3) is False


class TestDetermineWinner:
    """勝負判定"""

    def test_player_wins(self):
        p = make_hand(Rank.NINE, Rank.TEN)   # 9
        b = make_hand(Rank.SEVEN, Rank.TEN)  # 7
        assert BaccaratEngine.determine_winner(p, b) == "player"

    def test_banker_wins(self):
        p = make_hand(Rank.THREE, Rank.TEN)  # 3
        b = make_hand(Rank.EIGHT, Rank.TEN)  # 8
        assert BaccaratEngine.determine_winner(p, b) == "banker"

    def test_tie(self):
        p = make_hand(Rank.FIVE, Rank.TEN)   # 5
        b = make_hand(Rank.FIVE, Rank.TEN)   # 5
        assert BaccaratEngine.determine_winner(p, b) == "tie"


class TestPlayRound:
    """完整一局測試"""

    def test_round_returns_result(self):
        shoe = Shoe(rng=random.Random(42))
        engine = BaccaratEngine(shoe)
        result = engine.play_round()
        assert isinstance(result, RoundResult)
        assert result.winner in ("player", "banker", "tie")
        assert result.player_hand.card_count >= 2
        assert result.banker_hand.card_count >= 2
        assert result.player_hand.card_count <= 3
        assert result.banker_hand.card_count <= 3

    def test_natural_no_draw(self):
        """天生贏家不補牌：任一方前兩張 8 或 9"""
        # 使用固定種子找到天生贏家的情境
        for seed in range(1000):
            shoe = Shoe(rng=random.Random(seed))
            engine = BaccaratEngine(shoe)
            result = engine.play_round()
            p_natural = result.player_hand.is_natural
            b_natural = result.banker_hand.is_natural
            if p_natural or b_natural:
                # 天生贏家時，雙方都不應補牌
                assert result.player_hand.card_count == 2
                assert result.banker_hand.card_count == 2
                break

    def test_result_to_dict(self):
        shoe = Shoe(rng=random.Random(42))
        engine = BaccaratEngine(shoe)
        result = engine.play_round()
        d = result.to_dict()
        assert "winner" in d
        assert "player_total" in d
        assert "banker_total" in d
        assert "player_pair" in d
        assert "banker_pair" in d
        assert "player_cards" in d
        assert "banker_cards" in d

    def test_multiple_rounds_deterministic(self):
        """相同種子應產生相同結果"""
        results1 = []
        results2 = []
        for i in range(10):
            shoe = Shoe(rng=random.Random(i))
            engine = BaccaratEngine(shoe)
            results1.append(engine.play_round().winner)

            shoe = Shoe(rng=random.Random(i))
            engine = BaccaratEngine(shoe)
            results2.append(engine.play_round().winner)

        assert results1 == results2
