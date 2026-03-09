"""
股票分析報告 PDF 生成器

將 Markdown 分析報告轉換為中文 PDF，結構：
1. 封面（標的名稱、日期、代號）
2. 重點摘要（從最終決策 + 投資計畫提取）
3. 正式內容（技術/新聞/基本面/情緒/投資計畫/最終決策）

使用 fpdf2 + 微軟雅黑字體（Windows 內建）。
"""

import re
from pathlib import Path
from typing import Optional

from fpdf import FPDF

# Windows 內建中文字體路徑
FONT_PATH = Path("C:/Windows/Fonts/msyh.ttc")
FONT_BOLD_PATH = Path("C:/Windows/Fonts/msyhbd.ttc")


class StockReportPDF(FPDF):
    """股票分析報告 PDF 文件"""

    def __init__(self) -> None:
        super().__init__()
        # 載入中文字體（微軟雅黑）
        self.add_font("msyh", "", str(FONT_PATH), uni=True)
        if FONT_BOLD_PATH.exists():
            self.add_font("msyh", "B", str(FONT_BOLD_PATH), uni=True)
        else:
            # 沒有粗體就用普通字體代替
            self.add_font("msyh", "B", str(FONT_PATH), uni=True)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self) -> None:
        """頁首"""
        self.set_font("msyh", "B", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, "Stock Analyzer Report", align="R")
        self.ln(8)

    def footer(self) -> None:
        """頁尾 — 頁碼"""
        self.set_y(-15)
        self.set_font("msyh", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"第 {self.page_no()} 頁", align="C")

    def add_cover(
        self, display_name: str, ticker: str, date: str, elapsed_sec: float
    ) -> None:
        """封面頁"""
        self.add_page()
        self.ln(40)
        # 標題
        self.set_font("msyh", "B", 28)
        self.set_text_color(30, 30, 30)
        self.cell(0, 15, display_name, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        # 副標題
        self.set_font("msyh", "", 14)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, "投資分析報告", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(15)
        # 基本資訊
        self.set_font("msyh", "", 12)
        self.set_text_color(60, 60, 60)
        info_lines = [
            f"代號：{ticker}",
            f"分析日期：{date}",
            f"分析耗時：{elapsed_sec:.0f} 秒",
        ]
        for line in info_lines:
            self.cell(0, 8, line, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(30)
        # 分隔線
        self.set_draw_color(200, 200, 200)
        self.line(30, self.get_y(), self.w - 30, self.get_y())

    def add_summary_section(self, decision: str, plan: str) -> None:
        """重點摘要區塊 — 模擬「跨週金股」格式"""
        self.add_page()
        self._section_title("重點摘要")
        self.ln(3)

        # 最終決策（結構化格式：標的/操作/價格/停損/目標）
        if decision and decision.strip() not in ("_無決策_", ""):
            # 用較大字體顯示決策（最重要的資訊）
            self.set_font("msyh", "B", 12)
            self.set_text_color(30, 30, 30)
            cleaned = _clean_markdown(decision)
            self.multi_cell(0, 7, cleaned)
            self.ln(8)

        # 投資計畫（較詳細的策略說明）
        if plan and plan.strip() not in ("_無資料_", ""):
            self._subsection_title("投資策略")
            self._body_text(plan)

    def add_detail_section(self, title: str, content: str) -> None:
        """正式內容段落"""
        if not content or content.strip() == "_無資料_":
            return
        self.add_page()
        self._section_title(title)
        self.ln(3)
        self._body_text(content)

    def _section_title(self, text: str) -> None:
        """段落大標題"""
        self.set_font("msyh", "B", 16)
        self.set_text_color(30, 30, 30)
        self.cell(0, 12, text, new_x="LMARGIN", new_y="NEXT")
        # 底線
        self.set_draw_color(70, 130, 180)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.ln(5)

    def _subsection_title(self, text: str) -> None:
        """子標題"""
        self.set_font("msyh", "B", 13)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def _body_text(self, text: str) -> None:
        """內文（處理 Markdown 基本格式）"""
        self.set_font("msyh", "", 10)
        self.set_text_color(40, 40, 40)
        # 清除 Markdown 格式標記，保留純文字
        cleaned = _clean_markdown(text)
        self.multi_cell(0, 6, cleaned)


def _clean_markdown(text: str) -> str:
    """清除 Markdown 格式標記，轉為適合 PDF 的純文字"""
    # 移除 HTML 標籤
    text = re.sub(r"<[^>]+>", "", text)
    # 標題標記 → 保留文字
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 粗體/斜體 → 保留文字
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # 行內代碼
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 連結 [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 表格分隔線 |---|---| → 移除
    text = re.sub(r"^\|[-:| ]+\|$", "", text, flags=re.MULTILINE)
    # 表格管線 | → 空格
    text = re.sub(r"\|", "  ", text)
    # 獨立的 --- 分隔線
    text = re.sub(r"^\s*---+\s*$", "", text, flags=re.MULTILINE)
    # 多餘空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def generate_pdf_report(
    display_name: str,
    ticker: str,
    date: str,
    elapsed_sec: float,
    market_report: str,
    news_report: str,
    fundamentals_report: str,
    sentiment_report: str,
    investment_plan: str,
    final_decision: str,
    output_path: Optional[Path] = None,
) -> Path:
    """
    生成完整的股票分析 PDF 報告。

    結構：封面 → 重點摘要 → 技術分析 → 新聞分析 → 基本面 → 情緒 → 完整計畫

    Args:
        display_name: 標的顯示名稱（如 "台積電 TSMC"）
        ticker: 股票代號
        date: 分析日期
        elapsed_sec: 分析耗時
        market_report: 技術分析內容
        news_report: 新聞分析內容
        fundamentals_report: 基本面分析內容
        sentiment_report: 情緒分析內容
        investment_plan: 投資計畫
        final_decision: 最終決策
        output_path: PDF 輸出路徑（預設為 reports/<ticker>_<date>.pdf）

    Returns:
        生成的 PDF 檔案路徑
    """
    pdf = StockReportPDF()

    # 1. 封面
    pdf.add_cover(display_name, ticker, date, elapsed_sec)

    # 2. 重點摘要（決策 + 計畫）
    pdf.add_summary_section(final_decision, investment_plan)

    # 3. 正式內容（詳細分析）
    sections = [
        ("一、技術分析", market_report),
        ("二、新聞分析", news_report),
        ("三、基本面分析", fundamentals_report),
        ("四、情緒分析", sentiment_report),
    ]
    for title, content in sections:
        pdf.add_detail_section(title, content)

    # 輸出
    if output_path is None:
        safe_ticker = ticker.replace("=", "_").replace("-", "_")
        output_path = Path("reports") / f"{safe_ticker}_{date}.pdf"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path
