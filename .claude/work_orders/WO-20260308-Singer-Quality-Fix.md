# WO-20260308-Singer-Quality-Fix

## 狀態：[DONE]

## 背景
CEO 驗收 Singer MV 發現三大致命品質問題：
1. 非人聲段落（間奏/呼吸）嘴巴亂動
2. 情緒標籤「感傷」但人物微笑
3. 無自動品管機制

## 智囊團辯論摘要
- **Qwen3 提案**：3 方案（VAD/Demucs/混合）
- **Sonnet 攻擊**：
  - 🔴 Silero VAD 在有伴奏 MV 中完全失效（背景音樂干擾）
  - 🔴 `--pose_style` 控制頭部旋轉，不控制表情（三方案都搞錯）
  - 🔴 源圖微笑 = SadTalker 產出微笑（根本問題在 source image）
  - ✅ Demucs subprocess 隔離可行（3-4GB → 釋放 → SadTalker 4-5GB）
  - ✅ `--expression_scale` 可放大表情幅度
  - ✅ MediaPipe QA 在動畫臉精度 -15-20% 但仍可用
- **Opus 裁決**：分階段實作，優先做確定可行的 3 項

## 任務執行日誌

### DEV-1：Demucs 人聲分離（subprocess 隔離）✅
- [x] 新增 `src/singer_agent/audio_preprocessor.py`
- [x] Demucs htdemucs 透過 SadTalker venv subprocess 執行
- [x] 輸入：完整混音 → 輸出：純人聲 WAV
- [x] VRAM 隔離：subprocess 結束後自動釋放 3-4GB
- [x] ffmpeg noise gate（agate 濾鏡）強制靜音
- [x] 測試：19 個 → 全部通過

### DEV-2：mood_hint → expression_scale 橋接 ✅
- [x] `video_renderer.py` 加入 `--expression_scale` 參數
- [x] 情緒映射：中英文雙語（sad→0.5, 感傷→0.5, 情緒低落→0.4...）
- [x] Pipeline Step 7 → mood_to_expression_scale() → Step 8 renderer.render()
- [x] 測試：現有測試 + 新增 9 個映射測試

### DEV-3：MediaPipe QA 自動化 ✅
- [x] 新增 `src/singer_agent/quality_checker.py`（QualityChecker 類別）
- [x] MediaPipe Face Mesh 分析嘴唇 landmark 幀間 MSD
- [x] 音訊 RMS 能量分析判斷靜音區段
- [x] 靜音段嘴唇運動比率 > 30% → FAIL
- [x] 依賴可選：MediaPipe 缺失時優雅跳過
- [x] PCM16 自動轉換（ffmpeg）
- [x] 測試：12 個 → 全部通過

### DEV-4：（下輪）ComfyUI ControlNet 表情重繪
- [ ] 需先研究 IP-Adapter FaceID 在 12GB 環境可行性
- [ ] 需下載 ControlNet 模型（1.4-2.5GB）
- [ ] 需修改 ComfyUI workflow JSON
- **狀態**：DEFERRED — 高風險，需獨立研究
- **備註**：CEO 已授權觸發技術碰壁協議，若 expression_scale 無法滿足需求

### Pipeline 整合 ✅
- [x] 管線從 8 步擴充到 10 步
- [x] Step 7: 音訊前處理（Demucs + noise gate）
- [x] Step 8: 影片渲染（人聲軌 + expression_scale）
- [x] Step 9: QA 品質檢驗（MediaPipe 嘴唇同步）
- [x] **354 個測試全部通過**

## 依賴安裝
- `demucs`：安裝到 SadTalker venv（已有 torch）
- `mediapipe`：安裝到 Singer Bot venv（CPU only，不需 torch）
