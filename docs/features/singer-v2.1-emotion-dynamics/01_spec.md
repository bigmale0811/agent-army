# Singer Agent V2.1 — 需求規格書

> Stage 1 產出 | 2026-03-09
> FSM 狀態：🟢 Stage 1 需求釐清

## 概述

Singer Agent V2.1 包含 3 項核心升級，目標是讓 MV 產出從「靜態單一情緒」
進化為「動態多情緒 + 動態背景」，同時修復 Step 9 QA 品質檢驗。

## 升級項目

### 🎭 Feature 1: 情緒動態化（Emotion Timeline）

**現況**：整首歌只用一種情緒（由 `mood_to_exp_type(mood_hint)` 決定）。
**目標**：根據音訊能量曲線自動分段，每段渲染不同 EDTalk 情緒，最後拼接。

#### 驗收標準 (AC)

- [ ] AC-1.1: 新增 `emotion_segmenter.py` 模組，輸入人聲 WAV，
  輸出時間軸情緒分段列表 `list[EmotionSegment]`
  - `EmotionSegment(start_sec, end_sec, exp_type, energy_level)`
- [ ] AC-1.2: 使用 librosa 分析音訊能量曲線（RMS envelope），
  識別高能量（副歌/高潮）與低能量（前奏/間奏/安靜段）
- [ ] AC-1.3: 使用 Ollama Qwen3 14B 輔助判斷情緒：
  - 輸入：能量分段 + mood_hint（使用者 Telegram caption）
  - 輸出：每段的 exp_type（8 種 EDTalk 情緒之一）
- [ ] AC-1.4: 靜音段 / 間奏段自動標記為 `neutral`（不做表情）
- [ ] AC-1.5: pipeline.py Step 8 改為「分段渲染」：
  - 根據 EmotionSegment 列表，用 FFmpeg 切割人聲為多段
  - 每段呼叫 EDTalk `--exp_type` 渲染
  - 最後用 FFmpeg `concat` 拼接所有片段
- [ ] AC-1.6: 分段渲染後總時長 = 原始音訊時長（±0.5 秒容差）
- [ ] AC-1.7: 最少 2 段、最多 8 段（避免過度碎片化）
- [ ] AC-1.8: dry_run 模式支援（不執行實際渲染）

#### 邊界條件

- 極短音訊（<30 秒）：不分段，退化為原始單情緒模式
- 全靜音音訊：全部標記 neutral
- Qwen3 回應異常：fallback 到純能量曲線規則（高能量→happy，低能量→sad）
- 分段過渡：相鄰段使用相同 exp_type 時合併為一段

#### 不做的事

- 不做歌詞辨識（ASR）—— 純音訊能量分析
- 不做逐幀情緒變化 —— 以「段落」為最小單位
- 不修改 EDTalk 模型本身

---

### 🔍 Feature 2: QA 品質檢驗修復（face_alignment + MAR）

**現況**：Step 9 使用 MediaPipe Face Mesh，但 MediaPipe 0.10.32
移除了 `mp.solutions` API，導致 QA 直接跳過。
**目標**：用 `face_alignment` + MAR (Mouth Aspect Ratio) 取代 MediaPipe。

#### 驗收標準 (AC)

- [ ] AC-2.1: 移除 `mediapipe` 依賴，改用 `face-alignment` 套件
- [ ] AC-2.2: 重寫 `quality_checker.py` 的 `_analyze_lip_motion()` 方法：
  - 使用 face_alignment 偵測 68 點臉部關鍵點
  - 計算 MAR (Mouth Aspect Ratio) = 嘴巴垂直距離 / 水平距離
  - 有唱歌時 MAR 應有明顯變化（>閾值）
  - 靜音時 MAR 應接近靜止
- [ ] AC-2.3: QAResult 結構不變（passed, lip_sync_score, 等）
- [ ] AC-2.4: 保持「非致命」設計 — QA 失敗不阻擋 MV 輸出
- [ ] AC-2.5: VRAM 使用 < 1GB（face_alignment 可用 CPU 模式）
- [ ] AC-2.6: 測試覆蓋率 80%+

#### 邊界條件

