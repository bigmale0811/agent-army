"""WSAnalyzer Socket.IO 格式解析測試"""
import pytest
from slot_cloner.reverse.ws_analyzer import WSAnalyzer


class TestSocketIOParsing:
    """Socket.IO 訊息格式的解析測試"""

    def test_parse_socketio_event(self):
        """解析 Socket.IO EVENT 訊息 42["event", {...}]"""
        analyzer = WSAnalyzer()
        analyzer.add_message('42["game_init",{"symbols":["A","B","C"],"paytable":{"A":10}}]')

        assert len(analyzer.messages) == 1
        parsed = analyzer.messages[0]["parsed"]
        assert parsed["type"] == "socketio_event"
        assert parsed["prefix"] == "42"
        assert parsed["event"] == "game_init"
        assert parsed["data"]["symbols"] == ["A", "B", "C"]

    def test_parse_socketio_control_ping(self):
        """解析 Socket.IO PING 控制訊息"""
        analyzer = WSAnalyzer()
        analyzer.add_message("2")

        parsed = analyzer.messages[0]["parsed"]
        assert parsed["type"] == "socketio_control"
        assert parsed["prefix"] == "2"

    def test_parse_socketio_control_pong(self):
        """解析 Socket.IO PONG 控制訊息"""
        analyzer = WSAnalyzer()
        analyzer.add_message("3")

        parsed = analyzer.messages[0]["parsed"]
        assert parsed["type"] == "socketio_control"
        assert parsed["prefix"] == "3"

    def test_parse_socketio_connect(self):
        """解析 Socket.IO namespace CONNECT"""
        analyzer = WSAnalyzer()
        analyzer.add_message("40")

        parsed = analyzer.messages[0]["parsed"]
        assert parsed["type"] == "socketio_control"
        assert parsed["prefix"] == "40"

    def test_parse_plain_json(self):
        """一般 JSON 訊息仍可正常解析"""
        analyzer = WSAnalyzer()
        analyzer.add_message('{"type":"spin","result":{"grid":[[1,2],[3,4]]}}')

        parsed = analyzer.messages[0]["parsed"]
        assert parsed["type"] == "spin"
        assert parsed["result"]["grid"] == [[1, 2], [3, 4]]

    def test_parse_binary_message(self):
        """二進位訊息的處理"""
        analyzer = WSAnalyzer()
        analyzer.add_message(b"\x00\x01\x02\xff")

        parsed = analyzer.messages[0]["parsed"]
        assert parsed["type"] == "binary"


class TestFindGameConfigSocketIO:
    """Socket.IO 格式中搜尋遊戲配置"""

    def test_find_config_in_socketio_event(self):
        """從 Socket.IO EVENT 中找到遊戲配置"""
        analyzer = WSAnalyzer()
        # 模擬 ATG 的遊戲初始化事件
        analyzer.add_message(
            '42["game_config",{"paytable":{"wild":100,"scatter":50},'
            '"symbol":["wild","scatter","A","K","Q"],'
            '"reel":[["A","K"],["Q","J"]],'
            '"bonus":{"free_spins":10}}]'
        )

        config = analyzer.find_game_config()
        assert config is not None
        assert "paytable" in config
        assert "symbol" in config

    def test_find_config_skips_control_messages(self):
        """控制訊息不會被誤判為遊戲配置"""
        analyzer = WSAnalyzer()
        analyzer.add_message("2")   # PING
        analyzer.add_message("3")   # PONG
        analyzer.add_message("40")  # CONNECT

        assert analyzer.find_game_config() is None

    def test_find_config_mixed_messages(self):
        """混合訊息中正確找到配置"""
        analyzer = WSAnalyzer()
        analyzer.add_message("40")  # CONNECT
        analyzer.add_message("2")   # PING
        analyzer.add_message(
            '42["init",{"version":"1.0","name":"test"}]'
        )
        analyzer.add_message(
            '42["game_data",{"paytable":{"A":5},"symbol":["A","B"],'
            '"reel":[[1,2]],"wild":"W","scatter":"S"}]'
        )

        config = analyzer.find_game_config()
        assert config is not None
        assert "paytable" in config


class TestFindSpinResultsSocketIO:
    """Socket.IO 格式中搜尋 Spin 結果"""

    def test_find_spin_results(self):
        """從 Socket.IO 訊息找到 spin 結果"""
        analyzer = WSAnalyzer()
        analyzer.add_message(
            '42["spin_result",{"result":"win","grid":[[1,2,3],[4,5,6]],'
            '"payout":25,"cascade":true}]'
        )

        results = analyzer.find_spin_results()
        assert len(results) == 1
        assert results[0]["result"] == "win"
        assert results[0]["grid"] == [[1, 2, 3], [4, 5, 6]]

    def test_find_multiple_spin_results(self):
        """找到多次 spin 結果"""
        analyzer = WSAnalyzer()
        for i in range(3):
            analyzer.add_message(
                f'42["spin",{{"result":"win","win":{i * 10},"board":[[{i}]]}}]'
            )

        results = analyzer.find_spin_results()
        assert len(results) == 3


class TestGetAllEvents:
    """事件摘要功能測試"""

    def test_get_all_events(self):
        """取得所有 Socket.IO 事件名稱"""
        analyzer = WSAnalyzer()
        analyzer.add_message('42["game_init",{"config":true}]')
        analyzer.add_message('42["spin_result",{"win":100}]')
        analyzer.add_message("2")  # PING（不是 event）

        events = analyzer.get_all_events()
        assert len(events) == 2
        assert events[0]["event"] == "game_init"
        assert events[1]["event"] == "spin_result"

    def test_events_include_direction(self):
        """事件包含方向資訊"""
        analyzer = WSAnalyzer()
        analyzer.add_message('42["bet",{"amount":100}]', "sent")
        analyzer.add_message('42["result",{"win":50}]', "received")

        events = analyzer.get_all_events()
        assert events[0]["direction"] == "sent"
        assert events[1]["direction"] == "received"
