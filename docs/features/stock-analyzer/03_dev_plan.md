# 📊 Stock Analyzer — 開發計畫

> **Feature**: 綜合投資分析工具
> **版本**: v0.1
> **日期**: 2026-03-06
> **階段**: 🟡 Stage 2 開發計畫

---

## 開發批次

按依賴關係分為 4 個批次，逐步可測試。

---

### 批次 A：環境建置 + 基底整合（Day 1）

#### DEV-A1: 安裝 TradingAgents 依賴
- **對應 AC**: 前置條件
- **複雜度**: S
- **工作內容**:
  1. Clone TradingAgents 到 `vendor/` 或 pip install
  2. 安裝所有依賴：langgraph, langchain-openai, yfinance, etc.
  3. 驗證 `from tradingagents.graph.trading_graph import TradingAgentsGraph` 可正常 import
  4. 驗證 Ollama QWen3 14B 可連接 (`http://localhost:11434/v1`)
- **驗收**: import 成功 + Ollama 連線成功

#### DEV-A2: 建立 stock_analyzer 模組骨架
- **對應 AC**: 前置條件
- **複雜度**: S
- **工作內容**:
  1. 建立 `src/stock_analyzer/` 目錄結構
  2. `__init__.py`, `__main__.py`, `config.py`, `main.py`
  3. 配置管理：讀取 `.env` + 預設 Ollama 配置
  4. 基本 CLI 入口（argparse）
- **驗收**: `python -m stock_analyzer --help` 可執行

---

### 批次 B：核心分析功能（Day 2-3）

#### DEV-B1: 美股分析（驗證 TradingAgents 基底）
- **對應 AC**: AC-3
- **複雜度**: M
- **工作內容**:
  1. 封裝 `StockAnalyzer` 類別，整合 `TradingAgentsGraph`
  2. 配置 Ollama 作為 LLM provider
  3. 對美股（如 AAPL）執行完整分析流程
  4. 驗證四個分析師報告都有產出
- **驗收**: `python -m stock_analyzer analyze AAPL` 產出完整報告

#### DEV-B2: 台股分析
- **對應 AC**: AC-1
- **複雜度**: M
- **工作內容**:
  1. 建立 `ticker_resolver.py`，自動辨識並轉換 ticker 格式
  2. 建立 `tw_stock.py`，處理台股特殊邏輯（.TW 後綴、交易時間）
  3. 驗證 yfinance 台股資料抓取（2330.TW, 0050.TW）
  4. 處理台股基本面資料可能缺失的情況
- **驗收**: `python -m stock_analyzer analyze 2330.TW` 產出報告

#### DEV-B3: 比特幣 + 黃金分析
- **對應 AC**: AC-2, AC-4
- **複雜度**: M
- **工作內容**:
  1. 建立 `crypto.py`，處理加密貨幣資料（BTC-USD, ETH-USD）
  2. 建立 `gold.py`，處理黃金期貨（GC=F）
  3. 加密貨幣無傳統基本面，調整分析師組合（跳過 Fundamentals）
  4. 黃金以宏觀經濟指標為主
- **驗收**: `python -m stock_analyzer analyze BTC-USD GC=F` 產出報告

---

### 批次 C：中文化 + 報告增強（Day 4-5）

#### DEV-C1: 中文系統提示詞
- **對應 AC**: AC-5, AC-8
- **複雜度**: M
- **工作內容**:
  1. 建立 `prompts_tw.py`，翻譯/改寫所有系統提示詞為中文
  2. 確保 QWen3 14B 的中文輸出品質
  3. 報告輸出格式改為中文（利多/利空/中性）
  4. 綜合評分機制（1-10 分）
- **驗收**: 分析報告為中文輸出

#### DEV-C2: 中文新聞爬蟲
- **對應 AC**: AC-5
- **複雜度**: L
- **工作內容**:
  1. 建立 `news_tw.py`，爬取中文財經新聞
  2. 資料來源：Yahoo 股市新聞（最容易取得）
  3. 新聞清洗 + 摘要提取
  4. 整合到 News Analyst 的工具呼叫中
  5. Fallback：若爬蟲失敗，使用 yfinance 內建新聞
- **驗收**: 台股分析報告包含中文新聞引用

#### DEV-C3: Markdown 報告產出
- **對應 AC**: AC-8, AC-9
- **複雜度**: M
- **工作內容**:
  1. 建立 `formatter.py`，格式化分析報告
  2. 報告模板：三面向評分 + 綜合建議
  3. 儲存到 `reports/<ticker>_<date>.md`
  4. CLI 輸出美化（rich 終端格式）
- **驗收**: 產出格式化的 Markdown 報告檔案

---

### 批次 D：測試 + 穩定化（Day 6-7）

#### DEV-D1: 單元測試
- **對應 AC**: 所有
- **複雜度**: M
- **工作內容**:
  1. `tests/stock_analyzer/test_config.py` — 配置管理測試
  2. `tests/stock_analyzer/test_ticker_resolver.py` — 代號解析測試
  3. `tests/stock_analyzer/test_dataflows.py` — 資料源測試（mock）
  4. `tests/stock_analyzer/test_formatter.py` — 報告格式化測試
  5. 覆蓋率目標 80%+
- **驗收**: `pytest tests/stock_analyzer/ --cov` 通過 80%+

#### DEV-D2: 整合測試 + E2E
- **對應 AC**: AC-1 ~ AC-10
- **複雜度**: L
- **工作內容**:
  1. 整合測試：真實呼叫 yfinance + Ollama（需要網路+Ollama running）
  2. E2E 測試：`python -m stock_analyzer analyze 2330.TW --dry-run`
  3. 錯誤處理測試：網路斷線、Ollama 離線、無效 ticker
  4. 效能測試：單次分析耗時基準
- **驗收**: 全部 AC 通過 + E2E 正常

---

## AC 對應矩陣

| AC | 描述 | 對應 DEV |
|----|------|---------|
| AC-1 | 台股分析 | DEV-B2 |
| AC-2 | 比特幣分析 | DEV-B3 |
| AC-3 | 美股分析 | DEV-B1 |
| AC-4 | 黃金分析 | DEV-B3 |
| AC-5 | 新聞情緒判定 | DEV-C1, DEV-C2 |
| AC-6 | 5 種技術指標 | DEV-B1（TradingAgents 內建）|
| AC-7 | PE/ROE/殖利率 | DEV-B1（TradingAgents 內建）|
| AC-8 | 綜合報告 | DEV-C1, DEV-C3 |
| AC-9 | Markdown 存檔 | DEV-C3 |
| AC-10 | Ollama 本地 LLM | DEV-A1, DEV-B1 |

---

## 時程估算

| 批次 | 天數 | 說明 |
|------|------|------|
| 批次 A | 1 天 | 環境建置，風險最低 |
| 批次 B | 2 天 | 核心功能，最重要 |
| 批次 C | 2 天 | 中文化，差異化價值 |
| 批次 D | 2 天 | 測試穩定化 |
| **合計** | **~7 天** | |
