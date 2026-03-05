# 📚 讀書 Agent v2（Reading Agent）

## 身份定義

**讀書 Agent** 是 Agent Army 旗下的知識策展專員。
自動追蹤暢銷書排行榜 → 搜尋 YouTube 說書影片 → 擷取字幕 → Gemini 深度重點整理 → Telegram 推送。
同時具備 AI 技術資訊蒐集、來源自動探索、Telegram Bot 互動等功能。

## 角色職責

| 項目 | 說明 |
|------|------|
| **代號** | Reading Agent v2 |
| **類型** | 資訊蒐集 + AI 深度整理 + 互動 Bot |
| **資料來源** | 暢銷書排行榜（博客來/誠品/金石堂/Amazon）→ YouTube 說書影片 |
| **AI 引擎** | Google Gemini 2.5 Flash（字幕分析、重點整理、來源評分） |
| **輸出管道** | Telegram Bot（互動模式 + 報告推送） |
| **輸出語言** | 繁體中文（英文影片自動翻譯） |
| **排程** | 每週日 21:00 自動執行（Windows Task Scheduler） |

## 追蹤頻道

| 頻道 | 分類 | Channel ID |
|------|------|-----------|
| 文森說書 | 綜合知識 | UCPgGtH2PxZ9xR0ehzQ27FHw |
| 老高與小茉 | 綜合知識 | UCMUnInmOkrWN4gof9KlhNmQ |
| 閱部客 | 商業管理 | UCBvQ4hOEoDdYeIBu0tE-7Sg |

可在 `data/reading_agent/channels.json` 自訂頻道列表，或透過 Telegram `/add` `/remove` 管理。
使用 `/discover` 可自動探索並推薦新的說書頻道與書評網站。

## 架構

```
src/reading_agent/
├── __init__.py               # 套件入口
├── __main__.py               # python -m 支援
├── config.py                 # 設定：頻道、API keys、分類、Discovery 參數
├── models.py                 # Book, Video, ReadingReport, DiscoveredSource
├── runner.py                 # CLI 入口與 v2 主流程
├── telegram_bot_handler.py   # Telegram Bot 互動模式（12 個指令）
├── telegram_sender.py        # Telegram 報告發送（單向推送）
├── bestseller_scraper.py     # 暢銷書爬取（博客來/誠品/金石堂/Amazon）
├── youtube_searcher.py       # YouTube 說書影片搜尋
├── youtube_client.py         # YouTube RSS 頻道監控（自訂頻道）
├── transcript_extractor.py   # YouTube 字幕擷取
├── content_analyzer.py       # Gemini 深度重點整理（中英雙語）
├── source_discovery.py       # 來源探索（YouTube+網站+Gemini 評分）
├── ai_weekly.py              # AI Weekly 技術資訊蒐集
├── reporter.py               # 報告產生器
├── storage.py                # JSON 本地儲存
├── summarizer.py             # v1 舊版 Gemini 摘要（保留相容）
└── README.md                 # 本文件
```

## 使用方式

### CLI 模式（一次性執行）

```bash
# 完整蒐集流程（暢銷書→說書影片→字幕→Gemini整理→發送）
python -m src.reading_agent --mode weekly

# 首次蒐集（範圍更大，近一個月）
python -m src.reading_agent --mode initial

# 只蒐集不發送（預覽報告）
python -m src.reading_agent --mode weekly --dry-run

# AI Weekly 獨立蒐集
python -m src.reading_agent --ai-weekly

# 直接分析指定 YouTube 影片
python -m src.reading_agent --analyze-url <youtube_url>

# 列出暢銷書排行榜
python -m src.reading_agent --list-books

# 列出追蹤的頻道
python -m src.reading_agent --list-channels

# 測試 Telegram 連線
python -m src.reading_agent --test-telegram
```

### Telegram Bot 互動模式（長駐）

```bash
python -m src.reading_agent --bot
```

啟動後在 Telegram 與 Bot 互動，支援以下指令：

