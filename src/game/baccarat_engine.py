"""百家樂核心引擎：發牌流程與補牌規則"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from .card import Card
from .shoe import Shoe
from .hand import Hand

logger = logging.getLogger(__name__)


@dataclass
class RoundResult:
    """一局的完整結果"""
    player_hand: Hand
    banker_hand: Hand
    winner: str  # "player" | "banker" | "tie"
    player_pair: bool
    banker_pair: bool
    player_third: Optional[Card] = None
    banker_third: Optional[Card] = None

    def to_dict(self) -> dict:
        return {
            "winner": self.winner,
            "player_total": self.player_hand.total,
            "banker_total": self.banker_hand.total,
            "player_pair": self.player_pair,
            "banker_pair": self.banker_pair,
            "player_cards": self.player_hand.to_dict_list(),
            "banker_cards": self.banker_hand.to_dict_list(),
        }


class BaccaratEngine:
    """百家樂發牌引擎"""

    def __init__(self, shoe: Shoe) -> None:
        self.shoe = shoe

    def play_round(self) -> RoundResult:
        """執行一局完整的百家樂"""
        player_hand = Hand()
        banker_hand = Hand()

        # 發初始 4 張牌：閒1, 莊1, 閒2, 莊2
        player_hand.add(self.shoe.deal())
        banker_hand.add(self.shoe.deal())
        player_hand.add(self.shoe.deal())
        banker_hand.add(self.shoe.deal())

        logger.info("初始發牌 - 閒: %s, 莊: %s", player_hand, banker_hand)

        player_third: Optional[Card] = None
        banker_third: Optional[Card] = None

        # 天生贏家檢查：任一方 8 或 9 點則不補牌
        if not player_hand.is_natural and not banker_hand.is_natural:
            # 閒家補牌判斷
            if self.should_player_draw(player_hand):
                player_third = self.shoe.deal()
                player_hand.add(player_third)
                logger.info("閒家補牌: %s → %s", player_third, player_hand)

            # 莊家補牌判斷
            if self.should_banker_draw(banker_hand, player_third):
                banker_third = self.shoe.deal()
                banker_hand.add(banker_third)
                logger.info("莊家補牌: %s → %s", banker_third, banker_hand)

        # 決定勝負
        winner = self.determine_winner(player_hand, banker_hand)
        logger.info("結果: %s 勝 (閒 %d vs 莊 %d)", winner, player_hand.total, banker_hand.total)

        return RoundResult(
            player_hand=player_hand,
            banker_hand=banker_hand,
            winner=winner,
            player_pair=player_hand.is_pair,
            banker_pair=banker_hand.is_pair,
            player_third=player_third,
            banker_third=banker_third,
        )

    @staticmethod
    def should_player_draw(player_hand: Hand) -> bool:
        """閒家補牌規則：0-5 補牌，6-7 不補"""
        return player_hand.total <= 5

    @staticmethod
    def should_banker_draw(banker_hand: Hand, player_third: Optional[Card]) -> bool:
        """
        莊家補牌規則：
        - 若閒家未補牌：莊家 0-5 補牌，6-7 不補
        - 若閒家已補牌：根據完整補牌規則表判斷
        """
        banker_total = banker_hand.total

        # 莊家 0-2：永遠補牌
        if banker_total <= 2:
            return True

        # 莊家 7：永遠不補
        if banker_total == 7:
            return False

        # 閒家未補牌：莊家 3-5 補，6 不補
        if player_third is None:
            return banker_total <= 5

        # 閒家已補牌：依據閒家第三張牌的點數決定
        p3 = player_third.baccarat_value

        if banker_total == 3:
            # 閒家第三張非 8 時補牌
            return p3 != 8
        elif banker_total == 4:
            # 閒家第三張為 2-7 時補牌
            return 2 <= p3 <= 7
        elif banker_total == 5:
            # 閒家第三張為 4-7 時補牌
            return 4 <= p3 <= 7
        elif banker_total == 6:
            # 閒家第三張為 6-7 時補牌
            return 6 <= p3 <= 7

        return False

    @staticmethod
    def determine_winner(player_hand: Hand, banker_hand: Hand) -> str:
        """決定勝負"""
        if player_hand.total > banker_hand.total:
            return "player"
        elif banker_hand.total > player_hand.total:
            return "banker"
        else:
            return "tie"
