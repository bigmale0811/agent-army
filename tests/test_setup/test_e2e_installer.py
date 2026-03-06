"""安裝精靈 E2E 端對端測試。

用 subprocess 執行 install.py / setup.py 的 --dry-run --auto 模式，
驗證完整流程不會 crash、輸出正確、且不產生副作用。

這些測試補齊 mock unit test 測不到的整合問題。
"""

import subprocess
import sys
from pathlib import Path

import pytest

INSTALL_SCRIPT = Path(__file__).parent.parent.parent / "install.py"
SETUP_SCRIPT = Path(__file__).parent.parent.parent / "setup.py"
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _run_installer(*extra_args, cwd=None):
    """執行 install.py --dry-run --auto，回傳 CompletedProcess。"""
    env = {"PYTHONIOENCODING": "utf-8"}
    import os
    env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, str(INSTALL_SCRIPT), "--dry-run", "--auto", *extra_args],
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
    )


def _run_setup(*extra_args):
    """執行 setup.py --dry-run --auto，回傳 CompletedProcess。"""
    import os
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, str(SETUP_SCRIPT), "--dry-run", "--auto", *extra_args],
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
        cwd=str(PROJECT_ROOT),
        env=env,
    )


class TestInstallDryRunAuto:
    """install.py --dry-run --auto E2E 測試。"""

    def test_exits_zero(self):
        """--dry-run --auto 應正常結束（exit code 0）。"""
        result = _run_installer()
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_shows_all_steps(self):
        """輸出應包含所有 4 個 step header。"""
        result = _run_installer()
        output = result.stdout
        assert "Step 1" in output, "缺少 Step 1"
        assert "Step 2" in output, "缺少 Step 2"
        assert "Step 3" in output, "缺少 Step 3"
        assert "Step 4" in output, "缺少 Step 4"

    def test_no_traceback(self):
        """輸出不應包含 Python traceback。"""
        result = _run_installer()
        combined = result.stdout + result.stderr
        assert "Traceback" not in combined

    def test_shows_dry_run_markers(self):
        """dry-run 模式應標示 [DRY RUN]。"""
        result = _run_installer()
        assert "DRY RUN" in result.stdout

    def test_no_side_effects(self, tmp_path):
        """dry-run 不應建立任何新目錄或檔案。"""
        fake_path = tmp_path / "agent-army-test"
        result = _run_installer("--path", str(fake_path))
        assert not fake_path.exists(), f"dry-run 不應建立 {fake_path}"


class TestInstallDryRunExistingProject:
    """install.py --dry-run --auto --path 既有專案 偵測測試。"""

    def test_detects_existing_project(self):
        """指向既有 agent-army 專案時應偵測到。"""
        result = _run_installer("--path", str(PROJECT_ROOT))
        assert result.returncode == 0
        # 應包含「既有」或「偵測」的字眼
        assert "既有" in result.stdout or "偵測" in result.stdout


class TestSetupDryRunAuto:
    """setup.py --dry-run --auto E2E 測試。"""

    def test_exits_zero(self):
        """setup.py --dry-run --auto 應正常結束。"""
        result = _run_setup()
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_no_traceback(self):
        """輸出不應包含 Python traceback。"""
        result = _run_setup()
        combined = result.stdout + result.stderr
        assert "Traceback" not in combined
