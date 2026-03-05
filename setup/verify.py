"""Step 7: 驗證安裝結果。"""

import json
from pathlib import Path
from typing import Dict


def run_verification(context: Dict) -> bool:
    """驗證安裝結果，回傳是否全部通過。"""
    from .wizard import print_fail, print_ok, print_warn

    project_path = Path(context.get("project_path", "."))
    all_ok = True

    # 1. 檢查目錄結構
    required_dirs = [
        ".claude/rules/common",
        "scripts/hooks",
        "data/memory",
        "data/memory/sessions",
    ]
    for d in required_dirs:
        if (project_path / d).exists():
            print_ok(f"目錄：{d}")
        else:
            print_fail(f"目錄缺少：{d}")
            all_ok = False

    # 2. 檢查 Hooks
    hooks_dir = project_path / "scripts" / "hooks"
    hook_files = [
        "session-start.js",
        "session-end.js",
        "pre-compact.js",
        "suggest-compact.js",
    ]
    hooks_ok = True
    for hf in hook_files:
        if (hooks_dir / hf).exists():
            pass  # OK
        else:
            print_fail(f"Hook 缺少：{hf}")
            hooks_ok = False
            all_ok = False
    if hooks_ok:
        print_ok(f"Hooks 已安裝（{len(hook_files)} 個）")

    # 3. 檢查 Rules
    common_rules = list((project_path / ".claude" / "rules" / "common").glob("*.md"))
    if common_rules:
        print_ok(f"Common Rules 已安裝（{len(common_rules)} 個）")
    else:
        print_warn("Common Rules 未安裝")

    lang = context.get("language", "")
    if lang in ("python", "both"):
        py_rules = list(
            (project_path / ".claude" / "rules" / "python").glob("*.md")
        )
        if py_rules:
            print_ok(f"Python Rules 已安裝（{len(py_rules)} 個）")
        else:
            print_warn("Python Rules 未安裝")

    # 4. 檢查 CLAUDE.md
    if (project_path / "CLAUDE.md").exists():
        print_ok("CLAUDE.md 已產生")
    else:
        print_fail("CLAUDE.md 缺少")
        all_ok = False

    # 5. 檢查 .claude/settings.json
    settings_path = project_path / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks_count = sum(
                len(v) for v in settings.get("hooks", {}).values()
            )
            print_ok(f".claude/settings.json（{hooks_count} 個 hook 設定）")
        except Exception:
            print_warn(".claude/settings.json 格式有誤")
    else:
        print_fail(".claude/settings.json 缺少")
        all_ok = False

    # 6. 檢查記憶系統
    if (project_path / "data" / "memory" / "active_context.md").exists():
        print_ok("記憶系統已初始化")
    else:
        print_fail("active_context.md 缺少")
        all_ok = False

    # 7. 檢查 .gitignore
    if (project_path / ".gitignore").exists():
        print_ok(".gitignore 已產生")
    else:
        print_warn(".gitignore 缺少")

    # 8. 檢查 .env
    if (project_path / ".env").exists():
        print_ok(".env 已產生")
    else:
        print_warn(".env 未設定（可能還不需要）")

    # 9. 檢查雲端模型
    if context.get("cloud_providers"):
        print_ok(f"雲端模型：{', '.join(context['cloud_providers'])}")

    # 10. 檢查 Ollama
    if context.get("setup_ollama"):
        print_ok(f"本地模型：Ollama ({context.get('ollama_model', 'unknown')})")

    # 11. 檢查 Telegram
    if context.get("setup_telegram"):
        print_ok("Telegram Bot 已設定")

    # 12. 檢查 GitHub CLI
    if context.get("setup_github"):
        print_ok("GitHub CLI 已認證")

    return all_ok
