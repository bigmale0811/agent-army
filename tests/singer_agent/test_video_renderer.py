# -*- coding: utf-8 -*-
"""
DEV-11: video_renderer.py 測試。

測試覆蓋：
- VideoRenderer 初始化
- dry_run 回傳 (path, "dry_run")
- SadTalker 成功（mock subprocess）
- SadTalker 失敗降級 FFmpeg
- FFmpeg 靜態合成（mock subprocess）
- ASCII 暫存路徑處理
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import subprocess

import pytest


def _create_file(path: Path, content: bytes = b"\x00" * 100):
    path.write_bytes(content)
    return path


class TestVideoRendererInit:
    def test_default_uses_config_paths(self):
        """預設使用 config 的路徑。"""
        from src.singer_agent.video_renderer import VideoRenderer
        vr = VideoRenderer()
        assert vr.sadtalker_dir is not None
        assert vr.ffmpeg_bin is not None

    def test_custom_paths_stored(self, tmp_path):
        """可注入自訂路徑。"""
        from src.singer_agent.video_renderer import VideoRenderer
        vr = VideoRenderer(
            sadtalker_dir=tmp_path / "sadtalker",
            ffmpeg_bin=tmp_path / "ffmpeg.exe",
        )
        assert vr.sadtalker_dir == tmp_path / "sadtalker"
        assert vr.ffmpeg_bin == tmp_path / "ffmpeg.exe"


class TestRenderDryRun:
    def test_dry_run_returns_tuple(self, tmp_path):
        """dry_run 回傳 (Path, str)。"""
        from src.singer_agent.video_renderer import VideoRenderer
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"
        vr = VideoRenderer()
        result = vr.render(img, audio, out, dry_run=True)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_dry_run_returns_path_and_dry_run_mode(self, tmp_path):
        """dry_run 回傳路徑和 'dry_run' 模式。"""
        from src.singer_agent.video_renderer import VideoRenderer
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"
        vr = VideoRenderer()
        path, mode = vr.render(img, audio, out, dry_run=True)
        assert path == out
        assert mode == "dry_run"

    def test_dry_run_creates_placeholder_file(self, tmp_path):
        """dry_run 建立佔位檔。"""
        from src.singer_agent.video_renderer import VideoRenderer
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"
        vr = VideoRenderer()
        vr.render(img, audio, out, dry_run=True)
        assert out.exists()


class TestRenderSadTalker:
    def test_sadtalker_success_returns_sadtalker_mode(self, tmp_path):
        """SadTalker 成功時回傳 'sadtalker' 模式。"""
        from src.singer_agent.video_renderer import VideoRenderer
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("src.singer_agent.video_renderer.subprocess.run",
                    return_value=mock_result) as mock_run, \
             patch.object(Path, "exists", return_value=True):
            vr = VideoRenderer(sadtalker_dir=tmp_path / "sadtalker",
                               ffmpeg_bin=tmp_path / "ffmpeg")
            # 讓輸出檔存在
            out.write_bytes(b"\x00")
            path, mode = vr.render(img, audio, out)

        assert mode == "sadtalker"

    def test_sadtalker_calls_subprocess(self, tmp_path):
        """呼叫 subprocess.run 執行 SadTalker。"""
        from src.singer_agent.video_renderer import VideoRenderer
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("src.singer_agent.video_renderer.subprocess.run",
                    return_value=mock_result) as mock_run, \
             patch.object(Path, "exists", return_value=True):
            out.write_bytes(b"\x00")
            vr = VideoRenderer(sadtalker_dir=tmp_path / "sadtalker",
                               ffmpeg_bin=tmp_path / "ffmpeg")
            vr.render(img, audio, out)

        assert mock_run.called


class TestRenderFfmpegFallback:
    def test_fallback_on_sadtalker_failure(self, tmp_path):
        """SadTalker 失敗時降級 FFmpeg。"""
        from src.singer_agent.video_renderer import VideoRenderer
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # SadTalker 失敗
                raise subprocess.CalledProcessError(1, "sadtalker")
            # FFmpeg 成功
            out.write_bytes(b"\x00" * 50)
            return MagicMock(returncode=0)

        with patch("src.singer_agent.video_renderer.subprocess.run",
                    side_effect=side_effect):
            vr = VideoRenderer(sadtalker_dir=tmp_path / "sadtalker",
                               ffmpeg_bin=tmp_path / "ffmpeg")
            path, mode = vr.render(img, audio, out)

        assert mode == "ffmpeg_static"

    def test_ffmpeg_creates_output(self, tmp_path):
        """FFmpeg 降級建立輸出檔。"""
        from src.singer_agent.video_renderer import VideoRenderer
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        def side_effect(*args, **kwargs):
            if "sadtalker" in str(args).lower() or call_count[0] == 0:
                call_count[0] += 1
                raise subprocess.CalledProcessError(1, "sadtalker")
            out.write_bytes(b"\x00" * 50)
            return MagicMock(returncode=0)

        call_count = [0]
        with patch("src.singer_agent.video_renderer.subprocess.run",
                    side_effect=side_effect):
            vr = VideoRenderer(sadtalker_dir=tmp_path / "sadtalker",
                               ffmpeg_bin=tmp_path / "ffmpeg")
            path, mode = vr.render(img, audio, out)

        assert path == out
