# 📊 Stock Analyzer — 需求規格書

> **Feature**: 綜合投資分析工具
> **版本**: v0.1
> **日期**: 2026-03-06
> **狀態**: 🟢 Stage 1 需求釐清

---

## 1. 功能概述

基於 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 開源框架進行二次開發，
建立一個綜合多面向（時事新聞、技術分析、公司基本面）的投資分析工具。
以多代理人 (Multi-Agent) 架構協作，產出具參考價值的分析報告。

---

## 2. 投資標的範圍

| 類別 | 優先級 | 資料源 | 說明 |
|------|--------|--------|------|
| 🇹🇼 台股 | ⭐ 主力 | yfinance (`.TW`) / FinMind | 個股 + ETF |
| 📊 基金 | ⭐ 主力 | yfinance / 基金平台 | ETF、共同基金 |
| ₿ 比特幣 | ⭐ 主力 | yfinance (`BTC-USD`) / CoinGecko | 加密貨幣 |
| 🇺🇸 美股 | 參考 | yfinance | 連動分析、全球趨勢 |
| 🥇 黃金 | 參考 | yfinance (`GC=F`) | 避險指標 |

---

## 3. 三大分析面向

### 3.1 時事新聞分析 (News Sentiment)
- 抓取中文財經新聞（鉅亨網、Yahoo 股市、工商時報）
- 抓取英文財經新聞（Yahoo Finance、Reuters）
- 使用 LLM（Ollama QWen3 14B）進行情緒分析
- 產出：利多/利空/中性判定 + 影響程度評估

### 3.2 技術分析 (Technical Analysis)
- 基於 pandas-ta 計算技術指標
- 核心指標：MA、EMA、RSI、MACD、Bollinger Bands、KDJ、成交量
- K 線型態辨識（可選用 TA-Lib）
- 產出：技術面多空判定 + 支撐壓力位

### 3.3 基本面分析 (Fundamental Analysis)
- 財務報表分析：營收、EPS、毛利率、ROE
- 估值指標：PE、PB、殖利率
- 同業比較
- 產出：基本面評級 + 合理價估算

---

## 4. 系統架構（基於 TradingAgents）

### 4.1 代理人角色

| 代理人 | 職責 | 對應 TradingAgents 角色 |
|--------|------|------------------------|
| News Analyst | 新聞蒐集 + 情緒分析 | news_analyst |
| Technical Analyst | 技術指標計算 + 多空判定 | technical_analyst |
| Fundamentals Analyst | 財報分析 + 估值 | fundamentals_analyst |
| Sentiment Analyst | 市場情緒綜合評估 | sentiment_analyst |
| Research Manager | 彙整各分析師報告 | researcher |
| Risk Manager | 風險評估 + 建議 | risk_manager |
| Portfolio Manager | 最終投資建議 | trader |

### 4.2 LLM 策略
- **主要**：Ollama QWen3 14B（本地端，免費，中文能力佳）
- **備援**：可配置雲端 LLM（Claude / OpenAI）用於重要決策
- 符合 Agent Army 的模型分層策略

---

## 5. 使用模式

### 5.1 手動觸發（MVP 優先）
```bash
# 分析單一台股
python -m stock_analyzer analyze 2330.TW

# 分析比特幣
python -m stock_analyzer analyze BTC-USD

# 分析多個標的
python -m stock_analyzer analyze 2330.TW 0050.TW BTC-USD GC=F
```

### 5.2 未來擴充
- 定時排程分析（每日早晚）
- Telegram Bot 推播
- 觸發條件警報

---

## 6. 輸出格式

### 6.1 MVP — 終端 + Markdown 報告
```
📊 分析報告：台積電 (2330.TW)
日期：2026-03-06

📰 新聞面：🟢 利多（7/10）
  - AI 晶片需求持續強勁
  - 北美客戶追單

📈 技術面：🟡 中性（5/10）
  - RSI: 55（中性）
  - MACD: 金叉形成中
  - 支撐：850 / 壓力：920

💰 基本面：🟢 正面（8/10）
  - PE: 22.5（合理）
  - ROE: 28%（優秀）
  - 殖利率: 1.8%

🎯 綜合建議：偏多操作
  - 信心指數：7/10
  - 建議：逢低布局
  - 風險提示：地緣政治不確定性
```

### 6.2 存檔
- 每次分析產出 `reports/<ticker>_<date>.md`
- 可追蹤歷史分析結果

---

## 7. 驗收標準 (Acceptance Criteria)

| AC 編號 | 描述 | 可測試 |
|---------|------|--------|
| AC-1 | 可對台股個股（如 2330.TW）執行完整三面向分析 | ✅ |
| AC-2 | 可對比特幣（BTC-USD）執行分析 | ✅ |
| AC-3 | 可對美股（如 AAPL）執行分析 | ✅ |
| AC-4 | 可對黃金（GC=F）執行分析 | ✅ |
| AC-5 | 新聞分析產出利多/利空/中性判定 | ✅ |
| AC-6 | 技術分析計算至少 5 種指標（MA, RSI, MACD, BB, KDJ）| ✅ |
| AC-7 | 基本面分析包含 PE、ROE、殖利率 | ✅ |
| AC-8 | 產出綜合報告（含三面向評分 + 建議）| ✅ |
| AC-9 | 報告存為 Markdown 檔案 | ✅ |
| AC-10 | 使用 Ollama 本地 LLM 進行分析（不依賴雲端）| ✅ |

---

## 8. 邊界條件

- 台股只在開盤時間有即時資料，盤後為收盤價
- yfinance 台股資料偶爾不穩定，需有錯誤處理
- 新聞爬蟲可能被反爬蟲機制阻擋
- Ollama 推理速度取決於本機 GPU 資源
- 基金資料較難統一取得，MVP 先支援 ETF

---

## 9. 不做的事（Scope Out）

- ❌ 不做自動下單 / 交易執行
- ❌ 不做即時盯盤（MVP 階段）
- ❌ 不做投資組合管理（MVP 階段）
- ❌ 不做回測系統（MVP 階段）
- ❌ 不保證分析準確性（僅供參考）

---

## 10. 技術依賴

| 套件 | 用途 | 授權 |
|------|------|------|
| TradingAgents | 多代理人框架基底 | Apache 2.0 |
| yfinance | 股票資料抓取 | Apache 2.0 |
| pandas-ta | 技術指標計算 | MIT |
| Ollama (QWen3 14B) | 新聞情緒分析 LLM | 本地部署 |
| LangGraph | 代理人工作流 | MIT |
| requests / httpx | 新聞爬蟲 | MIT / BSD |
