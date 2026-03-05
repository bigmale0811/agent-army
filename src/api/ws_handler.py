"""WebSocket 訊息處理器 - 整合遊戲引擎與玩家 session"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import WebSocket
from pydantic import ValidationError

from .models import make_message, PlaceBetPayload
from .session import SessionManager, PlayerSession
from ..config import MIN_BET, MAX_BET, BETTING_COUNTDOWN
from ..game.shoe import Shoe
from ..game.baccarat_engine import BaccaratEngine, RoundResult
from ..game.bet_resolver import BetResolver
from ..game.state_machine import BaccaratStateMachine, GameState

logger = logging.getLogger(__name__)


class GameRoom:
    """一個遊戲房間，管理完整的遊戲流程"""

    def __init__(self) -> None:
        self.sessions = SessionManager()
        self.state_machine = BaccaratStateMachine(
            on_state_change=self._on_state_change,
        )
        self.shoe = Shoe()
        self.engine = BaccaratEngine(self.shoe)
        self.resolver = BetResolver()
        self._betting_task: Optional[asyncio.Task] = None
        self._game_running = False
        # 用於保護 _game_running 的讀寫與 _start_game_loop 啟動的互斥鎖
        self._lock = asyncio.Lock()

    async def connect(self, player_id: str, ws: WebSocket) -> None:
        """玩家連線"""
        await ws.accept()
        session = await self.sessions.add(player_id, ws)

        # 傳送初始化訊息
        await self.sessions.send_to(player_id, make_message("PLAYER_INIT", {
            "player_id": player_id,
            "balance": session.balance,
            "min_bet": MIN_BET,
            "max_bet": MAX_BET,
        }))

        # 傳送當前狀態
        await self.sessions.send_to(player_id, make_message("STATE_CHANGE", {
            "state": self.state_machine.state.value,
        }))

        # 用鎖保護 _game_running 的判斷與設置，避免玩家重連時的競爭條件
        async with self._lock:
            if not self._game_running:
                self._game_running = True
                asyncio.create_task(self._start_game_loop())

    async def disconnect(self, player_id: str) -> None:
        """玩家斷線"""
        await self.sessions.remove(player_id)
        # 用鎖保護 _game_running 的修改，避免與 connect() 的啟動邏輯產生競爭條件
        async with self._lock:
            if self.sessions.active_count == 0:
                self._game_running = False

    async def handle_message(self, player_id: str, raw: str) -> None:
        """處理收到的 WebSocket 訊息"""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(player_id, "INVALID_JSON", "無效的 JSON 格式")
            return

        msg_type = msg.get("type", "")
        payload = msg.get("payload", {})

        if msg_type == "PLACE_BET":
            await self._handle_bet(player_id, payload)
        elif msg_type == "BET_CONFIRMED":
            await self._handle_confirm(player_id)
        else:
            await self._send_error(player_id, "UNKNOWN_MESSAGE", f"未知訊息類型: {msg_type}")

    async def _handle_bet(self, player_id: str, payload: dict) -> None:
        """處理下注"""
        if self.state_machine.state != GameState.BETTING:
            await self._send_error(player_id, "NOT_BETTING", "目前不是下注階段")
            return

        session = self.sessions.get(player_id)
        if not session:
            return

        # 使用 Pydantic 進行格式驗證（押注類型合法性、金額不為負數）
        try:
            bet_payload = PlaceBetPayload(**payload)
        except ValidationError as exc:
            # 從 Pydantic 錯誤訊息判斷要回傳哪個錯誤碼
            first_msg = str(exc.errors()[0].get("msg", ""))
            if "無效的押注區" in first_msg:
                # 取出押注區名稱以便組成詳細訊息
                bet_type_hint = first_msg.split("無效的押注區:")[-1].strip() if ":" in first_msg else ""
                await self._send_error(
                    player_id,
                    "INVALID_BET_TYPE",
                    f"無效的押注區: {bet_type_hint}" if bet_type_hint else "無效的押注區",
                )
            else:
                await self._send_error(player_id, "INVALID_BET", "下注金額不能為負數")
            return

        bets = bet_payload.bets

        # 業務邏輯驗證：餘額與單注限額（非格式問題，不交給 Pydantic）
        total_bet = sum(bets.values())
        if total_bet > session.balance:
            await self._send_error(player_id, "INSUFFICIENT_BALANCE", "餘額不足")
            return

        for bet_type, amount in bets.items():
            if amount > 0 and amount < MIN_BET:
                await self._send_error(player_id, "BET_TOO_LOW", f"最低下注 {MIN_BET}")
                return
            if amount > MAX_BET:
                await self._send_error(player_id, "BET_TOO_HIGH", f"最高下注 {MAX_BET}")
                return

        session.current_bets = {k: v for k, v in bets.items() if v > 0}
        logger.info("玩家 %s 下注: %s", player_id, session.current_bets)

    async def _handle_confirm(self, player_id: str) -> None:
        """處理確認下注"""
        if self.state_machine.state != GameState.BETTING:
            await self._send_error(player_id, "NOT_BETTING", "目前不是下注階段")
            return

        session = self.sessions.get(player_id)
        if not session:
            return

        if not session.current_bets:
            await self._send_error(player_id, "NO_BETS", "請先下注")
            return

        session.bet_confirmed = True
        logger.info("玩家 %s 確認下注", player_id)

        # 回應確認 ACK，讓前端同步狀態
        await self.sessions.send_to(player_id, make_message("BET_CONFIRMED_ACK", {
            "total_bet": sum(session.current_bets.values()),
        }))

    async def _start_game_loop(self) -> None:
        """主遊戲循環"""
        logger.info("遊戲循環啟動")
        while self._game_running and self.sessions.active_count > 0:
            try:
                await self._play_one_round()
                # 結算後等待 5 秒再開始下一局（讓玩家看清結算動畫）
                await asyncio.sleep(5)
            except Exception as e:
                logger.exception("遊戲循環異常: %s", e)
                # 緊急重置狀態機，防止因中間狀態（如 DEALING）導致下一局
                # transition(BETTING) 觸發 InvalidTransition 錯誤
                self.state_machine.reset()
                await asyncio.sleep(1)

        # 用鎖保護旗標清除，確保與 connect() 的啟動判斷互斥
        async with self._lock:
            self._game_running = False
        # 遊戲循環正常結束：透過合法轉換回到 IDLE，讓前端收到最終狀態廣播
        # 若狀態機已在 IDLE（例如異常分支）則 reset_to_idle 會靜默跳過
        await self.state_machine.reset_to_idle()
        logger.info("遊戲循環結束")

    async def _play_one_round(self) -> None:
        """執行一局完整流程"""
        # 1. 下注階段
        await self.state_machine.transition(GameState.BETTING)
        self.sessions.reset_bets()

        # 等待下注（倒數計時）
        for remaining in range(BETTING_COUNTDOWN, 0, -1):
            await self.sessions.broadcast(make_message("STATE_CHANGE", {
                "state": "BETTING",
                "countdown": remaining,
            }))
            await asyncio.sleep(1)
            if self.sessions.active_count == 0:
                return

        # 2. 發牌階段
        await self.state_machine.transition(GameState.DEALING)

        # 執行發牌
        result = self.engine.play_round()

        # 逐張發牌動畫訊息
        await self._send_dealing_sequence(result)

        # 3. 補牌階段（engine.play_round 已計算補牌結果，這裡只更新狀態機並播放動畫）
        #    合法轉換路徑：
        #      DEALING → PLAYER_DRAW（閒補）→ BANKER_DRAW（莊補）→ RESULT
        #      DEALING → PLAYER_DRAW（閒補）→ RESULT（莊不補）
        #      DEALING → RESULT（雙方均不補，天生贏家）
        #    注意：狀態機不允許 DEALING → BANKER_DRAW，莊家補牌前必須先經過 PLAYER_DRAW
        if result.player_hand.card_count > 2:
            # 閒家有補牌
            await self.state_machine.transition(GameState.PLAYER_DRAW)
            await asyncio.sleep(1.0)

        if result.banker_hand.card_count > 2:
            # 莊家有補牌：若閒家未補則需先走 PLAYER_DRAW 再走 BANKER_DRAW
            if self.state_machine.state == GameState.DEALING:
                await self.state_machine.transition(GameState.PLAYER_DRAW)
            await self.state_machine.transition(GameState.BANKER_DRAW)
            await asyncio.sleep(1.0)

        # 4. 結果階段（無論目前在 DEALING / PLAYER_DRAW / BANKER_DRAW 均可轉到 RESULT）
        await self.state_machine.transition(GameState.RESULT)

        await self.sessions.broadcast(make_message("GAME_RESULT", result.to_dict()))
        await asyncio.sleep(3)

        # 5. 結算階段：RESULT → SETTLE
        await self.state_machine.transition(GameState.SETTLE)

        for session in self.sessions.all_sessions:
            if session.current_bets:
                settle = self.resolver.settle(
                    bets=session.current_bets,
                    result=result,
                    current_balance=session.balance,
                )
                session.balance = settle.new_balance

                await self.sessions.send_to(session.player_id, make_message("SETTLE_RESULT", {
                    "bets": {
                        k: {"amount": v.amount, "won": v.won, "payout": v.payout}
                        for k, v in settle.details.items()
                    },
                    "net_change": settle.net_change,
                    "new_balance": settle.new_balance,
                }))

        # 6. 結算完畢：SETTLE → IDLE，讓前端收到明確的 IDLE 狀態廣播
        #    下一局由 _start_game_loop 呼叫 _play_one_round，重新從 IDLE → BETTING 開始
        #    不再在此處呼叫 transition(BETTING) 後立刻 reset()，避免前後端狀態不同步
        await self.state_machine.transition(GameState.IDLE)

    async def _send_dealing_sequence(self, result: RoundResult) -> None:
        """逐張發送發牌動畫訊息"""
        p_cards = result.player_hand.cards
        b_cards = result.banker_hand.cards

        # 前兩張：閒1, 莊1
        await self._send_card("player", p_cards[0], 0, p_cards[0].baccarat_value)
        await asyncio.sleep(0.8)
        await self._send_card("banker", b_cards[0], 0, b_cards[0].baccarat_value)
        await asyncio.sleep(0.8)

        # 閒2, 莊2
        hand_val_p = (p_cards[0].baccarat_value + p_cards[1].baccarat_value) % 10
        await self._send_card("player", p_cards[1], 1, hand_val_p)
        await asyncio.sleep(0.8)
        hand_val_b = (b_cards[0].baccarat_value + b_cards[1].baccarat_value) % 10
        await self._send_card("banker", b_cards[1], 1, hand_val_b)
        await asyncio.sleep(1.0)

        # 閒家第三張（補牌前多停頓一下）
        if len(p_cards) > 2:
            await self._send_card("player", p_cards[2], 2, result.player_hand.total)
            await asyncio.sleep(1.0)

        # 莊家第三張
        if len(b_cards) > 2:
            await self._send_card("banker", b_cards[2], 2, result.banker_hand.total)
            await asyncio.sleep(1.0)

    async def _send_card(self, target: str, card, index: int, hand_value: int) -> None:
        """發送單張牌的訊息"""
        await self.sessions.broadcast(make_message("CARD_DEALT", {
            "target": target,
            "card": card.to_dict(),
            "hand_value": hand_value,
            "card_index": index,
        }))

    async def _send_error(self, player_id: str, code: str, message: str) -> None:
        """傳送錯誤訊息"""
        await self.sessions.send_to(player_id, make_message("ERROR", {
            "code": code,
            "message": message,
        }))

    async def _on_state_change(self, new_state: GameState) -> None:
        """狀態變更時廣播"""
        await self.sessions.broadcast(make_message("STATE_CHANGE", {
            "state": new_state.value,
        }))
