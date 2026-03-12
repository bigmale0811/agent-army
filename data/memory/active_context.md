# 🧠 Active Context
更新：2026-03-12 第五輪突破 — ATG Token 完全破解！

## 🎰 老虎機遊戲 Clone & 生產線工具

### FSM 狀態：🟢🟢🟢 第五輪突破 — Token 破解 + Pipeline 全通！
- Stage 1~6 ✅ 基礎框架 → commit `f59c755`（尚未 commit 第二~五輪修復）
- 第二輪修復 ✅ → Socket.IO + Cocos Creator + Spin 觸發
- 第三輪修復 ✅ → 統一 Session + --interactive + --browser-profile
- 第四輪強化 ✅ → Token 401 自動偵測 + 互動導航引導
- **第五輪突破 ✅ → ATG Demo Token 自動生成 + ReconEngine WS 阻擋 + Pipeline 全通！**

### 🏆 第五輪突破成果
- [x] ATG Demo API 發現：`api.godeebxp.com/trail/egyptian-mythology`
- [x] 從 ATG 官網自動取得新鮮 Token（無需 CEO 手動操作）
- [x] ReconEngine 加入 WS 阻擋（add_init_script 覆寫 WebSocket）
- [x] Token 不再被 RECON 消耗 → SCRAPE 認證成功
- [x] Pipeline 全 4 Phase 通過：recon → scrape → reverse → report
- [x] **41 則 WS 訊息、30 個 Spin 結果、286 圖片、4 音效、209 設定檔**
- [x] 174 tests ALL PASSED

### 🔑 ATG Token 機制（完全破解！）
- Token 由 `api.godeebxp.com/trail/{game}` API 生成
- ATG 官網 "DEMO PLAY" 按鈕呼叫 `window.open()` 觸發此 API
- Token 在 WS `initial` 訊息發送時被消耗（一次性）
- **解法**：ReconEngine 用 `add_init_script` 阻擋 WS → Token 保鮮到 SCRAPE

### 真實 URL 測試 — 第二輪結果（大幅改善！）
| Phase | 第一輪 | 第二輪 | 改善 |
|-------|--------|--------|------|
| RECON | ✅ | ✅ | — |
| SCRAPE | ✅ 285img | ✅ 285img | — |
| REVERSE | ❌ 0 符號 | ✅ **30 符號** | 🎯 從 0→30 |
| REPORT | ✅ | ✅ | 內容更豐富 |
| BUILD | ❌ 參數錯 | ⏭️ skip | CLI 已正確 |

### 提取到的 30 個符號
- 特殊：Wild, Scatter, Multiplier, FreeSpin
- 高價值：Ra, Eye, Scarab（埃及神話主題）
- 一般：symbol_01~18, icon_01~02
- 撲克牌：10

### 🔐 Token 認證問題 → 已有解法！
- WS Spin 觸發成功 → 但回應 **401: Token 過期**
- **解法 1**: `--interactive` → 開可見瀏覽器，使用者手動處理認證
- **解法 2**: `--browser-profile ./profile` → 持久化 Cookie，只需登入一次
- **解法 3**: 統一 Session 架構 → Scraper 同時攔截 WS，Token 不會被二次消耗
- **待 CEO 提供新鮮 URL 測試**

### CEO 確認的決策
1. **範圍**：先做 Clone 工具，換皮留 Phase 2
2. **遊戲類型**：先支援消除型 (Cascade)
3. **RTP 模擬**：能做就做，不行就下一階段
4. **對標遊戲**：ATG 戰神賽特 (Storm of Seth)

### 關鍵文件
- 規格書：`docs/features/slot-clone-pipeline/01_spec.md`
- 架構：`docs/features/slot-clone-pipeline/02_architecture.md`
- 開發計畫：`docs/features/slot-clone-pipeline/03_dev_plan.md`
- PixiJS 引擎：`src/slot_cloner/builder/template/`

### 模組架構
```
src/slot_cloner/
├── models/     (18 Pydantic 模型, frozen=True)
├── pipeline/   (Orchestrator + Context, 5 Phase 狀態機)
├── plugins/    (BaseAdapter + Registry + ATG + Generic)
├── recon/      (ReconEngine — Playwright 偵察)
├── scraper/    (ScraperEngine + SpriteSplitter)
├── reverse/    (ReverseEngine + WS/JS/Paytable 分析)
├── report/     (ReportBuilder + Jinja2 模板)
├── builder/    (GameBuilder + ConfigGenerator + PixiJS 模板)
├── storage/    (StorageManager)
├── config/     (Settings + YAML)
├── progress/   (ProgressReporter)
└── cli.py      (Click CLI)
```

---

## 🛑 暫停中：Singer Agent 技術碰壁
- V3.2 2D 後處理天花板，探勘報告已完成
- 待 CEO 決定：MultiTalk / EchoMimicV3 / LatentSync

## Git 狀態
- slot_cloner 全部新檔案尚未 commit
- V3.2 修復尚未 commit
- V3.0 `0a3a650` 尚未 push

## 硬體
- GFX 5070 12GB VRAM / 64GB RAM

## ⚡ 最近壓縮事件
- [2026-03-12 16:38:57] Context 被自動壓縮，以上內容是壓縮前的狀態
- **請重新讀取此檔案確認進度**
