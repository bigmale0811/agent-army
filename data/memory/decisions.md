# 📋 決策紀錄

跨對話累積的重要決策，供未來參考。

- [2026-03-04] Singer Agent 使用 SadTalker 作為主要動畫引擎，FFmpeg 靜態模式作為降級方案
- [2026-03-04] 三個 Telegram Bot 各自獨立運作：Reading Bot、Japan Intel Bot、Singer Bot
- [2026-03-05] 建立 Memory System（跨對話記憶），存放在 data/memory/，CLAUDE.md 要求每次對話開頭先讀取
- [2026-03-06] **ECC 流程違規教訓**：開發 LLM 模組 + Setup Wizard 時跳過 Plan/TDD/Review/Verify，導致 5 個 bug 到使用者手上。未來所有開發必須嚴格遵循 Phase 0-7，即使使用者催促也不可省略
- [2026-03-06] 雲端 LLM 統一架構：OpenAI-compatible 用 `openai` SDK（切換 base_url），Gemini 用 `google-genai` SDK，Ollama 為可選本地模型
- [2026-03-06] Setup Wizard 使用純 stdlib，不依賴 pip，支援既有專案偵測（CLAUDE.md + .claude/settings.json）
- [2026-03-06] **ECC v2 升級**：從 4 步線性流程升級為 8 Phase 文件驅動流程。新增：Phase 0 RECEIVE（需求規格 + 人工閘門）、Phase 1 ARCHITECT（架構設計 + 人工閘門）、Phase 5 QA（獨立 qa-reviewer agent，只讀 spec 不讀程式碼）、Phase 5b ITERATE（迴圈修復最多 3 輪）。文件模板在 docs/templates/，每個功能的文件在 docs/features/<name>/
