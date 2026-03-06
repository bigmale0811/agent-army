# -*- coding: utf-8 -*-
"""
DEV-6: researcher.py 測試。

測試覆蓋：
- SongResearcher 初始化（預設 / 自訂 client）
- dry_run 回傳 stub SongResearch
- 正常呼叫 OllamaClient.generate() 並解析 JSON
- prompt 包含 title/artist/hints
- 無效 JSON 回應時拋出例外
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.singer_agent.models import SongResearch


# ─────────────────────────────────────────────────
# 共用假資料
# ─────────────────────────────────────────────────

_VALID_RESEARCH_JSON = json.dumps({
    "genre": "ballad",
    "mood": "romantic",
    "visual_style": "Pastel Watercolor",
    "color_palette": ["soft_pink", "light_blue"],
    "background_prompt": "pastel dreamy landscape",
    "outfit_prompt": "white elegant dress",
    "scene_description": "夢幻水彩風格場景",
    "research_summary": "浪漫抒情風格適合柔和視覺",
})


# ─────────────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────────────

class TestSongResearcherInit:
    def test_default_creates_ollama_client(self):
        """預設建構時自動建立 OllamaClient。"""
        from src.singer_agent.researcher import SongResearcher
        r = SongResearcher()
        assert r.client is not None

    def test_custom_client_is_stored(self):
        """可注入自訂 OllamaClient。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        r = SongResearcher(ollama_client=mock_client)
        assert r.client is mock_client


# ─────────────────────────────────────────────────
# dry_run 模式
# ─────────────────────────────────────────────────

class TestResearchDryRun:
    def test_dry_run_returns_song_research(self):
        """dry_run 回傳 SongResearch 實例。"""
        from src.singer_agent.researcher import SongResearcher
        r = SongResearcher(ollama_client=MagicMock())
        result = r.research("測試歌", "測試歌手", dry_run=True)
        assert isinstance(result, SongResearch)

    def test_dry_run_does_not_call_client(self):
        """dry_run 不呼叫 OllamaClient。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        r = SongResearcher(ollama_client=mock_client)
        r.research("測試歌", "測試歌手", dry_run=True)
        mock_client.generate.assert_not_called()

    def test_dry_run_has_non_empty_fields(self):
        """dry_run stub 各欄位非空。"""
        from src.singer_agent.researcher import SongResearcher
        r = SongResearcher(ollama_client=MagicMock())
        result = r.research("歌", "歌手", dry_run=True)
        assert result.genre != ""
        assert result.mood != ""
        assert result.visual_style != ""
        assert len(result.color_palette) > 0


# ─────────────────────────────────────────────────
# 正常呼叫
# ─────────────────────────────────────────────────

class TestResearchNormal:
    def test_calls_ollama_generate(self):
        """呼叫 OllamaClient.generate()。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = _VALID_RESEARCH_JSON
        r = SongResearcher(ollama_client=mock_client)
        r.research("愛情", "歌手")
        mock_client.generate.assert_called_once()

    def test_returns_song_research_instance(self):
        """回傳 SongResearch 實例。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = _VALID_RESEARCH_JSON
        r = SongResearcher(ollama_client=mock_client)
        result = r.research("愛情", "歌手")
        assert isinstance(result, SongResearch)

    def test_parses_genre_correctly(self):
        """正確解析 genre 欄位。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = _VALID_RESEARCH_JSON
        r = SongResearcher(ollama_client=mock_client)
        result = r.research("愛情", "歌手")
        assert result.genre == "ballad"

    def test_parses_color_palette_as_list(self):
        """color_palette 是 list。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = _VALID_RESEARCH_JSON
        r = SongResearcher(ollama_client=mock_client)
        result = r.research("愛情", "歌手")
        assert isinstance(result.color_palette, list)
        assert len(result.color_palette) == 2

    def test_prompt_contains_title_and_artist(self):
        """prompt 包含歌名和歌手。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = _VALID_RESEARCH_JSON
        r = SongResearcher(ollama_client=mock_client)
        r.research("月亮代表我的心", "鄧麗君")
        prompt = mock_client.generate.call_args[0][0]
        assert "月亮代表我的心" in prompt
        assert "鄧麗君" in prompt

    def test_prompt_includes_genre_hint(self):
        """提供 genre_hint 時 prompt 包含該提示。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = _VALID_RESEARCH_JSON
        r = SongResearcher(ollama_client=mock_client)
        r.research("歌", "手", genre_hint="jazz")
        prompt = mock_client.generate.call_args[0][0]
        assert "jazz" in prompt

    def test_prompt_includes_mood_hint(self):
        """提供 mood_hint 時 prompt 包含該提示。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = _VALID_RESEARCH_JSON
        r = SongResearcher(ollama_client=mock_client)
        r.research("歌", "手", mood_hint="happy")
        prompt = mock_client.generate.call_args[0][0]
        assert "happy" in prompt

    def test_handles_markdown_wrapped_json(self):
        """處理被 ```json 包裹的 JSON。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = f"```json\n{_VALID_RESEARCH_JSON}\n```"
        r = SongResearcher(ollama_client=mock_client)
        result = r.research("歌", "手")
        assert isinstance(result, SongResearch)
        assert result.genre == "ballad"


# ─────────────────────────────────────────────────
# 錯誤處理
# ─────────────────────────────────────────────────

class TestResearchErrors:
    def test_invalid_json_raises_value_error(self):
        """無效 JSON 拋出 ValueError。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = "not valid json at all"
        r = SongResearcher(ollama_client=mock_client)
        with pytest.raises((ValueError, json.JSONDecodeError)):
            r.research("歌", "手")

    def test_missing_key_raises_key_error(self):
        """JSON 缺少必要欄位拋出 KeyError。"""
        from src.singer_agent.researcher import SongResearcher
        mock_client = MagicMock()
        mock_client.generate.return_value = json.dumps({"genre": "pop"})
        r = SongResearcher(ollama_client=mock_client)
        with pytest.raises(KeyError):
            r.research("歌", "手")
