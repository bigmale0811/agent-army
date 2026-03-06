# -*- coding: utf-8 -*-
"""
DEV-13: cli.py 測試。

測試覆蓋：
- argparse 參數解析（必填 / 選填 / 旗標）
- --list 模式（列出專案）
- --dry-run 模式
- Pipeline.run() 呼叫
- 錯誤處理與 exit code
- __main__.py 進入點
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ─────────────────────────────────────────────────
# argparse 解析測試
# ─────────────────────────────────────────────────

class TestArgParsing:
    """測試 CLI 參數解析邏輯。"""

    def test_parse_required_args(self):
        """必填參數（--title, --artist, --audio）正確解析。"""
        from src.singer_agent.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--title", "月亮代表我的心",
            "--artist", "鄧麗君",
            "--audio", "/tmp/song.mp3",
        ])
        assert args.title == "月亮代表我的心"
        assert args.artist == "鄧麗君"
        assert args.audio == "/tmp/song.mp3"

    def test_parse_optional_image(self):
        """選填參數 --image 正確解析。"""
        from src.singer_agent.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--title", "T", "--artist", "A", "--audio", "a.mp3",
            "--image", "/tmp/avatar.png",
        ])
        assert args.image == "/tmp/avatar.png"

    def test_image_default_is_none(self):
        """--image 未指定時預設為 None。"""
        from src.singer_agent.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--title", "T", "--artist", "A", "--audio", "a.mp3",
        ])
        assert args.image is None

    def test_parse_dry_run_flag(self):
        """--dry-run 旗標正確解析。"""
        from src.singer_agent.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--title", "T", "--artist", "A", "--audio", "a.mp3",
            "--dry-run",
        ])
        assert args.dry_run is True

    def test_dry_run_default_is_false(self):
        """--dry-run 未指定時預設為 False。"""
        from src.singer_agent.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--title", "T", "--artist", "A", "--audio", "a.mp3",
        ])
        assert args.dry_run is False

    def test_parse_auto_flag(self):
        """--auto 旗標正確解析。"""
        from src.singer_agent.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--title", "T", "--artist", "A", "--audio", "a.mp3",
            "--auto",
        ])
        assert args.auto is True

    def test_auto_default_is_false(self):
        """--auto 未指定時預設為 False。"""
        from src.singer_agent.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--title", "T", "--artist", "A", "--audio", "a.mp3",
        ])
        assert args.auto is False

    def test_parse_list_flag(self):
        """--list 旗標正確解析，不需其他參數。"""
        from src.singer_agent.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["--list"])
        assert args.list is True

    def test_missing_required_args_returns_one(self):
        """缺少必填參數（非 --list 模式）時 main() 回傳 exit code 1。

        因為 --list 模式不需要 --title/--artist/--audio，
        所以驗證放在 main() 層級而非 argparse 層級。
        """
        from src.singer_agent.cli import main

        # 只給 --title，缺少 --artist 和 --audio
        exit_code = main(["--title", "T"])
        assert exit_code == 1


# ─────────────────────────────────────────────────
# --list 模式測試
# ─────────────────────────────────────────────────

class TestListMode:
    """測試 --list 模式：列出已儲存專案。"""

    @patch("src.singer_agent.cli.ProjectStore")
    def test_list_mode_calls_list_projects(self, mock_store_cls, capsys):
        """--list 呼叫 ProjectStore.list_projects()。"""
        from src.singer_agent.cli import main

        mock_store = MagicMock()
        mock_store.list_projects.return_value = []
        mock_store_cls.return_value = mock_store

        exit_code = main(["--list"])

        mock_store.list_projects.assert_called_once()
        assert exit_code == 0

    @patch("src.singer_agent.cli.ProjectStore")
    def test_list_mode_prints_projects(self, mock_store_cls, capsys):
        """--list 輸出專案資訊到 stdout。"""
        from src.singer_agent.cli import main
        from src.singer_agent.models import ProjectState

        # 建立模擬的 ProjectState
        fake_project = ProjectState(
            project_id="proj-abc12345",
            source_audio="/tmp/song.mp3",
            status="completed",
            metadata={},
            song_spec=None,
            copy_spec=None,
            background_image="",
            composite_image="",
            precheck_result=None,
            final_video="",
            render_mode="",
            error_message="",
            created_at="2026-03-06T10:00:00",
            completed_at="2026-03-06T10:05:00",
        )
        mock_store = MagicMock()
        mock_store.list_projects.return_value = [fake_project]
        mock_store_cls.return_value = mock_store

        exit_code = main(["--list"])

        captured = capsys.readouterr()
        assert "proj-abc12345" in captured.out
        assert exit_code == 0

    @patch("src.singer_agent.cli.ProjectStore")
    def test_list_mode_empty(self, mock_store_cls, capsys):
        """--list 無專案時顯示提示訊息。"""
        from src.singer_agent.cli import main

        mock_store = MagicMock()
        mock_store.list_projects.return_value = []
        mock_store_cls.return_value = mock_store

        exit_code = main(["--list"])

        captured = capsys.readouterr()
        # 應有「無專案」或「沒有」之類的提示
        assert len(captured.out.strip()) > 0
        assert exit_code == 0


# ─────────────────────────────────────────────────
# Pipeline 執行測試
# ─────────────────────────────────────────────────

class TestPipelineExecution:
    """測試 CLI 呼叫 Pipeline.run() 的邏輯。"""

    @patch("src.singer_agent.cli.ProjectStore")
    @patch("src.singer_agent.cli.Pipeline")
    def test_run_creates_pipeline_request(
        self, mock_pipeline_cls, mock_store_cls, tmp_path,
    ):
        """CLI 用正確參數建立 PipelineRequest 並呼叫 Pipeline.run()。"""
        from src.singer_agent.cli import main
        from src.singer_agent.models import ProjectState

        # 建立暫存音訊檔
        audio_file = tmp_path / "song.mp3"
        audio_file.write_bytes(b"\xff\xfb\x90\x00")

        # 模擬 Pipeline.run() 回傳成功的 ProjectState
        mock_pipeline = MagicMock()
        mock_state = MagicMock(spec=ProjectState)
        mock_state.status = "completed"
        mock_state.project_id = "proj-test1234"
        mock_state.error_message = ""
        mock_pipeline.run.return_value = mock_state
        mock_pipeline_cls.return_value = mock_pipeline

        exit_code = main([
            "--title", "測試歌",
            "--artist", "測試歌手",
            "--audio", str(audio_file),
            "--dry-run",
        ])

        # 驗證 Pipeline 被正確建立
        mock_pipeline_cls.assert_called_once()
        # 驗證 run() 被呼叫
        mock_pipeline.run.assert_called_once()
        # 驗證 PipelineRequest 參數
        req = mock_pipeline.run.call_args[0][0]
        assert req.title == "測試歌"
        assert req.artist == "測試歌手"
        assert req.audio_path == audio_file
        assert exit_code == 0

    @patch("src.singer_agent.cli.ProjectStore")
    @patch("src.singer_agent.cli.Pipeline")
    def test_dry_run_passed_to_pipeline(
        self, mock_pipeline_cls, mock_store_cls, tmp_path,
    ):
        """--dry-run 旗標正確傳遞給 Pipeline。"""
        from src.singer_agent.cli import main
        from src.singer_agent.models import ProjectState

        audio_file = tmp_path / "song.mp3"
        audio_file.write_bytes(b"\xff\xfb\x90\x00")

        mock_pipeline = MagicMock()
        mock_state = MagicMock(spec=ProjectState)
        mock_state.status = "completed"
        mock_state.project_id = "proj-dry12345"
        mock_state.error_message = ""
        mock_pipeline.run.return_value = mock_state
        mock_pipeline_cls.return_value = mock_pipeline

        main([
            "--title", "T", "--artist", "A",
            "--audio", str(audio_file),
            "--dry-run",
        ])

        # Pipeline 建構時 dry_run=True
        _, kwargs = mock_pipeline_cls.call_args
        assert kwargs.get("dry_run") is True

    @patch("src.singer_agent.cli.ProjectStore")
    @patch("src.singer_agent.cli.Pipeline")
    def test_custom_image_passed_to_pipeline(
        self, mock_pipeline_cls, mock_store_cls, tmp_path,
    ):
        """--image 參數正確傳遞給 Pipeline。"""
        from src.singer_agent.cli import main
        from src.singer_agent.models import ProjectState

        audio_file = tmp_path / "song.mp3"
        audio_file.write_bytes(b"\xff\xfb\x90\x00")
        image_file = tmp_path / "custom.png"
        image_file.write_bytes(b"\x89PNG")

        mock_pipeline = MagicMock()
        mock_state = MagicMock(spec=ProjectState)
        mock_state.status = "completed"
        mock_state.project_id = "proj-img12345"
        mock_state.error_message = ""
        mock_pipeline.run.return_value = mock_state
        mock_pipeline_cls.return_value = mock_pipeline

        main([
            "--title", "T", "--artist", "A",
            "--audio", str(audio_file),
            "--image", str(image_file),
            "--dry-run",
        ])

        # Pipeline 建構時 character_image 應是自訂路徑
        _, kwargs = mock_pipeline_cls.call_args
        assert kwargs.get("character_image") == image_file


# ─────────────────────────────────────────────────
# exit code 測試
# ─────────────────────────────────────────────────

class TestExitCodes:
    """測試 CLI exit code 邏輯。"""

    @patch("src.singer_agent.cli.ProjectStore")
    @patch("src.singer_agent.cli.Pipeline")
    def test_success_returns_zero(
        self, mock_pipeline_cls, mock_store_cls, tmp_path,
    ):
        """Pipeline 完成時 exit code = 0。"""
        from src.singer_agent.cli import main
        from src.singer_agent.models import ProjectState

        audio_file = tmp_path / "song.mp3"
        audio_file.write_bytes(b"\xff\xfb\x90\x00")

        mock_pipeline = MagicMock()
        mock_state = MagicMock(spec=ProjectState)
        mock_state.status = "completed"
        mock_state.project_id = "proj-ok123456"
        mock_state.error_message = ""
        mock_pipeline.run.return_value = mock_state
        mock_pipeline_cls.return_value = mock_pipeline

        exit_code = main([
            "--title", "T", "--artist", "A",
            "--audio", str(audio_file), "--dry-run",
        ])
        assert exit_code == 0

    @patch("src.singer_agent.cli.ProjectStore")
    @patch("src.singer_agent.cli.Pipeline")
    def test_pipeline_failure_returns_one(
        self, mock_pipeline_cls, mock_store_cls, tmp_path,
    ):
        """Pipeline 失敗時 exit code = 1。"""
        from src.singer_agent.cli import main
        from src.singer_agent.models import ProjectState

        audio_file = tmp_path / "song.mp3"
        audio_file.write_bytes(b"\xff\xfb\x90\x00")

        mock_pipeline = MagicMock()
        mock_state = MagicMock(spec=ProjectState)
        mock_state.status = "failed"
        mock_state.project_id = "proj-fail1234"
        mock_state.error_message = "LLM 離線"
        mock_pipeline.run.return_value = mock_state
        mock_pipeline_cls.return_value = mock_pipeline

        exit_code = main([
            "--title", "T", "--artist", "A",
            "--audio", str(audio_file), "--dry-run",
        ])
        assert exit_code == 1

    @patch("src.singer_agent.cli.Pipeline")
    def test_audio_file_not_found_returns_one(
        self, mock_pipeline_cls, tmp_path,
    ):
        """音訊檔案不存在時 exit code = 1。"""
        from src.singer_agent.cli import main

        exit_code = main([
            "--title", "T", "--artist", "A",
            "--audio", str(tmp_path / "nonexistent.mp3"),
            "--dry-run",
        ])
        assert exit_code == 1

    @patch("src.singer_agent.cli.ProjectStore")
    @patch("src.singer_agent.cli.Pipeline")
    def test_unexpected_exception_returns_one(
        self, mock_pipeline_cls, mock_store_cls, tmp_path,
    ):
        """未預期例外時 exit code = 1。"""
        from src.singer_agent.cli import main

        audio_file = tmp_path / "song.mp3"
        audio_file.write_bytes(b"\xff\xfb\x90\x00")

        mock_pipeline_cls.side_effect = RuntimeError("未預期錯誤")

        exit_code = main([
            "--title", "T", "--artist", "A",
            "--audio", str(audio_file), "--dry-run",
        ])
        assert exit_code == 1


# ─────────────────────────────────────────────────
# 錯誤訊息輸出測試
# ─────────────────────────────────────────────────

class TestErrorMessages:
    """測試錯誤情境的輸出訊息。"""

    @patch("src.singer_agent.cli.ProjectStore")
    @patch("src.singer_agent.cli.Pipeline")
    def test_failure_prints_error(
        self, mock_pipeline_cls, mock_store_cls, tmp_path, capsys,
    ):
        """Pipeline 失敗時輸出錯誤訊息。"""
        from src.singer_agent.cli import main
        from src.singer_agent.models import ProjectState

        audio_file = tmp_path / "song.mp3"
        audio_file.write_bytes(b"\xff\xfb\x90\x00")

        mock_pipeline = MagicMock()
        mock_state = MagicMock(spec=ProjectState)
        mock_state.status = "failed"
        mock_state.project_id = "proj-errmsg01"
        mock_state.error_message = "Ollama 服務無回應"
        mock_pipeline.run.return_value = mock_state
        mock_pipeline_cls.return_value = mock_pipeline

        main([
            "--title", "T", "--artist", "A",
            "--audio", str(audio_file), "--dry-run",
        ])

        captured = capsys.readouterr()
        assert "Ollama 服務無回應" in captured.err

    def test_audio_not_found_prints_error(self, tmp_path, capsys):
        """音訊檔案不存在時輸出提示。"""
        from src.singer_agent.cli import main

        exit_code = main([
            "--title", "T", "--artist", "A",
            "--audio", str(tmp_path / "ghost.mp3"),
        ])

        captured = capsys.readouterr()
        assert "ghost.mp3" in captured.err or "不存在" in captured.err
        assert exit_code == 1


# ─────────────────────────────────────────────────
# __main__.py 測試
# ─────────────────────────────────────────────────

class TestMainEntry:
    """測試 __main__.py 進入點。"""

    def test_main_module_importable(self):
        """__main__.py 可被正常 import，不會觸發 sys.exit。"""
        import importlib
        # 先移除快取，確保重新載入
        import sys
        sys.modules.pop("src.singer_agent.__main__", None)
        mod = importlib.import_module("src.singer_agent.__main__")
        assert mod is not None

    def test_main_module_has_main_reference(self):
        """__main__.py 有 import cli.main。"""
        import importlib
        import sys
        sys.modules.pop("src.singer_agent.__main__", None)
        mod = importlib.import_module("src.singer_agent.__main__")
        # 驗證模組中有 main 的引用
        assert hasattr(mod, "main")
