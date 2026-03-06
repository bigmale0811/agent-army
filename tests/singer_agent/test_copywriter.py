# -*- coding: utf-8 -*-
"""
DEV-7: copywriter.py 測試。

測試覆蓋：
- Copywriter 初始化
- dry_run 回傳 stub CopySpec
- 正常呼叫解析 JSON
- prompt 包含歌曲資訊
- 錯誤處理
"""
import json
from unittest.mock import MagicMock

import pytest

from src.singer_agent.models import CopySpec, SongResearch, SongSpec

_SAMPLE_SPEC = SongSpec(
    title="愛我的人和我愛的人",
    artist="測試歌手",
    language="zh-TW",
    research=SongResearch(
        genre="ballad",
        mood="romantic",
        visual_style="Pastel Watercolor",
        color_palette=["soft_pink"],
        background_prompt="pastel bg",
        outfit_prompt="white dress",
        scene_description="夢幻場景",
        research_summary="浪漫風格",
    ),
    created_at="2026-03-06T12:00:00",
)

_VALID_COPY_JSON = json.dumps({
    "title": "【MV】愛我的人和我愛的人",
    "description": "感人情歌 MV\n\n#虛擬歌手 #MV",
    "tags": ["虛擬歌手", "MV", "情歌", "AI"],
})


class TestCopywriterInit:
    def test_default_creates_ollama_client(self):
        """預設建構自動建立 OllamaClient。"""
        from src.singer_agent.copywriter import Copywriter
        c = Copywriter()
        assert c.client is not None

    def test_custom_client_is_stored(self):
        """可注入自訂 client。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        c = Copywriter(ollama_client=mock)
        assert c.client is mock


class TestWriteDryRun:
    def test_dry_run_returns_copy_spec(self):
        """dry_run 回傳 CopySpec 實例。"""
        from src.singer_agent.copywriter import Copywriter
        c = Copywriter(ollama_client=MagicMock())
        result = c.write(_SAMPLE_SPEC, dry_run=True)
        assert isinstance(result, CopySpec)

    def test_dry_run_does_not_call_client(self):
        """dry_run 不呼叫 client。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        c = Copywriter(ollama_client=mock)
        c.write(_SAMPLE_SPEC, dry_run=True)
        mock.generate.assert_not_called()

    def test_dry_run_has_non_empty_title(self):
        """dry_run stub 有標題。"""
        from src.singer_agent.copywriter import Copywriter
        c = Copywriter(ollama_client=MagicMock())
        result = c.write(_SAMPLE_SPEC, dry_run=True)
        assert result.title != ""

    def test_dry_run_has_tags(self):
        """dry_run stub 有 tags。"""
        from src.singer_agent.copywriter import Copywriter
        c = Copywriter(ollama_client=MagicMock())
        result = c.write(_SAMPLE_SPEC, dry_run=True)
        assert isinstance(result.tags, list)
        assert len(result.tags) > 0


class TestWriteNormal:
    def test_calls_ollama_generate(self):
        """呼叫 OllamaClient.generate()。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        mock.generate.return_value = _VALID_COPY_JSON
        c = Copywriter(ollama_client=mock)
        c.write(_SAMPLE_SPEC)
        mock.generate.assert_called_once()

    def test_returns_copy_spec_instance(self):
        """回傳 CopySpec 實例。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        mock.generate.return_value = _VALID_COPY_JSON
        c = Copywriter(ollama_client=mock)
        result = c.write(_SAMPLE_SPEC)
        assert isinstance(result, CopySpec)

    def test_parses_title(self):
        """正確解析 title。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        mock.generate.return_value = _VALID_COPY_JSON
        c = Copywriter(ollama_client=mock)
        result = c.write(_SAMPLE_SPEC)
        assert "愛我的人" in result.title

    def test_parses_tags_as_list(self):
        """tags 是 list。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        mock.generate.return_value = _VALID_COPY_JSON
        c = Copywriter(ollama_client=mock)
        result = c.write(_SAMPLE_SPEC)
        assert isinstance(result.tags, list)
        assert len(result.tags) >= 3

    def test_prompt_contains_song_title(self):
        """prompt 包含歌名。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        mock.generate.return_value = _VALID_COPY_JSON
        c = Copywriter(ollama_client=mock)
        c.write(_SAMPLE_SPEC)
        prompt = mock.generate.call_args[0][0]
        assert "愛我的人和我愛的人" in prompt

    def test_prompt_contains_artist(self):
        """prompt 包含歌手。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        mock.generate.return_value = _VALID_COPY_JSON
        c = Copywriter(ollama_client=mock)
        c.write(_SAMPLE_SPEC)
        prompt = mock.generate.call_args[0][0]
        assert "測試歌手" in prompt

    def test_handles_markdown_wrapped_json(self):
        """處理 ```json 包裹。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        mock.generate.return_value = f"```json\n{_VALID_COPY_JSON}\n```"
        c = Copywriter(ollama_client=mock)
        result = c.write(_SAMPLE_SPEC)
        assert isinstance(result, CopySpec)


class TestWriteErrors:
    def test_invalid_json_raises(self):
        """無效 JSON 拋出例外。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        mock.generate.return_value = "invalid json"
        c = Copywriter(ollama_client=mock)
        with pytest.raises((ValueError, json.JSONDecodeError)):
            c.write(_SAMPLE_SPEC)

    def test_missing_key_raises(self):
        """JSON 缺少必要欄位拋出例外。"""
        from src.singer_agent.copywriter import Copywriter
        mock = MagicMock()
        mock.generate.return_value = json.dumps({"title": "foo"})
        c = Copywriter(ollama_client=mock)
        with pytest.raises(KeyError):
            c.write(_SAMPLE_SPEC)
