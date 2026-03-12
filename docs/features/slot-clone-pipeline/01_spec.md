# 需求規格書：老虎機遊戲 Clone & 生產線工具

> **Feature**: slot-clone-pipeline
> **Stage**: 🟢 Stage 1 需求釐清
> **日期**: 2026-03-12
> **請求者**: CEO

---

## 1. 專案願景

建立一套**自動化老虎機遊戲生產線**，核心流程：

```
輸入 URL + 遊戲名稱
       ↓
  🔍 自動爬取分析
       ↓
  📦 資源擷取（圖片/音效/動畫）
       ↓
  🧮 遊戲機制逆向（賠率表/符號/Bonus 規則）
       ↓
  📊 分析報告產出
       ↓
  🎮 可玩的 Clone 遊戲
       ↓
  🎨 換皮 & 優化改造
```

**最終目標**：輸入一個老虎機遊戲 URL，全自動產出可運行的 Clone + 完整分析報告，再進行換皮變成新遊戲。

---

## 2. 對標遊戲

| 項目 | 詳情 |
|------|------|
| 遊戲名稱 | **戰神賽特 (Storm of Seth)** |
| 開發商 | ATG (Agile Titan Games) |
| 類型 | 消除型老虎機 (Cascade/Avalanche) |
| RTP | 96.89% |
| 最大倍率 | x51,000 |
| 特殊符號 | Wild、Scatter、Bonus |
| 核心機制 | 乘數符號 (2x-500x)、Free Spin、Bonus Game |
| 遊戲子類型 | slot-erase-any-times（消除任意次） |
| 試玩 URL | `play.godeebxp.com/egames/...` |

---

## 3. 功能需求

### 3.1 Clone 工具（核心模組）

**輸入**：遊戲 URL + 遊戲名稱
**輸出**：完整遊戲資源包 + 分析報告 + 可運行 Clone

#### A. 資源擷取引擎
| 擷取項目 | 說明 | 優先級 |
|----------|------|--------|
| 圖片素材 | 符號圖、背景、UI 元件、Logo | P0 |
| Sprite Sheets | TexturePacker 格式的合圖 + JSON atlas | P0 |
| 音效 | BGM、中獎音效、按鈕音效、Bonus 音效 | P0 |
| 動畫資料 | Spine/DragonBones 骨骼動畫、CSS 動畫 | P1 |
| 字型 | 自訂 WebFont | P1 |
| 設定檔 | 遊戲配置 JSON（如有暴露） | P0 |

#### B. 遊戲機制逆向分析
| 分析項目 | 說明 | 優先級 |
|----------|------|--------|
| 賠率表 (Paytable) | 各符號組合的賠率 | P0 |
| 符號分佈 | 各 Reel 上符號出現的權重 | P0 |
| 遊戲規則 | Payline/Ways/Cluster 類型判定 | P0 |
| 特殊機制 | Wild 替代、Scatter 觸發、Free Spin 規則 | P0 |
| Bonus 規則 | Bonus Game 觸發條件與獎勵邏輯 | P0 |
| 乘數機制 | 乘數符號的出現機率與累積規則 | P0 |
| Cascade 機制 | 消除後掉落、連鎖消除邏輯 | P0 |
| RTP 估算 | 透過 Monte Carlo 模擬驗證 | P1 |

#### C. 分析報告
| 報告內容 | 格式 |
|----------|------|
| 遊戲概覽（類型、RTP、波動率） | Markdown |
| 賠率表（含圖片預覽） | Markdown + 表格 |
| 符號清單（圖片 + 名稱 + 賠率） | Markdown + 圖片 |
| 特殊機制分析 | Markdown |
| 技術架構分析（引擎、框架、通訊協議） | Markdown |
| UI/UX 佈局分析 | Markdown + 截圖 |
| 資源清單（所有擷取的檔案） | JSON + Markdown |

### 3.2 遊戲重建引擎

**輸入**：Clone 工具產出的資源包 + 分析報告
**輸出**：可在瀏覽器運行的 HTML5 老虎機遊戲

| 功能 | 說明 | 優先級 |
|------|------|--------|
| 基礎 Slot Engine | PixiJS + TypeScript，支援多種遊戲類型 | P0 |
| Cascade (消除) 模式 | 符號消除、掉落、連鎖 | P0 |
| 符號系統 | 普通/Wild/Scatter/Bonus 符號管理 | P0 |
| 賠率計算引擎 | 根據 Paytable 自動計算獎金 | P0 |
| Free Spin 系統 | 觸發、計數、特殊規則 | P0 |
| 乘數系統 | 乘數符號顯示、累積、結算 | P0 |
| 動畫系統 | 轉輪、中獎、大獎動畫 | P1 |
| 音效系統 | BGM + 事件音效 | P1 |
| RNG 引擎 | 加密安全隨機數（crypto.getRandomValues） | P0 |

### 3.3 換皮工具（Phase 2 未來擴展）

> 此階段先不實作，但架構設計需預留擴展空間

| 功能 | 說明 |
|------|------|
| 主題配置檔 | JSON 定義主題（符號圖映射、配色、音效映射） |
| 素材替換 CLI | 批量替換圖片/音效，保持相同 atlas 格式 |
| Paytable 編輯器 | 修改賠率表 + Monte Carlo 驗證新 RTP |

---

## 4. 技術約束