| 指令 | 功能 |
|------|------|
| `/start` `/help` | 歡迎訊息與指令說明 |
| `/videos` | 最近蒐集的影片摘要 |
| `/books` | 暢銷書排行榜 |
| `/channels` | 列出追蹤頻道 |
| `/add <url>` | 新增追蹤頻道 |
| `/remove <名稱>` | 移除追蹤頻道 |
| `/collect` | **執行完整蒐集（含完成通知）** |
| `/weekly` | 執行每週說書影片蒐集 |
| `/ai` | 執行 AI Weekly 蒐集 |
| `/analyze <url>` | 分析指定 YouTube 影片 |
| `/discover` | 探索推薦新來源（Inline Keyboard 審核） |

### 自動排程

Windows Task Scheduler 已設定 `AgentArmy_WeeklyCollect`：
- **執行時間**：每週日 21:00
- **腳本**：`scripts/weekly_collect.bat`
- **紀錄**：`logs/weekly_collect.log`

## 核心流程

```
v2 蒐集流程（--mode weekly / /collect）：

  ┌─ 0. 來源探索（若超過 30 天自動觸發）
  │
  ├─ 1. 爬取暢銷書排行榜（博客來/誠品/金石堂/Amazon）
  │
  ├─ 2. YouTube 搜尋說書影片（依書名搜尋）
  │
  ├─ 3. 擷取影片字幕
  │
  ├─ 4. Gemini 深度重點整理（中英雙語）
  │
  ├─ 5. 檢查自訂頻道（若有）
  │
  ├─ 5.5 AI Weekly 蒐集
  │
  ├─ 6. 儲存影片資料（JSON）
  │
  ├─ 7. 產生報告
  │
  └─ 8. 發送 Telegram
```

## 來源探索系統（Source Discovery）

自動探索新的說書頻道和書評網站：

1. **YouTube 探索**：使用中英文關鍵字搜尋，提取頻道資訊
2. **網站探索**：從預設書評網站清單中產生候選
3. **Gemini 評分**：4 維度評分（內容相關性 40 + 品質 30 + 活躍度 20 + 受眾契合 10）
4. **Telegram 審核**：Inline Keyboard 讓使用者一鍵確認或拒絕
5. **自動寫入**：approved 的 YouTube 頻道自動加入 channels.json

觸發方式：
- 手動：Telegram `/discover`
- 自動：每次 `--mode weekly` 時檢查，超過 30 天自動執行

## 環境變數（.env）

```
# Telegram Bot（讀書 Agent 專用）
READING_BOT_TOKEN=<Telegram Bot Token>
READING_CHAT_ID=<Telegram Chat ID>

# Telegram Bot（舊版/共用，降級使用）
TELEGRAM_BOT_TOKEN=<Telegram Bot Token>
TELEGRAM_CHAT_ID=<Telegram Chat ID>

# AI
GEMINI_API_KEY=<Google Gemini API Key>
```

## 測試

```bash
# 讀書 Agent 相關測試
python -m pytest tests/test_reading_agent_*.py tests/test_telegram_bot_handler.py tests/test_source_discovery.py -v

# 全部測試
python -m pytest tests/ -v
```

測試檔案：
- `test_reading_agent_models.py` — 資料模型
- `test_reading_agent_youtube.py` — YouTube RSS 解析
- `test_reading_agent_reporter.py` — 報告產生器
- `test_reading_agent_sender.py` — Telegram 發送
- `test_reading_agent_bestseller.py` — 暢銷書爬取
- `test_reading_agent_analyzer.py` — Gemini 分析
- `test_reading_agent_ai_weekly.py` — AI Weekly
- `test_telegram_bot_handler.py` — Telegram Bot 互動（43 個測試）
- `test_source_discovery.py` — 來源探索（34 個測試）

## 技術依賴

- `httpx` — 非同步 HTTP 客戶端
- `google-genai` — Gemini AI SDK
- `python-telegram-bot` — Telegram Bot API（v20+ async）
- `feedparser` — RSS/Atom feed 解析
- `beautifulsoup4` — HTML 解析（暢銷書爬取）
- `youtubesearchpython` — YouTube 搜尋
- `youtube-transcript-api` — YouTube 字幕擷取
- `python-dotenv` — 環境變數管理

## 所屬

Agent Army 專案（D:\Projects\agent-army）
由 Claude Code Opus 4.6 指揮調度
