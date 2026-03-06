"""
Stock Analyzer 獨立執行腳本

完全脫離 Claude session 運行，結果寫入檔案。
用法：
    python scripts/run_analysis.py analyze AAPL
    python scripts/run_analysis.py analyze 2330.TW --date 2026-03-05
    python scripts/run_analysis.py analyze BTC GC=F AAPL
    python scripts/run_analysis.py status
    python scripts/run_analysis.py clean

特點：
    - 獨立 process，不受 session timeout 影響
    - PID lock 防重複啟動
    - 細粒度進度追蹤（每個代理人階段）
    - 結果寫入 reports/<ticker>_<date>.md
    - 狀態寫入 reports/.status/<ticker>_<date>.json
"""

import argparse
import json
import os
import signal
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# 確保 src/ 在 Python path 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

REPORTS_DIR = PROJECT_ROOT / "reports"
STATUS_DIR = REPORTS_DIR / ".status"
LOCKS_DIR = REPORTS_DIR / ".locks"
LOG_DIR = REPORTS_DIR / ".logs"


# === PID Lock 機制（防重複啟動） ===

def _lock_path(ticker: str) -> Path:
    """取得 lock 檔路徑"""
    safe = ticker.replace("=", "_").replace("-", "_")
    return LOCKS_DIR / f"{safe}.pid"


def _is_pid_alive(pid: int) -> bool:
    """跨平台檢查 PID 是否仍在執行"""
    if sys.platform == "win32":
        # Windows：用 tasklist 查詢
        import subprocess
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    else:
        # Linux/Mac：用 os.kill(pid, 0)
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


def acquire_lock(ticker: str) -> bool:
    """
    嘗試取得 lock。如果已有同一 ticker 在跑，回傳 False。
    會檢查 PID 是否仍存活，避免 stale lock。
    """
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = _lock_path(ticker)

    if lock_file.exists():
        try:
            old_pid = int(lock_file.read_text().strip())
            if _is_pid_alive(old_pid):
                # process 還在 → 已有分析在跑
                print(f"⚠️ {ticker} 分析已在執行中 (PID: {old_pid})，跳過。")
                return False
            else:
                # process 已死 → stale lock，可以覆蓋
                print(f"🔓 清除 {ticker} 的 stale lock (舊 process 已結束)")
        except (ValueError, OSError):
            # lock 檔內容損壞，直接覆蓋
            print(f"🔓 清除 {ticker} 的損壞 lock 檔")

    lock_file.write_text(str(os.getpid()))
    return True


def release_lock(ticker: str):
    """釋放 lock"""
    lock_file = _lock_path(ticker)
    if lock_file.exists():
        try:
            lock_file.unlink()
        except OSError:
            pass


# === 狀態追蹤 ===

def write_status(
    ticker: str,
    date: str,
    status: str,
    step: str = "",
    detail: str = "",
    elapsed: float = 0,
):
    """
    寫入狀態檔，供外部查詢進度。

    status: pending / running / complete / error
    step: 目前在哪個階段（如 market_analyst, news_analyst, debate...）
    """
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    safe_ticker = ticker.replace("=", "_").replace("-", "_")
    status_file = STATUS_DIR / f"{safe_ticker}_{date}.json"
    data = {
        "ticker": ticker,
        "date": date,
        "status": status,
        "step": step,
        "detail": detail,
        "elapsed_sec": round(elapsed, 1),
        "pid": os.getpid(),
        "updated_at": datetime.now().isoformat(),
    }
    status_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# === 核心分析 ===

