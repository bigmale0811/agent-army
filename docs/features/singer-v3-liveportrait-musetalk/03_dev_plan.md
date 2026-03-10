# Singer V3.0 開發計畫
日期：2026-03-10
對應規格：01_spec.md
對應架構：02_architecture.md

## 概述

8 個 DEV 項目，將 LivePortrait + MuseTalk 混合管線整合進 Singer Agent。
遵循 TDD（RED → GREEN → REFACTOR）。

## 驗收標準追蹤矩陣

| AC | 對應 DEV |
|----|---------|
| AC-1：liveportrait_musetalk 產出影片 | DEV-2, DEV-3, DEV-5 |
| AC-2：嘴唇同步品質 | DEV-3 |
| AC-3：表情符合指定情緒 | DEV-1, DEV-2 |
| AC-4：VRAM ≤ 10GB | DEV-3 |
| AC-5：切換舊引擎不受影響 | DEV-5, DEV-8 |
| AC-6：既有測試通過 | DEV-8 |

---

## DEV-1：情緒 → LivePortrait 表情參數映射器（S）

**修改**：`audio_preprocessor.py`（新增 `LivePortraitExpression` + `EMOTION_LIVEPORTRAIT_MAP`）
**測試**：`test_video_renderer.py`（新增 `TestEmotionToLivePortraitParams`，10 test）
**AC**：8 種情緒標籤全覆蓋、未知標籤 fallback neutral、參數值範圍合理
**依賴**：無
**預估**：2h

---

## DEV-2：LivePortrait subprocess 包裝器（M）

**新增**：`liveportrait_adapter.py`（~200 行）、`scripts/liveportrait_retarget.py`（~180 行）
**測試**：`test_liveportrait_adapter.py`（7 test）
**AC**：subprocess 正確呼叫、venv 不存在 raise FileNotFoundError、超時/失敗 raise RuntimeError
**依賴**：DEV-4（config 常數）
**預估**：4h

---

## DEV-3：混合管線主方法 `_render_liveportrait_musetalk()`（M）

**修改**：`video_renderer.py`（新增方法，~50 行 orchestrator）
**測試**：`test_video_renderer.py`（新增 `TestRenderLivePortraitMusetalk`，6 test）
**AC**：兩 subprocess 依序、VRAM 閘門呼叫、暫存清理、失敗降級
**依賴**：DEV-2
**預估**：4h

---

## DEV-4：config.py 新增 LivePortrait 路徑常數（S）

**修改**：`config.py`
**新增**：LIVEPORTRAIT_DIR / PYTHON / INFERENCE_SCRIPT / DRIVING_VIDEO
**測試**：`test_config.py`（3 test）
**AC**：環境變數可覆寫、路徑格式正確
**依賴**：無
**預估**：1h

---

## DEV-5：render() dispatch 新增 liveportrait_musetalk 路由（S）

**修改**：`video_renderer.py`（render() 方法 + docstring）
**測試**：`TestRendererDispatch`（3 test）
**AC**：dispatch 正確、現有 edtalk/musetalk 不受影響
**依賴**：DEV-3
**預估**：1.5h

---

## DEV-6：VideoRenderer.__init__ 注入 LivePortrait 路徑（S）

**修改**：`video_renderer.py`（__init__ 新增 liveportrait_dir 參數）
**測試**：更新 `TestVideoRendererInit`
**AC**：可注入自訂路徑、預設值使用 config
**依賴**：DEV-4
**預估**：1h

---

## DEV-7：pipeline.py Step 8 log 更新（S）

**修改**：`pipeline.py`（Step 8 log 文字 + 注解）
**測試**：確認現有 pipeline 測試全通過
**AC**：無 regression
**依賴**：DEV-5
**預估**：0.5h

---

## DEV-8：測試套件彙整 + 覆蓋率確認（M）

**修改**：`test_video_renderer.py`（補充邊界測試）
**目標**：video_renderer.py 覆蓋率 ≥ 80%、全部 mock（無真實 subprocess）
**AC**：全部測試通過、覆蓋率達標
**依賴**：DEV-1~7 全部
**預估**：3h

---

## 執行順序

```
DEV-4（config）─┬─→ DEV-1（情緒映射）─┐
                └─→ DEV-6（init 注入）─┤
                                       ▼
                                  DEV-2（LP subprocess）
                                       │
                                       ▼
                                  DEV-3（混合管線）
                                       │
                                       ▼
                                  DEV-5（dispatch）
                                       │
                                       ▼
                                  DEV-7（pipeline log）
                                       │
                                       ▼
                                  DEV-8（測試彙整）
```

可並行：DEV-4 + DEV-1 + DEV-6

## 總估算

| 項目 | 時間 |
|------|------|
| DEV-1~8 合計 | ~17h |
| 手動表情參數調試 | 1-2h |
| **總計** | **~19h（2-3 天）** |
