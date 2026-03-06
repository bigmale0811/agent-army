# -*- coding: utf-8 -*-
"""
Singer Agent 測試共用 fixtures。
提供各測試模組使用的基礎資料物件。
"""
import pytest
from pathlib import Path


@pytest.fixture
def sample_song_research_data() -> dict:
    """提供 SongResearch 的標準測試資料字典。"""
    return {
        "genre": "ballad",
        "mood": "romantic, nostalgic",
        "visual_style": "Pastel Watercolor",
        "color_palette": ["soft_pink", "light_blue", "cream"],
        "background_prompt": "pastel watercolor dreamy landscape, soft clouds",
        "outfit_prompt": "white flowing dress, elegant",
        "scene_description": "溫柔的粉彩水彩風格，夢幻背景",
        "research_summary": "這首情歌帶有懷舊感，適合柔和的視覺風格",
    }


@pytest.fixture
def sample_song_spec_data(sample_song_research_data) -> dict:
    """提供 SongSpec 的標準測試資料字典（含巢狀 SongResearch）。"""
    return {
        "title": "愛我的人和我愛的人",
        "artist": "測試歌手",
        "language": "zh-TW",
        "research": sample_song_research_data,
        "created_at": "2026-03-06T12:00:00",
    }


@pytest.fixture
def sample_copy_spec_data() -> dict:
    """提供 CopySpec 的標準測試資料字典。"""
    return {
        "title": "【虛擬歌手】愛我的人和我愛的人 MV",
        "description": "這是一首感人的情歌，帶有懷舊氛圍。\n\n#虛擬歌手 #情歌",
        "tags": ["虛擬歌手", "情歌", "MV", "AI"],
    }


@pytest.fixture
def sample_precheck_result_data() -> dict:
    """提供 PrecheckResult 的標準測試資料字典。"""
    return {
        "passed": True,
        "checks": {
            "image_exists": True,
            "audio_exists": True,
            "disk_space": True,
            "sadtalker_available": True,
            "ffmpeg_available": True,
        },
        "warnings": [],
        "gemini_score": 85,
        "gemini_feedback": "圖片與音樂搭配良好",
    }


@pytest.fixture
def sample_project_state_data(
    sample_song_spec_data, sample_copy_spec_data, sample_precheck_result_data
) -> dict:
    """提供 ProjectState 的完整測試資料字典。"""
    return {
        "project_id": "test-project-001",
        "source_audio": "data/singer_agent/inbox/test.mp3",
        "status": "completed",
        "metadata": {"duration": 180, "sample_rate": 44100},
        "song_spec": sample_song_spec_data,
        "copy_spec": sample_copy_spec_data,
        "background_image": "data/singer_agent/backgrounds/test-project-001.png",
        "composite_image": "data/singer_agent/composites/test-project-001.png",
        "precheck_result": sample_precheck_result_data,
        "final_video": "data/singer_agent/videos/test-project-001.mp4",
        "render_mode": "sadtalker",
        "error_message": "",
        "created_at": "2026-03-06T12:00:00",
        "completed_at": "2026-03-06T12:30:00",
    }


@pytest.fixture
def stub_mp3_path(tmp_path) -> Path:
    """建立一個假的 MP3 檔案供測試使用。"""
    mp3_file = tmp_path / "test_song.mp3"
    # 寫入最小化的假 MP3 header bytes
    mp3_file.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    return mp3_file


@pytest.fixture
def stub_png_path(tmp_path) -> Path:
    """建立一個假的 PNG 檔案供測試使用。"""
    png_file = tmp_path / "avatar.png"
    # 最小化的 PNG magic bytes
    png_file.write_bytes(
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR"  # IHDR chunk
        b"\x00\x00\x00\x01"    # width = 1
        b"\x00\x00\x00\x01"    # height = 1
        b"\x08\x02"             # bit depth = 8, color type = RGB
        b"\x00\x00\x00"        # compression, filter, interlace
        b"\x90wS\xde"          # CRC
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return png_file
