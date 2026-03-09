# 技術探勘報告：SadTalker 替代方案
日期：2026-03-08
探勘者：@Technology-Scout
授權觸發：CEO 手動指派（碰壁協議 Stage 4）

---

## 需求缺口（SadTalker 架構限制）

SadTalker 的表情系統有以下根本性架構限制，無法透過修補解決：

1. `--expression_scale` 只能等比例放大/縮小現有表情幅度，無法改變表情類型
2. `--pose_style` 控制頭部轉動方向，與面部情緒無關
3. 表情完全由輸入音訊的 3DMM 係數解碼決定，系統沒有外部情緒注入的接口
4. 源圖微笑 = 輸出影片整體保持微笑，架構上不可修改
5. 結論：**SadTalker 無法支援「從外部標籤強制覆蓋情緒」** — 碰壁確認

---

## 探勘範圍與方法

搜尋來源：GitHub、HuggingFace、arXiv、官方文件
搜尋時間：2026-03-08
重點篩選條件：
- VRAM <= 10GB（保留 2GB 給 GFX 5070 系統）
- 支援外部情緒標籤注入（非僅由音訊被動推導）
- 音訊驅動對嘴同步
- MIT / Apache-2.0 授權
- Python 3.12 相容，Windows 10 可用

---

## 候選方案全面評估

