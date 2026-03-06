"""
clean_thinking_tags() 單元測試

驗證 QWen3 等本地 LLM 輸出的 <think>...</think> 雜訊能被正確清除。
"""

import pytest

from stock_analyzer.main import clean_thinking_tags


class TestCleanThinkingTags:
    """clean_thinking_tags 功能測試"""

    def test_empty_string(self):
        """空字串應原樣回傳"""
        assert clean_thinking_tags("") == ""

    def test_none_input(self):
        """None 應原樣回傳"""
        assert clean_thinking_tags(None) is None

    def test_no_tags(self):
        """不含 think 標籤的正常文字應不變"""
        text = "這是一段正常的分析報告內容。"
        assert clean_thinking_tags(text) == text

    def test_single_think_block(self):
        """單一 <think>...</think> 區塊應被移除"""
        text = "<think>這是模型的內部推理</think>這是報告內容。"
        assert clean_thinking_tags(text) == "這是報告內容。"

    def test_multiline_think_block(self):
        """多行 <think> 區塊應被完整移除"""
        text = (
            "<think>\n"
            "第一行推理\n"
            "第二行推理\n"
            "第三行推理\n"
            "</think>\n"
            "正式報告開始。"
        )
        assert clean_thinking_tags(text) == "正式報告開始。"

    def test_multiple_think_blocks(self):
        """多個 <think> 區塊應全部被移除"""
        text = (
            "<think>推理1</think>結論1。"
            "<think>推理2</think>結論2。"
        )
        assert clean_thinking_tags(text) == "結論1。結論2。"

    def test_unclosed_closing_tag(self):
        """殘留的 </think> 標籤應被移除"""
        text = "報告內容</think>繼續。"
        assert clean_thinking_tags(text) == "報告內容繼續。"

    def test_unclosed_opening_tag(self):
        """殘留的 <think> 標籤應被移除"""
        text = "報告內容<think>繼續。"
        assert clean_thinking_tags(text) == "報告內容繼續。"

    def test_real_world_qwen3_output(self):
        """模擬 QWen3 真實輸出：think 區塊在報告開頭"""
        text = (
            "<think>\n"
            "Let me analyze AAPL...\n"
            "The user wants a market analysis.\n"
            "I should provide technical indicators.\n"
            "</think>\n"
            "\n"
            "## AAPL Technical Analysis\n"
            "\n"
            "Based on recent market data, AAPL shows..."
        )
        result = clean_thinking_tags(text)
        assert "<think>" not in result
        assert "</think>" not in result
        assert "## AAPL Technical Analysis" in result
        assert "Based on recent market data" in result

    def test_investment_plan_with_trailing_think(self):
        """模擬投資計畫中尾部殘留 </think> 的情境（BUG-2 實際案例）"""
        text = (
            "## Investment Plan\n"
            "\n"
            "1. Entry: $180\n"
            "2. Stop Loss: $170\n"
            "</think>"
        )
        result = clean_thinking_tags(text)
        assert "</think>" not in result
        assert "Entry: $180" in result

    def test_preserves_other_html_tags(self):
        """應保留非 think 的 HTML 標籤"""
        text = "<b>Bold</b> and <i>italic</i> text."
        assert clean_thinking_tags(text) == "<b>Bold</b> and <i>italic</i> text."

    def test_leading_newlines_stripped(self):
        """think 區塊移除後，開頭多餘空行應被清除"""
        text = "<think>reasoning</think>\n\n\nContent here."
        result = clean_thinking_tags(text)
        assert not result.startswith("\n")
        assert "Content here." in result
