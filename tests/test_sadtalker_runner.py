# -*- coding: utf-8 -*-
"""SadTalker Runner 單元測試

測試策略：全部 mock subprocess，不實際呼叫 SadTalker。
驗證：可用性檢查、影片生成、stdout 解析、降級邏輯。
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.singer_agent.sadtalker_runner import (
    is_sadtalker_available,
    generate_singing_video,
    _find_generated_video,
    _find_latest_video,
)


# =========================================================
# is_sadtalker_available 測試
# =========================================================

class TestIsSadTalkerAvailable:
    """檢測 SadTalker 可用性"""

    def test_available_when_all_exist(self, tmp_path):
        """inference.py + checkpoints 存在 → True"""
        inference = tmp_path / "inference.py"
        inference.touch()
        checkpoints = tmp_path / "checkpoints"
        checkpoints.mkdir()
        (checkpoints / "model.safetensors").touch()

        with patch("src.singer_agent.sadtalker_runner.SADTALKER_INFERENCE", inference), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_CHECKPOINTS", checkpoints):
            assert is_sadtalker_available() is True

    def test_unavailable_when_inference_missing(self, tmp_path):
        """inference.py 不存在 → False"""
        with patch("src.singer_agent.sadtalker_runner.SADTALKER_INFERENCE",
                    tmp_path / "missing.py"):
            assert is_sadtalker_available() is False

    def test_unavailable_when_checkpoints_missing(self, tmp_path):
        """checkpoints 目錄不存在 → False"""
        inference = tmp_path / "inference.py"
        inference.touch()

        with patch("src.singer_agent.sadtalker_runner.SADTALKER_INFERENCE", inference), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_CHECKPOINTS",
                    tmp_path / "no_checkpoints"):
            assert is_sadtalker_available() is False

    def test_unavailable_when_no_model_files(self, tmp_path):
        """checkpoints 目錄為空 → False"""
        inference = tmp_path / "inference.py"
        inference.touch()
        checkpoints = tmp_path / "checkpoints"
        checkpoints.mkdir()

        with patch("src.singer_agent.sadtalker_runner.SADTALKER_INFERENCE", inference), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_CHECKPOINTS", checkpoints):
            assert is_sadtalker_available() is False

    def test_available_with_pth_files(self, tmp_path):
        """支援 .pth 模型檔案"""
        inference = tmp_path / "inference.py"
        inference.touch()
        checkpoints = tmp_path / "checkpoints"
        checkpoints.mkdir()
        (checkpoints / "model.pth").touch()

        with patch("src.singer_agent.sadtalker_runner.SADTALKER_INFERENCE", inference), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_CHECKPOINTS", checkpoints):
            assert is_sadtalker_available() is True


# =========================================================
# _find_generated_video 測試
# =========================================================

class TestFindGeneratedVideo:
    """從 SadTalker stdout 解析輸出影片路徑"""

    def test_parse_standard_output(self, tmp_path):
        """標準格式：The generated video is named: path.mp4"""
        video = tmp_path / "test.mp4"
        video.touch()
        stdout = f"Loading...\nThe generated video is named: {video}\nDone"

        with patch("src.singer_agent.sadtalker_runner.SADTALKER_DIR", tmp_path):
            result = _find_generated_video(stdout)
            assert result is not None
            assert result.endswith("test.mp4")

    def test_parse_without_colon(self, tmp_path):
        """不含冒號的格式"""
        video = tmp_path / "result.mp4"
        video.touch()
        stdout = f"The generated video is named {video}"

        with patch("src.singer_agent.sadtalker_runner.SADTALKER_DIR", tmp_path):
            result = _find_generated_video(stdout)
            assert result is not None

    def test_parse_relative_path(self, tmp_path):
        """相對路徑（在 SADTALKER_DIR 下找）"""
        results = tmp_path / "results"
        results.mkdir()
        video = results / "output.mp4"
        video.touch()
        stdout = "The generated video is named: results/output.mp4"

        with patch("src.singer_agent.sadtalker_runner.SADTALKER_DIR", tmp_path):
            result = _find_generated_video(stdout)
            assert result is not None

    def test_no_video_line(self):
        """沒有相關輸出 → None"""
        assert _find_generated_video("some random output\nno video here") is None

    def test_empty_stdout(self):
        """空 stdout → None"""
        assert _find_generated_video("") is None


# =========================================================
# _find_latest_video 測試
# =========================================================

class TestFindLatestVideo:
    """搜尋 results 目錄中最新的 .mp4"""

    def test_finds_latest(self, tmp_path):
        """找到最新的 .mp4"""
        (tmp_path / "old.mp4").touch()
        (tmp_path / "new.mp4").touch()
        result = _find_latest_video(tmp_path)
        assert result is not None
        assert result.endswith(".mp4")

    def test_empty_dir(self, tmp_path):
        """空目錄 → None"""
        assert _find_latest_video(tmp_path) is None

    def test_nonexistent_dir(self, tmp_path):
        """目錄不存在 → None"""
        assert _find_latest_video(tmp_path / "nope") is None

    def test_ignores_non_mp4(self, tmp_path):
        """忽略非 .mp4 檔案"""
        (tmp_path / "video.avi").touch()
        (tmp_path / "readme.txt").touch()
        assert _find_latest_video(tmp_path) is None


# =========================================================
# generate_singing_video 測試
# =========================================================

class TestGenerateSingingVideo:
    """主生成函式（mock subprocess）"""

    def test_missing_image_raises(self, tmp_path):
        """角色圖片不存在 → FileNotFoundError"""
        with pytest.raises(FileNotFoundError, match="角色圖片"):
            generate_singing_video(
                source_image=str(tmp_path / "missing.png"),
                driven_audio=str(tmp_path / "song.mp3"),
                output_path=str(tmp_path / "out.mp4"),
            )

    def test_missing_audio_raises(self, tmp_path):
        """音檔不存在 → FileNotFoundError"""
        img = tmp_path / "avatar.png"
        img.touch()
        with pytest.raises(FileNotFoundError, match="音檔"):
            generate_singing_video(
                source_image=str(img),
                driven_audio=str(tmp_path / "missing.mp3"),
                output_path=str(tmp_path / "out.mp4"),
            )

    def test_sadtalker_unavailable_raises(self, tmp_path):
        """SadTalker 不可用 → RuntimeError"""
        img = tmp_path / "avatar.png"
        img.touch()
        audio = tmp_path / "song.mp3"
        audio.touch()

        with patch("src.singer_agent.sadtalker_runner.is_sadtalker_available",
                    return_value=False):
            with pytest.raises(RuntimeError, match="不可用"):
                generate_singing_video(
                    source_image=str(img),
                    driven_audio=str(audio),
                    output_path=str(tmp_path / "out.mp4"),
                )

    def test_success_with_stdout_parsing(self, tmp_path):
        """成功：從 stdout 解析影片路徑"""
        img = tmp_path / "avatar.png"
        img.touch()
        audio = tmp_path / "song.mp3"
        audio.touch()
        output = tmp_path / "output.mp4"

        # 模擬 SadTalker 產出的影片
        result_dir = tmp_path / "results"
        result_dir.mkdir()
        generated = result_dir / "2024_01_01_12.00.00.mp4"
        generated.write_bytes(b"fake video data")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"The generated video is named: {generated}"
        mock_result.stderr = ""

        with patch("src.singer_agent.sadtalker_runner.is_sadtalker_available",
                    return_value=True), \
             patch("subprocess.run", return_value=mock_result), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_DIR", tmp_path), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_RESULT_DIR", result_dir):
            result = generate_singing_video(
                source_image=str(img),
                driven_audio=str(audio),
                output_path=str(output),
            )
            assert Path(result).name == "output.mp4"
            assert output.exists()

    def test_success_with_fallback_search(self, tmp_path):
        """成功：stdout 解析失敗，用最新 .mp4 備用策略"""
        img = tmp_path / "avatar.png"
        img.touch()
        audio = tmp_path / "song.mp3"
        audio.touch()
        output = tmp_path / "output.mp4"

        result_dir = tmp_path / "results"
        result_dir.mkdir()
        latest = result_dir / "latest.mp4"
        latest.write_bytes(b"fake video")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Done. No standard path line."
        mock_result.stderr = ""

        with patch("src.singer_agent.sadtalker_runner.is_sadtalker_available",
                    return_value=True), \
             patch("subprocess.run", return_value=mock_result), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_DIR", tmp_path), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_RESULT_DIR", result_dir):
            result = generate_singing_video(
                source_image=str(img),
                driven_audio=str(audio),
                output_path=str(output),
            )
            assert output.exists()

    def test_nonzero_returncode_raises(self, tmp_path):
        """SadTalker 回傳非零 exit code → RuntimeError"""
        img = tmp_path / "avatar.png"
        img.touch()
        audio = tmp_path / "song.mp3"
        audio.touch()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "CUDA out of memory"

        with patch("src.singer_agent.sadtalker_runner.is_sadtalker_available",
                    return_value=True), \
             patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="執行失敗"):
                generate_singing_video(
                    source_image=str(img),
                    driven_audio=str(audio),
                    output_path=str(tmp_path / "out.mp4"),
                )

    def test_timeout_raises(self, tmp_path):
        """SadTalker 超時 → RuntimeError"""
        import subprocess as sp

        img = tmp_path / "avatar.png"
        img.touch()
        audio = tmp_path / "song.mp3"
        audio.touch()

        with patch("src.singer_agent.sadtalker_runner.is_sadtalker_available",
                    return_value=True), \
             patch("subprocess.run", side_effect=sp.TimeoutExpired("cmd", 600)):
            with pytest.raises(RuntimeError, match="超時"):
                generate_singing_video(
                    source_image=str(img),
                    driven_audio=str(audio),
                    output_path=str(tmp_path / "out.mp4"),
                    timeout=600,
                )

    def test_body_motion_flag_in_command(self, tmp_path):
        """確認 --body_motion flag 有被加入指令"""
        img = tmp_path / "avatar.png"
        img.touch()
        audio = tmp_path / "song.mp3"
        audio.touch()

        result_dir = tmp_path / "results"
        result_dir.mkdir()
        generated = result_dir / "test.mp4"
        generated.write_bytes(b"video")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"The generated video is named: {generated}"
        mock_result.stderr = ""

        with patch("src.singer_agent.sadtalker_runner.is_sadtalker_available",
                    return_value=True), \
             patch("subprocess.run", return_value=mock_result) as mock_run, \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_DIR", tmp_path), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_RESULT_DIR", result_dir):

            generate_singing_video(
                source_image=str(img),
                driven_audio=str(audio),
                output_path=str(tmp_path / "out.mp4"),
                body_motion=True,
            )

            # 驗證 subprocess.run 被呼叫時包含 --body_motion
            call_args = mock_run.call_args
            cmd_list = call_args[0][0]
            assert "--body_motion" in cmd_list

    def test_no_body_motion_flag_when_disabled(self, tmp_path):
        """body_motion=False 時不加 --body_motion"""
        img = tmp_path / "avatar.png"
        img.touch()
        audio = tmp_path / "song.mp3"
        audio.touch()

        result_dir = tmp_path / "results"
        result_dir.mkdir()
        generated = result_dir / "test.mp4"
        generated.write_bytes(b"video")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"The generated video is named: {generated}"
        mock_result.stderr = ""

        with patch("src.singer_agent.sadtalker_runner.is_sadtalker_available",
                    return_value=True), \
             patch("subprocess.run", return_value=mock_result) as mock_run, \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_DIR", tmp_path), \
             patch("src.singer_agent.sadtalker_runner.SADTALKER_RESULT_DIR", result_dir):

            generate_singing_video(
                source_image=str(img),
                driven_audio=str(audio),
                output_path=str(tmp_path / "out.mp4"),
                body_motion=False,
            )

            cmd_list = mock_run.call_args[0][0]
            assert "--body_motion" not in cmd_list
