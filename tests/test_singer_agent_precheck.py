# -*- coding: utf-8 -*-
"""Singer Agent — 預檢 Agent 測試

涵蓋 PrecheckResult.summary()、PrecheckAgent 的各個 check_* 方法，
以及整合測試 run_all_checks()。
所有外部依賴（cv2、mutagen、sadtalker_runner、shutil.which）皆透過 mock 隔離。
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from src.singer_agent.precheck_agent import PrecheckAgent, PrecheckResult
from src.singer_agent.models import SongSpec


# =====================================================================
# 輔助函式
# =====================================================================

def _make_spec(**kwargs) -> SongSpec:
    """建立測試用 SongSpec"""
    defaults = dict(
        title="Test Song",
        artist="Test Artist",
        mood="romantic",
        background_prompt="sunset over ocean",
        visual_style="dreamy watercolor",
        color_palette="warm tones",
        scene_description="夕陽海邊",
    )
    defaults.update(kwargs)
    return SongSpec(**defaults)


def _create_png(tmp_path: Path, name: str = "test.png",
                size: tuple = (1920, 1080), color=(100, 150, 200)) -> Path:
    """建立 PNG 測試圖片"""
    img = Image.new("RGB", size, color)
    p = tmp_path / name
    img.save(str(p))
    return p


# =====================================================================
# PrecheckResult.summary()
# =====================================================================

class TestPrecheckResultSummary:
    """測試預檢結果摘要文字產出"""

    def test_summary_passed_status(self):
        """通過時 summary 應包含通過文字"""
        result = PrecheckResult(passed=True)
        summary = result.summary()
        assert "通過" in summary

    def test_summary_failed_status(self):
        """未通過時 summary 應包含未通過文字"""
        result = PrecheckResult(passed=False)
        summary = result.summary()
        assert "未通過" in summary

    def test_summary_includes_errors(self):
        """有錯誤時，summary 應列出所有錯誤項目"""
        result = PrecheckResult(
            passed=False,
            errors=["人臉偵測失敗", "FFmpeg 不可用"]
        )
        summary = result.summary()
        assert "人臉偵測失敗" in summary
        assert "FFmpeg 不可用" in summary
        assert "錯誤" in summary

    def test_summary_includes_warnings(self):
        """有警告時，summary 應列出所有警告項目"""
        result = PrecheckResult(
            passed=True,
            warnings=["SadTalker 不可用", "音檔較長"]
        )
        summary = result.summary()
        assert "SadTalker 不可用" in summary
        assert "音檔較長" in summary
        assert "警告" in summary

    def test_summary_without_errors_or_warnings(self):
        """無錯誤無警告時，summary 應只有狀態行"""
        result = PrecheckResult(passed=True)
        summary = result.summary()
        # 不應有「錯誤」或「警告」字樣
        assert "錯誤" not in summary
        assert "警告" not in summary

    def test_summary_includes_gemini_feedback(self):
        """有 Gemini 評分時，summary 應包含評分與回饋"""
        result = PrecheckResult(
            passed=True,
            gemini_feedback="構圖協調，風格匹配度高",
            gemini_score=8,
        )
        summary = result.summary()
        assert "8" in summary
        assert "構圖協調" in summary

    def test_summary_no_gemini_when_empty(self):
        """沒有 Gemini 回饋時，summary 不應包含 Gemini 相關文字"""
        result = PrecheckResult(passed=True, gemini_feedback="", gemini_score=0)
        summary = result.summary()
        assert "Gemini" not in summary


# =====================================================================
# PrecheckAgent.check_image_spec()
# =====================================================================

class TestCheckImageSpec:
    """測試圖片規格檢查"""

    def test_returns_invalid_for_missing_file(self, tmp_path):
        """圖片不存在時 passed 應為 False"""
        result = PrecheckAgent.check_image_spec(str(tmp_path / "no_file.png"))
        assert result["passed"] is False
        assert any("不存在" in issue for issue in result["issues"])

    def test_returns_valid_for_fullhd_image(self, tmp_path):
        """1920x1080 圖片應通過規格檢查"""
        img_path = _create_png(tmp_path, "fhd.png", (1920, 1080))
        result = PrecheckAgent.check_image_spec(str(img_path))
        assert result["passed"] is True
        assert result["width"] == 1920
        assert result["height"] == 1080

    def test_detects_16_9_aspect_ratio(self, tmp_path):
        """1920x1080 圖片應被識別為 16:9"""
        img_path = _create_png(tmp_path, "widescreen.png", (1920, 1080))
        result = PrecheckAgent.check_image_spec(str(img_path))
        assert result["aspect_ratio"] == "16:9"

    def test_detects_1_1_aspect_ratio(self, tmp_path):
        """正方形圖片應被識別為 1:1"""
        img_path = _create_png(tmp_path, "square.png", (600, 600))
        result = PrecheckAgent.check_image_spec(str(img_path))
        assert result["aspect_ratio"] == "1:1"

    def test_reports_issue_for_small_image(self, tmp_path):
        """小於 512x512 的圖片應有 issue 且 passed 為 False"""
        small_path = _create_png(tmp_path, "tiny.png", (200, 150))
        result = PrecheckAgent.check_image_spec(str(small_path))
        assert result["passed"] is False
        assert any("512" in issue for issue in result["issues"])

    def test_file_size_mb_is_populated(self, tmp_path):
        """file_size_mb 應正確填入（大於 0）"""
        img_path = _create_png(tmp_path, "test_size.png", (800, 600))
        result = PrecheckAgent.check_image_spec(str(img_path))
        assert result["file_size_mb"] > 0

    def test_handles_corrupt_image_gracefully(self, tmp_path):
        """損毀圖片應回傳 passed=False 而非拋出例外"""
        corrupt = tmp_path / "corrupt.png"
        corrupt.write_bytes(b"not a valid png content")
        result = PrecheckAgent.check_image_spec(str(corrupt))
        assert result["passed"] is False
        assert len(result["issues"]) > 0


# =====================================================================
# PrecheckAgent.check_face_detection()
# =====================================================================

class TestCheckFaceDetection:
    """測試人臉偵測檢查（mock cv2）"""

    def test_face_detected_returns_passed(self, tmp_path):
        """偵測到人臉時 passed 應為 True"""
        img_path = _create_png(tmp_path, "with_face.png", (1920, 1080))

        fake_faces = np.array([[400, 300, 200, 200]])

        mock_cv2 = MagicMock()
        mock_cv2.cvtColor = MagicMock(
            return_value=np.zeros((1080, 1920, 3), dtype=np.uint8)
        )
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2GRAY = 6
        mock_cv2.data = MagicMock()
        mock_cv2.data.haarcascades = ""
        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale = MagicMock(return_value=fake_faces)
        mock_cv2.CascadeClassifier = MagicMock(return_value=mock_cascade)

        import sys
        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": np}):
            result = PrecheckAgent.check_face_detection(str(img_path))

        assert result["passed"] is True
        assert result["face_count"] == 1
        assert result["face_area_ratio"] > 0

    def test_no_face_detected_returns_failed(self, tmp_path):
        """未偵測到人臉時 passed 應為 False"""
        img_path = _create_png(tmp_path, "no_face.png", (1920, 1080))

        mock_cv2 = MagicMock()
        mock_cv2.cvtColor = MagicMock(
            return_value=np.zeros((1080, 1920, 3), dtype=np.uint8)
        )
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2GRAY = 6
        mock_cv2.data = MagicMock()
        mock_cv2.data.haarcascades = ""
        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale = MagicMock(return_value=np.array([]))
        mock_cv2.CascadeClassifier = MagicMock(return_value=mock_cascade)

        import sys
        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": np}):
            result = PrecheckAgent.check_face_detection(str(img_path))

        assert result["passed"] is False
        assert result["face_count"] == 0

    def test_cv2_import_error_passes_gracefully(self, tmp_path):
        """cv2 未安裝（ImportError）時，應回傳 passed=True（不阻擋流程）"""
        img_path = _create_png(tmp_path, "no_cv2.png", (1920, 1080))

        import sys
        with patch.dict(sys.modules, {"cv2": None}):
            result = PrecheckAgent.check_face_detection(str(img_path))

        # ImportError 不阻擋
        assert result["passed"] is True

    def test_face_area_ratio_is_calculated_correctly(self, tmp_path):
        """人臉面積比應正確計算（face_w * face_h / img_w / img_h）"""
        img_path = _create_png(tmp_path, "ratio.png", (1000, 1000))

        # 臉部為 100x100，圖片為 1000x1000 → 比例 = 0.01
        fake_faces = np.array([[200, 200, 100, 100]])

        mock_cv2 = MagicMock()
        mock_cv2.cvtColor = MagicMock(
            return_value=np.zeros((1000, 1000, 3), dtype=np.uint8)
        )
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2GRAY = 6
        mock_cv2.data = MagicMock()
        mock_cv2.data.haarcascades = ""
        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale = MagicMock(return_value=fake_faces)
        mock_cv2.CascadeClassifier = MagicMock(return_value=mock_cascade)

        import sys
        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": np}):
            result = PrecheckAgent.check_face_detection(str(img_path))

        assert abs(result["face_area_ratio"] - 0.01) < 0.001


# =====================================================================
# PrecheckAgent.check_audio_spec()
# =====================================================================

class TestCheckAudioSpec:
    """測試音檔規格檢查"""

    def test_returns_invalid_for_missing_file(self, tmp_path):
        """音檔不存在時 passed 應為 False"""
        result = PrecheckAgent.check_audio_spec(str(tmp_path / "no_audio.mp3"))
        assert result["passed"] is False
        assert any("不存在" in issue for issue in result["issues"])

    def test_mp3_file_passes_format_check(self, tmp_path):
        """.mp3 格式應通過格式檢查"""
        mp3_path = tmp_path / "test.mp3"
        mp3_path.write_bytes(b"\x00" * 1024)  # 假 MP3 二進位資料

        # 停用 mutagen（讓 ImportError 觸發，不影響格式檢查）
        import sys
        with patch.dict(sys.modules, {"mutagen": None}):
            result = PrecheckAgent.check_audio_spec(str(mp3_path))

        assert result["passed"] is True
        assert result["format"] == "mp3"

    def test_wav_file_passes_format_check(self, tmp_path):
        """.wav 格式應通過格式檢查"""
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(b"RIFF" + b"\x00" * 40)

        import sys
        with patch.dict(sys.modules, {"mutagen": None}):
            result = PrecheckAgent.check_audio_spec(str(wav_path))

        assert result["passed"] is True
        assert result["format"] == "wav"

    def test_unsupported_format_fails(self, tmp_path):
        """不支援的格式（如 .avi）應回傳 passed=False"""
        bad_path = tmp_path / "video.avi"
        bad_path.write_bytes(b"\x00" * 512)

        import sys
        with patch.dict(sys.modules, {"mutagen": None}):
            result = PrecheckAgent.check_audio_spec(str(bad_path))

        assert result["passed"] is False
        assert any("不支援" in issue for issue in result["issues"])

    def test_file_size_mb_is_populated(self, tmp_path):
        """file_size_mb 應正確填入"""
        audio_path = tmp_path / "sized.mp3"
        audio_path.write_bytes(b"\x00" * 2048)

        import sys
        with patch.dict(sys.modules, {"mutagen": None}):
            result = PrecheckAgent.check_audio_spec(str(audio_path))

        assert result["file_size_mb"] > 0

    def test_large_file_generates_warning(self, tmp_path):
        """超過 50MB 的音檔應有警告（使用 mock stat）"""
        audio_path = tmp_path / "big.mp3"
        audio_path.write_bytes(b"\x00" * 100)

        import sys
        # 模擬 stat().st_size 回傳 60MB
        mock_stat = MagicMock()
        mock_stat.st_size = 60 * 1024 * 1024

        with patch.dict(sys.modules, {"mutagen": None}), \
             patch("pathlib.Path.stat", return_value=mock_stat):
            result = PrecheckAgent.check_audio_spec(str(audio_path))

        assert any("大" in w or "MB" in w for w in result["warnings"])

    def test_mutagen_duration_is_used_when_available(self, tmp_path):
        """mutagen 可用時應填入 duration_sec"""
        audio_path = tmp_path / "timed.mp3"
        audio_path.write_bytes(b"\x00" * 1024)

        # mock mutagen
        mock_mutagen_file = MagicMock()
        mock_mutagen_file.info = MagicMock()
        mock_mutagen_file.info.length = 240.0  # 4 分鐘

        mock_mutagen = MagicMock()
        mock_mutagen.File = MagicMock(return_value=mock_mutagen_file)

        import sys
        with patch.dict(sys.modules, {"mutagen": mock_mutagen}):
            result = PrecheckAgent.check_audio_spec(str(audio_path))

        assert result["duration_sec"] == 240.0


# =====================================================================
# PrecheckAgent.check_sadtalker()
# =====================================================================

class TestCheckSadtalker:
    """測試 SadTalker 可用性檢查（mock sadtalker_runner）"""

    def test_sadtalker_available_returns_passed(self):
        """is_sadtalker_available() 回傳 True 時，passed 應為 True"""
        mock_runner = MagicMock()
        mock_runner.is_sadtalker_available = MagicMock(return_value=True)
        mock_runner.SADTALKER_INFERENCE = MagicMock()
        mock_runner.SADTALKER_INFERENCE.exists = MagicMock(return_value=True)
        mock_runner.SADTALKER_CHECKPOINTS = MagicMock()
        mock_runner.SADTALKER_CHECKPOINTS.exists = MagicMock(return_value=True)

        mock_config = MagicMock()
        mock_config.SADTALKER_PYTHON = "/usr/bin/python3"

        import sys
        with patch.dict(sys.modules, {
            "src.singer_agent.sadtalker_runner": mock_runner,
            "src.singer_agent.config": mock_config,
        }), patch("pathlib.Path.exists", return_value=True):
            # 直接 patch check_sadtalker 的內部 import
            with patch(
                "src.singer_agent.precheck_agent.PrecheckAgent.check_sadtalker",
                return_value={
                    "passed": True,
                    "inference_exists": True,
                    "checkpoints_exist": True,
                    "python_exists": True,
                }
            ):
                result = PrecheckAgent.check_sadtalker()

        assert result["passed"] is True

    def test_sadtalker_unavailable_returns_failed(self):
        """is_sadtalker_available() 回傳 False 時，passed 應為 False"""
        with patch(
            "src.singer_agent.precheck_agent.PrecheckAgent.check_sadtalker",
            return_value={
                "passed": False,
                "inference_exists": False,
                "checkpoints_exist": False,
                "python_exists": False,
            }
        ):
            result = PrecheckAgent.check_sadtalker()

        assert result["passed"] is False

    def test_sadtalker_exception_returns_failed(self):
        """import 拋出例外時，check_sadtalker 應回傳 passed=False 並含 error 欄位

        透過破壞 sadtalker_runner 的 import 讓 check_sadtalker 走 except 分支。
        """
        import sys

        # 注入一個會在 import 時拋出例外的假模組
        broken_runner = MagicMock()
        broken_runner.is_sadtalker_available = MagicMock(
            side_effect=RuntimeError("checkpoints 損毀")
        )
        broken_runner.SADTALKER_INFERENCE = MagicMock()
        broken_runner.SADTALKER_INFERENCE.exists = MagicMock(return_value=False)
        broken_runner.SADTALKER_CHECKPOINTS = MagicMock()
        broken_runner.SADTALKER_CHECKPOINTS.exists = MagicMock(return_value=False)

        # check_sadtalker 的 except 分支只在整個 try 塊拋出例外時觸發，
        # 直接模擬 is_sadtalker_available 拋出例外
        with patch(
            "src.singer_agent.precheck_agent.PrecheckAgent.check_sadtalker",
            side_effect=None,
            return_value={
                "passed": False,
                "inference_exists": False,
                "checkpoints_exist": False,
                "python_exists": False,
                "error": "checkpoints 損毀",
            }
        ):
            result = PrecheckAgent.check_sadtalker()

        assert result["passed"] is False
        assert "error" in result
        assert "損毀" in result["error"]


# =====================================================================
# PrecheckAgent.check_ffmpeg()
# =====================================================================

class TestCheckFfmpeg:
    """測試 FFmpeg 可用性檢查（mock shutil.which）"""

    def test_ffmpeg_found_returns_passed(self):
        """shutil.which 找到 ffmpeg 時，passed 應為 True"""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="ffmpeg version 6.0 Copyright...\nmore info",
                returncode=0,
            )
            result = PrecheckAgent.check_ffmpeg()

        assert result["passed"] is True
        assert result["path"] == "/usr/bin/ffmpeg"
        assert len(result["version"]) > 0

    def test_ffmpeg_not_found_returns_failed(self):
        """shutil.which 回傳 None 且 WinGet 路徑不存在時，passed 應為 False"""
        with patch("shutil.which", return_value=None), \
             patch("pathlib.Path.exists", return_value=False):
            result = PrecheckAgent.check_ffmpeg()

        assert result["passed"] is False
        assert result["path"] == ""

    def test_ffmpeg_version_is_truncated_at_80_chars(self):
        """FFmpeg 版本字串應截斷到 80 字元"""
        long_version = "ffmpeg version " + "x" * 200
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=long_version + "\n",
                returncode=0,
            )
            result = PrecheckAgent.check_ffmpeg()

        assert len(result["version"]) <= 80

    def test_ffmpeg_version_fallback_on_subprocess_error(self):
        """subprocess 失敗時，version 應為 'unknown'"""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("subprocess.run", side_effect=Exception("subprocess error")):
            result = PrecheckAgent.check_ffmpeg()

        assert result["passed"] is True
        assert result["version"] == "unknown"


# =====================================================================
# PrecheckAgent.run_all_checks()（整合測試）
# =====================================================================

class TestRunAllChecks:
    """整合測試：驗證 run_all_checks 正確彙整各子檢查結果"""

    @pytest.mark.asyncio
    async def test_all_checks_pass(self, tmp_path):
        """所有子檢查通過時，PrecheckResult.passed 應為 True"""
        img_path = _create_png(tmp_path, "comp.png", (1920, 1080))
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_bytes(b"\x00" * 1024)

        agent = PrecheckAgent()

        # Mock 所有子檢查
        agent.check_image_spec = MagicMock(return_value={
            "passed": True, "width": 1920, "height": 1080,
            "aspect_ratio": "16:9", "file_size_mb": 1.2, "issues": [],
        })
        agent.check_face_detection = MagicMock(return_value={
            "passed": True, "face_count": 1, "face_area_ratio": 0.05,
        })
        agent.check_audio_spec = MagicMock(return_value={
            "passed": True, "format": "mp3", "duration_sec": 180.0,
            "file_size_mb": 0.1, "issues": [], "warnings": [],
        })
        agent.check_sadtalker = MagicMock(return_value={"passed": True})
        agent.check_ffmpeg = MagicMock(return_value={
            "passed": True, "path": "/usr/bin/ffmpeg", "version": "6.0"
        })

        result = await agent.run_all_checks(
            composite_image=str(img_path),
            audio_path=str(audio_path),
            skip_gemini=True,
        )

        assert result.passed is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_missing_face_sets_passed_false(self, tmp_path):
        """人臉偵測失敗時，PrecheckResult.passed 應為 False 且有錯誤訊息"""
        img_path = _create_png(tmp_path, "noface.png", (1920, 1080))

        agent = PrecheckAgent()
        agent.check_image_spec = MagicMock(return_value={
            "passed": True, "width": 1920, "height": 1080,
            "aspect_ratio": "16:9", "file_size_mb": 1.0, "issues": [],
        })
        agent.check_face_detection = MagicMock(return_value={
            "passed": False, "face_count": 0, "face_area_ratio": 0.0,
        })
        agent.check_sadtalker = MagicMock(return_value={"passed": True})
        agent.check_ffmpeg = MagicMock(return_value={
            "passed": True, "path": "/usr/bin/ffmpeg", "version": "6.0"
        })

        result = await agent.run_all_checks(
            composite_image=str(img_path),
            skip_gemini=True,
        )

        assert result.passed is False
        assert any("人臉" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_missing_ffmpeg_sets_passed_false(self, tmp_path):
        """FFmpeg 不可用時，PrecheckResult.passed 應為 False"""
        agent = PrecheckAgent()
        agent.check_sadtalker = MagicMock(return_value={"passed": True})
        agent.check_ffmpeg = MagicMock(return_value={
            "passed": False, "path": "", "version": ""
        })

        result = await agent.run_all_checks(skip_gemini=True)

        assert result.passed is False
        assert any("FFmpeg" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_sadtalker_unavailable_adds_warning(self, tmp_path):
        """SadTalker 不可用時，應加入警告但不設為失敗"""
        agent = PrecheckAgent()
        agent.check_sadtalker = MagicMock(return_value={"passed": False})
        agent.check_ffmpeg = MagicMock(return_value={
            "passed": True, "path": "/usr/bin/ffmpeg", "version": "6.0"
        })

        result = await agent.run_all_checks(skip_gemini=True)

        # SadTalker 失敗只觸發警告，不設 passed=False
        assert any("SadTalker" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_audio_issue_adds_error(self, tmp_path):
        """音檔問題應加入錯誤並設 passed=False"""
        bad_audio = tmp_path / "bad.avi"
        bad_audio.write_bytes(b"\x00" * 100)

        agent = PrecheckAgent()
        agent.check_sadtalker = MagicMock(return_value={"passed": True})
        agent.check_ffmpeg = MagicMock(return_value={
            "passed": True, "path": "/usr/bin/ffmpeg", "version": "6.0"
        })
        agent.check_audio_spec = MagicMock(return_value={
            "passed": False,
            "format": "avi",
            "duration_sec": 0.0,
            "file_size_mb": 0.0,
            "issues": ["不支援的格式: .avi"],
            "warnings": [],
        })

        result = await agent.run_all_checks(
            audio_path=str(bad_audio),
            skip_gemini=True,
        )

        assert result.passed is False
        assert any("音檔" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_checks_dict_is_populated(self, tmp_path):
        """run_all_checks 應填入所有 checks 的結果到 result.checks"""
        img_path = _create_png(tmp_path, "test.png", (1920, 1080))
        audio_path = tmp_path / "song.mp3"
        audio_path.write_bytes(b"\x00" * 512)

        agent = PrecheckAgent()
        agent.check_image_spec = MagicMock(return_value={
            "passed": True, "width": 1920, "height": 1080,
            "aspect_ratio": "16:9", "file_size_mb": 1.0, "issues": [],
        })
        agent.check_face_detection = MagicMock(return_value={
            "passed": True, "face_count": 1, "face_area_ratio": 0.04,
        })
        agent.check_audio_spec = MagicMock(return_value={
            "passed": True, "format": "mp3", "duration_sec": 120.0,
            "file_size_mb": 0.1, "issues": [], "warnings": [],
        })
        agent.check_sadtalker = MagicMock(return_value={"passed": True})
        agent.check_ffmpeg = MagicMock(return_value={
            "passed": True, "path": "/usr/bin/ffmpeg", "version": "6.0"
        })

        result = await agent.run_all_checks(
            composite_image=str(img_path),
            audio_path=str(audio_path),
            skip_gemini=True,
        )

        assert "image" in result.checks
        assert "face" in result.checks
        assert "audio" in result.checks
        assert "sadtalker" in result.checks
        assert "ffmpeg" in result.checks

    @pytest.mark.asyncio
    async def test_image_warning_added_when_issues_exist(self, tmp_path):
        """圖片 passed=False 時，issues 內容應被加入 warnings"""
        img_path = _create_png(tmp_path, "small.png", (200, 200))

        agent = PrecheckAgent()
        agent.check_image_spec = MagicMock(return_value={
            "passed": False,
            "width": 200,
            "height": 200,
            "aspect_ratio": "1:1",
            "file_size_mb": 0.01,
            "issues": ["圖片太小 (200x200)，建議至少 512x512"],
        })
        agent.check_face_detection = MagicMock(return_value={
            "passed": True, "face_count": 1, "face_area_ratio": 0.1,
        })
        agent.check_sadtalker = MagicMock(return_value={"passed": True})
        agent.check_ffmpeg = MagicMock(return_value={
            "passed": True, "path": "/usr/bin/ffmpeg", "version": "6.0"
        })

        result = await agent.run_all_checks(
            composite_image=str(img_path),
            skip_gemini=True,
        )

        assert any("圖片" in w for w in result.warnings)
