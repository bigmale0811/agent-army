"""Step 3: 專案初始化 — 建立目錄結構、複製 hooks/rules、產生設定檔。"""

import shutil
from pathlib import Path
from typing import Dict

# 此腳本所在的 setup/ 目錄
_SETUP_DIR = Path(__file__).parent
# agent-army 根目錄（setup/ 的上一層）
_ROOT_DIR = _SETUP_DIR.parent


def scaffold_project(context: Dict) -> Dict:
    """互動式建立專案結構。"""
    from .wizard import ask_choice, ask_input, print_info, print_ok

    # 取得專案資訊
    if not context.get("project_path"):
        default_name = "my-agent-project"
        name = ask_input("專案名稱", default=default_name)
        context["project_name"] = name

        default_path = str(Path("D:/Projects") / name)
        path_str = ask_input("專案路徑", default=default_path)
        context["project_path"] = Path(path_str)
    else:
        context["project_name"] = context["project_path"].name

    language = ask_choice("主要程式語言", ["Python", "Node.js", "Both"])
    context["language"] = language.lower()

    project_path = Path(context["project_path"])

    # 建立目錄結構
    _create_directories(project_path)
    print_ok("目錄結構已建立")

    # 複製 hooks
    _copy_hooks(project_path)
    print_ok("Hooks 已複製")

    # 複製 rules
    _copy_rules(project_path, context["language"])
    print_ok("Rules 已複製")

    # 產生 CLAUDE.md
    _generate_claude_md(project_path, context)
    print_ok("CLAUDE.md 已產生")

    # 產生 .claude/settings.json
    _generate_settings_json(project_path)
    print_ok(".claude/settings.json 已產生")

    # 初始化記憶系統
    _init_memory(project_path)
    print_ok("記憶系統已初始化")

    # 產生 .gitignore
    _generate_gitignore(project_path)
    print_ok(".gitignore 已產生")

    # 產生 .env 模板
    _generate_env_template(project_path)
    print_ok(".env 模板已產生")

    print_info(f"專案已建立在：{project_path}")
    return context


def _create_directories(project_path: Path) -> None:
    """建立專案目錄結構。"""
    dirs = [
        ".claude/rules/common",
        ".claude/rules/python",
        "scripts/hooks",
        "data/memory/sessions",
        "config",
        "src",
        "tests",
    ]
    for d in dirs:
        (project_path / d).mkdir(parents=True, exist_ok=True)


def _copy_hooks(project_path: Path) -> None:
    """從 agent-army 複製 hooks 到新專案。"""
    hooks_src = _ROOT_DIR / "scripts" / "hooks"
    hooks_dst = project_path / "scripts" / "hooks"
    hooks_dst.mkdir(parents=True, exist_ok=True)

    hook_files = [
        "session-start.js",
        "session-end.js",
        "pre-compact.js",
        "suggest-compact.js",
    ]
    for hook_file in hook_files:
        src = hooks_src / hook_file
        if src.exists():
            # 讀取內容並替換路徑
            content = src.read_text(encoding="utf-8")
            # 替換 agent-army 的路徑為新專案路徑
            content = content.replace(
                str(_ROOT_DIR).replace("\\", "/"),
                str(project_path).replace("\\", "/"),
            )
            content = content.replace(
                str(_ROOT_DIR),
                str(project_path),
            )
            (hooks_dst / hook_file).write_text(content, encoding="utf-8")


def _copy_rules(project_path: Path, language: str) -> None:
    """從 agent-army 複製 rules 到新專案。"""
    # Common rules（所有專案都需要）
    common_src = _ROOT_DIR / ".claude" / "rules" / "common"
    common_dst = project_path / ".claude" / "rules" / "common"
    common_dst.mkdir(parents=True, exist_ok=True)

    if common_src.exists():
        for rule_file in common_src.glob("*.md"):
            shutil.copy2(rule_file, common_dst / rule_file.name)

    # Python rules
    if language in ("python", "both"):
        py_src = _ROOT_DIR / ".claude" / "rules" / "python"
        py_dst = project_path / ".claude" / "rules" / "python"
        py_dst.mkdir(parents=True, exist_ok=True)

        if py_src.exists():
            for rule_file in py_src.glob("*.md"):
                shutil.copy2(rule_file, py_dst / rule_file.name)


