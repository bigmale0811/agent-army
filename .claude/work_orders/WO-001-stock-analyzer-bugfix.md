# 派工單：#WO-001 Stock Analyzer 首次分析 Bug 修復

- 建立時間： 2026-03-06 16:00
- 當前狀態： [DONE]
- 當前負責人： —
- 目前所在階段： ✅ 完成（Stage 6 PASS）
- 完成時間： 2026-03-06

## 任務細節 (Telegram 接收到的原始需求)
> AAPL 首次分析已成功跑完（446 秒），但有以下 3 個 Bug 需修復：
> 1. 🔴 技術分析報告為空（Market Analyst 沒回傳資料）
> 2. 🟡 投資計畫含 `</think>` 思考鏈雜訊（QWen3 輸出未清理）
> 3. 🟡 報告全英文（預期中文輸出）

## 任務執行日誌 (Agent 需隨時更新此處進度)
- [x] 秘書已收單並分派任務
- [x] Planner 完成需求拆解與排程
- [x] Architect 完成系統架構設計（Bugfix 簡化流程，無需大型架構變更）
- [x] TDD-Guide 完成測試腳本撰寫（12 項 clean_thinking_tags 測試）
- [x] 工程師完成實作開發（BUG-1 + BUG-2 修復）
- [x] Code-Reviewer & Security-Reviewer 完成審查（2 HIGH + 2 MEDIUM 已修復）
- [x] QA 測試通過（15/15 PASS + AAPL 驗證分析已啟動）
- [x] Doc-Updater 更新文件（active_context + 派工單關閉）

## 審查修復紀錄

### Code Review 第一輪（已修復）
1. ✅ `clean_thinking_tags` 型別標註從 `str` 改為 `Optional[str]`
2. ✅ 3 個 regex 合併為 2 個（完整配對 + 殘留清理 `</?think>`）
3. ✅ 新增 3 項 `market_report` key 回歸測試

### Code Review 第二輪（已修復）
1. ✅ MEDIUM: `if not text` 改為明確 `if text is None` 避免語意混淆
2. ✅ MEDIUM: `lstrip("\n")` 改為 `lstrip("\r\n")` 支援 Windows 換行
3. ✅ MEDIUM: `propagate()` 加入 try/except 錯誤處理，符合 docstring 例外契約

### Security Review 發現（記錄，待 DEV-D 處理）
- 外部資料無 schema 驗證（建議用 Pydantic StateSchema）
- 無字串長度上限（建議 50KB）
- `raw_state` 直接序列化（建議僅保留已驗證欄位）

## 修復紀錄

### BUG-1: 🔴 技術分析報告為空 — ✅ 已修復
- **根因**：`src/stock_analyzer/main.py` L120 使用了錯誤的 key `market_research_report`
- **修正**：改為 `market_report`（對應 TradingAgents `AgentState` 定義）
- **影響檔案**：`src/stock_analyzer/main.py`

### BUG-2: 🟡 投資計畫含 think 雜訊 — ✅ 已修復
- **根因**：QWen3 14B 輸出包含 `<think>...</think>` 推理區塊，未被過濾
- **修正**：新增 `clean_thinking_tags()` 函式，用 regex 清除所有 think 標籤
- **適用範圍**：所有 6 個報告欄位皆已套用清理
- **測試**：12 項單元測試全部 PASS（含多行、殘留標籤、實際 QWen3 輸出等情境）
- **影響檔案**：`src/stock_analyzer/main.py`、`tests/stock_analyzer/test_clean_thinking_tags.py`

### BUG-3: 🟡 報告全英文 — ⏳ 留待 DEV-C1
- **說明**：需在 prompt 層面加入中文輸出指示，屬於 DEV-C1 批次任務
- **不在本次修復範圍**

### 額外改善
- 新增 `pytest.ini`：設定 `pythonpath = src`，統一測試 import 路徑
