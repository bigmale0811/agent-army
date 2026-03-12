"""JS Analyzer 測試"""
from slot_cloner.reverse.js_analyzer import JSAnalyzer


class TestJSAnalyzer:
    def test_find_symbols(self):
        analyzer = JSAnalyzer()
        js = '''
        var symbols = ["wild_symbol", "scatter_bonus", "regular_1"];
        var bonus_game = true;
        var freeSpinCount = 15;
        '''
        result = analyzer.analyze(js)
        assert "wild_symbol" in result["symbol_candidates"]
        assert "scatter_bonus" in result["symbol_candidates"]

    def test_find_grid_size(self):
        analyzer = JSAnalyzer()
        js = 'var config = { cols: 6, rows: 5 };'
        result = analyzer.analyze(js)
        assert result["grid_size"] is not None
        assert result["grid_size"]["cols"] == 6
        assert result["grid_size"]["rows"] == 5

    def test_find_rtp(self):
        analyzer = JSAnalyzer()
        js = 'var rtp = 96.89; var returnToPlayer = 95.5;'
        result = analyzer.analyze(js)
        assert 96.89 in result["rtp_candidates"]

    def test_find_framework_pixi(self):
        analyzer = JSAnalyzer()
        js = 'var app = new PIXI.Application();'
        result = analyzer.analyze(js)
        assert "pixi" in result["framework_hints"]

    def test_empty_js(self):
        analyzer = JSAnalyzer()
        result = analyzer.analyze("")
        assert result["paytable_candidates"] == []
