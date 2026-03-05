"""
端到端遊戲流程測試

分兩類：
1. 快速協定測試 - 驗證 WebSocket 訊息格式和錯誤處理（秒級完成）
2. 完整流程測試 - 需等待遊戲倒數（標記 slow，預設跳過）

QA Agent 執行方式：
    # 快速測試
    python -m pytest tests/test_e2e_game_flow.py -v

    # 包含完整流程（需約 30 秒）
    python -m pytest tests/test_e2e_game_flow.py -v --run-slow
"""

import time
import pytest
from fastapi.testclient import TestClient
from src.main import app, game_room
from src.game.state_machine import GameState


class TestProtocol:
    """快速協定測試 - 不依賴遊戲循環"""

    def setup_method(self):
        """每個測試開始前：鎖定遊戲循環，防止連線時啟動真實遊戲循環干擾訊息流"""
        game_room._game_running = True
        game_room.state_machine.reset()

    def teardown_method(self):
        """每個測試結束後：重置全域狀態，避免污染後續測試"""
        game_room.state_machine.reset()
        game_room._game_running = False

    def test_connect_receives_player_init(self):
        """連線後應收到 PLAYER_INIT"""
        client = TestClient(app)
        with client.websocket_connect("/ws/qa_proto_1") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "PLAYER_INIT"
            p = msg["payload"]
            assert p["player_id"] == "qa_proto_1"
            assert p["balance"] == 10000
            assert p["min_bet"] == 10
            assert p["max_bet"] == 5000
            assert "timestamp" in msg

    def test_connect_receives_state(self):
        """連線後應收到 STATE_CHANGE"""
        client = TestClient(app)
        with client.websocket_connect("/ws/qa_proto_2") as ws:
            ws.receive_json()  # PLAYER_INIT
            msg = ws.receive_json()
            assert msg["type"] == "STATE_CHANGE"
            assert "state" in msg["payload"]

    def test_invalid_json_returns_error(self):
        """無效 JSON 應回傳 ERROR（setup_method 已鎖定遊戲循環，不會有干擾訊息）"""
        client = TestClient(app)
        with client.websocket_connect("/ws/qa_proto_3") as ws:
            ws.receive_json()  # PLAYER_INIT
            ws.receive_json()  # STATE_CHANGE

            ws.send_text("not json at all")
            err = ws.receive_json()
            assert err["type"] == "ERROR"
            assert err["payload"]["code"] == "INVALID_JSON"

    def test_unknown_message_type(self):
        """未知訊息類型應回傳 ERROR"""
        client = TestClient(app)
        with client.websocket_connect("/ws/qa_proto_4") as ws:
            ws.receive_json()
            ws.receive_json()

            ws.send_json({"type": "FOOBAR", "payload": {}})
            err = ws.receive_json()
            assert err["type"] == "ERROR"
            assert err["payload"]["code"] == "UNKNOWN_MESSAGE"

    def test_message_format_has_timestamp(self):
        """所有伺服器訊息應包含 timestamp"""
        client = TestClient(app)
        with client.websocket_connect("/ws/qa_proto_5") as ws:
            msg1 = ws.receive_json()
            msg2 = ws.receive_json()
            assert "timestamp" in msg1
            assert "timestamp" in msg2
            assert isinstance(msg1["timestamp"], int)

    def test_health_endpoint(self):
        """健康檢查端點"""
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "active_players" in data
        assert "game_state" in data
        assert "cards_remaining" in data
        assert data["cards_remaining"] > 0

    def test_place_bet_not_betting_state(self):
        """非下注階段發送 PLACE_BET 應回傳 NOT_BETTING 錯誤

        策略：強制 game_room 進入 RESULT 狀態（非 BETTING）。
        setup_method 已鎖定 _game_running=True，connect() 不會啟動循環。
        _handle_bet() 的第一道檢查必定觸發 NOT_BETTING 錯誤。

        NOT_BETTING 的檢查在 Pydantic 驗證之前，所以押注內容不影響此錯誤路徑。
        teardown_method 會重置狀態。
        """
        # 設為 RESULT 狀態（非 BETTING），setup_method 已設 _game_running=True
        game_room.state_machine._state = GameState.RESULT

        client = TestClient(app)
        with client.websocket_connect("/ws/qa_not_betting_1") as ws:
            ws.receive_json()  # PLAYER_INIT
            ws.receive_json()  # STATE_CHANGE（回報當前 RESULT 狀態）

            ws.send_json({
                "type": "PLACE_BET",
                "payload": {"bets": {"player": 100}},
                "timestamp": int(time.time() * 1000),
            })
            err = ws.receive_json()
            assert err["type"] == "ERROR"
            assert err["payload"]["code"] == "NOT_BETTING"

    def test_place_bet_negative_amount_returns_invalid_bet(self):
        """押注金額為負數時應回傳 INVALID_BET 錯誤

        Pydantic PlaceBetPayload.validate_bets() 會拒絕負數金額。
        此路徑只有在 BETTING 狀態下才會執行到 Pydantic 驗證，
        因此測試前先強制狀態機設為 BETTING。
        setup_method 已鎖定 _game_running=True，避免 connect() 啟動循環
        （否則循環嘗試 BETTING→BETTING 轉換失敗後 reset()，導致狀態被清除）。
        teardown_method 會重置狀態。
        """
        # 強制切換到 BETTING 狀態，setup_method 已設 _game_running=True
        game_room.state_machine._state = GameState.BETTING

        client = TestClient(app)
        with client.websocket_connect("/ws/qa_invalid_bet_1") as ws:
            ws.receive_json()  # PLAYER_INIT
            ws.receive_json()  # STATE_CHANGE

            # bets 包含負數金額，應觸發 INVALID_BET
            ws.send_json({
                "type": "PLACE_BET",
                "payload": {"bets": {"player": -50}},
                "timestamp": int(time.time() * 1000),
            })
            err = ws.receive_json()
            assert err["type"] == "ERROR"
            assert err["payload"]["code"] == "INVALID_BET"

    def test_place_bet_invalid_bet_type_returns_error(self):
        """押注不存在的區域時應回傳 INVALID_BET_TYPE 錯誤

        Pydantic PlaceBetPayload.validate_bets() 會拒絕不在 VALID_BET_TYPES 內的押注區。
        此路徑只有在 BETTING 狀態下才會執行到 Pydantic 驗證，
        因此測試前先強制狀態機設為 BETTING。
        setup_method 已鎖定 _game_running=True，避免 connect() 啟動循環
        （否則循環嘗試 BETTING→BETTING 轉換失敗後 reset()，導致狀態被清除）。
        teardown_method 會重置狀態。
        """
        # 強制切換到 BETTING 狀態，setup_method 已設 _game_running=True
        game_room.state_machine._state = GameState.BETTING

        client = TestClient(app)
        with client.websocket_connect("/ws/qa_invalid_type_1") as ws:
            ws.receive_json()  # PLAYER_INIT
            ws.receive_json()  # STATE_CHANGE

            # "dragon" 不在合法押注區清單 VALID_BET_TYPES 內，應觸發 INVALID_BET_TYPE
            ws.send_json({
                "type": "PLACE_BET",
                "payload": {"bets": {"dragon": 100}},
                "timestamp": int(time.time() * 1000),
            })
            err = ws.receive_json()
            assert err["type"] == "ERROR"
            assert err["payload"]["code"] == "INVALID_BET_TYPE"


