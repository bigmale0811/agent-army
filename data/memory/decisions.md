# 📋 決策紀錄

跨對話累積的重要決策，供未來參考。

- [2026-03-04] Singer Agent 使用 SadTalker 作為主要動畫引擎，FFmpeg 靜態模式作為降級方案
- [2026-03-08] HR 招募：@Technology-Scout（技術探勘者）— CEO 指令，建立 R&D 研發部門
- [2026-03-08] 系統憲法更新：加入「技術碰壁協議」— Stage 6 失敗 3 次強制暫停，轉交 Scout 探勘替代方案
- [2026-03-08] 碰壁協議核心規則：Scout 只寫 PoC → 精算師 VRAM 攻擊 → 架構師整合 → 回到 Stage 2
- [2026-03-04] 三個 Telegram Bot 各自獨立運作：Reading Bot、Japan Intel Bot、Singer Bot
- [2026-03-05] 建立 Memory System（跨對話記憶），存放在 data/memory/，CLAUDE.md 要求每次對話開頭先讀取
- [2026-03-06] **ECC 流程違規教訓**：開發 LLM 模組 + Setup Wizard 時跳過 Plan/TDD/Review/Verify，導致 5 個 bug 到使用者手上。未來所有開發必須嚴格遵循 Phase 0-7，即使使用者催促也不可省略
- [2026-03-06] 雲端 LLM 統一架構：OpenAI-compatible 用 `openai` SDK（切換 base_url），Gemini 用 `google-genai` SDK，Ollama 為可選本地模型
- [2026-03-06] Setup Wizard 使用純 stdlib，不依賴 pip，支援既有專案偵測（CLAUDE.md + .claude/settings.json）
- [2026-03-06] **ECC v2 升級**：從 4 步線性流程升級為 8 Phase 文件驅動流程。新增：Phase 0 RECEIVE（需求規格 + 人工閘門）、Phase 1 ARCHITECT（架構設計 + 人工閘門）、Phase 5 QA（獨立 qa-reviewer agent，只讀 spec 不讀程式碼）、Phase 5b ITERATE（迴圈修復最多 3 輪）。文件模板在 docs/templates/，每個功能的文件在 docs/features/<name>/
- [2026-03-08] **ECC 熱更新**：新增「動態 HR 招募模組」與「異質多模型智囊團辯論」協議至 CLAUDE.md
- [2026-03-08] **HR 招募**：新增 generative-video-specialist.md（影片生成 + VRAM 安全）與 multimedia-pipeline-engineer.md（多媒體管線工程），roles/ 從 5 → 7 個角色
- [2026-03-08] **智囊團辯論結論（Singer VRAM）**：採用「GPU 時間分割 + 主動記憶體回收」策略。否決量化方案（Singer 不控制 SD 載入）與換模型方案（已是 FP16）。關鍵補丁：ComfyUI POST /free 卸載 + rembg session 釋放 + VRAM 監控。派工單 WO-20260308。

## 2026-03-08 動態 HR 招募：Multimedia-QA-Specialist
- **觸發原因**：CEO 驗收 Singer MV 發現三大品質問題（非人聲亂動、情緒斷層、品管缺失）
- **角色**：多媒體品管專家，負責影音管線自動化品質驗收
- **工具鏈**：MediaPipe + librosa + OpenCV + Silero VAD
- **設定檔**：`.claude/roles/multimedia-qa-specialist.md`
