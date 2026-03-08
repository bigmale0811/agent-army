# 🧠 Active Context
更新：2026-03-07 19:46

## 目前進行中
- **SadTalker 掛起修復**：改用 Popen + 輪詢策略
  - 根因：SadTalker process 產出 mp4 後卡在 cleanup（os.system ffmpeg / seamlessClone / shutil.rmtree）
  - 修復：video_renderer.py 改用 Popen + _poll_for_mp4 偵測產出 + _terminate_process 強制結束
  - 新增 `--verbose` flag 跳過 shutil.rmtree
  - 測試：18/18 通過（從 9 個增加到 18 個）
  - Singer Bot 已重啟，等待使用者透過 Telegram 發送 MP3 進行實測
- **Singer Agent 全部 14 個 DEV 項目已完成** 🎉
  - DEV-1 ~ DEV-14 全部完成、測試通過、Code Review 修復完畢
  - 283 測試，94% 覆蓋率
  - 5 個 commits：Batch A → B → C → D → E

## Singer Agent 完成摘要

| 批次 | DEV 項目 | Commit | 測試數 |
|------|---------|--------|-------|
| Batch A | DEV-1 models, DEV-2 config | `cd6096c` | 116 |
| Batch B | DEV-3 path_utils, DEV-4 ollama, DEV-5 project_store | `49e12cf` | 156 |
| Batch C | DEV-6 researcher, DEV-7 copywriter, DEV-8 background_gen, DEV-9 compositor, DEV-10 precheck, DEV-11 video_renderer | `b278f44` | 240 |
| Batch D | DEV-12 pipeline | `ba3149c` | 251 |
| Batch E | DEV-13 cli + __main__, DEV-14 bot | `843386b` | 283 |

### Code Review 修復歷史
- Batch B: 路徑穿越防護、完整例外處理、logging
- Batch E: 路徑穿越(bot)、config 驗證、coroutine 修復、錯誤洩漏、副檔名白名單

## 待處理（Stock Analyzer，未 commit）
1. `scripts/run_analysis.py` — Telegram 通知 + PDF 生成 + log 修復
2. `src/stock_analyzer/utils/pdf_report.py` — PDF 報告生成器（新增）
3. vendor prompts 中文化（6 個檔案）
4. trader prompt 結構化輸出（跨週金股風格）
5. ⚠️ 結構化格式需重跑分析才生效

## 最近完成
- ✅ Singer Agent 全部 14 DEV 項目（283 測試，94% 覆蓋率）
- ✅ Telegram Bot 整合 + PDF 報告 + 中文化 prompt
- ✅ run_analysis.py Bug 修復 + Code Review
- ✅ WO-001 Stock Analyzer Bug 修復
- ✅ FSM 狀態機 + Kanban 派工系統

## Git 狀態
- master 領先 origin/master 多個 commits（未 push）
- Stock Analyzer 相關檔案仍有未提交修改（run_analysis.py, pdf_report.py）

## 🖥️ 硬體火力與絕對限制
- **顯示卡**：GFX 5070 12GB VRAM
- **系統記憶體**：64GB RAM
- **⚠️ 最高指導原則**：任何涉及影像生成或 SadTalker 的任務，必須嚴格控管在 12GB VRAM 內，嚴防 OOM
- **模型武器庫**：
  - 雲端：Claude Opus 4.6 / Sonnet 4.5 / Haiku 4.5
  - 本地：Ollama + Qwen3 14B (localhost:11434)

## ⚡ 最近壓縮事件
- [2026-03-07 19:39:13] Context 被自動壓縮，以上內容是壓縮前的狀態
- **請重新讀取此檔案確認進度**

## 🔄 2026-03-08 ECC 熱更新
- ✅ 硬體火力寫入 active_context.md（GFX 5070 12GB / 64GB RAM）
- ✅ 動態 HR 招募模組寫入 CLAUDE.md
- ✅ 智囊團辯論協議寫入 CLAUDE.md
- ✅ HR 招募：generative-video-specialist.md + multimedia-pipeline-engineer.md
- ✅ 智囊團辯論完成（Qwen3 提案 → Sonnet 攻擊 → Opus 裁決）
- ✅ 派工單產出：WO-20260308-Singer-VRAM-Optimization.md（4 個 DEV 項目）
- ✅ VRAM 優化開發完成！4 個 DEV 全部通過（323 測試，88% 覆蓋率）
  - DEV-1: background_gen.py → POST /free 卸載 SDXL
  - DEV-2: compositor.py → rembg 後 gc + empty_cache
  - DEV-3: vram_monitor.py（新模組）+ pipeline.py 監控
  - DEV-4: video_renderer.py → _pre_launch_cleanup
- ⏳ 待 CEO 確認是否 commit + push
