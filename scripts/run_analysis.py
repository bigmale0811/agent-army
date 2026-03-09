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
import sys
import time
import traceback
import urllib.request
import urllib.parse
from typing import Optional
from datetime import datetime
from pathlib import Path

# 確保 src/ 在 Python path 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 載入 .env 環境變數
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass  # 無 dotenv 時依賴系統環境變數

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Windows CP950 console 無法顯示 emoji，強制使用 UTF-8 stdout/stderr
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPORTS_DIR = PROJECT_ROOT / "reports"
STATUS_DIR = REPORTS_DIR / ".status"
LOCKS_DIR = REPORTS_DIR / ".locks"
LOG_DIR = REPORTS_DIR / ".logs"


# === Telegram 通知 ===

def _telegram_send_message(text: str) -> bool:
    """透過 Telegram Bot API 發送文字訊息（最大 4096 字元）"""
    token = os.getenv("STOCK_BOT_TOKEN", "")
    chat_id = os.getenv("STOCK_CHAT_ID", "")
    if not token or not chat_id:
        print("⚠️ STOCK_BOT_TOKEN 或 STOCK_CHAT_ID 未設定，跳過 Telegram 通知")
        return False

    # Telegram 訊息上限 4096 字元，超過則截斷
    if len(text) > 4000:
        text = text[:3950] + "\n\n⋯（訊息過長，已截斷。完整報告見附件）"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"⚠️ Telegram 發送訊息失敗: {e}")
        return False


def _telegram_send_document(file_path: Path, caption: str = "") -> bool:
    """透過 Telegram Bot API 發送檔案（完整 .md 報告）"""
    token = os.getenv("STOCK_BOT_TOKEN", "")
    chat_id = os.getenv("STOCK_CHAT_ID", "")
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendDocument"

    # 手動建構 multipart/form-data（不依賴 requests 套件）
    boundary = "----StockAnalyzerBoundary"
    body = b""

    # chat_id 欄位
    body += f"--{boundary}\r\n".encode()
    body += b"Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n"
    body += f"{chat_id}\r\n".encode()

    # caption 欄位
    if caption:
        # 截斷 caption（Telegram 限制 1024 字元）
        cap = caption[:1000] if len(caption) > 1000 else caption
        body += f"--{boundary}\r\n".encode()
        body += b"Content-Disposition: form-data; name=\"caption\"\r\n\r\n"
        body += f"{cap}\r\n".encode()

    # document 欄位（檔案）
    file_content = file_path.read_bytes()
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="document"; '
        f'filename="{file_path.name}"\r\n'
    ).encode()
    body += b"Content-Type: text/markdown\r\n\r\n"
    body += file_content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"⚠️ Telegram 發送檔案失敗: {e}")
        return False


def notify_analysis_complete(
    display_name: str,
    ticker: str,
    date: str,
    elapsed_sec: float,
    report_file: Path,
    report: object = None,
) -> None:
    """
    分析完成後，生成 PDF 報告並透過 Telegram 發送。

    結構：摘要訊息 → PDF 附件（封面 → 重點摘要 → 正式內容）
    """
    # 1. 發送結構化摘要（從 final_decision 提取重點）
    decision_text = ""
    if report is not None:
        decision_text = getattr(report, "final_decision", "") or ""
    elif report_file.exists():
        import re as _re
        _content = report_file.read_text(encoding="utf-8")
        _m = _re.search(r"## 🎯.*?\n(.*?)(?=\Z)", _content, _re.DOTALL)
        decision_text = _m.group(1).strip() if _m else ""

    if decision_text and len(decision_text) > 20:
        # 最終決策已包含結構化格式，直接發送
        header = f"✨ {display_name} 分析報告 ✨\n推薦日期：{date}\n{'─' * 20}\n"
        _telegram_send_message(header + decision_text)
    else:
        # fallback：基本摘要
        _telegram_send_message(
            f"📊 {display_name} 分析完成\n📅 {date} | ⏱ {elapsed_sec:.0f}秒"
        )
    _telegram_send_message("完整分析 PDF 如下 👇")

    # 2. 生成 PDF 並發送
    try:
        from stock_analyzer.utils.pdf_report import generate_pdf_report

        # 從 report 物件取得各段落，或從 .md 檔案解析
        if report is not None:
            pdf_path = generate_pdf_report(
                display_name=display_name,
                ticker=ticker,
                date=date,
                elapsed_sec=elapsed_sec,
                market_report=getattr(report, "market_report", "") or "",
                news_report=getattr(report, "news_report", "") or "",
                fundamentals_report=getattr(report, "fundamentals_report", "") or "",
                sentiment_report=getattr(report, "sentiment_report", "") or "",
                investment_plan=getattr(report, "investment_plan", "") or "",
                final_decision=getattr(report, "final_decision", "") or "",
            )
        else:
            # 從 .md 檔案解析各段落
            sections = _parse_md_sections(report_file)
            pdf_path = generate_pdf_report(
                display_name=display_name,
                ticker=ticker,
                date=date,
                elapsed_sec=elapsed_sec,
                **sections,
            )

        _telegram_send_document(pdf_path, caption=f"{display_name} - {date}")
        print(f"📄 PDF 報告已發送：{pdf_path}")

    except Exception as e:
        print(f"⚠️ PDF 生成失敗: {e}")
        # fallback：發送原始 .md 檔
        _telegram_send_document(report_file, caption=f"{display_name} - {date}")


