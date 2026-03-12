# 開發計畫：老虎機遊戲 Clone & 生產線工具

> 本文件由 Phase 2: PLAN 產出，需使用者確認後才進入開發階段。
> 輸入：`01_spec.md` + `02_architecture.md`

## 基本資訊

| 欄位 | 內容 |
|------|------|
| 功能名稱 | slot-clone-pipeline |
| 企劃 | planner agent (Opus) |
| 建立日期 | 2026-03-12 |
| 預估開發項目數 | 22 項 |
| 預估總工時 | 18-24 天（4 個 Sprint） |
| 首個里程碑 | Sprint 2 結束：ATG 戰神賽特完整 Pipeline 跑通 |

---

## MVP 策略

### MVP 定義（Sprint 1-2 完成）

MVP 的目標是：**針對 ATG 戰神賽特，執行一次完整的 5 Phase Pipeline，產出資源包 + 分析報告 + 可運行的基礎 Clone 遊戲**。

MVP 包含：
- [x] Pydantic v2 不可變資料模型（全部）
- [x] Pipeline Orchestrator（不含斷點續傳）
- [x] ATG Adapter 的 Recon + Scrape + Reverse
- [x] 基礎 Report Builder
- [x] 基礎 Config Generator（game-config.json 產出）
- [x] PixiJS 引擎核心（Grid + Symbol + Spin + Cascade）
- [x] CLI 基本指令

MVP 不包含：
- [ ] 斷點續傳
- [ ] 動畫系統（P1）
- [ ] 音效系統（P1）
- [ ] Monte Carlo RTP 模擬
- [ ] Generic Adapter
- [ ] 進階 UI（PaytableView、BigWinAnimation）

### 里程碑定義

| 里程碑 | Sprint | 驗證方式 |
|--------|--------|---------|
| **M1**: 資料模型 + Pipeline 骨架可跑 | Sprint 1 | `pytest` 全綠，Pipeline 空跑 5 Phase 無報錯 |
| **M2**: ATG 戰神賽特 Clone 完成 | Sprint 2 | CLI 一鍵產出資源 + 報告 + 可在瀏覽器玩的基礎 Clone |
| **M3**: 遊戲引擎完整功能 | Sprint 3 | Free Spin + 乘數 + 完整動畫 + 音效 |
| **M4**: 產品化 + 測試強化 | Sprint 4 | 斷點續傳、Generic Adapter、E2E 自動化、覆蓋率 80%+ |

---

## Sprint 總覽

```
Sprint 1 (Day 1-4)：基礎設施 + 資料模型 + Pipeline 骨架
    ↓
Sprint 2 (Day 5-10)：ATG Adapter + Reverse Engine + 基礎遊戲引擎 → MVP ✅
    ↓
Sprint 3 (Day 11-16)：遊戲引擎完整功能 + 動畫 + 音效 + Report 強化
    ↓
Sprint 4 (Day 17-22)：產品化 + 斷點續傳 + E2E 測試 + 文件
```

---

## Sprint 1：基礎設施 + 資料模型 + Pipeline 骨架（Day 1-4）

> **目標**：建立所有核心骨架，確保資料模型、Plugin 系統、Pipeline 流程跑得通。
> **Demo**：`python -m slot_cloner clone <URL> --name test --dry-run` 可以走完 5 Phase（空實作）。

### DEV-1.1: 專案初始化 + 依賴安裝

| 欄位 | 內容 |
|------|------|
| 說明 | 建立 `src/slot_cloner/` 套件結構、`pyproject.toml`、`.gitignore`、基礎 `conftest.py` |
| 涉及檔案 | `src/slot_cloner/__init__.py`, `__main__.py`, `pyproject.toml`, `tests/slot_cloner/conftest.py` |
| 依賴 | 無 |
| 對應 AC | 前置條件（所有 AC 依賴） |
| 預估工時 | 0.5 天 |
| 複雜度 | S |

### DEV-1.2: Pydantic v2 不可變資料模型

| 欄位 | 內容 |
|------|------|
| 說明 | 建立核心資料模型：`GameFingerprint`, `AssetBundle`, `ImageAsset`, `AudioAsset`, `SpriteSheet`, `SymbolConfig`, `PaytableEntry`, `PaytableConfig`, `WildConfig`, `ScatterConfig`, `CascadeConfig`, `MultiplierConfig`, `FeaturesConfig`, `GridConfig`, `GameConfig`, `GameModel`, `GameType` enum, `ConfidenceLevel` enum, `PipelinePhase` enum |
| 涉及檔案 | `models/game.py`, `models/symbol.py`, `models/feature.py`, `models/asset.py`, `models/enums.py` |
| 依賴 | DEV-1.1 |
| 對應 AC | AC-2, AC-5 |
| 預估工時 | 1 天 |
| 複雜度 | M |

**TDD**：建構/序列化/反序列化、`frozen=True` 不可變性驗證、JSON round-trip