def run_single_analysis(ticker_input: str, date: str) -> bool:
    """執行單一標的分析，回傳是否成功"""
    from stock_analyzer.config import LLMConfig, StockAnalyzerConfig
    from stock_analyzer.main import StockAnalyzer
    from stock_analyzer.utils.ticker_resolver import resolve_ticker

    resolved = resolve_ticker(ticker_input)

    # 防重複啟動
    if not acquire_lock(resolved.ticker):
        return False

    # 設定 log 檔
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe_ticker = resolved.ticker.replace("=", "_").replace("-", "_")
    log_file = LOG_DIR / f"{safe_ticker}_{date}.log"

    start_time = time.time()

    def elapsed():
        return time.time() - start_time

    print(f"\n{'='*60}")
    print(f"  分析開始：{resolved.display_name}")
    print(f"  日期：{date}")
    print(f"  類型：{resolved.asset_type.value}")
    print(f"  PID：{os.getpid()}")
    print(f"{'='*60}\n")

    write_status(resolved.ticker, date, "running",
                 step="init", detail="初始化分析器...", elapsed=elapsed())

    try:
        config = StockAnalyzerConfig(
            llm=LLMConfig(
                provider=os.getenv("STOCK_LLM_PROVIDER", "ollama"),
                deep_think_model=os.getenv("STOCK_LLM_MODEL", "qwen3:14b"),
                quick_think_model=os.getenv("STOCK_LLM_MODEL", "qwen3:14b"),
                backend_url=os.getenv(
                    "STOCK_LLM_URL", "http://localhost:11434/v1"
                ),
            ),
        )

        analyzer = StockAnalyzer(config=config)

        write_status(resolved.ticker, date, "running",
                     step="analysts",
                     detail="多代理人分析進行中 — 技術/新聞/基本面/情緒分析師...",
                     elapsed=elapsed())

        # 執行分析（這一步最耗時）
        report = analyzer.analyze(ticker_input, date=date)

        write_status(resolved.ticker, date, "running",
                     step="saving", detail="儲存報告中...", elapsed=elapsed())

        # 儲存 Markdown 報告
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_file = REPORTS_DIR / f"{safe_ticker}_{date}.md"

        content = f"""# {resolved.display_name} 分析報告

**日期**: {date}
**類型**: {resolved.asset_type.value}
**代號**: {resolved.ticker}
**分析耗時**: {elapsed():.1f} 秒

---

## 📈 技術分析 (Market Report)

{report.market_report or '_無資料_'}

---

## 📰 新聞分析 (News Report)

{report.news_report or '_無資料_'}

---

## 💰 基本面分析 (Fundamentals Report)

{report.fundamentals_report or '_無資料_'}

---

## 😊 情緒分析 (Sentiment Report)

{report.sentiment_report or '_無資料_'}

---

## 📋 投資計畫 (Investment Plan)

{report.investment_plan or '_無資料_'}

---

## 🎯 最終決策 (Final Decision)

{report.final_decision or '_無決策_'}
"""
        report_file.write_text(content, encoding="utf-8")

        final_elapsed = elapsed()
        write_status(resolved.ticker, date, "complete",
                     step="done",
                     detail=f"分析完成！耗時 {final_elapsed:.1f} 秒。報告：{report_file.name}",
                     elapsed=final_elapsed)

        # 寫 log
        log_file.write_text(
            f"[{datetime.now().isoformat()}] {resolved.ticker} 分析完成，"
            f"耗時 {final_elapsed:.1f} 秒\n",
            encoding="utf-8",
        )

        print(f"\n✅ 分析完成！耗時 {final_elapsed:.1f} 秒")
        print(f"   報告已儲存：{report_file}")
        return True

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        full_trace = traceback.format_exc()
        write_status(resolved.ticker, date, "error",
                     step="error", detail=error_msg, elapsed=elapsed())

        # 寫 log（含完整 traceback）
        log_file.write_text(
            f"[{datetime.now().isoformat()}] {resolved.ticker} 分析失敗\n"
            f"{full_trace}\n",
            encoding="utf-8",
        )

        print(f"\n❌ 分析失敗：{e}")
        traceback.print_exc()
        return False

    finally:
        release_lock(resolved.ticker)


# === 狀態查詢 ===

def check_status(ticker: str = None):
    """查詢所有或特定標的的分析狀態"""
    if not STATUS_DIR.exists():
        print("尚無任何分析任務。")
        return

    status_files = sorted(STATUS_DIR.glob("*.json"))
    if not status_files:
        print("尚無任何分析任務。")
        return

    print(f"\n{'='*60}")
    print("  Stock Analyzer 任務狀態")
    print(f"{'='*60}\n")

    for sf in status_files:
        data = json.loads(sf.read_text(encoding="utf-8"))
        if ticker and ticker.upper() not in data["ticker"].upper():
            continue

        icons = {
            "pending": "⏳",
            "running": "🔄",
            "complete": "✅",
            "error": "❌",
        }
        icon = icons.get(data["status"], "❓")
        step = data.get("step", "")
        elapsed = data.get("elapsed_sec", 0)

        print(f"  {icon} {data['ticker']} ({data['date']})")
        print(f"     狀態：{data['status']}")
        if step:
            print(f"     步驟：{step}")
        if elapsed:
            print(f"     耗時：{elapsed}s")
        if data.get("detail"):
            print(f"     {data['detail'][:300]}")
        print()


def clean_status():
    """清除所有狀態檔和 lock 檔"""
    removed = 0
    for d in [STATUS_DIR, LOCKS_DIR]:
        if d.exists():
            for f in d.iterdir():
                f.unlink()
                removed += 1
    print(f"已清除 {removed} 個狀態/lock 檔案。")


# === CLI 入口 ===

def main():
    parser = argparse.ArgumentParser(
        description="Stock Analyzer 獨立執行腳本",
    )
    subparsers = parser.add_subparsers(dest="command")

    # analyze 命令
    analyze_p = subparsers.add_parser("analyze", help="執行分析")
    analyze_p.add_argument("tickers", nargs="+", help="股票代號")
    analyze_p.add_argument(
        "--date", default=datetime.now().strftime("%Y-%m-%d")
    )

    # status 命令
    status_p = subparsers.add_parser("status", help="查詢分析狀態")
    status_p.add_argument("ticker", nargs="?", default=None)

    # clean 命令
    subparsers.add_parser("clean", help="清除所有狀態和 lock 檔")

    args = parser.parse_args()

    if args.command == "status":
        check_status(args.ticker)
    elif args.command == "clean":
        clean_status()
    elif args.command == "analyze":
        success_count = 0
        for ticker in args.tickers:
            if run_single_analysis(ticker, args.date):
                success_count += 1
        print(f"\n{'='*60}")
        print(f"  完成：{success_count}/{len(args.tickers)} 個標的分析成功")
        print(f"{'='*60}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