- face_alignment 偵測不到臉：跳過 QA（logged warning）
- 影片幀率非 25fps：自適應取樣
- 256×256 小尺寸影片：face_alignment 仍需正確偵測

#### 不做的事

- 不做 SyncNet 分數計算（過重，另案評估）
- 不做完整 Wav2Lip 品質評估

---

### 🎬 Feature 3: 背景動態化（Ken Burns Effect）

**現況**：Step 4 生成 1920×1080 靜態背景，直到影片結束都是同一畫面。
**目標**：用 FFmpeg zoompan 濾鏡加入緩慢縮放平移，讓背景有生命力。

#### 驗收標準 (AC)

- [ ] AC-3.1: 新增 `ken_burns.py` 模組（或整合到 background_gen.py）
  - 輸入：靜態背景 PNG + 目標時長（秒）
  - 輸出：動態背景 MP4
- [ ] AC-3.2: 使用 FFmpeg `zoompan` 濾鏡：
  ```
  ffmpeg -loop 1 -i background.png \
    -vf "zoompan=z='min(zoom+0.0005,1.5)':d=<frames>:s=1920x1080" \
    -t <duration> -c:v libx264 -pix_fmt yuv420p background_animated.mp4
  ```
- [ ] AC-3.3: 輸出解析度 = 1920×1080，fps = 25
- [ ] AC-3.4: pipeline.py 在 Step 4 之後、Step 5 之前（或 Step 8 合成時）
  整合 Ken Burns 處理
- [ ] AC-3.5: dry_run 支援
- [ ] AC-3.6: 動畫時長自動匹配音訊時長

#### 邊界條件

- FFmpeg 不可用：fallback 到靜態背景（不中斷管線）
- 極長音訊（>10 分鐘）：zoompan 參數自動調整，避免縮放過大

#### 不做的事

- 不做多張背景輪播
- 不做背景隨音樂節奏變化（節拍同步）
- 不做 3D 視差效果

---

## VRAM 預算（12GB 紅線）

| 步驟 | 工具 | 峰值 VRAM | 變化 |
|------|------|----------|------|
| Step 4 | ComfyUI SDXL | ~7-8GB | 不變 |
| Step 4b（新） | FFmpeg Ken Burns | 0（CPU） | 新增 |
| Step 5 | rembg U²-Net | ~170MB | 不變 |
| Step 7 | Demucs | ~3-4GB | 不變 |
| Step 7b（新） | librosa 能量分析 | 0（CPU） | 新增 |
| Step 7c（新） | Qwen3 情緒判斷 | 0（Ollama 獨立） | 新增 |
| Step 8 | EDTalk × N 段 | ~2.4GB × N 次 | 序列執行，不堆疊 |
| Step 9 | face_alignment | <1GB（可 CPU） | 替換 MediaPipe |

**結論**：所有新增步驟都是 CPU 或獨立程序，不增加 GPU 壓力。
EDTalk 分段渲染是序列執行（一段結束→下一段開始），VRAM 峰值不變。

---

## 管線步驟變化

```
V2.0（現在）                    V2.1（升級後）
──────────────                 ──────────────
Step 1  歌曲研究                Step 1  歌曲研究
Step 2  歌曲規格                Step 2  歌曲規格
Step 3  YouTube 文案            Step 3  YouTube 文案
Step 4  背景生成（靜態）          Step 4  背景生成（靜態）
                               Step 4b 🆕 Ken Burns 動態化
Step 5  去背 + 合成              Step 5  去背 + 合成
Step 6  品質預檢                Step 6  品質預檢
Step 7  音訊前處理               Step 7  音訊前處理
                               Step 7b 🆕 情緒分段（librosa + Qwen3）
Step 8  EDTalk 渲染（單情緒）     Step 8  EDTalk 分段渲染（多情緒）
Step 9  QA（MediaPipe ❌）       Step 9  QA（face_alignment ✅）
Step 10 儲存專案                Step 10 儲存專案
```

## 優先級排序

1. 🥇 **Feature 1: 情緒動態化** — 最有價值的升級，直接提升 MV 品質
2. 🥈 **Feature 3: 背景動態化** — 簡單但效果明顯（FFmpeg 一行指令）
3. 🥉 **Feature 2: QA 修復** — 修復現有壞掉的功能
