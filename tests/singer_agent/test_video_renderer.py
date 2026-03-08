# -*- coding: utf-8 -*-
"""
DEV-11: video_renderer.py 測試。

測試覆蓋：
- VideoRenderer 初始化
- dry_run 回傳 (path, "dry_run")
- SadTalker Popen + 輪詢模式（mock subprocess）
- SadTalker venv 不存在時 raise FileNotFoundError
- _find_new_mp4 靜態方法
- _terminate_process 靜態方法
- _poll_for_mp4 輪詢邏輯
"""
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


def _create_file(path: Path, content: bytes = b"\x00" * 100):
    path.parent.mkdir(parents=True, exist_ok=True)
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
    """SadTalker Popen + 輪詢模式測試。"""

    def test_sadtalker_success_returns_sadtalker_mode(self, tmp_path):
        """SadTalker 正常退出時回傳 'sadtalker' 模式。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"

        # 建立 SadTalker venv python.exe
        sadtalker_dir = tmp_path / "sadtalker"
        python_exe = sadtalker_dir / "venv" / "Scripts" / "python.exe"
        _create_file(python_exe)

        # Mock Popen：process 立即退出 returncode=0
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # 立即退出

        # SadTalker 正常退出後，mp4 應出現在 result_dir
        def popen_side_effect(*args, **kwargs):
            # 模擬 SadTalker 產出 mp4
            _create_file(out.parent / "2026_03_07_12.00.00.mp4", b"\xff" * 500)
            return mock_proc

        with patch("src.singer_agent.video_renderer.subprocess.Popen",
                   side_effect=popen_side_effect):
            vr = VideoRenderer(
                sadtalker_dir=sadtalker_dir,
                ffmpeg_bin=tmp_path / "ffmpeg",
            )
            path, mode = vr.render(img, audio, out)

        assert mode == "sadtalker"
        assert path == out
        assert out.exists()

    def test_sadtalker_calls_popen(self, tmp_path):
        """呼叫 subprocess.Popen 執行 SadTalker。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"

        sadtalker_dir = tmp_path / "sadtalker"
        python_exe = sadtalker_dir / "venv" / "Scripts" / "python.exe"
        _create_file(python_exe)

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0

        def popen_side_effect(*args, **kwargs):
            _create_file(out.parent / "result.mp4", b"\xff" * 500)
            return mock_proc

        with patch("src.singer_agent.video_renderer.subprocess.Popen",
                   side_effect=popen_side_effect) as mock_popen:
            vr = VideoRenderer(
                sadtalker_dir=sadtalker_dir,
                ffmpeg_bin=tmp_path / "ffmpeg",
            )
            vr.render(img, audio, out)

        assert mock_popen.called
        # 確認 cmd 包含 inference.py 和 --still
        cmd_arg = mock_popen.call_args[0][0]
        assert any("inference.py" in str(a) for a in cmd_arg)
        assert "--still" in cmd_arg
        assert "--verbose" in cmd_arg

    def test_sadtalker_venv_missing_raises(self, tmp_path):
        """SadTalker venv 不存在時直接 raise FileNotFoundError。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        # sadtalker_dir 存在但 venv/python.exe 不存在
        vr = VideoRenderer(
            sadtalker_dir=tmp_path / "sadtalker",
            ffmpeg_bin=tmp_path / "ffmpeg",
        )

        with pytest.raises(FileNotFoundError, match="venv Python"):
            vr.render(img, audio, out)

    def test_sadtalker_process_error_raises(self, tmp_path):
        """SadTalker process 非零退出碼時 raise CalledProcessError。"""
        import subprocess as sp
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"

        sadtalker_dir = tmp_path / "sadtalker"
        _create_file(sadtalker_dir / "venv" / "Scripts" / "python.exe")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # 非零退出碼
        mock_proc.args = ["python", "inference.py"]

        with patch("src.singer_agent.video_renderer.subprocess.Popen",
                   return_value=mock_proc):
            vr = VideoRenderer(
                sadtalker_dir=sadtalker_dir,
                ffmpeg_bin=tmp_path / "ffmpeg",
            )
            with pytest.raises(sp.CalledProcessError):
                vr.render(img, audio, out)


class TestFindNewMp4:
    """_find_new_mp4 靜態方法測試。"""

    def test_finds_root_mp4(self, tmp_path):
        """在根目錄找到新的 mp4。"""
        from src.singer_agent.video_renderer import VideoRenderer

        _create_file(tmp_path / "new_video.mp4", b"\xff" * 100)
        result = VideoRenderer._find_new_mp4(tmp_path, set())
        assert result is not None
        assert result.name == "new_video.mp4"

    def test_ignores_pre_existing(self, tmp_path):
        """排除啟動前已存在的 mp4。"""
        from src.singer_agent.video_renderer import VideoRenderer

        old = _create_file(tmp_path / "old.mp4", b"\xff" * 100)
        result = VideoRenderer._find_new_mp4(tmp_path, {old})
        assert result is None

    def test_finds_subdir_mp4(self, tmp_path):
        """在子目錄中找到新的 mp4。"""
        from src.singer_agent.video_renderer import VideoRenderer

        subdir = tmp_path / "2026_03_07"
        _create_file(subdir / "result.mp4", b"\xff" * 100)
        result = VideoRenderer._find_new_mp4(tmp_path, set())
        assert result is not None
        assert result.name == "result.mp4"

    def test_prefers_root_over_subdir(self, tmp_path):
        """優先回傳根目錄的 mp4。"""
        from src.singer_agent.video_renderer import VideoRenderer

        _create_file(tmp_path / "root.mp4", b"\xff" * 100)
        subdir = tmp_path / "sub"
        _create_file(subdir / "sub.mp4", b"\xff" * 100)

        result = VideoRenderer._find_new_mp4(tmp_path, set())
        assert result is not None
        assert result.name == "root.mp4"

    def test_returns_none_when_empty(self, tmp_path):
        """沒有 mp4 時回傳 None。"""
        from src.singer_agent.video_renderer import VideoRenderer

        result = VideoRenderer._find_new_mp4(tmp_path, set())
        assert result is None


class TestTerminateProcess:
    """_terminate_process 靜態方法測試。"""

    def test_no_action_if_already_exited(self):
        """process 已退出時不做任何動作。"""
        from src.singer_agent.video_renderer import VideoRenderer

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        VideoRenderer._terminate_process(mock_proc)
        mock_proc.terminate.assert_not_called()

    def test_terminate_called(self):
        """嘗試 terminate 後 wait。"""
        from src.singer_agent.video_renderer import VideoRenderer

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # 仍在執行
        mock_proc.pid = 12345
        mock_proc.wait.return_value = None

        # terminate 後 poll 回傳已退出
        def terminate_effect():
            mock_proc.poll.return_value = 0

        mock_proc.terminate.side_effect = terminate_effect
        VideoRenderer._terminate_process(mock_proc)
        mock_proc.terminate.assert_called_once()

    def test_kill_on_timeout(self):
        """terminate 超時後 kill。"""
        import subprocess as sp
        from src.singer_agent.video_renderer import VideoRenderer

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 12345
        mock_proc.wait.side_effect = [
            sp.TimeoutExpired(cmd="test", timeout=15),
            None,
        ]

        VideoRenderer._terminate_process(mock_proc)
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()


class TestRenderFfmpeg:
    """FFmpeg 靜態渲染測試（直接呼叫 _render_ffmpeg）。"""

    def test_ffmpeg_returns_mode(self, tmp_path):
        """FFmpeg 渲染回傳 'ffmpeg_static' 模式。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        def run_side_effect(*args, **kwargs):
            out.write_bytes(b"\x00" * 50)
            return MagicMock(returncode=0)

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=run_side_effect):
            vr = VideoRenderer(
                sadtalker_dir=tmp_path / "sadtalker",
                ffmpeg_bin=tmp_path / "ffmpeg",
            )
            path, mode = vr._render_ffmpeg(img, audio, out)

        assert mode == "ffmpeg_static"
        assert path == out