def _parse_md_sections(report_file: Path) -> dict:
    """從 .md 報告檔案解析出各段落內容"""
    import re
    content = report_file.read_text(encoding="utf-8")

    def _extract(pattern: str) -> str:
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    return {
        "market_report": _extract(
            r"## 📈.*?\n(.*?)(?=\n## [📰💰😊📋🎯]|\Z)"
        ),
        "news_report": _extract(
            r"## 📰.*?\n(.*?)(?=\n## [💰😊📋🎯]|\Z)"
        ),
        "fundamentals_report": _extract(
            r"## 💰.*?\n(.*?)(?=\n## [😊📋🎯]|\Z)"
        ),
        "sentiment_report": _extract(
            r"## 😊.*?\n(.*?)(?=\n## [📋🎯]|\Z)"
        ),
        "investment_plan": _extract(
            r"## 📋.*?\n(.*?)(?=\n## 🎯|\Z)"
        ),
        "final_decision": _extract(
            r"## 🎯.*?\n(.*?)(?=\Z)"
        ),
    }


def notify_analysis_error(
    display_name: str,
    ticker: str,
    date: str,
    error_msg: str,
) -> None:
    """分析失敗時，發送錯誤通知至 Telegram"""
    text = (
        f"❌ *{display_name}* 分析失敗\n\n"
        f"📅 日期：{date}\n"
        f"🏷 代號：`{ticker}`\n"
        f"💥 錯誤：`{error_msg[:500]}`"
    )
    _telegram_send_message(text)


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

    # NOTE: Non-atomic check-then-write; acceptable for single-orchestrator use.
    try:
        lock_file.write_text(str(os.getpid()))
    except OSError as e:
        print(f"❌ 無法寫入 lock 檔 {ticker}: {e}")
        return False
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

        # 寫 log（append 模式，避免覆蓋 stdout 重導向的分析內容）
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(
                f"\n[{datetime.now().isoformat()}] {resolved.ticker} 分析完成，"
                f"耗時 {final_elapsed:.1f} 秒\n"
            )

        print(f"\n✅ 分析完成！耗時 {final_elapsed:.1f} 秒")
        print(f"   報告已儲存：{report_file}")

        # 透過 Telegram 推送 PDF 報告
        notify_analysis_complete(
            display_name=resolved.display_name,
            ticker=resolved.ticker,
            date=date,
            elapsed_sec=final_elapsed,
            report_file=report_file,
            report=report,
        )

        return True

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        full_trace = traceback.format_exc()
        write_status(resolved.ticker, date, "error",
                     step="error", detail=error_msg, elapsed=elapsed())

        # 寫 log（append 模式，保留 stdout 重導向的分析內容）
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(
                f"\n[{datetime.now().isoformat()}] {resolved.ticker} 分析失敗\n"
                f"{full_trace}\n"
            )

        print(f"\n❌ 分析失敗：{e}")
        traceback.print_exc()

        # 透過 Telegram 通知失敗
        notify_analysis_error(
            display_name=resolved.display_name,
            ticker=resolved.ticker,
            date=date,
            error_msg=error_msg,
        )

        return False

    finally:
        release_lock(resolved.ticker)


# === 狀態查詢 ===

def check_status(ticker: Optional[str] = None) -> None:
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
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [corrupt] {sf.name}: {e}")
            continue
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
                try:
                    f.unlink()
                    removed += 1
                except OSError as e:
                    print(f"  ⚠️ 無法刪除 {f.name}: {e}")
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
