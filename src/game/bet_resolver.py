"""下注結算邏輯"""

from dataclasses import dataclass, field
from typing import Dict

from ..config import PAYOUTS
from .baccarat_engine import RoundResult


@dataclass
class BetDetail:
    """單一押注的結算明細"""
    amount: int       # 押注金額（整數，單位：元）
    won: bool
    payout: int       # 淨贏金額（不含本金，整數）


@dataclass
class SettleResult:
    """完整結算結果"""
    details: Dict[str, BetDetail]
    net_change: int   # 本局淨損益（整數）
    new_balance: int  # 結算後餘額（整數）


class BetResolver:
    """下注結算器"""

    def settle(
        self,
        bets: Dict[str, int],
        result: RoundResult,
        current_balance: int,
    ) -> SettleResult:
        """
        結算所有下注

        Args:
            bets: 各押注區的下注金額（整數）
            result: 本局結果
            current_balance: 當前餘額（整數）

        Returns:
            完整的結算結果
        """
        details: Dict[str, BetDetail] = {}
        net_change = 0

        for bet_type, amount in bets.items():
            if amount <= 0:
                continue

            won = self._check_win(bet_type, result)

            if won:
                payout_rate = PAYOUTS.get(bet_type, 0.0)
                # 使用 int() 取整，避免浮點累積誤差
                # 莊家 0.95 賠率：100 元賠 95 元，小數點直接捨去
                payout = int(amount * payout_rate)
            elif bet_type in ("golden_three", "treasure_six"):
                # 規則待定，退回本金（不扣錢）
                payout = 0
            else:
                payout = -amount

            details[bet_type] = BetDetail(
                amount=amount,
                won=won,
                payout=payout,
            )
            net_change += payout

        # 和局時，莊/閒注退回（不輸不贏）
        if result.winner == "tie":
            for bet_type in ("banker", "player"):
                if bet_type in details:
                    # 先保存原始金額，讓意圖清晰：補回之前扣的本金
                    original_amount = details[bet_type].amount
                    net_change += original_amount  # 補回之前扣的
                    details[bet_type] = BetDetail(
                        amount=original_amount,
                        won=False,
                        payout=0,  # 退回本金，淨損益為 0
                    )

        return SettleResult(
            details=details,
            net_change=net_change,
            new_balance=current_balance + net_change,
        )

    @staticmethod
    def _check_win(bet_type: str, result: RoundResult) -> bool:
        """判斷指定押注是否獲勝"""
        if bet_type == "banker":
            return result.winner == "banker"
        elif bet_type == "player":
            return result.winner == "player"
        elif bet_type == "tie":
            return result.winner == "tie"
        elif bet_type == "banker_pair":
            return result.banker_pair
        elif bet_type == "player_pair":
            return result.player_pair
        elif bet_type == "golden_three":
            return False  # 規則待定
        elif bet_type == "treasure_six":
            return False  # 規則待定
        return False
