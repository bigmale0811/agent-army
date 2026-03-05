"""遊戲狀態機測試"""

import pytest
import asyncio
from src.game.state_machine import BaccaratStateMachine, GameState, InvalidTransition


@pytest.fixture
def sm():
    return BaccaratStateMachine()


class TestBaccaratStateMachine:

    @pytest.mark.asyncio
    async def test_initial_state(self, sm):
        assert sm.state == GameState.IDLE

    @pytest.mark.asyncio
    async def test_valid_transition_idle_to_betting(self, sm):
        await sm.transition(GameState.BETTING)
        assert sm.state == GameState.BETTING

    @pytest.mark.asyncio
    async def test_valid_full_flow(self, sm):
        """完整遊戲流程"""
        await sm.transition(GameState.BETTING)
        await sm.transition(GameState.DEALING)
        await sm.transition(GameState.PLAYER_DRAW)
        await sm.transition(GameState.BANKER_DRAW)
        await sm.transition(GameState.RESULT)
        await sm.transition(GameState.SETTLE)
        assert sm.state == GameState.SETTLE

    @pytest.mark.asyncio
    async def test_dealing_can_skip_to_result(self, sm):
        """天生贏家直接跳到結果"""
        await sm.transition(GameState.BETTING)
        await sm.transition(GameState.DEALING)
        await sm.transition(GameState.RESULT)
        assert sm.state == GameState.RESULT

    @pytest.mark.asyncio
    async def test_player_draw_can_skip_banker(self, sm):
        """閒家補牌後可直接到結果（莊家不補）"""
        await sm.transition(GameState.BETTING)
        await sm.transition(GameState.DEALING)
        await sm.transition(GameState.PLAYER_DRAW)
        await sm.transition(GameState.RESULT)
        assert sm.state == GameState.RESULT

    @pytest.mark.asyncio
    async def test_invalid_transition(self, sm):
        """無效的狀態轉換"""
        with pytest.raises(InvalidTransition):
            await sm.transition(GameState.DEALING)  # IDLE 不能直接到 DEALING

    @pytest.mark.asyncio
    async def test_invalid_backwards(self, sm):
        """不能倒退"""
        await sm.transition(GameState.BETTING)
        with pytest.raises(InvalidTransition):
            await sm.transition(GameState.IDLE)

    @pytest.mark.asyncio
    async def test_settle_to_betting(self, sm):
        """結算後可以開始新一局"""
        await sm.transition(GameState.BETTING)
        await sm.transition(GameState.DEALING)
        await sm.transition(GameState.RESULT)
        await sm.transition(GameState.SETTLE)
        await sm.transition(GameState.BETTING)
        assert sm.state == GameState.BETTING

    @pytest.mark.asyncio
    async def test_callback_called(self):
        """狀態變更回呼被觸發"""
        states = []

        async def callback(state: GameState):
            states.append(state)

        sm = BaccaratStateMachine(on_state_change=callback)
        await sm.transition(GameState.BETTING)
        await sm.transition(GameState.DEALING)
        assert states == [GameState.BETTING, GameState.DEALING]

    def test_reset(self, sm):
        sm.reset()
        assert sm.state == GameState.IDLE
