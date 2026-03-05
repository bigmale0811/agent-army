# Changelog

All notable changes to the Agent Army project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **Windows Task Scheduler**: weekly_collect.bat + 排程 `AgentArmy_WeeklyCollect`（每週日 21:00 自動執行 `--mode weekly`）
- **Telegram `/collect` 指令**: 完整蒐集流程（暢銷書 + 說書影片 + AI Weekly），含完成通知與耗時統計
- **Source Discovery 來源探索系統** (v2.1)
  - `src/reading_agent/source_discovery.py` — 核心探索引擎（YouTube 頻道 + 書評網站 + Gemini 評分）
  - `src/reading_agent/models.py` — 新增 `DiscoveredSource` dataclass
  - `src/reading_agent/config.py` — DISCOVERY_* 設定區塊
  - Telegram `/discover` 指令 + Inline Keyboard（✅ 加入 / ❌ 跳過）
  - `runner.py` 中 `discover_if_due()` 自動觸發（每 30 天）
  - `tests/test_source_discovery.py` — 34 個測試
- **Telegram Bot 互動模式** (`--bot`)
  - `src/reading_agent/telegram_bot_handler.py` — 12 個指令：/start, /help, /videos, /books, /channels, /add, /remove, /weekly, /ai, /analyze, /collect, /discover
  - `tests/test_telegram_bot_handler.py` — 43 個測試
- **CLAUDE.md 溝通規則**: 禁止沉默作業、每步回報、完成主動宣告等 6 條規則
- **CHANGELOG.md**: 本檔案，記錄所有修改歷史
- `scripts/weekly_collect.bat` — Windows 排程腳本
- `logs/` 目錄 — 排程執行紀錄

### Changed
- `data/reading_agent/channels.json` — 從 8 個頻道縮減為 3 個（文森說書、老高與小茉、閱部客）
- `src/reading_agent/config.py` — `_DEFAULT_CHANNELS` 同步更新為 3 個頻道
- `src/reading_agent/runner.py` — 新增 `--bot` CLI 參數、`discover_if_due()` 前置步驟
- `src/reading_agent/__init__.py` — 匯出 `TelegramBotHandler`

### Fixed
- Windows cp950 編碼問題：測試執行時使用 `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`
- `test_books_empty_result` 測試失敗：`BestsellerScraper` lazy import 導致 mock 失效，改用 `patch.dict(sys.modules)`

---

## [0.1.0] - 2026-03-03 (Initial Development)

### Added
- **讀書 Agent v2 核心流程**: 暢銷書排行榜 → YouTube 搜尋說書影片 → 字幕擷取 → Gemini 深度重點整理 → Telegram 發送
- `src/reading_agent/` 模組架構
  - `runner.py` — CLI 入口（--mode weekly/initial, --analyze-url, --list-books 等）
  - `bestseller_scraper.py` — 跨平台暢銷書爬取（博客來/誠品/金石堂/Amazon）
  - `youtube_searcher.py` — YouTube 說書影片搜尋
  - `youtube_client.py` — YouTube RSS 頻道監控
  - `transcript_extractor.py` — YouTube 字幕擷取
  - `content_analyzer.py` — Gemini 深度重點整理（中英雙語）
  - `reporter.py` — 報告產生器
  - `telegram_sender.py` — Telegram 報告發送
  - `storage.py` — 影片資料 JSON 儲存
  - `config.py` — 集中設定管理
  - `models.py` — Book, Video, ReadingReport 資料模型
  - `summarizer.py` — v1 舊版 Gemini 摘要
- **AI Weekly 蒐集**: `ai_weekly.py` — AI 技術影片蒐集與整理
- **測試套件**: 357+ 測試（pytest）
- **CLAUDE.md**: 專案規則與開發指引

### Known Issues
- `test_fetch_channel_date_filter` 測試失敗（日期過濾邏輯 bug，pre-existing）
