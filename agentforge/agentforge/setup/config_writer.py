# -*- coding: utf-8 -*-
"""設定寫入器 — 根據選擇的 Provider 產生 agentforge.yaml 及相關目錄結構。

此模組負責：
- 根據 provider 選擇對應的 YAML 範本
- 產生 agentforge.yaml + agents/example.yaml + .agentforge/ 目錄
- 建立或更新 .gitignore
- 支援 dry_run 模式（只印不寫）
"""

from __future__ import annotations

from pathlib import Path

import click

# Provider 對應的範本檔名
_PROVIDER_TEMPLATE_MAP: dict[str, str] = {
    "gemini": "agentforge_gemini.yaml",
    "claude-code": "agentforge_claude.yaml",
    "openai": "agentforge_openai.yaml",
    "ollama": "agentforge_ollama.yaml",
}

# 預設模型（搭配 provider）
_PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    "gemini": "gemini/gemini-2.0-flash",
    "claude-code": "claude-code/sonnet",
    "openai": "openai/gpt-4o-mini",
    "ollama": "ollama/qwen3:14b",
}

# 範本目錄（相對於此模組所在位置的上層 templates/）
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class ConfigWriter:
    """設定檔寫入器。

    負責產生 AgentForge 專案所需的所有設定檔案。
    支援 dry_run 模式，便於測試與預覽。
    """

    def write_config(
        self,
        project_path: Path,
        provider: str,
        model: str = "",
        dry_run: bool = False,
    ) -> list[Path]:
        """產生 agentforge.yaml + agents/example.yaml + .agentforge/ 目錄。

        根據 provider 選擇對應範本來源。
        dry_run 時只印出「[DRY-RUN] 將會建立 ...」而不實際寫入。

        Args:
            project_path: 專案根目錄路徑。
            provider: Provider 名稱（gemini / claude-code / openai / ollama）。
            model: 預設模型字串（空字串時使用 provider 預設值）。
            dry_run: True 時只印不寫。

        Returns:
            已建立（或預計建立）的檔案路徑清單。
        """
        created_files: list[Path] = []

        # 確認 provider 有對應範本
        if provider not in _PROVIDER_TEMPLATE_MAP:
            # 未知 provider，使用通用範本
            template_name = "agentforge.yaml"
        else:
            template_name = _PROVIDER_TEMPLATE_MAP[provider]

        # 決定最終模型字串
        effective_model = model or _PROVIDER_DEFAULT_MODEL.get(provider, "")

        # ── 1. 產生 agentforge.yaml ──
        config_file = project_path / "agentforge.yaml"
        template_file = _TEMPLATES_DIR / template_name

        if dry_run:
            click.echo(f"[DRY-RUN] 將會建立 {config_file}")
        else:
            project_path.mkdir(parents=True, exist_ok=True)

            if template_file.is_file():
                # 讀取範本，若需要替換 default_model 則進行替換
                content = template_file.read_text(encoding="utf-8")
                if effective_model and effective_model not in content:
                    # 替換 default_model 行
                    lines = content.splitlines()
                    new_lines = []
                    for line in lines:
                        if line.startswith("default_model:"):
                            new_lines.append(f"default_model: {effective_model}")
                        else:
                            new_lines.append(line)
                    content = "\n".join(new_lines) + "\n"
                config_file.write_text(content, encoding="utf-8")
            else:
                # 範本不存在，用最小設定
                minimal_config = (
                    f"# AgentForge 設定檔\n"
                    f"default_model: {effective_model}\n\n"
                    f"providers:\n"
                    f"  {provider}: {{}}\n"
                )
                config_file.write_text(minimal_config, encoding="utf-8")

        created_files.append(config_file)

        # ── 2. 產生 agents/example.yaml ──
        agents_dir = project_path / "agents"
        example_file = agents_dir / "example.yaml"
        example_template = _TEMPLATES_DIR / "example.yaml"

        if dry_run:
            click.echo(f"[DRY-RUN] 將會建立 {example_file}")
        else:
            agents_dir.mkdir(parents=True, exist_ok=True)
            if example_template.is_file():
                content = example_template.read_text(encoding="utf-8")
                # 將 example.yaml 中的 openai 模型替換為目前選擇的 provider 預設模型
                if effective_model:
                    content = content.replace(
                        "model: openai/gpt-4o-mini",
                        f"model: {effective_model}",
                    )
                example_file.write_text(content, encoding="utf-8")
            else:
                # 建立最小範例 agent
                minimal_agent = (
                    f"name: example-agent\n"
                    f"description: \"範例 Agent\"\n"
                    f"model: {effective_model}\n"
                    f"max_retries: 3\n\n"
                    f"steps:\n"
                    f"  - name: hello\n"
                    f"    action: llm\n"
                    f"    prompt: \"你好！請自我介紹。\"\n"
                )
                example_file.write_text(minimal_agent, encoding="utf-8")

        created_files.append(example_file)

        # ── 3. 建立 .agentforge/ 目錄 ──
        dot_dir = project_path / ".agentforge"

        if dry_run:
            click.echo(f"[DRY-RUN] 將會建立目錄 {dot_dir}")
        else:
            dot_dir.mkdir(parents=True, exist_ok=True)

        created_files.append(dot_dir)

        return created_files

    def write_gitignore(
        self,
        project_path: Path,
        dry_run: bool = False,
    ) -> Path | None:
        """建立或更新 .gitignore，確保包含 .agentforge/credentials.yaml。

        若 .gitignore 已存在，則附加而非覆蓋。
        若已包含相關規則，則不重複新增。

        Args:
            project_path: 專案根目錄路徑。
            dry_run: True 時只印不寫。

        Returns:
            .gitignore 路徑，若 dry_run 則回傳 None。
        """
        gitignore_path = project_path / ".gitignore"
        gitignore_entry = ".agentforge/credentials.yaml"

        if dry_run:
            click.echo(f"[DRY-RUN] 將會更新 {gitignore_path}，加入 {gitignore_entry}")
            return None

        # 讀取現有內容（若有）
        existing_content = ""
        if gitignore_path.is_file():
            existing_content = gitignore_path.read_text(encoding="utf-8")

        # 若已包含 credentials.yaml 相關規則，不重複新增
        if "credentials.yaml" in existing_content:
            return gitignore_path

        # 附加或建立 .gitignore
        new_entry = f"\n# AgentForge 通行證（不要上傳到 Git！）\n{gitignore_entry}\n"
        if existing_content and not existing_content.endswith("\n"):
            new_entry = "\n" + new_entry

        with open(gitignore_path, "a", encoding="utf-8") as f:
            f.write(new_entry)

        return gitignore_path
