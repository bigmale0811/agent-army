# -*- coding: utf-8 -*-
"""
DEV-11: video_renderer.py 測試（V2.1 — EDTalk / MuseTalk 雙引擎）。

測試覆蓋：
- VideoRenderer 初始化（EDTalk / MuseTalk 設定）
- dry_run 回傳 (path, "dry_run")
- EDTalk subprocess 呼叫（mock subprocess.run）
- EDTalk venv/demo 不存在時 raise FileNotFoundError
- EDTalk 推論失敗時 raise RuntimeError
- MuseTalk subprocess 呼叫（mock subprocess.run）
- MuseTalk YAML 配置生成
- MuseTalk 輸出路徑處理
- MuseTalk 情緒警告
- FFmpeg 降級路徑
- pre_launch_cleanup VRAM 清理
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _create_file(path: Path, content: bytes = b"\x00" * 100):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class TestVideoRendererInit:
    def test_default_uses_config_paths(self):
        """預設使用 config 的 EDTalk 路徑。"""
        from src.singer_agent.video_renderer import VideoRenderer
        vr = VideoRenderer()
        assert vr.edtalk_dir is not None
        assert vr.ffmpeg_bin is not None

    def test_custom_edtalk_dir(self, tmp_path):
        """可注入自訂 EDTalk 路徑。"""
        from src.singer_agent.video_renderer import VideoRenderer
        vr = VideoRenderer(
            edtalk_dir=tmp_path / "edtalk",
            ffmpeg_bin=tmp_path / "ffmpeg.exe",
        )
        assert vr.edtalk_dir == tmp_path / "edtalk"
        assert vr.ffmpeg_bin == tmp_path / "ffmpeg.exe"

    def test_custom_musetalk_dir(self, tmp_path):
        """可注入自訂 MuseTalk 路徑。"""
        from src.singer_agent.video_renderer import VideoRenderer
        vr = VideoRenderer(
            musetalk_dir=tmp_path / "musetalk",
        )
        assert vr.musetalk_dir == tmp_path / "musetalk"

    def test_renderer_selection_default(self):
        """預設渲染引擎由 config 決定。"""
        from src.singer_agent.video_renderer import VideoRenderer
        vr = VideoRenderer()
        assert vr.renderer in ("edtalk", "musetalk")

    def test_renderer_selection_override(self):
        """可透過建構參數覆寫渲染引擎。"""
        from src.singer_agent.video_renderer import VideoRenderer
        vr = VideoRenderer(renderer="musetalk")
        assert vr.renderer == "musetalk"


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


class TestRenderEdtalk:
    """EDTalk subprocess 呼叫測試。"""

    def test_edtalk_success_returns_edtalk_mode(self, tmp_path):
        """EDTalk 正常完成時回傳 'edtalk' 模式。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"

        # 建立 EDTalk 環境檔案
        edtalk_dir = tmp_path / "edtalk"
        python_exe = edtalk_dir / "edtalk_env" / "Scripts" / "python.exe"
        demo_script = edtalk_dir / "demo_EDTalk_A_using_predefined_exp_weights.py"
        pose_video = edtalk_dir / "test_data" / "pose_source1.mp4"
        _create_file(python_exe)
        _create_file(demo_script)
        _create_file(pose_video)

        def run_side_effect(*args, **kwargs):
            # 模擬 EDTalk 產出 mp4
            edtalk_output = edtalk_dir / "res" / f"singer_{out.stem}.mp4"
            _create_file(edtalk_output, b"\xff" * 500)
            return MagicMock(returncode=0, stdout="ok", stderr="")

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=run_side_effect), \
             patch("src.singer_agent.video_renderer.config") as mock_config:
            mock_config.EDTALK_DIR = edtalk_dir
            mock_config.EDTALK_PYTHON = python_exe
            mock_config.EDTALK_DEMO_SCRIPT = demo_script
            mock_config.EDTALK_POSE_VIDEO = pose_video
            mock_config.FFMPEG_BIN = tmp_path / "ffmpeg"
            mock_config.COMFYUI_URL = "http://localhost:8188"

            vr = VideoRenderer(edtalk_dir=edtalk_dir)
            # 注入 mock 路徑
            vr._edtalk_python = python_exe
            vr._edtalk_demo = demo_script
            vr._pose_video = pose_video
            path, mode = vr.render(img, audio, out, exp_type="sad")

        assert mode == "edtalk"
        assert path == out
        assert out.exists()

    def test_edtalk_passes_exp_type(self, tmp_path):
        """EDTalk 命令包含 --exp_type 參數。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"

        edtalk_dir = tmp_path / "edtalk"
        python_exe = edtalk_dir / "edtalk_env" / "Scripts" / "python.exe"
        demo_script = edtalk_dir / "demo_EDTalk_A_using_predefined_exp_weights.py"
        pose_video = edtalk_dir / "test_data" / "pose_source1.mp4"
        _create_file(python_exe)
        _create_file(demo_script)
        _create_file(pose_video)

        def run_side_effect(*args, **kwargs):
            edtalk_output = edtalk_dir / "res" / f"singer_{out.stem}.mp4"
            _create_file(edtalk_output, b"\xff" * 500)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=run_side_effect) as mock_run:
            vr = VideoRenderer(edtalk_dir=edtalk_dir)
            vr._edtalk_python = python_exe
            vr._edtalk_demo = demo_script
            vr._pose_video = pose_video
            vr.render(img, audio, out, exp_type="happy")

        cmd = mock_run.call_args[0][0]
        assert "--exp_type" in cmd
        assert "happy" in cmd

    def test_edtalk_python_missing_raises(self, tmp_path):
        """EDTalk venv Python 不存在時 raise FileNotFoundError。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        vr = VideoRenderer(edtalk_dir=tmp_path / "edtalk")
        vr._edtalk_python = tmp_path / "nonexistent" / "python.exe"
        vr._edtalk_demo = tmp_path / "demo.py"

        with pytest.raises(FileNotFoundError, match="EDTalk venv Python"):
            vr.render(img, audio, out)

    def test_edtalk_demo_missing_raises(self, tmp_path):
        """EDTalk demo 腳本不存在時 raise FileNotFoundError。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        python_exe = tmp_path / "python.exe"
        _create_file(python_exe)

        vr = VideoRenderer(edtalk_dir=tmp_path / "edtalk")
        vr._edtalk_python = python_exe
        vr._edtalk_demo = tmp_path / "nonexistent_demo.py"

        with pytest.raises(FileNotFoundError, match="EDTalk demo"):
            vr.render(img, audio, out)

    def test_edtalk_failure_raises_runtime_error(self, tmp_path):
        """EDTalk 推論失敗時 raise RuntimeError。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"

        edtalk_dir = tmp_path / "edtalk"
        python_exe = edtalk_dir / "edtalk_env" / "Scripts" / "python.exe"
        demo_script = edtalk_dir / "demo.py"
        pose_video = edtalk_dir / "test_data" / "pose.mp4"
        _create_file(python_exe)
        _create_file(demo_script)
        _create_file(pose_video)

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="", stderr="Error")):
            vr = VideoRenderer(edtalk_dir=edtalk_dir)
            vr._edtalk_python = python_exe
            vr._edtalk_demo = demo_script
            vr._pose_video = pose_video
            with pytest.raises(RuntimeError, match="EDTalk 推論失敗"):
                vr.render(img, audio, out)

    def test_edtalk_timeout_raises_runtime_error(self, tmp_path):
        """EDTalk 推論超時時 raise RuntimeError。"""
        import subprocess as sp
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"

        edtalk_dir = tmp_path / "edtalk"
        python_exe = edtalk_dir / "python.exe"
        demo_script = edtalk_dir / "demo.py"
        pose_video = edtalk_dir / "pose.mp4"
        _create_file(python_exe)
        _create_file(demo_script)
        _create_file(pose_video)

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=sp.TimeoutExpired(cmd="test", timeout=600)):
            vr = VideoRenderer(edtalk_dir=edtalk_dir)
            vr._edtalk_python = python_exe
            vr._edtalk_demo = demo_script
            vr._pose_video = pose_video
            with pytest.raises(RuntimeError, match="超時"):
                vr.render(img, audio, out)


