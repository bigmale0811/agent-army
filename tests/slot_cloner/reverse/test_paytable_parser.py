"""Paytable Parser 測試"""
from slot_cloner.reverse.paytable_parser import PaytableParser
from slot_cloner.models.enums import SymbolType, ConfidenceLevel


class TestPaytableParser:
    def test_parse_from_raw(self):
        parser = PaytableParser()
        symbols_data = [
            {"id": "anubis", "name": "Anubis", "payouts": {8: 1.0, 10: 2.5, 12: 10.0}},
            {"id": "wild", "name": "Wild", "type": "wild"},
        ]
        symbols, paytable = parser.parse_from_raw(symbols_data, {})

        assert len(symbols) == 2
        assert symbols[0].symbol_type == SymbolType.REGULAR
        assert symbols[1].symbol_type == SymbolType.WILD
        assert len(paytable.entries) == 3  # anubis 有 3 個賠率條目

    def test_parse_from_ws_config(self):
        parser = PaytableParser()
        config = {
            "symbols": [
                {"id": "1", "name": "Anubis", "payouts": {"8": 1.0, "10": 2.5}},
                {"id": "2", "name": "Scatter", "type": "scatter"},
            ],
            "minCluster": 8,
        }
        symbols, paytable = parser.parse_from_ws_config(config)

        assert len(symbols) == 2
        assert paytable.min_cluster_size == 8

    def test_detect_symbol_type(self):
        assert PaytableParser._detect_symbol_type("Wild Card") == SymbolType.WILD
        assert PaytableParser._detect_symbol_type("Scatter") == SymbolType.SCATTER
        assert PaytableParser._detect_symbol_type("Bonus Round") == SymbolType.BONUS
        assert PaytableParser._detect_symbol_type("Anubis") == SymbolType.REGULAR

    def test_detect_min_cluster(self):
        assert PaytableParser._detect_min_cluster({"minCluster": 5}) == 5
        assert PaytableParser._detect_min_cluster({}) == 8  # 預設值
