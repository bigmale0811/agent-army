# Agent Army 整體系統架構

**最後更新**: 2026-03-04
**系統概述**: 通用 Agent 框架，包含讀書 Agent v2、日本博弈資訊蒐集、百家樂遊戲核心

---

## 項目結構概覽

```
src/
├── reading_agent/          ★ 讀書 Agent v2（暢銷書→搜尋→整理→發送）
│   ├── runner.py           - CLI 入口，核心流程編排
│   ├── models.py           - 資料模型（Book、Video、ReadingReport）
│   ├── config.py           - 設定管理、頻道列表、分類定義
│   ├── telegram_bot_handler.py - Telegram Bot 互動模式（12 個指令）
│   ├── bestseller_scraper.py   - 暢銷書排行榜爬蟲（4 個平台）
│   ├── youtube_searcher.py     - YouTube 影片搜尋
│   ├── youtube_client.py       - YouTube RSS 客戶端
│   ├── transcript_extractor.py - 字幕擷取與清理
│   ├── content_analyzer.py     - Gemini 深度重點整理
│   ├── source_discovery.py     - 來源探索（新頻道推薦）
│   ├── ai_weekly.py            - AI 相關影片蒐集
│   ├── reporter.py             - 報告產生器
│   ├── telegram_sender.py      - Telegram 發送模組
│   ├── storage.py              - JSON 資料儲存
│   └── summarizer.py           - Gemini 全面摘要（舊版保留）
│
├── japan_intel/            ★ 日本博弈資訊蒐集 Agent
│   ├── runner.py           - CLI 入口
│   ├── collector.py        - 多源資訊蒐集
│   ├── sources/            - 來源模組（Google News、日本媒體等）
│   ├── models.py           - 資料模型
│   ├── config.py           - 設定管理
│   ├── reporter.py         - 報告產生器
│   ├── storage.py          - 資料儲存
│   ├── summarizer.py       - Gemini 摘要
│   └── telegram_sender.py  - Telegram 發送
│
├── game/                   ★ 百家樂遊戲引擎
│   ├── baccarat_engine.py  - 發牌邏輯與補牌規則
│   ├── shoe.py             - 牌靴（6 副牌）
│   ├── hand.py             - 手牌總和計算
│   ├── card.py             - 撲克牌資料結構
│   ├── state_machine.py    - 遊戲狀態機
│   └── bet_resolver.py     - 投注結算引擎
│
├── api/                    ★ WebSocket API 層
│   ├── models.py           - 通訊資料模型
│   ├── session.py          - 使用者會話管理
│   └── ws_handler.py       - WebSocket 訊息處理
│
├── config.py               - 全域設定
├── main.py                 - 主程式入口
└── __init__.py

tests/
├── reading_agent/          - 讀書 Agent 測試
├── game/                   - 遊戲引擎測試
└── japan_intel/            - 日本資訊蒐集測試

data/                        - 執行時資料目錄
├── reading_agent/
│   ├── videos/             - YYYY-MM-DD.json（影片資料）
│   ├── reports/            - 報告存檔
│   ├── books/              - 暢銷書資料
│   ├── channels.json       - 追蹤頻道列表
│   ├── custom_channels.json- 使用者自訂頻道
│   ├── ai_channels.json    - AI Weekly 頻道
│   └── discovery/          - 來源探索候選
├── japan_intel/
│   ├── articles/           - 文章快取
│   ├── reports/            - 報告存檔
│   └── summaries/          - 摘要存檔
└── game/                   - 遊戲狀態存檔
```

---

## 三大核心模組

### 1. 讀書 Agent v2（最重要）

**目標**: 自動蒐集暢銷書、搜尋說書影片、整理重點、發送 Telegram

**核心流程** (runner.py)：
```
暢銷書爬蟲 → YouTube 搜尋 → 字幕擷取 → Gemini 整理 → 報告產生 → Telegram 發送
```

**關鍵檔案統計**:
| 檔案 | 行數 | 用途 |
|------|------|------|
| runner.py | 775 | CLI 入口 + v2 主流程 |
| telegram_bot_handler.py | 1026 | 12 個指令互動 |
| models.py | 331 | Book/Video/ReadingReport 資料結構 |
| config.py | 340 | 設定、頻道、分類定義 |
| bestseller_scraper.py | 200+ | 4 平台爬蟲 |
| youtube_searcher.py | 150+ | YouTube 影片搜尋 |
| transcript_extractor.py | 150+ | 字幕擷取清理 |
| content_analyzer.py | 150+ | Gemini 深度分析 |
| reporter.py | 250+ | Telegram 報告格式化 |

**資料流向**:
```
Book (暢銷書)
  ↓
Video (YouTube 影片資訊)
  ├─ title, url, channel_name
  ├─ transcript (字幕)
  ├─ key_points_original (原語言)
  └─ key_points_zh (中文翻譯)
  ↓
ReadingReport
  ├─ period_start/end
  ├─ videos[]
  └─ mode (weekly/initial)
  ↓
Telegram 訊息 (分段發送)
```