def _generate_claude_md(project_path: Path, context: Dict) -> None:
    """從模板產生 CLAUDE.md。"""
    template_path = _SETUP_DIR / "templates" / "CLAUDE.md.template"
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
        # 替換佔位符
        content = content.replace("{{PROJECT_NAME}}", context.get("project_name", "my-project"))
        content = content.replace("{{PROJECT_PATH}}", str(project_path))
        content = content.replace("{{LANGUAGE}}", context.get("language", "python"))
    else:
        # 如果模板不存在，產生基本版本
        content = _generate_basic_claude_md(project_path, context)

    (project_path / "CLAUDE.md").write_text(content, encoding="utf-8")


def _generate_basic_claude_md(project_path: Path, context: Dict) -> str:
    """產生基本的 CLAUDE.md。"""
    name = context.get("project_name", "my-project")
    lang = context.get("language", "python")

    return f"""# {name} Project Rules

## Overview
Built on Agent Army / ECC (Everything Claude Code) framework.

## Tech Stack
- Languages: {"Python 3.12 (primary)" if lang in ("python", "both") else ""}{"Node.js" if lang in ("node.js", "both") else ""}
- Version Control: Git
- Language: Traditional Chinese for comments/docs, English for code

## Development Rules
- All files use UTF-8 encoding
- Every module needs corresponding tests
- Commit messages use Conventional Commits format

## Communication Rules
- 禁止沉默作業
- 每步回報進度
- 錯誤即時通報
- 明確完成宣告

## Memory System
- 每次新對話開始：讀取 `data/memory/active_context.md`
- 每次對話結束前：更新 `active_context.md`
- 重大決策：寫入 `data/memory/decisions.md`

## ECC Standard Workflow
- Phase 0: Research → Phase 1: Plan → Phase 2: TDD
- Phase 3: Review → Phase 4: Verify → Phase 5: Commit
- Phase 6: Document → Phase 7: Memory

## Project Paths
- Main: {project_path}
"""


def _generate_settings_json(project_path: Path) -> None:
    """產生 .claude/settings.json（hooks 設定）。"""
    import json

    # 使用正斜線路徑（Windows 也支援）
    hooks_path = str(project_path / "scripts" / "hooks").replace("\\", "/")

    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'node "{hooks_path}/suggest-compact.js"',
                        }
                    ],
                }
            ],
            "PreCompact": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'node "{hooks_path}/pre-compact.js"',
                        }
                    ],
                }
            ],
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'node "{hooks_path}/session-start.js"',
                        }
                    ],
                }
            ],
            "SessionEnd": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'node "{hooks_path}/session-end.js"',
                        }
                    ],
                }
            ],
        }
    }

    settings_path = project_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _init_memory(project_path: Path) -> None:
    """初始化記憶系統。"""
    memory_dir = project_path / "data" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "sessions").mkdir(exist_ok=True)

    # active_context.md 空模板
    active_context = memory_dir / "active_context.md"
    if not active_context.exists():
        active_context.write_text(
            "# 🧠 Active Context\n更新：（尚未開始）\n\n"
            "## 目前進行中\n- （無）\n\n"
            "## 最近完成\n- （無）\n\n"
            "## 下一步\n- （無）\n",
            encoding="utf-8",
        )

    # decisions.md 空模板
    decisions = memory_dir / "decisions.md"
    if not decisions.exists():
        decisions.write_text(
            "# 📋 重大決策紀錄\n\n（尚無紀錄）\n",
            encoding="utf-8",
        )


def _generate_gitignore(project_path: Path) -> None:
    """產生 .gitignore。"""
    gitignore = project_path / ".gitignore"
    if gitignore.exists():
        return  # 不覆蓋現有的

    gitignore.write_text(
        """# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/

# Environment
.env
.env.local

# IDE
.vscode/
.idea/

# Data
data/raw/
*.db
*.sqlite

# Claude Code
.claude/settings.local.json
.claude/worktrees/
.claude/plans/

# Testing
.pytest_cache/
htmlcov/
.coverage

# OS
.DS_Store
Thumbs.db
""",
        encoding="utf-8",
    )


def _generate_env_template(project_path: Path) -> None:
    """產生 .env 模板檔案。"""
    env_path = project_path / ".env"
    if env_path.exists():
        return  # 不覆蓋現有的

    env_path.write_text(
        """# === Cloud LLM API Keys（依需求填入）===
# OPENAI_API_KEY=sk-xxx
# DEEPSEEK_API_KEY=sk-xxx
# GROQ_API_KEY=gsk_xxx
# GOOGLE_API_KEY=xxx

# === 預設 LLM Provider ===
# DEFAULT_LLM_PROVIDER=openai
""",
        encoding="utf-8",
    )
