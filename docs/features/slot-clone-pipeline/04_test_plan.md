# 測試計畫：老虎機遊戲 Clone & 生產線工具

> **Feature**: slot-clone-pipeline
> **Stage**: 🟣 Stage 5 審查與 QA
> **日期**: 2026-03-12
> **審查者**: QA Reviewer (自動化)

---

## 1. 測試範圍

### 驗收標準對應測試矩陣

| AC | 驗收標準 | 測試方式 | 測試模組 |
|----|----------|----------|----------|
| AC-1 | 資源擷取 | Unit + Integration | `tests/slot_cloner/scraper/`, `test_storage.py` |
| AC-2 | 遊戲機制分析 | Unit | `tests/slot_cloner/reverse/`, `models/` |
| AC-3 | 遊戲重建 | Unit + TS Build | `tests/slot_cloner/builder/`, TypeScript `tsc --noEmit` |
| AC-4 | 自動化流程 | Unit + CLI dry-run | `tests/slot_cloner/test_cli.py`, `pipeline/` |
| AC-5 | 輸出目錄結構 | Unit | `tests/slot_cloner/test_storage.py` |

---

## 2. 測試層級

### 2.1 單元測試 (Unit Tests)

| 模組 | 測試檔案 | 測試數 | 覆蓋率 |
|------|----------|--------|--------|
| Models (enums/asset/symbol/feature/game) | `models/test_*.py` | 52 | 100% |
| Pipeline (context/orchestrator/checkpoint) | `pipeline/test_*.py` | 17 | 88% |
| Plugins (registry/atg/generic) | `plugins/test_*.py` | 9 | 60-100% |
| Recon Engine | `recon/test_engine.py` | 5 | 51% |
| Scraper (sprite_splitter) | `scraper/test_sprite_splitter.py` | 3 | 100% |
| Reverse (ws/js/paytable) | `reverse/test_*.py` | 15 | 92-94% |
| Builder (engine/config) | `builder/test_engine.py` | 5 | 67% |
| Math (rtp_simulator) | `math/test_rtp_simulator.py` | 6 | 93% |
| CLI | `test_cli.py` | 6 | 80% |
| Config | `test_config.py` | 4 | 68% |
| Storage | `test_storage.py` | 4 | 91% |
| Errors | `test_errors.py` | 11 | 100% |
| **總計** | | **147** | **78%** |

### 2.2 TypeScript 靜態分析

| 檢查項目 | 工具 | 預期 |
|----------|------|------|
| 型別正確性 | `npx tsc --noEmit` | 零錯誤 |
| 產品 Build | `npx vite build` | Build 成功 |

### 2.3 整合測試（未涵蓋，需手動 Fixture）

| 測試場景 | 狀態 | 說明 |
|----------|------|------|
| 真實 ATG URL Pipeline | ⏳ 待 Fixture | 需手動錄製 WS 訊息 + Sprite Sheet |
| 完整 CLI Pipeline | ⏳ 待 Fixture | 需 Playwright + 真實網路 |
| 跨模組 Pipeline 串接 | ✅ dry-run 通過 | CLI `--dry-run` 已驗證 5 Phase 串接 |

---

## 3. 驗收標準逐項測試

### AC-1：資源擷取

| # | 測試項目 | 方式 | 狀態 |
|---|----------|------|------|
| 1.1 | 自動開啟頁面等待載入 | ReconEngine 單元測試 | ✅ mock 通過 |
| 1.2 | 擷取圖片（MIME 分類） | ScraperEngine MIME 定義驗證 | ✅ |
| 1.3 | 擷取音效（含 Web Audio hook） | AUDIO_TYPES + AUDIO_EXTENSIONS 驗證 | ✅ |
| 1.4 | Sprite Sheet 拆解 | SpriteSplitter Hash/Array 格式 | ✅ 3 tests |
| 1.5 | 資源按類別分資料夾 | StorageManager 目錄結構 | ✅ 4 tests |

### AC-2：遊戲機制分析

| # | 測試項目 | 方式 | 狀態 |
|---|----------|------|------|
| 2.1 | 遊戲類型辨識 | ReconEngine game_type detection | ✅ |
| 2.2 | 賠率表產出 | PaytableParser + WSAnalyzer | ✅ 10 tests |
| 2.3 | 特殊符號識別 | SymbolConfig type enum | ✅ |
| 2.4 | Free Spin 規則 | FeaturesConfig 模型 | ✅ |
| 2.5 | Markdown 報告產出 | ReportBuilder 驗證 | ✅ |

### AC-3：遊戲重建

| # | 測試項目 | 方式 | 狀態 |
|---|----------|------|------|
| 3.1 | 瀏覽器可運行 | Vite build 成功 | ✅ |
| 3.2 | Spin 功能 | Game.ts 整合 SpinButton + CascadeGrid | ✅ TS 編譯 |
| 3.3 | Cascade 消除 | CascadeGrid + PaytableEngine BFS | ✅ TS 編譯 |
| 3.4 | Wild 替代 | PaytableEngine bfsCluster wild logic | ✅ TS 編譯 |
| 3.5 | Free Spin 觸發 | FreeSpinFeature 模組 | ✅ TS 編譯 |
| 3.6 | 乘數累積結算 | MultiplierFeature 模組 | ✅ TS 編譯 |

### AC-4：自動化流程

| # | 測試項目 | 方式 | 狀態 |
|---|----------|------|------|
| 4.1 | CLI 一鍵執行 | Click CLI `--dry-run` | ✅ 6 tests |
| 4.2 | 進度回報 | ProgressReporter 模組 | ✅ |
| 4.3 | 錯誤訊息 | errors.py 層級結構 | ✅ 11 tests |
| 4.4 | 結構化輸出目錄 | StorageManager verify_structure | ✅ |

### AC-5：輸出目錄結構

| # | 測試項目 | 方式 | 狀態 |
|---|----------|------|------|
| 5.1 | 9 個子目錄建立 | StorageManager 單元測試 | ✅ |
| 5.2 | 路徑助手正確 | get_images_dir 等 | ✅ |

---

## 4. 風險與缺口

| 風險 | 嚴重度 | 緩解 |
|------|--------|------|
| 覆蓋率 78% 未達 80% 目標 | MEDIUM | Scraper/Recon 為 Playwright async 程式碼，需真實瀏覽器才能完整測試 |
| 無真實 URL 整合測試 | HIGH | 需手動錄製 ATG fixture（約 4 小時） |
| TypeScript 只有靜態分析，無 JS 單元測試 | MEDIUM | 遊戲邏輯需瀏覽器環境測試 |
| Security 審查尚在進行 | — | 背景 Agent 執行中 |
