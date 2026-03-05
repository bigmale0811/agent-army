# -*- coding: utf-8 -*-
"""Singer Agent 文案生成模組測試"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.singer_agent.copywriter import _parse_copy_response, generate_copy
from src.singer_agent.models import SongSpec


class TestParseCopyResponse:
    """文案 JSON 解析測試"""

    def test_parse_valid_json(self):
        """解析有效的 JSON"""
        text = json.dumps({
            "youtube_title": "測試標題",
            "youtube_description": "測試描述",
            "youtube_tags": ["tag1", "tag2"],
        })
        result = _parse_copy_response(text)
        assert result["youtube_title"] == "測試標題"
        assert len(result["youtube_tags"]) == 2

    def test_parse_json_with_markdown(self):
        """解析帶 markdown 的 JSON"""
        text = '```json\n{"youtube_title": "標題"}\n```'
        result = _parse_copy_response(text)
        assert result["youtube_title"] == "標題"

    def test_parse_invalid_returns_defaults(self):
        """無法解析時回傳預設空值"""
        result = _parse_copy_response("not json")
        assert result["youtube_title"] == ""
        assert result["youtube_tags"] == []

    def test_missing_fields_filled(self):
        """缺少的欄位補空值"""
        text = '{"youtube_title": "只有標題"}'
        result = _parse_copy_response(text)
        assert result["youtube_title"] == "只有標題"
        assert result["youtube_description"] == ""
        assert result["youtube_tags"] == []


class TestGenerateCopy:
    """文案生成整合測試"""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """成功生成文案"""
        mock_response = {
            "message": {
                "role": "assistant",
                "content": json.dumps({
                    "youtube_title": "🎵 告白氣球｜虛擬歌手翻唱",
                    "youtube_description": "翻唱周杰倫經典情歌",
                    "youtube_tags": ["告白氣球", "周杰倫", "cover"],
                }),
            }
        }

        mock_post = AsyncMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = lambda: None
        mock_post.return_value.json = lambda: mock_response

        with patch("httpx.AsyncClient.post", mock_post):
            spec = SongSpec(title="告白氣球", artist="周杰倫", genre="pop")
            result = await generate_copy(spec)
            assert "告白氣球" in result["youtube_title"]
            assert len(result["youtube_tags"]) > 0
