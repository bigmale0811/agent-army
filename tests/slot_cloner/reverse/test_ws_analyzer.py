"""WS Analyzer 測試"""
import json
from slot_cloner.reverse.ws_analyzer import WSAnalyzer


class TestWSAnalyzer:
    def test_add_json_message(self):
        analyzer = WSAnalyzer()
        analyzer.add_message('{"type": "init", "data": {}}')
        assert len(analyzer.messages) == 1
        assert analyzer.messages[0]["parsed"]["type"] == "init"

    def test_add_binary_message(self):
        analyzer = WSAnalyzer()
        analyzer.add_message(b"\x00\x01\x02")
        assert len(analyzer.messages) == 1

    def test_find_game_config(self):
        analyzer = WSAnalyzer()
        # 模擬一則包含遊戲配置的 WS 訊息
        config = {
            "type": "gameConfig",
            "paytable": {"anubis": {8: 1.0}},
            "symbols": [{"id": "anubis", "type": "regular"}],
            "scatter": {"trigger": 4},
            "wild": {"substitutes": True},
            "multiplier": {"values": [2, 5, 10]},
        }
        analyzer.add_message(json.dumps(config))
        found = analyzer.find_game_config()
        assert found is not None
        assert "paytable" in found

    def test_find_game_config_not_found(self):
        analyzer = WSAnalyzer()
        analyzer.add_message('{"type": "ping"}')
        assert analyzer.find_game_config() is None

    def test_find_spin_results(self):
        analyzer = WSAnalyzer()
        spin = {"type": "spinResult", "result": True, "win": 100, "grid": [[1, 2]], "symbols": []}
        analyzer.add_message(json.dumps(spin))
        results = analyzer.find_spin_results()
        assert len(results) == 1

    def test_extract_symbols(self):
        analyzer = WSAnalyzer()
        config = {
            "symbols": [{"id": "wild"}, {"id": "scatter"}],
            "paytable": {},
            "wild": True,
            "bonus": True,
        }
        analyzer.add_message(json.dumps(config))
        symbols = analyzer.extract_symbols()
        assert len(symbols) > 0
