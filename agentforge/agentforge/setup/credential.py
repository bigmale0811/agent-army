# -*- coding: utf-8 -*-
"""通行證管理器 — 處理 API Key 的驗證、儲存與讀取。

此模組負責：
- 驗證 Gemini / OpenAI API key 格式（不呼叫實際 API）
- 確認 claude CLI 是否已安裝
- 將通行證安全儲存到 .agentforge/credentials.yaml
- 自動更新 .gitignore 防止通行證外洩
- 讀取已儲存的通行證
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
import yaml

from agentforge.setup.detector import EnvironmentDetector

# 通行證檔案相對路徑
_CRED_DIR = ".agentforge"
_CRED_FILE = "credentials.yaml"

# 安全警語（寫入 credentials.yaml 開頭）
_SECURITY_WARNING = """\
# ⚠️ 警告：這個檔案包含你的通行證（API Key），請不要分享給任何人！
# 如果不小心外洩，請立即去重新產生一個新的。
# 請確認 .gitignore 已包含 .agentforge/credentials.yaml

"""


class CredentialManager:
    """通行證管理器。

    負責驗證、儲存與讀取 API 通行證。
    所有驗證方法只做格式檢查，不呼叫實際 API。
    """

    def __init__(self) -> None:
        """初始化通行證管理器。"""
        self._detector = EnvironmentDetector()

    # ──────────────────────── 驗證方法 ────────────────────────

    def validate_gemini_key(self, api_key: str) -> bool:
        """驗證 Gemini API key 格式。

        有效格式：以 "AIza" 開頭，且長度 >= 30 個字元。
        只做格式驗證，不實際呼叫 Google API。

        Args:
            api_key: 要驗證的 Gemini API key。

        Returns:
            True 表示格式有效，False 表示無效。
        """
        if not api_key:
            return False
        if not api_key.startswith("AIza"):
            return False
        if len(api_key) < 30:
            return False
        return True

    def validate_openai_key(self, api_key: str) -> bool:
        """驗證 OpenAI API key 格式。

        有效格式：以 "sk-" 開頭，且長度 >= 20 個字元。
        只做格式驗證，不實際呼叫 OpenAI API。

        Args:
            api_key: 要驗證的 OpenAI API key。

        Returns:
            True 表示格式有效，False 表示無效。
        """
        if not api_key:
            return False
        if not api_key.startswith("sk-"):
            return False
        if len(api_key) < 20:
            return False
        return True

    def validate_claude_cli(self) -> tuple[bool, str]:
        """確認 claude CLI 是否已安裝。

        委派給 EnvironmentDetector.check_claude_cli()。

        Returns:
            (是否可用, 訊息字串)
        """
        return self._detector.check_claude_cli()

    # ──────────────────────── 儲存 / 讀取 ────────────────────────

    def save_credentials(
        self,
        path: Path,
        provider: str,
        api_key: str = "",
        dry_run: bool = False,
    ) -> Path:
        """將通行證存入 .agentforge/credentials.yaml。

        檔案開頭加安全警語。dry_run 模式只印出動作，不實際寫入。
        同時更新 .gitignore 以防止通行證外洩。

        Args:
            path: 專案根目錄路徑。
            provider: Provider 名稱（如 "gemini", "openai", "claude-code", "ollama"）。
            api_key: API Key 字串（claude-code 和 ollama 可留空）。
            dry_run: True 時只印不寫。

        Returns:
            credentials.yaml 的完整路徑（dry_run 時仍回傳預期路徑）。
        """
        cred_dir = path / _CRED_DIR
        cred_file = cred_dir / _CRED_FILE

        # 組合要寫入的資料
        data: dict[str, object] = {
            "provider": provider,
            "api_key": api_key,
        }
        yaml_content = _SECURITY_WARNING + yaml.dump(
            data,
            allow_unicode=True,
            default_flow_style=False,
        )

        if dry_run:
            click.echo(f"[DRY-RUN] 將會建立 {cred_file}")
            click.echo(f"[DRY-RUN]   provider: {provider}")
            if api_key:
                click.echo(f"[DRY-RUN]   api_key: {api_key[:8]}...")
        else:
            # 建立 .agentforge/ 目錄
            cred_dir.mkdir(parents=True, exist_ok=True)
            cred_file.write_text(yaml_content, encoding="utf-8")

        # 更新 .gitignore（dry_run 模式也會跳過）
        self._update_gitignore(path, dry_run=dry_run)

        return cred_file

    def load_credentials(self, path: Path) -> dict[str, str]:
        """讀取 .agentforge/credentials.yaml，回傳通行證 dict。

        Args:
            path: 專案根目錄路徑。

        Returns:
            包含 provider 和 api_key 的 dict。
            若檔案不存在則回傳空 dict。
        """
        cred_file = path / _CRED_DIR / _CRED_FILE

        if not cred_file.is_file():
            return {}

        try:
            raw = yaml.safe_load(cred_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return {}
            return {k: str(v) if v is not None else "" for k, v in raw.items()}
        except yaml.YAMLError:
            return {}

    # ──────────────────────── 私有輔助方法 ────────────────────────

    def _update_gitignore(self, path: Path, dry_run: bool = False) -> None:
        """建立或更新 .gitignore，確保包含 credentials.yaml。

        若 .gitignore 已存在，則附加而非覆蓋。
        若 .gitignore 已包含相關規則，則不重複新增。

        Args:
            path: 專案根目錄路徑。
            dry_run: True 時只印不寫。
        """
        gitignore_path = path / ".gitignore"
        gitignore_entry = ".agentforge/credentials.yaml"

        if dry_run:
            click.echo(f"[DRY-RUN] 將會更新 {gitignore_path}，加入 {gitignore_entry}")
            return

        # 讀取現有內容（若有）
        existing_content = ""
        if gitignore_path.is_file():
            existing_content = gitignore_path.read_text(encoding="utf-8")

        # 若已包含 credentials.yaml 相關規則，不重複新增
        if "credentials.yaml" in existing_content:
            return

        # 附加或建立 .gitignore
        new_entry = f"\n# AgentForge 通行證（不要上傳到 Git！）\n{gitignore_entry}\n"
        if existing_content and not existing_content.endswith("\n"):
            new_entry = "\n" + new_entry

        with open(gitignore_path, "a", encoding="utf-8") as f:
            f.write(new_entry)
