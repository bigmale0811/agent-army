"""Step 5: Ollama 本地模型設定（可選）。"""

import shutil
import subprocess
from typing import Dict


def setup_ollama(context: Dict) -> Dict:
    """互動式設定 Ollama。"""
    from .wizard import ask_input, ask_yes_no, print_fail, print_info, print_ok, print_warn

    # 檢查 Ollama 是否安裝
    if not shutil.which("ollama"):
        print_fail("Ollama 未安裝")
        print_info("下載：https://ollama.com/download")
        print_info("安裝後重新執行 python setup.py --add-ollama")
        return context

    # 檢查 Ollama 是否在執行
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print_ok("Ollama 正在執行")
            models = result.stdout.strip()
            if models:
                print_info(f"已安裝的模型：\n{models}")
        else:
            print_warn("Ollama 已安裝但未執行")
            print_info("請先啟動 Ollama：ollama serve")
            return context
    except Exception as e:
        print_warn(f"無法連線 Ollama：{e}")
        return context

    # 選擇模型
    default_model = "qwen3:14b"
    model = ask_input("要使用的模型", default=default_model)

    # 檢查模型是否已下載
    if model not in (result.stdout or ""):
        if ask_yes_no(f"要下載模型 {model} 嗎？（可能需要幾分鐘）"):
            print_info(f"正在下載 {model}...")
            try:
                pull_result = subprocess.run(
                    ["ollama", "pull", model],
                    timeout=600,
                )
                if pull_result.returncode == 0:
                    print_ok(f"{model} 下載完成")
                else:
                    print_fail(f"{model} 下載失敗")
            except subprocess.TimeoutExpired:
                print_fail("下載逾時（超過 10 分鐘）")
            except Exception as e:
                print_fail(f"下載失敗：{e}")
    else:
        print_ok(f"{model} 已安裝")

    context["setup_ollama"] = True
    context["ollama_model"] = model
    print_ok("Ollama 設定完成")
    return context
