# -*- coding: utf-8 -*-
"""安裝精靈主流程 — 一步步引導使用者完成 AgentForge 設定。

互動流程：
1. 選擇 AI 服務（Gemini / Claude / OpenAI / Ollama）
2. 設定 API 通行證
3. 測試連線
4. 建立設定檔

支援 --auto 模式（全自動，使用預設值）和 --dry-run 模式（只印不寫）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import click

from agentforge.setup.config_writer import ConfigWriter
from agentforge.setup.credential import CredentialManager
from agentforge.setup.detector import EnvironmentDetector

# Provider 選項清單（選號 -> provider 名稱）
_PROVIDER_CHOICES: dict[str, str] = {
    "1": "gemini",
    "2": "claude-code",
    "3": "openai",
    "4": "ollama",
}

# Provider 對應的預設模型
_PROVIDER_MODELS: dict[str, str] = {
    "gemini": "gemini/gemini-2.0-flash",
    "claude-code": "claude-code/sonnet",
    "openai": "openai/gpt-4o-mini",
    "ollama": "ollama/qwen3:14b",
}

# --auto 模式預設的 API key（測試用）
_AUTO_TEST_API_KEY = "test-key-auto"

# --auto 模式預設 provider
_AUTO_DEFAULT_PROVIDER = "gemini"


@dataclass
class WizardState:
    """精靈的執行狀態。

    記錄整個精靈流程中所有步驟的選擇結果。

    Attributes:
        provider: 選擇的 AI Provider（gemini / claude-code / openai / ollama）
        api_key: API key（gemini / openai 需要，claude-code / ollama 留空）
        model: 預設模型字串（如 gemini/gemini-2.0-flash）
        project_path: 專案根目錄路徑
        dry_run: True 表示模擬執行，不寫入任何檔案
        auto: True 表示全自動模式，所有選擇使用預設值
    """

    provider: str = ""
    api_key: str = ""
    model: str = ""
    project_path: Path = field(default_factory=Path.cwd)
    dry_run: bool = False
    auto: bool = False


class SetupWizard:
    """互動式安裝精靈。

    透過一系列互動步驟，引導使用者完成 AgentForge 的初始設定。

    支援兩種非互動模式：
    - --auto：全自動，所有選擇使用預設值（Gemini + test-key-auto）
    - --dry-run：模擬執行，不寫入任何實際檔案

    Args:
        dry_run: True 表示模擬執行。
        auto: True 表示全自動模式。
    """

    def __init__(self, dry_run: bool = False, auto: bool = False) -> None:
        """初始化安裝精靈。"""
        self._state = WizardState(dry_run=dry_run, auto=auto)
        self._detector = EnvironmentDetector()
        self._credential = CredentialManager()
        self._writer = ConfigWriter()

    # ──────────────────────── 主流程 ────────────────────────

    def run(self) -> bool:
        """執行完整精靈流程。

        Returns:
            True 表示成功完成所有步驟，False 表示使用者中途放棄或發生錯誤。
        """
        self._print_welcome()
        self._check_existing()
        self._step_choose_provider()
        self._step_configure_credential()
        self._step_verify_connection()
        self._step_write_config()
        self._print_completion()
        return True

    # ──────────────────────── 步驟方法 ────────────────────────

    def _step_choose_provider(self) -> bool:
        """步驟一：引導使用者選擇 AI 服務 Provider。

        auto 模式自動選擇 Gemini（選項 1）。

        Returns:
            True 表示選擇成功。
        """
        click.echo("\n━━━ 第一步：選擇 AI 服務 ━━━")
        click.echo("  1. Google Gemini ⭐ 推薦（免費）")
        click.echo("  2. Claude（訂閱制）")
        click.echo("  3. OpenAI / ChatGPT（付費）")
        click.echo("  4. Ollama（本地免費）")

        if self._state.auto:
            # auto 模式直接選 Gemini
            choice = "1"
        else:
            choice = click.prompt(
                "你的選擇",
                default="1",
                type=click.Choice(["1", "2", "3", "4"]),
            )

        provider = _PROVIDER_CHOICES.get(choice, "gemini")
        self._state.provider = provider
        self._state.model = _PROVIDER_MODELS.get(provider, "")

        click.echo(f"已選擇：{provider}")
        return True

    def _step_configure_credential(self) -> bool:
        """步驟二：引導使用者設定 API 通行證。

        根據 provider 顯示不同指引：
        - gemini：要求輸入 AIza 開頭的 API key
        - claude-code：確認 claude CLI 是否已安裝
        - openai：要求輸入 sk- 開頭的 API key
        - ollama：確認 Ollama 是否已安裝並執行中

        auto 模式跳過所有驗證，直接設定 test-key-auto。

        Returns:
            True 表示設定成功。
        """
        click.echo("\n━━━ 第二步：設定通行證 ━━━")
        provider = self._state.provider

        if self._state.auto:
            # auto 模式跳過輸入，設定假 key
            if provider in ("gemini", "openai"):
                self._state.api_key = _AUTO_TEST_API_KEY
            return True

        if provider == "gemini":
            return self._configure_gemini()
        elif provider == "claude-code":
            return self._configure_claude_code()
        elif provider == "openai":
            return self._configure_openai()
        elif provider == "ollama":
            return self._configure_ollama()
        else:
            click.echo(f"不認識的 Provider：{provider}")
            return False

    def _step_verify_connection(self) -> bool:
        """步驟三：測試連線是否正常。

        auto 模式或 dry_run 模式跳過實際連線測試。
        對於 claude-code 和 ollama，會實際呼叫 CLI 偵測工具。

        Returns:
            True 表示連線成功（或跳過）。
        """
        click.echo("\n━━━ 第三步：測試連線 ━━━")

        if self._state.auto:
            click.echo("（auto 模式，跳過連線測試）")
            return True

        provider = self._state.provider
        click.echo("正在測試連線...")

        if provider == "claude-code":
            ok, msg = self._detector.check_claude_cli()
            if ok:
                click.echo(f"✅ Claude CLI 可用：{msg}")
            else:
                click.echo(f"⚠️  連線測試失敗：{msg}")
                click.echo("（可繼續設定，之後再安裝 Claude CLI）")
        elif provider == "ollama":
            ok, msg = self._detector.check_ollama()
            if ok:
                click.echo("✅ Ollama 執行中")
            else:
                click.echo(f"⚠️  連線測試失敗：{msg}")
                click.echo("（可繼續設定，之後再啟動 Ollama）")
        else:
            # Gemini / OpenAI 目前只做格式驗證，不實際呼叫 API
            click.echo("✅ 通行證格式驗證通過")

        return True

    def _step_write_config(self) -> bool:
        """步驟四：建立設定檔。

        dry_run 模式只印出動作，不實際寫入。

        Returns:
            True 表示建立成功（或模擬成功）。
        """
        click.echo("\n━━━ 第四步：建立設定檔 ━━━")

        provider = self._state.provider
        model = self._state.model
        project_path = self._state.project_path
        dry_run = self._state.dry_run

        # 寫入設定檔
        created_files = self._writer.write_config(
            project_path=project_path,
            provider=provider,
            model=model,
            dry_run=dry_run,
        )

        # 儲存通行證（claude-code 和 ollama 不需要 api_key）
        api_key = self._state.api_key
        if not (self._state.auto and api_key == _AUTO_TEST_API_KEY):
            # 只在非 auto 模式、或 api_key 不是假 key 時才儲存
            if api_key or provider in ("claude-code", "ollama"):
                self._credential.save_credentials(
                    path=project_path,
                    provider=provider,
                    api_key=api_key if provider not in ("claude-code", "ollama") else "",
                    dry_run=dry_run,
                )
        else:
            # auto 模式下也記錄 provider（不寫真實 key）
            if not dry_run:
                self._credential.save_credentials(
                    path=project_path,
                    provider=provider,
                    api_key="",
                    dry_run=dry_run,
                )
            else:
                click.echo(f"[DRY-RUN] 將會建立 {project_path / '.agentforge' / 'credentials.yaml'}")

        if not dry_run:
            click.echo("✅ 設定完成！")
            for f in created_files:
                click.echo(f"   已建立：{f}")
        else:
            click.echo("（DRY-RUN 模式：所有動作僅為預覽，未寫入任何檔案）")

        return True

    # ──────────────────────── 私有設定方法 ────────────────────────

    def _configure_gemini(self) -> bool:
        """設定 Gemini API 通行證。

        Returns:
            True 表示格式驗證通過。
        """
        click.echo("請前往 https://aistudio.google.com/app/apikey 取得免費的 Gemini 通行證。")
        click.echo("格式：以 'AIza' 開頭的長字串。")

        api_key = click.prompt("請輸入你的 Gemini 通行證")

        if not self._credential.validate_gemini_key(api_key):
            click.echo("⚠️  通行證格式不正確（應以 AIza 開頭且長度 >= 30）")
            click.echo("請重新確認後再輸入。")
            # 非 auto 模式允許重試一次
            api_key = click.prompt("請重新輸入你的 Gemini 通行證")
            if not self._credential.validate_gemini_key(api_key):
                click.echo("通行證格式仍不正確，稍後可手動編輯 .agentforge/credentials.yaml。")

        self._state.api_key = api_key
        return True

    def _configure_openai(self) -> bool:
        """設定 OpenAI API 通行證。

        Returns:
            True 表示格式驗證通過。
        """
        click.echo("請前往 https://platform.openai.com/api-keys 取得 OpenAI 通行證。")
        click.echo("格式：以 'sk-' 開頭的長字串。")

        api_key = click.prompt("請輸入你的 OpenAI 通行證")

        if not self._credential.validate_openai_key(api_key):
            click.echo("⚠️  通行證格式不正確（應以 sk- 開頭且長度 >= 20）")
            click.echo("請重新確認後再輸入。")
            api_key = click.prompt("請重新輸入你的 OpenAI 通行證")
            if not self._credential.validate_openai_key(api_key):
                click.echo("通行證格式仍不正確，稍後可手動編輯 .agentforge/credentials.yaml。")

        self._state.api_key = api_key
        return True

    def _configure_claude_code(self) -> bool:
        """確認 Claude CLI 已安裝。

        Returns:
            True（即使 CLI 未安裝也繼續，只顯示警告）。
        """
        click.echo("Claude Code 使用訂閱制，不需要 API Key。")
        click.echo("請確認已安裝 Claude CLI：npm install -g @anthropic-ai/claude-code")
        click.echo("正在偵測 Claude CLI...")

        ok, msg = self._detector.check_claude_cli()
        if ok:
            click.echo(f"✅ 找到 Claude CLI：{msg}")
        else:
            click.echo(f"⚠️  未找到 Claude CLI：{msg}")
            click.echo("（可繼續設定，之後再安裝）")

        return True

    def _configure_ollama(self) -> bool:
        """確認 Ollama 已安裝並執行。

        Returns:
            True（即使 Ollama 未執行也繼續，只顯示警告）。
        """
        click.echo("Ollama 在本機執行，完全免費且私密。")
        click.echo("請確認已安裝並啟動 Ollama：https://ollama.ai")
        click.echo("正在偵測 Ollama...")

        ok, msg = self._detector.check_ollama()
        if ok:
            click.echo("✅ Ollama 執行中")
        else:
            click.echo(f"⚠️  Ollama 未執行：{msg}")
            click.echo("（可繼續設定，之後再啟動 Ollama）")

        return True

    # ──────────────────────── UI 輔助方法 ────────────────────────

    def _print_welcome(self) -> None:
        """印出歡迎訊息。"""
        click.echo("")
        click.echo("你好！歡迎使用 AgentForge")
        click.echo("這個精靈會幫你一步步完成初始設定。")

        if self._state.dry_run:
            click.echo("（DRY-RUN 模式：不會寫入任何實際檔案）")
        if self._state.auto:
            click.echo("（auto 模式：所有選擇使用預設值）")

    def _check_existing(self) -> None:
        """偵測是否已有設定檔，若有則詢問是否覆蓋。"""
        project_path = self._state.project_path

        if self._detector.check_existing_config(project_path):
            click.echo(f"\n⚠️  偵測到 {project_path / 'agentforge.yaml'} 已存在。")

            if not self._state.auto:
                proceed = click.confirm("是否繼續並覆蓋現有設定？", default=False)
                if not proceed:
                    click.echo("已取消設定。")
                    raise SystemExit(0)

    def _print_completion(self) -> None:
        """印出完成訊息。"""
        click.echo("\n" + "━" * 40)
        click.echo("AgentForge 設定完成！")
        click.echo("")
        click.echo("下一步：")
        click.echo("  agentforge list          # 查看 Agent 清單")
        click.echo("  agentforge run <agent>   # 執行 Agent")
        click.echo("━" * 40)
