# -*- coding: utf-8 -*-
"""agentforge list 指令測試。

測試 list 子指令的完整行為：
- 無 agents 時顯示提示
- 有 agents 時顯示表格
- 無效 YAML 不崩潰
"""

from pathlib import Path

from click.testing import CliRunner

from agentforge.cli.main import cli


class TestListCommand:
    """agentforge list 指令測試群組。"""

    def setup_method(self) -> None:
        """每個測試前重設 CliRunner。"""
        self.runner = CliRunner()

    def test_list_empty_no_agents_dir(self, tmp_path: Path) -> None:
        """若無 agents/ 目錄，list 應顯示提示訊息。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            result = self.runner.invoke(cli, ["list"])
            assert result.exit_code == 0
            # 應提示使用者執行 init 或建立 agents 目錄
            assert "agents" in result.output.lower() or "init" in result.output.lower()

    def test_list_empty_agents_dir(self, tmp_path: Path) -> None:
        """agents/ 目錄存在但為空時，list 應顯示提示訊息。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            Path("agents").mkdir()
            result = self.runner.invoke(cli, ["list"])
            assert result.exit_code == 0
            # 應提示沒有找到 agent 定義
            output_lower = result.output.lower()
            assert "agent" in output_lower

    def test_list_with_agents(self, tmp_path: Path) -> None:
        """有 YAML agent 定義時，list 應以表格列出。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            agents_dir = Path("agents")
            agents_dir.mkdir()
            # 建立測試用 agent YAML
            agent_yaml = agents_dir / "test-agent.yaml"
            agent_yaml.write_text(
                "name: test-agent\n"
                "description: A test agent for unit testing\n"
                "steps:\n"
                "  - name: step1\n"
                "    action: shell\n"
                '    command: "echo hello"\n',
                encoding="utf-8",
            )
            result = self.runner.invoke(cli, ["list"])
            assert result.exit_code == 0
            assert "test-agent" in result.output
            assert "A test agent" in result.output

    def test_list_multiple_agents(self, tmp_path: Path) -> None:
        """多個 agent 定義時，list 應全部列出。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            agents_dir = Path("agents")
            agents_dir.mkdir()
            for i in range(3):
                agent_yaml = agents_dir / f"agent-{i}.yaml"
                agent_yaml.write_text(
                    f"name: agent-{i}\n"
                    f"description: Agent number {i}\n"
                    "steps:\n"
                    "  - name: step1\n"
                    "    action: shell\n"
                    '    command: "echo hello"\n',
                    encoding="utf-8",
                )
            result = self.runner.invoke(cli, ["list"])
            assert result.exit_code == 0
            for i in range(3):
                assert f"agent-{i}" in result.output

    def test_list_invalid_yaml(self, tmp_path: Path) -> None:
        """無效 YAML 不應導致指令崩潰。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            agents_dir = Path("agents")
            agents_dir.mkdir()
            # 建立無效 YAML 檔案
            bad_yaml = agents_dir / "bad-agent.yaml"
            bad_yaml.write_text(
                "invalid: yaml: content:\n  - [broken",
                encoding="utf-8",
            )
            # 加入一個正常的 agent
            good_yaml = agents_dir / "good-agent.yaml"
            good_yaml.write_text(
                "name: good-agent\n"
                "description: A valid agent\n"
                "steps:\n"
                "  - name: step1\n"
                "    action: shell\n"
                '    command: "echo hello"\n',
                encoding="utf-8",
            )
            result = self.runner.invoke(cli, ["list"])
            assert result.exit_code == 0
            # 正常的 agent 應仍被列出
            assert "good-agent" in result.output

    def test_list_shows_step_count(self, tmp_path: Path) -> None:
        """list 表格應顯示每個 agent 的 steps 數量。"""
        with self.runner.isolated_filesystem(temp_dir=tmp_path):
            agents_dir = Path("agents")
            agents_dir.mkdir()
            agent_yaml = agents_dir / "multi-step.yaml"
            agent_yaml.write_text(
                "name: multi-step\n"
                "description: Agent with multiple steps\n"
                "steps:\n"
                "  - name: step1\n"
                "    action: shell\n"
                '    command: "echo 1"\n'
                "  - name: step2\n"
                "    action: shell\n"
                '    command: "echo 2"\n'
                "  - name: step3\n"
                "    action: shell\n"
                '    command: "echo 3"\n',
                encoding="utf-8",
            )
            result = self.runner.invoke(cli, ["list"])
            assert result.exit_code == 0
            # 應顯示步驟數量 3
            assert "3" in result.output
