# 📊 Stock Analyzer — 架構設計

> **Feature**: 綜合投資分析工具
> **版本**: v0.1
> **日期**: 2026-03-06
> **階段**: 🟡 Stage 2 架構設計
> **基底**: [TradingAgents](https://github.com/TauricResearch/TradingAgents) v0.2.0

---

## 1. 架構總覽

基於 TradingAgents 的多代理人架構進行二次開發，主要改動：
- 增加台股 / 基金 / 比特幣 / 黃金的資料源支援
- 以 Ollama QWen3 14B 為主要 LLM（取代雲端 OpenAI）
- 增加中文新聞爬蟲與情緒分析
- 整合進 Agent Army 專案結構

### 1.1 系統架構圖

```
┌──────────────────────────────────────────────────────────┐
│                    Stock Analyzer CLI                      │
│                  python -m stock_analyzer                  │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│              TradingAgentsGraph（LangGraph）               │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │           Phase 1: 分析師層 (Analysts)               │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │  │
│  │  │ Market   │ │ News     │ │ Fund.    │ │ Social │ │  │
│  │  │ Analyst  │ │ Analyst  │ │ Analyst  │ │ Analyst│ │  │
│  │  │(技術分析)│ │(新聞情緒)│ │(基本面)  │ │(社群)  │ │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │  │
│  │       │            │            │            │      │  │
│  │       ▼            ▼            ▼            ▼      │  │
│  │  [技術報告]   [新聞報告]   [基本面報告]  [情緒報告]  │  │
│  └─────────────────────┬───────────────────────────────┘  │
│                        │                                  │
│  ┌─────────────────────▼───────────────────────────────┐  │
│  │           Phase 2: 研究辯論 (Debate)                 │  │
│  │       Bull Researcher ⟷ Bear Researcher             │  │
│  │              ↓ Research Manager 仲裁                  │  │
│  └─────────────────────┬───────────────────────────────┘  │
│                        │                                  │
│  ┌─────────────────────▼───────────────────────────────┐  │
│  │           Phase 3: 風險評估 (Risk)                   │  │
│  │   Aggressive ⟷ Neutral ⟷ Conservative               │  │
│  │              ↓ Risk Manager 最終裁判                  │  │
│  └─────────────────────┬───────────────────────────────┘  │
│                        │                                  │
│                        ▼                                  │
│              [最終分析報告 + 建議]                         │
└──────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│                   資料層 (Dataflows)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ yfinance │ │ 中文新聞 │ │CoinGecko │ │Alpha Vantage│ │
│  │ 台股/美股│ │ 爬蟲     │ │ 加密貨幣 │ │  (備援)    │  │
│  │ 黃金/基金│ │ 鉅亨/Yahoo│ │          │ │            │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │
└──────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│                   LLM 層 (LLM Clients)                    │
│  ┌─────────────────────┐  ┌─────────────────────┐       │
│  │ Ollama QWen3 14B    │  │ Claude API (備援)    │       │
│  │ quick_think + deep  │  │ 重要決策時使用       │       │
│  │ localhost:11434     │  │                      │       │
│  └─────────────────────┘  └─────────────────────┘       │
└──────────────────────────────────────────────────────────┘
```

---

## 2. 模組拆分

### 2.1 目錄結構（在 agent-army 中的位置）

```
src/stock_analyzer/
├── __init__.py
├── __main__.py                  # CLI 入口（python -m stock_analyzer）
├── config.py                    # 配置管理
├── main.py                      # 主邏輯：初始化 TradingAgentsGraph
│
├── dataflows/                   # 資料源擴充（繼承 TradingAgents）
│   ├── __init__.py
│   ├── tw_stock.py              # 🆕 台股資料源（yfinance .TW + 補充）
│   ├── crypto.py                # 🆕 加密貨幣（BTC, ETH）
│   ├── gold.py                  # 🆕 黃金/大宗商品
│   ├── fund.py                  # 🆕 基金/ETF 資料
│   └── news_tw.py               # 🆕 中文新聞爬蟲
│
├── agents/                      # 代理人擴充（覆寫 TradingAgents 預設）
│   ├── __init__.py
│   └── prompts_tw.py            # 🆕 中文化系統提示詞
│
├── reports/                     # 報告產出
│   ├── __init__.py
│   ├── formatter.py             # 報告格式化（Markdown）
│   └── templates/               # 報告模板
│       └── analysis_report.md
│
└── utils/                       # 工具函式
    ├── __init__.py
    └── ticker_resolver.py       # 🆕 股票代號解析（台股/美股/加密貨幣）
```

### 2.2 TradingAgents 作為依賴

```
安裝方式：pip install tradingagents
或：git clone + pip install -e ./TradingAgents

我們的程式碼透過 Python import 使用：
  from tradingagents.graph.trading_graph import TradingAgentsGraph
  from tradingagents.default_config import DEFAULT_CONFIG
```

**原則**：盡量不修改 TradingAgents 原始碼，透過配置和擴充來實現需求。

---

## 3. 技術選型

### 3.1 核心依賴

| 套件 | 版本 | 用途 | 來源 |
|------|------|------|------|
| tradingagents | 0.2.x | 多代理人框架 | pip/git |
| langgraph | latest | 工作流引擎 | pip |
| langchain-openai | latest | Ollama LLM 客戶端 | pip |
| yfinance | latest | 股票/基金/黃金資料 | pip |
| pandas-ta | latest | 技術指標補充 | pip |
| httpx | latest | 中文新聞爬蟲 | pip |
| beautifulsoup4 | latest | HTML 解析 | pip |
| python-dotenv | latest | 環境變數 | pip |

### 3.2 LLM 配置

```python
# Ollama 本地配置（MVP 預設）
STOCK_ANALYZER_CONFIG = {
    "llm_provider": "ollama",
    "deep_think_llm": "qwen3:14b",
    "quick_think_llm": "qwen3:14b",
    "backend_url": "http://localhost:11434/v1",
    "max_debate_rounds": 1,          # MVP 先用 1 輪辯論
    "max_risk_discuss_rounds": 1,
}
```

### 3.3 資料源策略

| 標的類型 | 資料源 | Ticker 格式 | 備註 |
|----------|--------|------------|------|
| 台股 | yfinance | `2330.TW` | 個股 |
| 台股 ETF | yfinance | `0050.TW` | ETF |
| 美股 | yfinance | `AAPL` | 原生支援 |
| 比特幣 | yfinance | `BTC-USD` | 加密貨幣 |
| 以太幣 | yfinance | `ETH-USD` | 加密貨幣 |
| 黃金 | yfinance | `GC=F` | 期貨 |
| 基金 | yfinance | 依基金代號 | 共同基金 |

---

## 4. 介面定義

### 4.1 CLI 介面

```bash
# 基本用法
python -m stock_analyzer analyze <ticker> [options]

# 選項
--date DATE          # 分析日期（預設今天）
--output-dir DIR     # 報告輸出目錄（預設 ./reports）
--llm-provider STR   # LLM 供應商（預設 ollama）
--model STR          # 模型名稱（預設 qwen3:14b）
--no-news            # 跳過新聞分析
--no-fundamental     # 跳過基本面分析
--verbose            # 詳細輸出

# 範例
python -m stock_analyzer analyze 2330.TW
python -m stock_analyzer analyze BTC-USD --date 2026-03-01
python -m stock_analyzer analyze 2330.TW 0050.TW AAPL GC=F
```

### 4.2 Python API

```python
from stock_analyzer.main import StockAnalyzer

analyzer = StockAnalyzer(llm_provider="ollama", model="qwen3:14b")

# 單一標的分析
report = analyzer.analyze("2330.TW")
print(report.summary)

# 多標的分析
reports = analyzer.analyze_batch(["2330.TW", "BTC-USD", "GC=F"])
```

### 4.3 報告輸出介面

```python
@dataclass
class AnalysisReport:
    ticker: str                    # 股票代號
    date: str                      # 分析日期
    market_report: str             # 技術分析報告
    news_report: str               # 新聞分析報告
    fundamentals_report: str       # 基本面報告
    sentiment_report: str          # 情緒分析報告
    investment_plan: str           # 投資計畫
    final_decision: str            # 最終建議（BUY/SELL/HOLD）
    confidence: int                # 信心指數（1-10）
    risk_level: str                # 風險等級（LOW/MEDIUM/HIGH）
```

---

## 5. 風險評估

| 風險 | 等級 | 緩解方案 |
|------|------|---------|
| Ollama QWen3 14B 分析品質不足 | MEDIUM | 預留 Claude API 備援配置 |
| yfinance 台股資料不穩定 | MEDIUM | 增加重試機制 + 資料驗證 |
| 中文新聞爬蟲被反爬蟲阻擋 | HIGH | 使用 yfinance 內建新聞作為 fallback |
| TradingAgents 版本升級破壞相容 | LOW | 鎖定版本 + 包裝層隔離 |
| LangGraph 執行時間過長 | MEDIUM | 限制辯論輪數 + 設定 timeout |
| 加密貨幣 24h 交易，分析時點問題 | LOW | 使用 UTC 時間標準化 |

---

## 6. 與 TradingAgents 的差異

| 項目 | TradingAgents 原版 | 我們的版本 |
|------|-------------------|-----------|
| LLM | OpenAI GPT-5 (雲端) | Ollama QWen3 14B (本地) |
| 資料源 | yfinance (美股為主) | yfinance + 中文新聞爬蟲 |
| 語言 | 英文 | 中文報告輸出 |
| 標的 | 美股 | 台股 + 基金 + BTC + 美股 + 黃金 |
| 介面 | 互動式 CLI | 命令式 CLI（可腳本化） |
| 部署 | 獨立專案 | Agent Army 子模組 |