**CLI 指令**:
- `--mode weekly/initial` — 執行蒐集流程
- `--bot` — 啟動 Telegram Bot 互動
- `--analyze-url <url>` — 直接分析影片
- `--ai-weekly` — AI 相關影片蒐集
- `--list-books` — 列出暢銷書
- `--add-channel <url>` — 新增追蹤頻道
- `--discover` — 探索推薦新頻道

### 2. 日本博弈資訊蒐集 Agent

**目標**: 定期蒐集日本博弈相關新聞和資訊，經 Gemini 摘要後發送

**流程**: 多源蒐集 → Gemini 摘要 → Telegram 發送

**來源模組** (sources/):
- google_news.py — Google News 爬蟲
- industry_sites.py — 產業網站爬蟲
- japan_media.py — 日本主流媒體爬蟲

### 3. 百家樂遊戲引擎

**目標**: 實現完整的百家樂遊戲邏輯（發牌、補牌、結算）

**核心類別**:
- BaccaratEngine — 發牌與補牌邏輯
- Shoe — 6 副牌的牌靴管理
- Hand — 手牌點數計算（模 10）
- RoundResult — 一局結果資料結構

---

## 外部依賴速查表

### 讀書 Agent v2
| 套件 | 用途 | 版本 |
|------|------|------|
| google-genai | Gemini API | latest |
| youtube-transcript-api | 字幕擷取 | 0.6.x |
| youtubesearchpython | YouTube 搜尋 | 1.6.x |
| python-telegram-bot | Telegram Bot | 20.x |
| beautifulsoup4 | HTML 解析 | 4.x |
| httpx | 非同步 HTTP | 0.27+ |

### 日本資訊蒐集
同上，外加新聞來源爬蟲

### 百家樂遊戲
純 Python，無外部依賴

---

## 設定管理

### 環境變數（.env）

```
# Telegram
TELEGRAM_BOT_TOKEN=      # 舊版 Bot（通用）
TELEGRAM_CHAT_ID=        # 舊版 Chat ID
READING_BOT_TOKEN=       # 讀書 Agent 專用 Bot（優先）
READING_CHAT_ID=         # 讀書 Agent Chat ID

# Gemini
GEMINI_API_KEY=          # Google Gemini API Key

# YouTube（可選，預設免鑰）
YOUTUBE_API_KEY=         # 可設定以提升搜尋速率
```

### 執行時組態檔

**讀書 Agent**:
- `data/reading_agent/channels.json` — 預設說書頻道列表
- `data/reading_agent/custom_channels.json` — 使用者自訂追蹤頻道
- `data/reading_agent/ai_channels.json` — AI Weekly 頻道列表
- `data/reading_agent/discovery/discovered_sources.json` — 來源探索候選清單

**日本資訊**:
- `data/japan_intel/*.json` — 來源設定與快取

---

## 資料儲存層

### VideoStorage (reading_agent/storage.py)
按日期分檔存檔影片：
```
data/reading_agent/videos/
├── 2026-03-04.json
├── 2026-03-03.json
└── ...
```

每個 JSON 包含 `Video[]` 陣列，支援日期範圍查詢。

### ReportStorage (japan_intel/storage.py)
相同架構，存檔報告與摘要。

---

## 通訊協議

### Telegram 訊息分段
- 單則上限: 4096 字元
- 自動分段: 按換行符切割，保持段落完整
- 發送延遲: 1.5 秒（避免速率限制）

### WebSocket API (api/)
- ws_handler.py — 遊戲狀態實時推送
- session.py — 使用者會話追蹤
- models.py — 通訊資料結構

---

## 開發快速導航

### 新增暢銷書來源
編輯 `config.py` 的 `BESTSELLER_SOURCES`，在 `bestseller_scraper.py` 新增平台爬蟲

### 新增 AI Weekly 頻道
編輯 `data/reading_agent/ai_channels.json`，或在 `config.py` 中編輯 `_DEFAULT_AI_CHANNELS`

### 新增 Telegram 指令
在 `telegram_bot_handler.py` 新增方法 `async def cmd_xxx()`，並在 `run()` 中註冊 `CommandHandler`

### 擴展遊戲引擎
修改 `baccarat_engine.py` 的補牌邏輯或 `state_machine.py` 的狀態轉移

---

## 版本歷史

- **v2.0** (讀書 Agent) — 暢銷書架構，Gemini 深度整理，雙語輸出
- **v2.1** — 新增來源探索、AI Weekly
- **v1.0** (Japan Intel) — 日本博弈資訊蒐集
- **v1.0** (Game) — 百家樂引擎核心

---

**相關文件**:
- [讀書 Agent 詳細架構](reading-agent.md)
- CLAUDE.md — 開發規則
- SECRETARY.md — 專案狀態