### DEV-1.3: PipelineContext + Pipeline Orchestrator 骨架

| 欄位 | 內容 |
|------|------|
| 說明 | `PipelineContext`（不可變上下文）、`PipelineOrchestrator`（狀態機驅動，依序執行 5 Phase，先用空實作 pass-through） |
| 涉及檔案 | `pipeline/orchestrator.py`, `pipeline/context.py` |
| 依賴 | DEV-1.2 |
| 對應 AC | AC-4 |
| 預估工時 | 1 天 |
| 複雜度 | M |

**TDD**：依序執行 5 Phase、Phase 跳過、異常處理（Mock 所有 Phase）

### DEV-1.4: Plugin Registry + BaseAdapter 抽象類別

| 欄位 | 內容 |
|------|------|
| 說明 | `BaseAdapter` ABC（`can_handle`, `recon`, `scrape`, `reverse`）、`PluginRegistry`（自動發現 Adapter）、空的 `GenericAdapter` |
| 涉及檔案 | `plugins/base.py`, `plugins/registry.py`, `plugins/generic/adapter.py` |
| 依賴 | DEV-1.2 |
| 對應 AC | AC-4 |
| 預估工時 | 0.5 天 |
| 複雜度 | S |

### DEV-1.5: Storage Manager + Config Manager

| 欄位 | 內容 |
|------|------|
| 說明 | 建立 AC-5 定義的輸出目錄結構、YAML 設定檔管理 |
| 依賴 | DEV-1.1 |
| 對應 AC | AC-5 |
| 預估工時 | 0.5 天 |

### DEV-1.6: CLI 入口 + Progress Reporter

| 欄位 | 內容 |
|------|------|
| 說明 | Click CLI（`clone` 指令 + 所有參數）、Rich 進度條 |
| 依賴 | DEV-1.3, DEV-1.5 |
| 對應 AC | AC-4 |
| 預估工時 | 0.5 天 |

---

## Sprint 2：ATG Adapter + Reverse Engine + 基礎遊戲引擎（Day 5-10）

> **目標**：針對 ATG 戰神賽特跑通完整 Pipeline → **MVP 達成**
> **Demo**：`python -m slot_cloner clone <ATG_URL> --name storm-of-seth` → 資源 + 報告 + 可在瀏覽器玩的基礎 Clone

### DEV-2.1: Recon Engine + ATG Recon（1.5 天）
- Playwright 開啟 URL、等待遊戲載入、收集技術指紋
- ATG 特徵辨識（URL 模式、API 端點、PixiJS 指紋）
- **風險：高** — ATG 可能有反自動化機制

### DEV-2.2: Asset Scraper + ATG Scraper（1.5 天）
- Playwright `page.route()` 攔截 Network 請求，依 MIME type 分類
- SpriteSheetSplitter：TexturePacker JSON atlas → Pillow 拆解
- **風險：高** — Sprite 格式可能不標準

### DEV-2.3: Reverse Engine + WS 分析器 + ATG Reverse（2 天）⚠️ 最高風險
- **Layer 1**：JSON config 搜尋 paytable/symbol 關鍵字
- **Layer 2**：WebSocket 攔截（瀏覽器 JS context，取得解密後明文）
- **Layer 3**：JS 靜態分析（jsbeautifier + AST，簡化版）
- ATG 特有 WS 訊息格式解析
- **風險：極高** — WS 格式未知、JS 混淆

### DEV-2.4: Report Builder 基礎版（0.5 天）
- Jinja2 模板 → Markdown 報告 + JSON（paytable/symbols/rules）

### DEV-2.5: Config Generator（0.5 天）
- GameModel → game-config.json（PixiJS 引擎消費格式）

### DEV-2.6: PixiJS 遊戲引擎核心（3 天）⚠️ 高風險
- Engine + AssetLoader + Game + Grid + Symbol
- **CascadeGrid**：消除判定（BFS/flood-fill）、掉落填充、連鎖消除
- RNG（crypto.getRandomValues）+ PaytableEngine
- HUD + SpinButton
- **風險：高** — Cascade 消除邏輯複雜

### DEV-2.7: Game Builder（0.5 天）
- 模板複製 + config 注入 + `npm install && npm run build`

---

## Sprint 3：遊戲引擎完整功能（Day 11-16）

| 任務 | 工時 | 說明 |
|------|------|------|
| DEV-3.1 Free Spin 系統 | 1 天 | Scatter 觸發、計數、retrigger |
| DEV-3.2 乘數系統 | 1 天 | 乘數符號、累積、結算 |
| DEV-3.3 動畫系統 | 1.5 天 | 中獎/大獎/Cascade 掉落動畫 |
| DEV-3.4 音效系統 | 0.5 天 | @pixi/sound、事件驅動 |
| DEV-3.5 Report 強化 | 0.5 天 | 技術架構分析、可信度標注 |
| DEV-3.6 Audio 強化 | 0.5 天 | Web Audio API hook |

