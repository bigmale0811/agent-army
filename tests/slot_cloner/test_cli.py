"""CLI 測試"""
from click.testing import CliRunner
from slot_cloner.cli import main


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "老虎機" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_clone_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["clone", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output
        assert "--dry-run" in result.output

    def test_clone_dry_run(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, [
            "clone", "https://play.godeebxp.com/test",
            "--name", "test-game",
            "--output", str(tmp_path),
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "Clone 完成" in result.output or "完成" in result.output

    def test_clone_missing_name(self):
        runner = CliRunner()
        result = runner.invoke(main, ["clone", "https://example.com"])
        assert result.exit_code != 0

    def test_clone_invalid_phases(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, [
            "clone", "https://example.com/game",
            "--name", "test",
            "--output", str(tmp_path),
            "--phases", "invalid_phase",
            "--dry-run",
        ])
        assert result.exit_code != 0
