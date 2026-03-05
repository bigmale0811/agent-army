"""LLM CLI 入口 — 讓 Claude 透過 Bash 工具呼叫雲端模型。

使用方式：
    # 列出可用 Provider
    python -m src.llm.cli --list

    # 產生文字
    python -m src.llm.cli --provider deepseek --prompt "寫一個排序演算法"

    # 對話模式（JSON 格式的 messages）
    python -m src.llm.cli --provider openai --model gpt-4o --chat '[{"role":"user","content":"你好"}]'

    # 測試連線
    python -m src.llm.cli --provider deepseek --test
"""

import argparse
import json
import sys
from pathlib import Path

# Windows 環境強制 UTF-8 輸出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


def main() -> None:
    """CLI 主入口。"""
    parser = argparse.ArgumentParser(
        description="雲端 LLM 統一呼叫工具",
        prog="python -m src.llm.cli",
    )
    parser.add_argument(
        "--provider", "-p",
        help="Provider 名稱（openai, deepseek, groq, together, gemini）",
    )
    parser.add_argument(
        "--model", "-m",
        help="模型名稱（預設使用 Provider 的預設模型）",
    )
    parser.add_argument(
        "--prompt",
        help="提示詞（單次產生模式）",
    )
    parser.add_argument(
        "--chat",
        help="對話訊息（JSON 格式的 messages 陣列）",
    )
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        help="溫度參數（0.0-2.0）",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        help="最大產生 token 數",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有 Provider 及其可用狀態",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="測試 Provider 連線",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="設定檔路徑（預設 config/llm_providers.yaml）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="以 JSON 格式輸出結果",
    )

    args = parser.parse_args()

    # 載入 .env（如果有 python-dotenv）
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # 列出 Provider
    if args.list:
        _handle_list(args)
        return

    # 需要 Provider 的操作
    if not args.provider:
        # 嘗試使用預設 Provider
        from .config import get_default_provider
        args.provider = get_default_provider(args.config)

    # 測試連線
    if args.test:
        _handle_test(args)
        return

    # 產生文字
    if args.prompt:
        _handle_generate(args)
        return

    # 對話模式
    if args.chat:
        _handle_chat(args)
        return

    # 如果從 stdin 讀取 prompt
    if not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
        if prompt:
            args.prompt = prompt
            _handle_generate(args)
            return

    parser.print_help()


def _handle_list(args: argparse.Namespace) -> None:
    """列出所有 Provider。"""
    from .client import LLMClient

    providers = LLMClient.list_all(args.config)

    if args.output_json:
        print(json.dumps(providers, ensure_ascii=False, indent=2))
        return

    print("\n📋 已設定的 LLM Provider：\n")
    for p in providers:
        status = "✅" if p["available"] else "❌"
        print(f"  {status} {p['name']:12s} | {p['model']:30s} | {p['description']}")
        if not p["available"]:
            print(f"     ↳ 需設定環境變數：{p['api_key_env']}")
    print()


def _handle_test(args: argparse.Namespace) -> None:
    """測試 Provider 連線。"""
    from .client import LLMClient

    try:
        client = LLMClient(
            provider=args.provider,
            model=args.model,
            config_path=args.config,
        )
        success = client.test_connection()

        if args.output_json:
            print(json.dumps({
                "provider": client.provider_name,
                "model": client.model,
                "success": success,
            }))
        elif success:
            print(f"✅ {client.provider_name} ({client.model}) 連線正常")
        else:
            print(f"❌ {client.provider_name} ({client.model}) 連線失敗")
            sys.exit(1)

    except Exception as e:
        if args.output_json:
            print(json.dumps({"error": str(e), "success": False}))
        else:
            print(f"❌ 錯誤：{e}")
        sys.exit(1)


def _handle_generate(args: argparse.Namespace) -> None:
    """產生文字回應。"""
    from .client import LLMClient

    try:
        client = LLMClient(
            provider=args.provider,
            model=args.model,
            config_path=args.config,
        )

        kwargs = {}
        if args.temperature is not None:
            kwargs["temperature"] = args.temperature
        if args.max_tokens is not None:
            kwargs["max_tokens"] = args.max_tokens

        response = client.generate(args.prompt, **kwargs)

        if args.output_json:
            print(json.dumps({
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": response.usage,
            }, ensure_ascii=False, indent=2))
        else:
            print(response.content)

    except Exception as e:
        if args.output_json:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"❌ 錯誤：{e}", file=sys.stderr)
        sys.exit(1)


def _handle_chat(args: argparse.Namespace) -> None:
    """對話模式。"""
    from .client import LLMClient

    try:
        messages = json.loads(args.chat)
        if not isinstance(messages, list):
            raise ValueError("--chat 參數需要是 JSON 陣列格式")

        client = LLMClient(
            provider=args.provider,
            model=args.model,
            config_path=args.config,
        )

        kwargs = {}
        if args.temperature is not None:
            kwargs["temperature"] = args.temperature
        if args.max_tokens is not None:
            kwargs["max_tokens"] = args.max_tokens

        response = client.chat(messages, **kwargs)

        if args.output_json:
            print(json.dumps({
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": response.usage,
            }, ensure_ascii=False, indent=2))
        else:
            print(response.content)

    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤：{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.output_json:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"❌ 錯誤：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
