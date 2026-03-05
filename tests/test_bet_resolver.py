"""下注結算測試"""

import pytest
from src.game.card import Card, Suit, Rank
from src.game.hand import Hand
from src.game.baccarat_engine import RoundResult
from src.game.bet_resolver import BetResolver


def make_result(
    winner: str = "banker",
    player_pair: bool = False,
    banker_pair: bool = False,
) -> RoundResult:
    """建立測試用的 RoundResult"""
    p_hand = Hand()
    b_hand = Hand()
    # 填入假牌（測試結算不需要真實牌面）
    p_hand.add(Card(Suit.HEARTS, Rank.THREE))
    p_hand.add(Card(Suit.HEARTS, Rank.FOUR if not player_pair else Rank.THREE))
    b_hand.add(Card(Suit.CLUBS, Rank.FIVE))
    b_hand.add(Card(Suit.CLUBS, Rank.SIX if not banker_pair else Rank.FIVE))
    return RoundResult(
        player_hand=p_hand,
        banker_hand=b_hand,
        winner=winner,
        player_pair=player_pair,
        banker_pair=banker_pair,
    )


class TestBetResolver:
    """下注結算器測試"""

    def setup_method(self):
        self.resolver = BetResolver()

    # === 莊贏 ===
    def test_banker_bet_wins(self):
        """押莊，莊贏：賠率 1:0.95（100 元賠 95 元，int 取整）"""
        result = make_result(winner="banker")
        settle = self.resolver.settle(
            bets={"banker": 100},
            result=result,
            current_balance=10000,
        )
        assert settle.details["banker"].won is True
        assert settle.details["banker"].payout == 95
        assert settle.net_change == 95
        assert settle.new_balance == 10095

    def test_player_bet_loses_when_banker_wins(self):
        """押閒，莊贏：輸掉全部"""
        result = make_result(winner="banker")
        settle = self.resolver.settle(
            bets={"player": 200},
            result=result,
            current_balance=10000,
        )
        assert settle.details["player"].won is False
        assert settle.details["player"].payout == -200
        assert settle.net_change == -200

    # === 閒贏 ===
    def test_player_bet_wins(self):
        """押閒，閒贏：賠率 1:1"""
        result = make_result(winner="player")
        settle = self.resolver.settle(
            bets={"player": 100},
            result=result,
            current_balance=10000,
        )
        assert settle.details["player"].won is True
        assert settle.details["player"].payout == 100
        assert settle.new_balance == 10100

    # === 和 ===
    def test_tie_bet_wins(self):
        """押和，和局：賠率 1:8"""
        result = make_result(winner="tie")
        settle = self.resolver.settle(
            bets={"tie": 50},
            result=result,
            current_balance=10000,
        )
        assert settle.details["tie"].won is True
        assert settle.details["tie"].payout == 400

    def test_tie_refunds_banker_and_player_bets(self):
        """和局時，莊/閒注退回（不輸不贏）"""
        result = make_result(winner="tie")
        settle = self.resolver.settle(
            bets={"banker": 100, "player": 200},
            result=result,
            current_balance=10000,
        )
        # 莊/閒注退回
        assert settle.details["banker"].payout == 0
        assert settle.details["player"].payout == 0

    # === 對子 ===
    def test_banker_pair_wins(self):
        """押莊對，莊家出對子：賠率 1:11"""
        result = make_result(winner="banker", banker_pair=True)
        settle = self.resolver.settle(
            bets={"banker_pair": 50},
            result=result,
            current_balance=10000,
        )
        assert settle.details["banker_pair"].won is True
        assert settle.details["banker_pair"].payout == 550

    def test_player_pair_wins(self):
        """押閒對，閒家出對子：賠率 1:11"""
        result = make_result(winner="player", player_pair=True)
        settle = self.resolver.settle(
            bets={"player_pair": 50},
            result=result,
            current_balance=10000,
        )
        assert settle.details["player_pair"].won is True
        assert settle.details["player_pair"].payout == 550

    def test_pair_bet_loses(self):
        """押對子但沒出對子"""
        result = make_result(winner="banker", banker_pair=False)
        settle = self.resolver.settle(
            bets={"banker_pair": 50},
            result=result,
            current_balance=10000,
        )
        assert settle.details["banker_pair"].won is False
        assert settle.details["banker_pair"].payout == -50

    # === 複合下注 ===
    def test_multiple_bets(self):
        """同時押多個區域"""
        result = make_result(winner="banker", banker_pair=True, player_pair=False)
        settle = self.resolver.settle(
            bets={"banker": 100, "banker_pair": 50, "player_pair": 30},
            result=result,
            current_balance=10000,
        )
        # 莊贏 +95，莊對贏 +550，閒對輸 -30（全為整數，不需要 approx）
        expected_net = 95 + 550 - 30
        assert settle.net_change == expected_net

    def test_zero_bets_ignored(self):
        """金額為 0 的下注會被忽略"""
        result = make_result(winner="banker")
        settle = self.resolver.settle(
            bets={"banker": 100, "player": 0},
            result=result,
            current_balance=10000,
        )
        assert "player" not in settle.details

    # === 和局退款與複合下注 net_change / new_balance ===

    def test_banker_and_tie_bet_on_tie_result(self):
        """
        同時押莊和押和，結果和局：
        - 莊注退回（net_change 莊 = 0）
        - 和贏 50 * 8 = 400
        - 總 net_change = 400，new_balance = 10400
        """
        result = make_result(winner="tie")
        settle = self.resolver.settle(
            bets={"banker": 100, "tie": 50},
            result=result,
            current_balance=10000,
        )
        # 莊注退回，淨損益為 0
        assert settle.details["banker"].payout == 0
        # 和局贏 int(50 * 8) = 400
        assert settle.details["tie"].payout == 400
        # 總 net_change = 0 + 400 = 400
        assert settle.net_change == 400
        # new_balance = 10000 + 400 = 10400
        assert settle.new_balance == 10400

    def test_player_and_banker_pair_player_wins_with_banker_pair(self):
        """
        同時押閒和莊對，結果閒贏且出莊對：
        - 閒贏 int(200 * 1.0) = 200
        - 莊對贏 int(30 * 11) = 330
        - 總 net_change = 530，new_balance = 10530
        """
        result = make_result(winner="player", banker_pair=True)
        settle = self.resolver.settle(
            bets={"player": 200, "banker_pair": 30},
            result=result,
            current_balance=10000,
        )
        assert settle.details["player"].won is True
        assert settle.details["player"].payout == 200
        assert settle.details["banker_pair"].won is True
        assert settle.details["banker_pair"].payout == 330
        assert settle.net_change == 530
        assert settle.new_balance == 10530

    def test_banker_player_tie_bet_banker_wins_no_pair(self):
        """
        同時押莊、閒、和，結果莊贏無對子：
        - 莊贏 int(100 * 0.95) = 95
        - 閒輸 -200
        - 和輸 -50
        - 總 net_change = 95 - 200 - 50 = -155
        """
        result = make_result(winner="banker")
        settle = self.resolver.settle(
            bets={"banker": 100, "player": 200, "tie": 50},
            result=result,
            current_balance=10000,
        )
        assert settle.details["banker"].payout == 95
        assert settle.details["player"].payout == -200
        assert settle.details["tie"].payout == -50
        assert settle.net_change == -155

    def test_all_settle_values_are_int(self):
        """
        驗證所有結算值（payout、net_change、new_balance）均為 int 而非 float：
        使用莊 0.95 賠率確認 int 轉型有效
        """
        result = make_result(winner="banker", banker_pair=True)
        settle = self.resolver.settle(
            bets={"banker": 100, "banker_pair": 30, "player": 50},
            result=result,
            current_balance=10000,
        )
        assert isinstance(settle.net_change, int)
        assert isinstance(settle.new_balance, int)
        for detail in settle.details.values():
            assert isinstance(detail.payout, int)

    # === 金三條/聚寶六（規則待定，退回本金）===
    def test_golden_three_placeholder(self):
        """金三條規則待定：不贏，但退回本金（payout=0，net_change=0）"""
        result = make_result(winner="banker")
        settle = self.resolver.settle(
            bets={"golden_three": 50},
            result=result,
            current_balance=10000,
        )
        assert settle.details["golden_three"].won is False
        # 規則待定期間退回本金，不扣錢
        assert settle.details["golden_three"].payout == 0
        assert settle.net_change == 0
        assert settle.new_balance == 10000

    def test_treasure_six_placeholder(self):
        """聚寶六規則待定：不贏，但退回本金（payout=0，net_change=0）"""
        result = make_result(winner="banker")
        settle = self.resolver.settle(
            bets={"treasure_six": 50},
            result=result,
            current_balance=10000,
        )
        assert settle.details["treasure_six"].won is False
        # 規則待定期間退回本金，不扣錢
        assert settle.details["treasure_six"].payout == 0
        assert settle.net_change == 0
        assert settle.new_balance == 10000
