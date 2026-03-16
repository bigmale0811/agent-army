# -*- coding: utf-8 -*-
"""TemplateEngine 單元測試。

測試模板渲染的各種情境，包括：
- 正常替換（output / error）
- 無佔位符的純文字
- 缺少步驟或欄位時的 KeyError
- has_placeholders 偵測方法
"""

import pytest

from agentforge.utils.template import TemplateEngine


@pytest.fixture
def engine() -> TemplateEngine:
    """建立 TemplateEngine 實例。"""
    return TemplateEngine()


@pytest.fixture
def base_context() -> dict:
    """基本步驟輸出環境。"""
    return {
        "steps": {
            "fetch": {"output": "Hello, World!", "error": ""},
            "analyze": {"output": "Summary text", "error": "Some warning"},
        }
    }


class TestRender:
    """render() 方法測試。"""

    def test_render_output_placeholder(self, engine: TemplateEngine, base_context: dict) -> None:
        """應正確替換 steps.<name>.output 佔位符。"""
        result = engine.render("Result: {{ steps.fetch.output }}", base_context)
        assert result == "Result: Hello, World!"

    def test_render_error_placeholder(self, engine: TemplateEngine, base_context: dict) -> None:
        """應正確替換 steps.<name>.error 佔位符。"""
        result = engine.render("Error was: {{ steps.analyze.error }}", base_context)
        assert result == "Error was: Some warning"

    def test_render_multiple_placeholders(self, engine: TemplateEngine, base_context: dict) -> None:
        """應正確替換多個佔位符。"""
        template = "Fetch: {{ steps.fetch.output }}, Analyze: {{ steps.analyze.output }}"
        result = engine.render(template, base_context)
        assert result == "Fetch: Hello, World!, Analyze: Summary text"

    def test_render_no_placeholders(self, engine: TemplateEngine, base_context: dict) -> None:
        """無佔位符的字串應原樣回傳。"""
        result = engine.render("plain text without placeholders", base_context)
        assert result == "plain text without placeholders"

    def test_render_empty_string(self, engine: TemplateEngine, base_context: dict) -> None:
        """空字串應回傳空字串。"""
        result = engine.render("", base_context)
        assert result == ""

    def test_render_with_spaces_in_placeholder(self, engine: TemplateEngine, base_context: dict) -> None:
        """佔位符內有多餘空白應仍能正確替換。"""
        result = engine.render("{{  steps.fetch.output  }}", base_context)
        assert result == "Hello, World!"

    def test_render_empty_context(self, engine: TemplateEngine) -> None:
        """空 context 且無佔位符應正常回傳。"""
        result = engine.render("no placeholders here", {})
        assert result == "no placeholders here"

    def test_render_missing_step_raises_key_error(
        self, engine: TemplateEngine, base_context: dict
    ) -> None:
        """引用不存在的步驟應拋出 KeyError。"""
        with pytest.raises(KeyError, match="nonexistent"):
            engine.render("{{ steps.nonexistent.output }}", base_context)

    def test_render_missing_field_raises_key_error(
        self, engine: TemplateEngine
    ) -> None:
        """引用存在但欄位不對應應拋出 KeyError（模擬 steps 資料缺少欄位）。"""
        context = {"steps": {"step1": {"output": "val"}}}
        # 'error' 欄位不存在 -> 觸發 KeyError
        with pytest.raises(KeyError):
            engine.render("{{ steps.step1.error }}", context)

    def test_render_static_method_call(self) -> None:
        """render 為 staticmethod，可直接透過類別呼叫。"""
        context = {"steps": {"s": {"output": "ok", "error": ""}}}
        result = TemplateEngine.render("{{ steps.s.output }}", context)
        assert result == "ok"


class TestHasPlaceholders:
    """has_placeholders() 方法測試。"""

    def test_has_placeholders_true(self, engine: TemplateEngine) -> None:
        """含佔位符應回傳 True。"""
        assert engine.has_placeholders("{{ steps.foo.output }}") is True

    def test_has_placeholders_false(self, engine: TemplateEngine) -> None:
        """不含佔位符應回傳 False。"""
        assert engine.has_placeholders("plain text") is False

    def test_has_placeholders_empty(self, engine: TemplateEngine) -> None:
        """空字串應回傳 False。"""
        assert engine.has_placeholders("") is False

    def test_has_placeholders_partial_match(self, engine: TemplateEngine) -> None:
        """不完整的佔位符語法不應匹配。"""
        assert engine.has_placeholders("{{ steps.foo }}") is False
        assert engine.has_placeholders("steps.foo.output") is False
