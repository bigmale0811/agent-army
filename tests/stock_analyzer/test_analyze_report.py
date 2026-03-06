"""
AnalysisReport 建構測試

驗證 analyze() 方法從 TradingAgents state 正確提取報告欄位，
特別是 BUG-1 的回歸測試（market_report key 正確性）。
"""

from unittest.mock import MagicMock, patch

import pytest

from stock_analyzer.main import AnalysisReport, StockAnalyzer
from stock_analyzer.utils.ticker_resolver import AssetType


class TestAnalyzeReportKeyMapping:
    """驗證 state dict → AnalysisReport 的 key 對應正確性"""

    @patch("stock_analyzer.main.StockAnalyzer._ensure_graph")
    def test_market_report_uses_correct_key(self, mock_ensure):
        """
        BUG-1 回歸測試：確保使用 'market_report' 而非 'market_research_report'。

        如果 key 回退為錯誤的 'market_research_report'，
        market_report 欄位將為空字串。
        """
        # 準備：模擬 TradingAgents state（包含正確 key）
        fake_state = {
            "market_report": "Market is bullish on AAPL.",
            "news_report": "Apple released new product.",
            "fundamentals_report": "Revenue grew 15%.",
            "sentiment_report": "Positive sentiment detected.",
            "investment_plan": "Buy at $180, stop loss $170.",
        }
        fake_decision = "BUY"

        analyzer = StockAnalyzer.__new__(StockAnalyzer)
        analyzer._graph = MagicMock()
        analyzer._graph.propagate.return_value = (fake_state, fake_decision)

        report = analyzer.analyze("AAPL", date="2026-03-06")

        # 驗證：market_report 不為空（BUG-1 的核心驗收標準）
        assert report.market_report == "Market is bullish on AAPL."
        assert report.market_report != ""

    @patch("stock_analyzer.main.StockAnalyzer._ensure_graph")
    def test_wrong_key_would_produce_empty(self, mock_ensure):
        """
        反向驗證：如果 state 只有 'market_research_report'（錯誤 key），
        market_report 應為空，證明我們不再使用舊 key。
        """
        fake_state = {
            "market_research_report": "This should NOT appear.",
            "news_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "investment_plan": "",
        }

        analyzer = StockAnalyzer.__new__(StockAnalyzer)
        analyzer._graph = MagicMock()
        analyzer._graph.propagate.return_value = (fake_state, "HOLD")

        report = analyzer.analyze("AAPL", date="2026-03-06")

        # 使用錯誤 key 的 state，market_report 應為空
        assert report.market_report == ""

    @patch("stock_analyzer.main.StockAnalyzer._ensure_graph")
    def test_all_report_fields_cleaned(self, mock_ensure):
        """驗證所有 6 個報告欄位都經過 clean_thinking_tags 處理"""
        fake_state = {
            "market_report": "<think>reasoning</think>Clean market.",
            "news_report": "<think>reasoning</think>Clean news.",
            "fundamentals_report": "<think>reasoning</think>Clean fundamentals.",
            "sentiment_report": "<think>reasoning</think>Clean sentiment.",
            "investment_plan": "<think>reasoning</think>Clean plan.",
        }
        fake_decision = "<think>reasoning</think>BUY"

        analyzer = StockAnalyzer.__new__(StockAnalyzer)
        analyzer._graph = MagicMock()
        analyzer._graph.propagate.return_value = (fake_state, fake_decision)

        report = analyzer.analyze("AAPL", date="2026-03-06")

        # 所有欄位都不應包含 <think> 標籤
        assert "<think>" not in report.market_report
        assert "<think>" not in report.news_report
        assert "<think>" not in report.fundamentals_report
        assert "<think>" not in report.sentiment_report
        assert "<think>" not in report.investment_plan
        assert "<think>" not in report.final_decision

        # 內容本身應保留
        assert "Clean market." in report.market_report
        assert "BUY" in report.final_decision
