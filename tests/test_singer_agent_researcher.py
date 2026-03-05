# -*- coding: utf-8 -*-
"""Singer Agent 歌曲研究模組測試"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.singer_agent.models import SongMetadata
from src.singer_agent.song_researcher import (
    _parse_json_response,
    research_song,
)


class TestParseJsonResponse:
    """JSON 解析工具測試"""

    def test_parse_clean_json(self):
        """解析乾淨的 JSON"""
        text = '{"genre": "pop", "mood": "happy"}'
        result = _parse_json_response(text)
        assert result["genre"] == "pop"

    def test_parse_json_with_markdown(self):
        """解析帶 markdown 標記的 JSON"""
        text = '```json\n{"genre": "rock"}\n```'
        result = _parse_json_response(text)
        assert result["genre"] == "rock"

    def test_parse_json_with_prefix(self):
        """解析前面有多餘文字的 JSON"""
        text = '以下是分析結果：\n{"genre": "ballad", "mood": "sad"}'
        result = _parse_json_response(text)
        assert result["genre"] == "ballad"

    def test_parse_invalid_json_raises(self):
        """無法解析的文字拋出 ValueError"""
        with pytest.raises(ValueError, match="無法從 LLM"):
            _parse_json_response("this is not json at all")

    def test_parse_empty_string_raises(self):
        """空字串拋出 ValueError"""
        with pytest.raises(ValueError):
            _parse_json_response("")


class TestResearchSong:
    """歌曲風格研究測試"""

    @pytest.mark.asyncio
    async def test_research_success(self):
        """成功呼叫 Ollama 並解析結果"""
        mock_response = json.dumps({
            "genre": "chinese_pop",
            "mood": "romantic",
            "research_summary": "這是一首甜蜜的流行情歌",
            "visual_style": "dreamy pastel",
            "color_palette": "pink, warm, soft light",
            "background_prompt": "cherry blossom park",
            "outfit_prompt": "cute casual dress",
            "scene_description": "櫻花樹下的浪漫場景",
        })

        mock_ollama = AsyncMock(return_value=mock_response)
        with patch(
            "src.singer_agent.song_researcher._call_ollama",
            mock_ollama,
        ):
            metadata = SongMetadata(title="告白氣球", artist="周杰倫", language="zh")
            result = await research_song(metadata)

            assert result["genre"] == "chinese_pop"
            assert result["mood"] == "romantic"
            assert "櫻花" in result["scene_description"]

    @pytest.mark.asyncio
    async def test_research_with_hints(self):
        """使用者提供的提示會被包含在 prompt 中"""
        mock_ollama = AsyncMock(return_value='{"genre":"rock","mood":"energetic"}')

        with patch(
            "src.singer_agent.song_researcher._call_ollama",
            mock_ollama,
        ):
            metadata = SongMetadata(
                title="test",
                genre_hint="搖滾",
                mood_hint="激昂",
            )
            await research_song(metadata)

            # 確認 prompt 中包含提示文字
            call_args = mock_ollama.call_args[0][0]
            assert "搖滾" in call_args
            assert "激昂" in call_args

    @pytest.mark.asyncio
    async def test_research_connection_error(self):
        """Ollama 連線失敗時拋出 ConnectionError"""
        import httpx

        mock_ollama = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with patch(
            "src.singer_agent.song_researcher._call_ollama",
            side_effect=httpx.ConnectError("refused"),
        ):
            metadata = SongMetadata(title="test")
            with pytest.raises(ConnectionError):
                await research_song(metadata)