class TestPreLaunchCleanup:
    """DEV-4: SadTalker 啟動前 VRAM 清理。"""

    def test_pre_launch_cleanup_called_before_popen(self, tmp_path):
        """SadTalker 啟動前呼叫 _pre_launch_cleanup。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"

        sadtalker_dir = tmp_path / "sadtalker"
        _create_file(sadtalker_dir / "venv" / "Scripts" / "python.exe")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0

        def popen_side_effect(*args, **kwargs):
            _create_file(out.parent / "result.mp4", b"\xff" * 500)
            return mock_proc

        with patch("src.singer_agent.video_renderer.subprocess.Popen",
                   side_effect=popen_side_effect), \
             patch.object(
                 VideoRenderer, "_pre_launch_cleanup"
             ) as mock_cleanup:
            vr = VideoRenderer(
                sadtalker_dir=sadtalker_dir,
                ffmpeg_bin=tmp_path / "ffmpeg",
            )
            vr.render(img, audio, out)
            mock_cleanup.assert_called_once()

    def test_pre_launch_cleanup_not_called_in_dry_run(self, tmp_path):
        """dry_run 不呼叫 _pre_launch_cleanup。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        with patch.object(
            VideoRenderer, "_pre_launch_cleanup"
        ) as mock_cleanup:
            vr = VideoRenderer()
            vr.render(img, audio, out, dry_run=True)
            mock_cleanup.assert_not_called()

    def test_pre_launch_cleanup_calls_vram_functions(self, tmp_path):
        """_pre_launch_cleanup 呼叫 free_comfyui + force_cleanup + log + check。"""
        from src.singer_agent.video_renderer import VideoRenderer

        vr = VideoRenderer(
            sadtalker_dir=tmp_path / "sadtalker",
            ffmpeg_bin=tmp_path / "ffmpeg",
        )

        with patch("src.singer_agent.vram_monitor.free_comfyui_models") as m_free, \
             patch("src.singer_agent.vram_monitor.force_cleanup") as m_force, \
             patch("src.singer_agent.vram_monitor.log_vram") as m_log, \
             patch("src.singer_agent.vram_monitor.check_vram_safety") as m_check:
            vr._pre_launch_cleanup()
            m_free.assert_called_once()
            m_force.assert_called_once()
            m_log.assert_called_once()
            m_check.assert_called_once()
