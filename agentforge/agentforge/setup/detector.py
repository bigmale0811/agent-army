# -*- coding: utf-8 -*-
"""環境偵測器 — 偵測本機環境是否符合 AgentForge 執行需求。

此模組負責：
- 檢查 Python 版本是否 >= 3.10
- 偵測 claude CLI 是否已安裝並可執行
- 偵測 Ollama 是否已安裝並正在執行
- 偵測指定目錄是否已有 agentforge.yaml 設定檔
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


class EnvironmentDetector:
    """本機環境偵測器。

    提供各項環境檢查方法，供安裝精靈使用。
    所有方法皆回傳 (bool, str) tuple：
    - bool: 是否通過檢查
    - str: 版本字串或錯誤訊息
    """

    def check_python_version(self) -> tuple[bool, str]:
        """檢查目前 Python 版本是否 >= 3.10。

        Returns:
            (是否通過, 版本字串)
            例：(True, "3.12.8") 或 (False, "3.9.7（需要 3.10 以上）")
        """
        major = sys.version_info.major
        minor = sys.version_info.minor
        micro = sys.version_info.micro
        version_str = f"{major}.{minor}.{micro}"

        if major >= 3 and minor >= 10:
            return True, version_str
        else:
            return False, f"{version_str}（需要 3.10 以上）"

    def check_claude_cli(self) -> tuple[bool, str]:
        """偵測 claude CLI 是否已安裝並可執行。

        先用 shutil.which 確認 CLI 存在，再執行 claude --version 取得版本。

        Returns:
            (是否可用, 版本字串或錯誤訊息)
            例：(True, "claude 1.2.3") 或 (False, "找不到 claude CLI")
        """
        # 先確認 claude 指令是否存在於 PATH
        if shutil.which("claude") is None:
            return False, "找不到 claude CLI（請先安裝：npm install -g @anthropic-ai/claude-code）"

        # 執行 claude --version 取得版本資訊
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                version = result.stdout.strip() or "claude（版本未知）"
                return True, version
            else:
                return False, f"claude CLI 執行失敗（exit code {result.returncode}）"
        except FileNotFoundError:
            return False, "找不到 claude CLI（請先安裝：npm install -g @anthropic-ai/claude-code）"
        except subprocess.TimeoutExpired:
            return False, "claude CLI 執行超時"
        except Exception as e:  # noqa: BLE001
            return False, f"claude CLI 偵測失敗：{e}"

    def check_ollama(self) -> tuple[bool, str]:
        """偵測 Ollama 是否已安裝並正在執行。

        先用 shutil.which 確認 ollama 指令存在，再執行 ollama list 確認服務正在執行。

        Returns:
            (是否可用, 模型清單或錯誤訊息)
            例：(True, "qwen3:14b 已安裝") 或 (False, "Ollama 服務未啟動")
        """
        # 先確認 ollama 指令是否存在於 PATH
        if shutil.which("ollama") is None:
            return False, "找不到 Ollama（請先安裝：https://ollama.ai）"

        # 執行 ollama list 確認服務正在執行
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                return True, output if output else "Ollama 執行中（尚無已安裝模型）"
            else:
                return False, "Ollama 服務未啟動（請執行 ollama serve）"
        except FileNotFoundError:
            return False, "找不到 Ollama（請先安裝：https://ollama.ai）"
        except subprocess.TimeoutExpired:
            return False, "Ollama 回應超時（服務可能未啟動）"
        except Exception as e:  # noqa: BLE001
            return False, f"Ollama 偵測失敗：{e}"

    def check_node_npm(self) -> tuple[bool, str]:
        """偵測 Node.js 及 npm 是否已安裝。

        Returns:
            (是否可用, 版本字串或錯誤訊息)
            例：(True, "npm 10.2.0") 或 (False, "找不到 npm")
        """
        # 先確認 npm 指令是否存在於 PATH
        if shutil.which("npm") is None:
            return False, "找不到 npm（請先安裝 Node.js：https://nodejs.org）"

        try:
            result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, f"npm {version}"
            else:
                return False, "npm 執行失敗"
        except FileNotFoundError:
            return False, "找不到 npm（請先安裝 Node.js：https://nodejs.org）"
        except subprocess.TimeoutExpired:
            return False, "npm 執行超時"
        except Exception as e:  # noqa: BLE001
            return False, f"npm 偵測失敗：{e}"

    def install_claude_cli(self) -> tuple[bool, str]:
        """透過 npm 全域安裝 Claude Code CLI。

        會先偵測 npm 是否可用，若不可用則回傳失敗。
        安裝指令：npm install -g @anthropic-ai/claude-code

        Returns:
            (是否安裝成功, 結果訊息)
        """
        # 先確認 npm 可用
        npm_ok, npm_msg = self.check_node_npm()
        if not npm_ok:
            return False, f"無法安裝 Claude CLI：{npm_msg}"

        try:
            result = subprocess.run(
                ["npm", "install", "-g", "@anthropic-ai/claude-code"],
                capture_output=True,
                text=True,
                timeout=300,  # npm 安裝可能較慢，給 5 分鐘
            )
            if result.returncode == 0:
                # 安裝成功，再驗證一次
                cli_ok, cli_msg = self.check_claude_cli()
                if cli_ok:
                    return True, f"Claude CLI 安裝成功：{cli_msg}"
                else:
                    return True, "npm 安裝完成，但 claude 指令尚未生效（可能需要重啟終端機）"
            else:
                stderr = result.stderr.strip()
                return False, f"npm 安裝失敗：{stderr[:200]}"
        except FileNotFoundError:
            return False, "找不到 npm，無法安裝 Claude CLI"
        except subprocess.TimeoutExpired:
            return False, "安裝超時（超過 5 分鐘），請手動執行：npm install -g @anthropic-ai/claude-code"
        except Exception as e:  # noqa: BLE001
            return False, f"安裝過程發生錯誤：{e}"

    def check_existing_config(self, path: Path) -> bool:
        """偵測指定目錄是否已有 agentforge.yaml 設定檔。

        Args:
            path: 要檢查的目錄路徑。

        Returns:
            True 表示已有設定檔，False 表示尚未設定。
        """
        return (path / "agentforge.yaml").is_file()