---

## Sprint 4：產品化 + 測試強化（Day 17-22）

| 任務 | 工時 | 說明 |
|------|------|------|
| DEV-4.1 斷點續傳 | 1 天 | Checkpoint 序列化/反序列化 |
| DEV-4.2 Visual OCR | 1 天 | Layer 4 兜底：Tesseract OCR |
| DEV-4.3 PaytableView + RTP | 1 天 | 遊戲內賠率表 + Monte Carlo 模擬 |
| DEV-4.4 Generic Adapter | 1 天 | 通用兜底策略 |
| DEV-4.5 E2E 測試 | 1.5 天 | 完整 Pipeline E2E |
| DEV-4.6 錯誤處理強化 | 1 天 | 全域 try/except + logging |
| DEV-4.7 文件 | 0.5 天 | README + 教學 |

---

## 開發順序與依賴圖

```
Day 1-2:
  DEV-1.1 → DEV-1.2 → DEV-1.3
               │         │
               ├→ DEV-1.4│
               │         │
  DEV-1.1 → DEV-1.5    ▼
                      DEV-1.6

Day 5-6:
  DEV-2.1 (Recon) → DEV-2.2 (Scraper)

Day 7-8:
  DEV-2.2 → DEV-2.3 (Reverse) → DEV-2.4 (Report)
                                → DEV-2.5 (Config)

Day 9-10:
  DEV-2.5 → DEV-2.6 (PixiJS) → DEV-2.7 (Build)

Day 11-14:
  DEV-3.1 + 3.2（平行）→ DEV-3.3
  DEV-3.4 + 3.5（平行）

Day 17-22:
  DEV-4.1 + 4.2 + 4.3（平行）→ DEV-4.5 (E2E) → DEV-4.6 → DEV-4.7
```

---

## Fixture 準備清單（Sprint 2 前置）

> ⚠️ Sprint 2 開始前必須手動完成，這些是所有 ATG 測試的基礎

| # | 任務 | 方式 | 預估時間 |
|---|------|------|---------|
| F1 | 錄製 ATG WS 訊息 | DevTools → Network → WS → 匯出 | 1 小時 |
| F2 | 下載 ATG 主 JS bundle | DevTools → Sources → 儲存 | 15 分鐘 |
| F3 | 截取 ATG Paytable 截圖 | 手動操作遊戲 → 截圖 | 15 分鐘 |
| F4 | 下載 Sprite Sheet + Atlas | DevTools → Network → 篩選 | 30 分鐘 |
| F5 | 記錄遊戲規則（人工觀察） | 玩 50+ 次，記錄 cluster/乘數 | 2 小時 |

---

## 風險對策

| 風險 | 等級 | 應對策略 |
|------|------|---------|
| **R1: JS 混淆** | 🔴 極高 | 不依賴 Layer 3；優先 WS 攔截 > 設定檔 > OCR |
| **R2: WS 格式未知** | 🔴 高 | Sprint 2 前手動錄製 WS；在 JS context hook 取明文 |
| **R3: Server-Side Logic** | 🔴 高 | 用本地 RNG 模擬，從 WS 提取 Paytable + 權重 |
| **R4: Cascade 複雜度** | 🟡 高 | 參考 match-3 演算法；BFS/flood-fill；TDD 20+ case |
| **R5: Playwright 穩定性** | 🟡 中 | 合理逾時 + 自動重試 + checkpoint |
| **R6: PixiJS v8 API** | 🟡 中 | 鎖版本 ^8.0；先做 Hello World 確認 |

---

## 任務 × AC 矩陣

| 任務 | AC-1 資源 | AC-2 機制 | AC-3 重建 | AC-4 自動化 | AC-5 目錄 |
|------|:-:|:-:|:-:|:-:|:-:|
| DEV-1.1~1.6 | | | | ● | ● |
| DEV-2.1 Recon | ● | ● | | | |
| DEV-2.2 Scrape | ● | | | | ● |
| DEV-2.3 Reverse | | ● | | | |
| DEV-2.4 Report | | ● | | | ● |
| DEV-2.5 Config | | | ● | | |
| DEV-2.6 PixiJS | | | ● | | |
| DEV-2.7 Build | | | ● | | ● |
| DEV-3.1~3.6 | ● | ● | ● | | |
| DEV-4.1~4.7 | ● | ● | ● | ● | ● |

---

## Mock 策略

```
Level 1: 純資料 Mock（Pydantic 模型工廠）
  → models、report、config_generator

Level 2: Playwright Mock（page.route + page.evaluate）
  → recon、scraper、reverse（不連線真實伺服器）

Level 3: Subprocess Mock（mock subprocess.run）
  → builder（mock npm install/build）

Level 4: E2E（完整但離線）
  → 啟動本地 HTTP server 提供 fixture，走完整 Pipeline
```
