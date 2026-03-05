"""Step 4: 雲端模型設定 — 設定 API key 並測試連線。"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

# 支援的雲端 Provider
CLOUD_PROVIDERS = {
    "OpenAI": {
        "env_var": "OPENAI_API_KEY",
        "description": "GPT-4o、GPT-4o-mini（通用型模型）",
        "test_cmd": "openai",
    },
    "DeepSeek": {
        "env_var": "DEEPSEEK_API_KEY",
        "description": "DeepSeek-Chat、DeepSeek-Coder（高性價比）",
        "test_cmd": "deepseek",
    },
    "Groq": {
        "env_var": "GROQ_API_KEY",
        "description": "Llama 3.3（超低延遲推理）",
        "test_cmd": "groq",
    },
    "Together AI": {
        "env_var": "TOGETHER_API_KEY",
        "description": "多模型平台（Llama、Mixtral 等）",
        "test_cmd": "together",
    },
    "Google Gemini": {
        "env_var": "GOOGLE_API_KEY",
        "description": "Gemini 2.0 Flash/Pro（多模態）",
        "test_cmd": "gemini",
    },
}


def setup_cloud_models(context: Dict) -> Dict:
    """互動式設定雲端模型。"""
    from .wizard import (
        ask_input,
        ask_multi_choice,
        ask_yes_no,
        print_fail,
        print_info,
        print_ok,
        print_warn,
    )

    provider_names = list(CLOUD_PROVIDERS.keys())
    display_choices = [
        f"{name} — {info['description']}"
        for name, info in CLOUD_PROVIDERS.items()
    ]

    selected_display = ask_multi_choice(
        "選擇要啟用的 Provider：", display_choices
    )

    if not selected_display:
        print_info("未選擇任何 Provider")
        return context

    # 從顯示文字提取 Provider 名稱
    selected_names = []
    for display in selected_display:
        name = display.split(" — ")[0]
        selected_names.append(name)

    project_path = Path(context.get("project_path", "."))
    env_lines: List[str] = []
    configured_providers: List[str] = []

    for name in selected_names:
        info = CLOUD_PROVIDERS[name]
        env_var = info["env_var"]

        print(f"\n  📝 設定 {name}:")

        # 檢查是否已有環境變數
        existing_key = os.environ.get(env_var)
        if existing_key:
            print_info(f"偵測到現有的 {env_var}")
            if not ask_yes_no("要使用現有的 key 嗎？"):
                existing_key = None

        if not existing_key:
            # 取得 API key
            api_key = _ask_api_key(name, env_var)
            if not api_key:
                print_warn(f"略過 {name}")
                continue
        else:
            api_key = existing_key

        # 寫入 .env
        env_lines.append(f"{env_var}={api_key}")
        configured_providers.append(name.lower().replace(" ", "_"))

        # 測試連線
        if ask_yes_no(f"要測試 {name} 連線嗎？"):
            _test_provider_connection(
                name, info["test_cmd"], api_key, info["env_var"]
            )

    # 寫入 .env
    if env_lines:
        _append_to_env(project_path, env_lines)
        print_ok(f"API key 已存入 .env（{len(env_lines)} 個）")

    context["cloud_providers"] = configured_providers
    return context


def _ask_api_key(provider_name: str, env_var: str) -> str:
    """詢問 API key（隱藏輸入）。"""
    from .wizard import print_info

    print_info(f"環境變數名稱：{env_var}")

    # 提供取得 API key 的連結
    links = {
        "OpenAI": "https://platform.openai.com/api-keys",
        "DeepSeek": "https://platform.deepseek.com/api_keys",
        "Groq": "https://console.groq.com/keys",
        "Together AI": "https://api.together.xyz/settings/api-keys",
        "Google Gemini": "https://aistudio.google.com/apikey",
    }
    if provider_name in links:
        print_info(f"取得 API key：{links[provider_name]}")

    # 直接用一般輸入（getpass 在部分 Windows 終端會卡住）
    api_key = input(f"  請輸入 {provider_name} API Key：").strip()

    return api_key


def _test_provider_connection(
    name: str, provider_id: str, api_key: str, env_var: str
) -> None:
    """測試 Provider 連線。"""
    from .wizard import print_fail, print_info, print_ok

    print_info(f"測試 {name} 連線...")

    # 設定臨時環境變數
    env = os.environ.copy()
    env[env_var] = api_key

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "src.llm.cli",
                "--provider", provider_id,
                "--test", "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            cwd=str(Path(__file__).parent.parent),
        )
        if result.returncode == 0:
            print_ok(f"{name} 連線正常")
        else:
            print_fail(f"{name} 連線失敗：{result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        print_fail(f"{name} 連線逾時")
    except Exception as e:
        print_fail(f"測試失敗：{e}")


def _append_to_env(project_path: Path, lines: List[str]) -> None:
    """將設定附加到 .env 檔案。"""
    env_path = project_path / ".env"

    existing_content = ""
    if env_path.exists():
        existing_content = env_path.read_text(encoding="utf-8")

    # 加入雲端模型區塊
    new_section = "\n# === Cloud LLM API Keys ===\n"
    for line in lines:
        key = line.split("=")[0]
        # 如果已存在則跳過
        if key in existing_content:
            continue
        new_section += f"{line}\n"

    if new_section.strip() != "# === Cloud LLM API Keys ===":
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(new_section)
