# -*- coding: utf-8 -*-
"""agentforge init 指令測試。

測試 init 子指令的完整行為：
- 建立專案目錄結構
- 複製模板設定檔
- 處理重複目錄錯誤
- 支援巢狀路徑
"""

from pathlib import Path

from click.testing import CliRunner

from agentforge.cli.main import cli


class TestInitCommand:
    """agentforge init <name> 指令測試群組。"""

    def setup_method(self) -> None:
        """每個測試前重設 CliRunner。"""
        self.runner = CliRunner()

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        """init 應在指定路徑下建立專案目錄。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            result = self.runner.invoke(cli, ["init", "my-project"])
            assert result.exit_code == 0
            assert Path("my-project").is_dir()

    def test_init_creates_agentforge_yaml(self, tmp_path: Path) -> None:
        """init 應複製 agentforge.yaml 到專案根目錄。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            result = self.runner.invoke(cli, ["init", "my-project"])
            assert result.exit_code == 0
            yaml_path = Path("my-project") / "agentforge.yaml"
            assert yaml_path.is_file()
            content = yaml_path.read_text(encoding="utf-8")
            # 確認包含 default_model 設定（來自模板）
            assert "default_model" in content

    def test_init_creates_example_agent(self, tmp_path: Path) -> None:
        """init 應複製 example.yaml 到 agents/ 子目錄。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            result = self.runner.invoke(cli, ["init", "my-project"])
            assert result.exit_code == 0
            agent_path = Path("my-project") / "agents" / "example.yaml"
            assert agent_path.is_file()
            content = agent_path.read_text(encoding="utf-8")
            # 確認包含 agent 定義（來自模板）
            assert "name:" in content
            assert "steps:" in content

    def test_init_creates_dot_agentforge(self, tmp_path: Path) -> None:
        """init 應建立 .agentforge/ 隱藏目錄。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            result = self.runner.invoke(cli, ["init", "my-project"])
            assert result.exit_code == 0
            dot_dir = Path("my-project") / ".agentforge"
            assert dot_dir.is_dir()

    def test_init_existing_directory_fails(self, tmp_path: Path) -> None:
        """若目錄已存在，init 應回傳錯誤（不覆蓋）。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            Path("existing-project").mkdir()
            result = self.runner.invoke(cli, ["init", "existing-project"])
            assert result.exit_code != 0
            assert "existing-project" in result.output

    def test_init_nested_path(self, tmp_path: Path) -> None:
        """init 應支援巢狀路徑（自動建立父目錄）。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            result = self.runner.invoke(cli, ["init", "parent/child-project"])
            assert result.exit_code == 0
            assert Path("parent/child-project").is_dir()
            assert (Path("parent/child-project") / "agentforge.yaml").is_file()
            assert (Path("parent/child-project") / "agents" / "example.yaml").is_file()
            assert (Path("parent/child-project") / ".agentforge").is_dir()

    def test_init_shows_created_files(self, tmp_path: Path) -> None:
        """init 應在輸出中列出已建立的檔案。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            result = self.runner.invoke(cli, ["init", "my-project"])
            assert result.exit_code == 0
            # 輸出應包含建立的檔案路徑或成功訊息
            assert "my-project" in result.output

    def test_init_no_name_shows_usage(self) -> None:
        """缺少 name 參數時應顯示用法說明。"""
        result = self.runner.invoke(cli, ["init"])
        assert result.exit_code != 0