@pytest.mark.slow
class TestFullGameFlow:
    """完整遊戲流程測試（需要 --run-slow）"""

    def _drain_until(self, ws, msg_type: str, max_msgs: int = 100) -> tuple[dict, list[dict]]:
        """接收訊息直到指定類型，回傳 (目標訊息, 所有訊息)"""
        all_msgs = []
        for _ in range(max_msgs):
            msg = ws.receive_json()
            all_msgs.append(msg)
            if msg["type"] == msg_type:
                return msg, all_msgs
        raise TimeoutError(f"等待 {msg_type} 超時，收到 {len(all_msgs)} 則")

    def test_complete_round_with_bet(self):
        """完整一局：連線 → 等待下注 → 下注 → 確認 → 發牌 → 結果 → 結算"""
        client = TestClient(app)
        with client.websocket_connect("/ws/qa_full_1") as ws:
            init = ws.receive_json()
            assert init["type"] == "PLAYER_INIT"
            initial_balance = init["payload"]["balance"]

            # 等待進入 BETTING 且有倒數
            betting_msg, _ = self._drain_until(ws, "STATE_CHANGE", max_msgs=30)
            # 可能需要再等幾個 countdown 訊息
            while betting_msg["payload"].get("state") != "BETTING" or \
                  betting_msg["payload"].get("countdown", 0) < 5:
                betting_msg = ws.receive_json()
                if betting_msg["type"] != "STATE_CHANGE":
                    continue

            # 下注
            ws.send_json({
                "type": "PLACE_BET",
                "payload": {"bets": {"player": 100, "tie": 50}},
                "timestamp": int(time.time() * 1000),
            })
            ws.send_json({
                "type": "BET_CONFIRMED",
                "payload": {},
                "timestamp": int(time.time() * 1000),
            })

            # 等待發牌
            card_msgs = []
            result_msg = None
            settle_msg = None

            for _ in range(100):
                msg = ws.receive_json()
                if msg["type"] == "CARD_DEALT":
                    card_msgs.append(msg)
                elif msg["type"] == "GAME_RESULT":
                    result_msg = msg
                elif msg["type"] == "SETTLE_RESULT":
                    settle_msg = msg
                    break

            # 驗證發牌
            assert len(card_msgs) >= 4, f"至少 4 張牌，收到 {len(card_msgs)}"
            assert card_msgs[0]["payload"]["target"] == "player"
            assert card_msgs[1]["payload"]["target"] == "banker"
            assert card_msgs[2]["payload"]["target"] == "player"
            assert card_msgs[3]["payload"]["target"] == "banker"

            # 驗證結果
            assert result_msg is not None
            rp = result_msg["payload"]
            assert rp["winner"] in ("player", "banker", "tie")
            assert 0 <= rp["player_total"] <= 9
            assert 0 <= rp["banker_total"] <= 9

            # 驗證結算
            assert settle_msg is not None
            sp = settle_msg["payload"]
            assert "player" in sp["bets"]
            assert "tie" in sp["bets"]
            assert sp["bets"]["player"]["amount"] == 100
            assert sp["bets"]["tie"]["amount"] == 50
            assert sp["new_balance"] == initial_balance + sp["net_change"]

            # 驗證每張牌的結構
            for cm in card_msgs:
                card = cm["payload"]["card"]
                assert card["suit"] in ("hearts", "diamonds", "clubs", "spades")
                assert card["rank"] in ("A","2","3","4","5","6","7","8","9","T","J","Q","K")
                assert 0 <= card["value"] <= 9