| 工具 | GitHub | Stars | 最後更新 | VRAM 估算 | 情緒外部控制 | 授權 | 評級 |
|------|--------|-------|---------|-----------|------------|------|------|
| **EDTalk** | [tanshuai0219/EDTalk](https://github.com/tanshuai0219/EDTalk) | 456 | 2024 Q3 | ~6-8GB (估) | ✅ 8種情緒標籤CLI | 未確認 | ⭐⭐⭐⭐⭐ |
| **LivePortrait** | [KwaiVGI/LivePortrait](https://github.com/KwaiVGI/LivePortrait) | 17.9k | 2025 Q1 | ~4-6GB | ⚠️ 表情重定向(需驅動圖) | MIT | ⭐⭐⭐⭐ |
| **MuseTalk 1.5** | [TMElyralab/MuseTalk](https://github.com/TMElyralab/MuseTalk) | 5.4k | 2025-03 | ~4GB | ❌ 僅唇形同步 | MIT | ⭐⭐⭐ |
| **EchoMimic V1** | [antgroup/echomimic](https://github.com/antgroup/echomimic) | 4.2k | 2024 Q4 | ~12GB(V100) | ❌ 無情緒標籤 | Apache-2.0 | ⭐⭐ |
| **EchoMimic V3** | [antgroup/echomimic_v3](https://github.com/antgroup/echomimic_v3) | - | 2025 | ❌ 16GB+ | ❌ | Apache-2.0 | ❌ VRAM 超限 |
| **Hallo2** | [fudan-generative-vision/hallo2](https://github.com/fudan-generative-vision/hallo2) | 3.7k | 2024-10 | 16GB+(A100測試) | ❌ 純音訊驅動 | MIT | ❌ VRAM 超限 |
| **Hallo3** | [fudan-generative-vision/hallo3](https://github.com/fudan-generative-vision/hallo3) | - | 2025 | ❌ 80GB | ❌ | - | ❌ VRAM 超限 |
| **AniPortrait** | [Zejun-Yang/AniPortrait](https://github.com/Zejun-Yang/AniPortrait) | - | 2024 Q1 | ~16GB(T4) | ❌ 音訊+姿態控制 | Apache-2.0 | ❌ VRAM 超限 |
| **EAT** | [yuangan/EAT_code](https://github.com/yuangan/EAT_code) | - | 2023 | 17GB/GPU訓練 | ⚠️ 情緒驅動但基於3090 | 未確認 | ⭐⭐ |
| **SieveSync** | [sieve-community/sievesync](https://github.com/sieve-community/sievesync) | - | 2024 | ~8-10GB(估) | ⚠️ LP情緒 + MT唇形 | 未確認 | ⭐⭐⭐⭐ |
| **EmotiveTalk** | [EmotiveTalk](https://github.com/EmotiveTalk/EmotiveTalk.github.io) | - | 2025(CVPR) | 未知 | ✅ EDI情緒解耦注入 | 研究用 | ⭐⭐⭐（代碼未釋出） |
| **LES-Talker** | arXiv:2411.09268 | - | 2025-03 | 未知 | ✅ 線性情緒空間編輯 | 研究用 | ⭐⭐⭐（代碼未釋出） |

---

## 重點方案詳細分析

### 方案 A：EDTalk (ECCV 2024 Oral) — 主要推薦

**GitHub**：https://github.com/tanshuai0219/EDTalk
**論文**：ECCV 2024 Oral，"Efficient Disentanglement for Emotional Talking Head Synthesis"

**核心優勢**：
- 分離式表情控制架構：嘴形 / 頭姿 / 情緒表情三個獨立潛在空間
- 支援 8 種預定義情緒：angry, contempt, disgusted, fear, happy, sad + 其他
- CLI 直接注入情緒標籤：
  ```bash
  python demo_EDTalk_A_using_predefined_exp_weights.py --exp_type sad \
      --audio_path audio.wav --source_img portrait.jpg --save_path output.mp4
  ```
- 或用參考圖/影片作為表情驅動源
- Gradio WebUI 可視化操作
- Python 3.8 + PyTorch（應可升 3.12）

**核心風險**：
- VRAM 未官方說明（估算：解碼器 UNet 約 6-8GB）
- 授權未確認（需查 LICENSE.txt）
- 456 stars 偏低，社群支援有限
- Python 3.8 環境依賴需測試 3.12 相容性
- 對嘴同步品質可能不如 MuseTalk

---

### 方案 B：LivePortrait + MuseTalk 組合管線 — 備選推薦

**核心概念**：分工協作
- **LivePortrait**（17.9k stars, MIT）：負責表情重定向 — 從一張「悲傷表情參考圖」驅動源圖，覆蓋原始表情
- **MuseTalk 1.5**（5.4k stars, MIT, 2025-03）：負責精確音訊唇形同步，4GB VRAM 即可運行

**已驗證組合**：
- SieveSync（sieve-community/sievesync）已完成 LivePortrait + MuseTalk + CodeFormer 三方整合
- LivePortrait 先用「情緒參考圖」將源圖改寫表情，MuseTalk 再做唇形貼合

**工作流**：
```
源圖(微笑) + 悲傷表情參考圖
      ↓ LivePortrait 表情重定向
源圖(悲傷) - 嘴巴中性化
      ↓ MuseTalk 1.5 唇形同步
最終輸出(悲傷 + 對嘴同步)
```

**優勢**：
- 兩個模型都是 MIT 授權
- LivePortrait 12ms/frame @ RTX 4090（速度快）
- MuseTalk 4GB VRAM，即使加上 LivePortrait 也在 12GB 內
- 社群龐大，文件完善，Windows 可用

**劣勢**：
- 需要人工準備「悲傷/高興/憤怒」等情緒參考圖庫
- 兩個模型串接需要工程整合工作
- 表情重定向細膩度依賴參考圖品質

---

### 方案 C：MuseTalk 1.5 單獨使用 — 最保守選項

**適用場景**：如果需求只是「更好的唇形同步」而非情緒改變
- MIT 授權，4GB VRAM，30fps 實時
- 2025-03 最新版 1.5，品質大幅提升
- 但情緒表情完全不可控 — 不符合核心需求

---

### 淘汰方案說明

| 方案 | 淘汰原因 |
|------|---------|
| Hallo3 | 80GB VRAM，完全不可行 |
| Hallo2 | A100 測試，估算 16GB+，超出 12GB 紅線 |
| AniPortrait | T4(16GB) 測試，不確定 12GB 是否可行 |
| EchoMimic V3 | 16GB VRAM ComfyUI 版，超限 |
| EchoMimic V1 | V100(16GB) 測試，無情緒標籤控制 |
| EmotiveTalk | CVPR 2025 論文，代碼尚未公開釋出 |
| LES-Talker | arXiv 論文，代碼尚未公開釋出 |
| EAT | 訓練需 17GB/GPU，推論估算偏高，2023 年模型較舊 |

---

## 推薦方案

### 首選：方案 A（EDTalk）+ 方案 B（LivePortrait + MuseTalk）PoC 並行驗證

**理由**：

EDTalk 是目前已釋出代碼的模型中，**唯一**同時具備：
1. 外部情緒標籤直接 CLI 注入（--exp_type sad/angry/happy）
2. 音訊驅動唇形同步
3. 單一模型，整合簡單

LivePortrait + MuseTalk 組合的優勢在於：
1. 兩個都是成熟的高星數 MIT 授權模型
2. 已有 SieveSync 作為整合範例
3. VRAM 使用更低（分別 4-6GB）
4. 但需要情緒參考圖庫，有額外前置工作

**建議行動**：
1. 先建立 EDTalk PoC，測試 12GB VRAM 是否足夠
2. 同時建立 LivePortrait + MuseTalk 的情緒重定向 PoC
3. 由精算師（Sonnet）對兩個方案進行 VRAM 攻擊測試
4. 架構師（Opus）根據 PoC 結果選定最終方案

---

## 整合路線圖

### 如果選擇 EDTalk

**Step 1 - PoC 驗證（1天）**
```bash
# 建立 Python 3.12 環境
conda create -n edtalk python=3.12
pip install torch torchvision --index-url https://cuda.nvidia.com/...
git clone https://github.com/tanshuai0219/EDTalk
pip install -r requirements.txt

# 測試情緒注入
python demo_EDTalk_A_using_predefined_exp_weights.py \
    --exp_type sad --audio_path test.wav --source_img portrait.jpg
```

**Step 2 - VRAM 測量**
```python
import torch
# 測量推論時 VRAM 峰值
torch.cuda.reset_peak_memory_stats()
# ... 執行推論 ...
print(f"Peak VRAM: {torch.cuda.max_memory_allocated()/1024**3:.2f} GB")
```

**Step 3 - Singer Agent 整合**
- 替換 `src/singer_agent/video_renderer.py` 中的 SadTalker 呼叫
- 新增 `emotion_type` 參數（從 pipeline 傳入）
- 保留 FFmpeg 靜態模式作為最終降級方案

### 如果選擇 LivePortrait + MuseTalk

**Step 1 - 情緒參考圖庫建立**
- 收集或生成標準化情緒表情圖：neutral / happy / sad / angry / fearful
- 建議使用 StyleGAN 或 Stable Diffusion 生成標準化表情

**Step 2 - 管線整合**
```python
# 偽代碼
def render_with_emotion(source_img, audio, emotion):
    # Stage 1: LivePortrait 表情重定向
    emotion_ref = load_emotion_reference(emotion)  # e.g., "sad.jpg"
    neutral_face = liveportrait.retarget(source_img, emotion_ref)

    # Stage 2: MuseTalk 唇形同步
    final_video = musetalk.lipsync(neutral_face, audio)
    return final_video
```

**Step 3 - VRAM 時間分割**
- LivePortrait 完成後釋放 VRAM，再載入 MuseTalk
- 利用現有 `vram_monitor.py` 監控

---

## 風險評估

| 風險 | 機率 | 影響 | 緩解措施 |
|------|------|------|---------|
| EDTalk VRAM 超過 10GB | 中 | 高 | 提前 PoC 量測，超限則轉 LP+MT |
| EDTalk Python 3.12 不相容 | 中 | 中 | 用 conda 3.8 環境隔離 |
| EDTalk 唇形同步品質差 | 中 | 高 | 加 MuseTalk 後處理 |
| LivePortrait 情緒重定向不自然 | 低 | 中 | 增加更多參考圖，調整 retarget 強度 |
| 兩個 PoC 都失敗 | 低 | 高 | 退回方案 C（MuseTalk 僅唇形同步），等待 EmotiveTalk/LES-Talker 代碼釋出 |

---

## 探勘者備注

本次探勘以搜尋方式完成，以下項目**未實測**，需 PoC 腳本驗證：
- EDTalk 的實際 VRAM 消耗（重要！）
- EDTalk 的授權類型（需查 LICENSE.txt）
- Python 3.12 環境相容性
- Windows 10 CUDA 環境下的執行穩定性

PoC 腳本應建立於 `scripts/poc/` 目錄下，不得直接修改產品程式碼。

---

*本報告由 @Technology-Scout 產出，依技術碰壁協議規定，需交付精算師（Claude Sonnet）進行 VRAM 攻擊驗證後，再由架構師（Claude Opus）裁決。*
