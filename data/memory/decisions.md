# 📋 決策紀錄

跨對話累積的重要決策，供未來參考。

- [2026-03-04] Singer Agent 使用 SadTalker 作為主要動畫引擎，FFmpeg 靜態模式作為降級方案
- [2026-03-08] HR 招募：@Technology-Scout（技術探勘者）— CEO 指令，建立 R&D 研發部門
- [2026-03-08] 系統憲法更新：加入「技術碰壁協議」— Stage 6 失敗 3 次強制暫停，轉交 Scout 探勘替代方案
- [2026-03-08] 碰壁協議核心規則：Scout 只寫 PoC → 精算師 VRAM 攻擊 → 架構師整合 → 回到 Stage 2
- [2026-03-11] HR 招募顧問團（CEO 指派）：3D 動畫顧問 + 2D 動態顧問 + Talking Head 工具顧問
- [2026-03-11] 技術碰壁協議正式啟動：2D warpAffine 天花板，CEO 判定「圖片在轉不是人在動」
- [2026-03-11] CEO 決策：嘴型品質不能再降（MuseTalk 是底線），先探勘再決定方案
- [2026-03-04] 三個 Telegram Bot 各自獨立運作：Reading Bot、Japan Intel Bot、Singer Bot
- [2026-03-05] 建立 Memory System（跨對話記憶），存放在 data/memory/，CLAUDE.md 要求每次對話開頭先讀取
- [2026-03-06] **ECC 流程違規教訓**：開發 LLM 模組 + Setup Wizard 時跳過 Plan/TDD/Review/Verify，導致 5 個 bug 到使用者手上。未來所有開發必須嚴格遵循 Phase 0-7，即使使用者催促也不可省略
- [2026-03-06] 雲端 LLM 統一架構：OpenAI-compatible 用 `openai` SDK（切換 base_url），Gemini 用 `google-genai` SDK，Ollama 為可選本地模型
- [2026-03-06] Setup Wizard 使用純 stdlib，不依賴 pip，支援既有專案偵測（CLAUDE.md + .claude/settings.json）
- [2026-03-06] **ECC v2 升級**：從 4 步線性流程升級為 8 Phase 文件驅動流程。新增：Phase 0 RECEIVE（需求規格 + 人工閘門）、Phase 1 ARCHITECT（架構設計 + 人工閘門）、Phase 5 QA（獨立 qa-reviewer agent，只讀 spec 不讀程式碼）、Phase 5b ITERATE（迴圈修復最多 3 輪）。文件模板在 docs/templates/，每個功能的文件在 docs/features/<name>/
- [2026-03-08] **ECC 熱更新**：新增「動態 HR 招募模組」與「異質多模型智囊團辯論」協議至 CLAUDE.md
- [2026-03-08] **HR 招募**：新增 generative-video-specialist.md（影片生成 + VRAM 安全）與 multimedia-pipeline-engineer.md（多媒體管線工程），roles/ 從 5 → 7 個角色
- [2026-03-08] **智囊團辯論結論（Singer VRAM）**：採用「GPU 時間分割 + 主動記憶體回收」策略。否決量化方案（Singer 不控制 SD 載入）與換模型方案（已是 FP16）。關鍵補丁：ComfyUI POST /free 卸載 + rembg session 釋放 + VRAM 監控。派工單 WO-20260308。

## 2026-03-09 CEO 指令：MuseTalk PoC 概念驗證

### 決策
- **CEO 質疑並推翻先前結論**：MuseTalk 不應被排除
- **CEO 指示**：嘗試 MuseTalk，不要只依賴 EDTalk

### 調查結論（推翻先前 Scout 報告的部分結論）
1. **Issue #40（Windows 卡死）**→ CLOSED，已修復（2024-05-31）
2. **RTX 50 系列支援**→ Issue #334 已有解法：PyTorch 2.7+cu128 + mmcv 2.1.0，RTX 5090 用戶確認可跑
3. **VRAM 需求**→ RTX 3050 Ti（4GB）fp16 即可跑，遠低於先前 Scout 估計的 4-6GB
4. **專案活躍度**→ 5,397 ⭐，2026-03-08 仍有更新

### 情緒動態化架構決策（CEO 建議）
- **否決**：純 librosa 能量分析驅動情緒（太粗糙，激昂悲歌能量也高，前奏也是低能量）
- **採用**：Qwen3 根據歌曲名稱 + 歌手 + caption 輸出時間軸情緒分配
- **能量分析**：降級為輔助參考，不作為主要驅動源
- **教訓**：Scout 報告中對 MuseTalk 的負面評估未經實際 GitHub 驗證，應先查 issue 再下結論

## 2026-03-08 動態 HR 招募：Multimedia-QA-Specialist
- **觸發原因**：CEO 驗收 Singer MV 發現三大品質問題（非人聲亂動、情緒斷層、品管缺失）
- **角色**：多媒體品管專家，負責影音管線自動化品質驗收
- **工具鏈**：MediaPipe + librosa + OpenCV + Silero VAD
- **設定檔**：`.claude/roles/multimedia-qa-specialist.md`

## 2026-03-08 技術碰壁協議：SadTalker 架構確認無解
- **碰壁確認**：SadTalker `--expression_scale` / `--pose_style` 均無法改變情緒類型，表情由 3DMM 音訊解碼決定，架構上不可外部注入情緒標籤
- **@Technology-Scout 探勘結果**（探勘報告：`docs/research/sadtalker-replacement-scout-2026-03-08.md`）：
  - 淘汰：Hallo3（80GB VRAM）、Hallo2（16GB+）、AniPortrait（16GB）、EchoMimic V3（16GB）
  - 尚未釋出代碼：EmotiveTalk（CVPR 2025）、LES-Talker（arXiv 2025）
  - **首選候選**：EDTalk（ECCV 2024 Oral，支援 8 種情緒 CLI 注入，456 stars）— 需 PoC 驗證 VRAM
  - **備選候選**：LivePortrait（17.9k stars, MIT）+ MuseTalk 1.5（5.4k stars, MIT）組合管線
- **下一步**：精算師（Sonnet）對兩個方案進行 VRAM 攻擊測試，架構師（Opus）裁決

## 2026-03-10 CEO 決策：Singer V3.0 — LivePortrait + MuseTalk 混合管線

### 決策
- **CEO 選擇方案 1**：LivePortrait + MuseTalk 混合管線
- **版本號**：V3.0（全新架構，大版本號）
- **LivePortrait**：負責頭部動態 + 表情（眨眼、抬眉、微笑）
- **MuseTalk**：負責嘴唇同步（已驗證 PASS，VRAM 峰值 8,258MB）
- **VRAM 策略**：分時管控（兩模型不同時載入）

### 技術研究結果
- LivePortrait 有**內建表情參數**（smile/blink/eyebrow/wink/aaa/eee/woo），不一定需要參考圖
- VRAM 僅 4-6GB（安全）
- Python API 可直接呼叫（`LivePortraitPipeline`）
- MIT 授權，17.9k stars
- ⚠️ 官方推薦 CUDA 11.8 + PyTorch 2.3.0，RTX 5070 (sm_120) 需 cu128

### 階段性決策
1. **先跑 PoC** — 先 clone + 壓測 VRAM 和品質
2. **先研究 LivePortrait 內建能力** — 確認表情參數是否足以取代參考圖庫
3. **情緒來源簡化** — 先做全曲單一情緒，時間軸情緒留後續版本
4. **EDTalk (V2.0) 保留** — 作為降級方案（256×256，2.4GB VRAM）