| 約束 | 說明 |
|------|------|
| **目標平台** | Web（HTML5 Canvas/WebGL） |
| **遊戲引擎** | PixiJS v8 + TypeScript |
| **爬蟲工具** | Playwright（無頭瀏覽器，處理動態載入） |
| **開發語言** | Python（Clone 工具）+ TypeScript（遊戲引擎） |
| **執行環境** | CLI 工具（Python），遊戲運行於瀏覽器 |
| **VRAM** | 不涉及 GPU 推理，無 VRAM 限制 |
| **合規** | 素材僅供學習分析，最終產品需使用原創素材 |

---

## 5. 驗收標準 (Acceptance Criteria)

### AC-1：資源擷取
- [ ] 輸入目標遊戲 URL，工具能自動開啟頁面並等待遊戲載入完成
- [ ] 擷取所有圖片資源（≥90% 覆蓋率），儲存為原始格式
- [ ] 擷取所有音效資源，儲存為 MP3/OGG
- [ ] 擷取 Sprite Sheet 並自動拆解為獨立圖片
- [ ] 所有資源按類別分資料夾存放

### AC-2：遊戲機制分析
- [ ] 自動辨識遊戲類型（Classic/Ways/Cluster/Cascade）
- [ ] 產出賠率表（Paytable），包含各符號組合的賠率
- [ ] 識別特殊符號（Wild/Scatter/Bonus）及其規則
- [ ] 識別 Free Spin 觸發條件與規則
- [ ] 分析報告以 Markdown 格式輸出，人類可讀

### AC-3：遊戲重建
- [ ] 用擷取的素材重建可在瀏覽器運行的遊戲
- [ ] 基本 Spin 功能正常（點擊 → 轉輪 → 停止 → 結算）
- [ ] Cascade 消除機制正常運作
- [ ] Wild 替代計算正確
- [ ] Free Spin 可正常觸發與進行
- [ ] 乘數符號正常累積與結算

### AC-4：自動化流程
- [ ] 整個流程 CLI 一鍵執行：`python -m slot_cloner clone <URL> --name <NAME>`
- [ ] 執行過程有進度條或狀態回報
- [ ] 失敗時有清楚的錯誤訊息
- [ ] 產出結構化的輸出目錄

### AC-5：輸出目錄結構
```
output/<game-name>/
├── assets/
│   ├── images/          # 擷取的圖片
│   ├── sprites/         # 拆解後的 sprite
│   ├── audio/           # 音效
│   └── fonts/           # 字型
├── analysis/
│   ├── report.md        # 完整分析報告
│   ├── paytable.json    # 結構化賠率表
│   ├── symbols.json     # 符號定義
│   ├── rules.json       # 遊戲規則
│   └── screenshots/     # 遊戲截圖
├── game/
│   ├── index.html       # 可運行的遊戲
│   ├── src/             # TypeScript 源碼
│   └── dist/            # 編譯後的遊戲
└── metadata.json        # 遊戲元數據
```

---

## 6. 邊界條件 & 風險

| 風險 | 影響 | 緩解 |
|------|------|------|
| 遊戲使用混淆/加密 JS | 無法逆向遊戲邏輯 | 改用 Network 攔截 + 黑箱分析 |
| WebSocket 通訊加密 | 無法擷取遊戲配置 | 用 Playwright 攔截解密前的資料 |
| Canvas 渲染無法直接擷取素材 | 圖片可能被合成到 Canvas | 攔截 Image/Texture 載入請求 |
| 不同遊戲框架差異大 | 一套工具無法通吃 | 設計 Plugin 架構，針對不同框架寫 Adapter |
| 遊戲邏輯在 Server 端 | Client 只有表現層 | 透過大量模擬推算邏輯 |

---

## 7. 不做的事 (Out of Scope)

| 項目 | 原因 |
|------|------|
| ❌ 真錢博弈系統 | 法律風險，此工具僅供學習與遊戲開發 |
| ❌ 即時多人連線 | 先做單機版 |
| ❌ 後端系統（帳號/儲值） | 先專注前端遊戲引擎 |
| ❌ 手機 App 打包 | 先做 Web 版 |
| ❌ 自動換皮（Phase 2） | 先把 Clone 工具做好 |

---

## 8. 參考資源

### 開源 PixiJS Slot 專案
- [PixiSlot](https://github.com/MateuszSuder/PixiSlot) — PixiJS v5 + TypeScript
- [pixi-slot-machine](https://github.com/weyoss/pixi-slot-machine) — 可配置的 Slot
- [slot (React+Pixi+TS)](https://github.com/pioncz/slot) — React 整合
- [PixiJS Open Games](https://github.com/pixijs/open-games) — 官方開源遊戲集

### 資源擷取工具
- [Sprite-Extractor](https://github.com/Akascape/Sprite-Extractor-On-The-Go) — Python Sprite 拆解
- [awesome-game-file-format-reversing](https://github.com/VelocityRa/awesome-game-file-format-reversing) — 遊戲逆向資源

### 老虎機數學模型
- [Slot Math: RNG, Reel Mapping & RTP](https://sdlccorp.com/post/how-slot-game-algorithms-work-understanding-random-number-generators/) — RNG 演算法
- [GammaStack: Slot Math Basics](https://www.gammastack.com/blog/the-basic-mathematics-of-slot-game-machines/) — 基礎數學
- [Slot RTP Optimization (Academic)](https://www.researchgate.net/publication/316050890_Slot_Machine_Base_Game_Evolutionary_RTP_Optimization) — 學術論文
- [Elements of Slot Design (PDF)](http://slotdesigner.com/wp/wp-content/uploads/Elements-of-Slot-Design-2nd-Edition.pdf) — 設計聖經

### ATG 戰神賽特
- [ATG 官方 - Storm of Seth](https://www.atg-games.com/en/game/storm-of-seth/)
- [戰神賽特玩法教學](https://atg-slots.com/)