class TestRenderMusetalk:
    """MuseTalk subprocess 呼叫測試（V2.1）。"""

    def _make_renderer(self, tmp_path):
        """建立 MuseTalk 測試用 VideoRenderer。"""
        from src.singer_agent.video_renderer import VideoRenderer

        musetalk_dir = tmp_path / "musetalk"
        python_exe = musetalk_dir / "musetalk_env" / "Scripts" / "python.exe"
        _create_file(python_exe)

        vr = VideoRenderer(
            musetalk_dir=musetalk_dir,
            renderer="musetalk",
        )
        vr._musetalk_python = python_exe
        vr._musetalk_version = "v15"
        return vr, musetalk_dir

    def test_musetalk_subprocess_call(self, tmp_path):
        """MuseTalk 正常完成時回傳 'musetalk' 模式，且命令正確。"""
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"
        vr, musetalk_dir = self._make_renderer(tmp_path)

        def run_side_effect(*args, **kwargs):
            # 模擬 MuseTalk 產出 mp4（在 result_dir/v15/ 下）
            result_dir = Path(kwargs.get("cwd", "."))
            # subprocess.run 的 cwd 是 musetalk_dir，但產出在 result_dir 參數
            cmd = args[0]
            for i, arg in enumerate(cmd):
                if arg == "--result_dir":
                    rd = Path(cmd[i + 1])
                    mp4 = rd / "v15" / "output.mp4"
                    _create_file(mp4, b"\xff" * 500)
                    break
            return MagicMock(returncode=0, stdout="ok", stderr="")

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=run_side_effect) as mock_run, \
             patch.object(type(vr), "_pre_launch_cleanup"):
            path, mode = vr.render(img, audio, out)

        assert mode == "musetalk"
        assert path == out
        assert out.exists()

        # 驗證 subprocess 命令包含正確參數
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd
        assert "scripts.inference" in cmd
        assert "--inference_config" in cmd
        assert "--use_float16" in cmd

    def test_musetalk_dry_run_skips_subprocess(self, tmp_path):
        """dry_run 模式不呼叫 MuseTalk subprocess。"""
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"
        vr, _ = self._make_renderer(tmp_path)

        with patch("src.singer_agent.video_renderer.subprocess.run") as mock_run:
            path, mode = vr.render(img, audio, out, dry_run=True)

        assert mode == "dry_run"
        mock_run.assert_not_called()

    def test_musetalk_yaml_config_generation(self, tmp_path):
        """MuseTalk 渲染時產生正確的 YAML 配置。"""
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"
        vr, _ = self._make_renderer(tmp_path)

        yaml_contents = []

        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            for i, arg in enumerate(cmd):
                if arg == "--inference_config":
                    yaml_path = Path(cmd[i + 1])
                    if yaml_path.exists():
                        yaml_contents.append(
                            yaml_path.read_text(encoding="utf-8")
                        )
                if arg == "--result_dir":
                    rd = Path(cmd[i + 1])
                    _create_file(rd / "v15" / "out.mp4", b"\xff" * 100)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=run_side_effect), \
             patch.object(type(vr), "_pre_launch_cleanup"):
            vr.render(img, audio, out)

        assert len(yaml_contents) == 1
        yaml_text = yaml_contents[0]
        assert "singer_task:" in yaml_text
        assert "video_path:" in yaml_text
        assert "audio_path:" in yaml_text

    def test_musetalk_failure_raises_runtime_error(self, tmp_path):
        """MuseTalk 推論失敗時 raise RuntimeError。"""
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"
        vr, _ = self._make_renderer(tmp_path)

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   return_value=MagicMock(
                       returncode=1, stdout="", stderr="CUDA OOM"
                   )), \
             patch.object(type(vr), "_pre_launch_cleanup"):
            with pytest.raises(RuntimeError, match="MuseTalk 推論失敗"):
                vr.render(img, audio, out)

    def test_musetalk_output_path_handling(self, tmp_path):
        """MuseTalk MP4 從 result_dir 搬移到 output_path。"""
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "final_output" / "my_video.mp4"
        vr, _ = self._make_renderer(tmp_path)

        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            for i, arg in enumerate(cmd):
                if arg == "--result_dir":
                    rd = Path(cmd[i + 1])
                    # MuseTalk 產出在 version 子目錄
                    _create_file(
                        rd / "v15" / "singer_output.mp4",
                        b"\xff" * 800,
                    )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=run_side_effect), \
             patch.object(type(vr), "_pre_launch_cleanup"):
            path, mode = vr.render(img, audio, out)

        assert path == out
        assert out.exists()
        # 確認檔案大小正確搬移
        assert out.stat().st_size == 800

    def test_musetalk_emotion_warning(self, tmp_path, caplog):
        """MuseTalk 遇到非 neutral 情緒時記錄 warning。"""
        import logging
        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"
        vr, _ = self._make_renderer(tmp_path)

        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            for i, arg in enumerate(cmd):
                if arg == "--result_dir":
                    rd = Path(cmd[i + 1])
                    _create_file(rd / "v15" / "out.mp4", b"\xff" * 100)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=run_side_effect), \
             patch.object(type(vr), "_pre_launch_cleanup"), \
             caplog.at_level(logging.WARNING):
            vr.render(img, audio, out, exp_type="happy")

        assert any("MuseTalk 不支援情緒控制" in r.message for r in caplog.records)

    def test_musetalk_python_missing_raises(self, tmp_path):
        """MuseTalk venv Python 不存在時 raise FileNotFoundError。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "video.mp4"

        vr = VideoRenderer(
            musetalk_dir=tmp_path / "musetalk",
            renderer="musetalk",
        )
        vr._musetalk_python = tmp_path / "nonexistent" / "python.exe"

        with patch.object(type(vr), "_pre_launch_cleanup"):
            with pytest.raises(FileNotFoundError, match="MuseTalk venv Python"):
                vr.render(img, audio, out)

    def test_musetalk_timeout_raises(self, tmp_path):
        """MuseTalk 推論超時時 raise RuntimeError。"""
        import subprocess as sp

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"
        vr, _ = self._make_renderer(tmp_path)

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=sp.TimeoutExpired(cmd="test", timeout=600)), \
             patch.object(type(vr), "_pre_launch_cleanup"):
            with pytest.raises(RuntimeError, match="超時"):
                vr.render(img, audio, out)


class TestRenderFfmpeg:
    """FFmpeg 靜態渲染測試。"""

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
                edtalk_dir=tmp_path / "edtalk",
                ffmpeg_bin=tmp_path / "ffmpeg",
            )
            path, mode = vr._render_ffmpeg(img, audio, out)

        assert mode == "ffmpeg_static"
        assert path == out


class TestPreLaunchCleanup:
    """EDTalk 啟動前 VRAM 清理。"""

    def test_pre_launch_cleanup_called_before_render(self, tmp_path):
        """EDTalk 渲染前呼叫 _pre_launch_cleanup。"""
        from src.singer_agent.video_renderer import VideoRenderer

        img = _create_file(tmp_path / "composite.png")
        audio = _create_file(tmp_path / "audio.mp3")
        out = tmp_path / "output" / "video.mp4"

        edtalk_dir = tmp_path / "edtalk"
        python_exe = edtalk_dir / "python.exe"
        demo_script = edtalk_dir / "demo.py"
        pose_video = edtalk_dir / "pose.mp4"
        _create_file(python_exe)
        _create_file(demo_script)
        _create_file(pose_video)

        def run_side_effect(*args, **kwargs):
            edtalk_output = edtalk_dir / "res" / f"singer_{out.stem}.mp4"
            _create_file(edtalk_output, b"\xff" * 500)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("src.singer_agent.video_renderer.subprocess.run",
                   side_effect=run_side_effect), \
             patch.object(
                 VideoRenderer, "_pre_launch_cleanup"
             ) as mock_cleanup:
            vr = VideoRenderer(edtalk_dir=edtalk_dir)
            vr._edtalk_python = python_exe
            vr._edtalk_demo = demo_script
            vr._pose_video = pose_video
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
        """_pre_launch_cleanup 呼叫所有 VRAM 清理函式。"""
        from src.singer_agent.video_renderer import VideoRenderer

        vr = VideoRenderer(
            edtalk_dir=tmp_path / "edtalk",
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


class TestMoodToExpType:
    """V2.0 情緒映射測試。"""

    def test_sad_chinese(self):
        """中文 '感傷' 映射到 'sad'。"""
        from src.singer_agent.audio_preprocessor import mood_to_exp_type
        assert mood_to_exp_type("感傷") == "sad"

    def test_sad_english(self):
        """英文 'melancholic' 映射到 'sad'。"""
        from src.singer_agent.audio_preprocessor import mood_to_exp_type
        assert mood_to_exp_type("melancholic") == "sad"

    def test_happy_chinese(self):
        """中文 '開心' 映射到 'happy'。"""
        from src.singer_agent.audio_preprocessor import mood_to_exp_type
        assert mood_to_exp_type("開心") == "happy"

    def test_angry_chinese(self):
        """中文 '憤怒' 映射到 'angry'。"""
        from src.singer_agent.audio_preprocessor import mood_to_exp_type
        assert mood_to_exp_type("憤怒") == "angry"

    def test_surprised_chinese(self):
        """中文 '驚訝' 映射到 'surprised'。"""
        from src.singer_agent.audio_preprocessor import mood_to_exp_type
        assert mood_to_exp_type("驚訝") == "surprised"

    def test_fear_english(self):
        """英文 'scared' 映射到 'fear'。"""
        from src.singer_agent.audio_preprocessor import mood_to_exp_type
        assert mood_to_exp_type("scared") == "fear"

    def test_default_neutral(self):
        """無匹配時回傳 'neutral'。"""
        from src.singer_agent.audio_preprocessor import mood_to_exp_type
        assert mood_to_exp_type("unknown mood") == "neutral"

    def test_empty_returns_neutral(self):
        """空字串回傳 'neutral'。"""
        from src.singer_agent.audio_preprocessor import mood_to_exp_type
        assert mood_to_exp_type("") == "neutral"

    def test_all_8_emotions_covered(self):
        """確認 8 種 EDTalk 情緒全部有對應。"""
        from src.singer_agent.audio_preprocessor import EMOTION_EDTALK_MAP
        edtalk_types = set(EMOTION_EDTALK_MAP.values())
        expected = {"angry", "contempt", "disgusted", "fear",
                    "happy", "sad", "surprised", "neutral"}
        assert edtalk_types == expected
