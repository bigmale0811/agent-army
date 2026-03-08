# 🧠 Active Context
更新：2026-03-09 04:30

## 🚀 雙軌並行指令（CEO 2026-03-08 下達）

### 軌道一：V1.0 產線上線 ✅
- ✅ demucs 4.0.1 已安裝於 SadTalker venv
- ✅ mediapipe 已安裝於 Bot venv
- ✅ Singer Bot 已啟動（PID 8968/552）
- 🟢 **V1.0 管線已進入待命狀態，CEO 可隨時丟 MP3 測試**

### 軌道二：EDTalk PoC 概念驗證 ✅ PASS！
- ✅ git clone EDTalk → D:\Projects\EDTalk
- ✅ edtalk_env (Python 3.10.11) 建立完成
- ✅ PyTorch 2.10.0+cu128 Nightly（CUDA 12.8, sm_120 正確識別）
- ✅ 模型權重全部到位（EDTalk.pt 483MB, Audio2Lip.pt 10.8MB, 8個 .npy）
- ✅ 全部依賴安裝完成（含 dlib-bin, face-alignment, gfpgan）
- ✅ 兼容性 Patch 4 處（torch.load, moviepy, librosa, np.float）
- 🏆 **PoC 壓測結果：**
  - 表情：sad ✅ PASS
  - VRAM 峰值：**2,381 MB**（遠低於 12GB 紅線）
  - VRAM 增量：1,653 MB（僅 1.6GB，比 SadTalker 省 50%）
  - 執行時間：11 秒（10 秒影片）
  - 產出：res/poc_edtalk_output.mp4（256×256, 25fps, H.264+AAC）
  - 授權：Apache 2.0 ✅ 可商用

### 軌道二：EDTalk PoC 概念驗證 ⏳
- ✅ git clone EDTalk → D:\Projects\EDTalk
- ✅ edtalk_env (Python 3.10 venv) 建立完成
- ⚠️ PyTorch cu128 安裝中（RTX 5070 = sm_120，需 cu128 支援）
  - cu124 → sm_120 不兼容（UserWarning）
  - typing-extensions 衝突待解
- ⏳ 模型權重下載中（OpenXLab git lfs pull）
  - 需要：Audio2Lip.pt, EDTalk_lip_pose.pt, EDTalk.pt
  - 8 個情緒 .npy 權重已有
- ✅ poc_edtalk.py 撰寫完成（nvidia-smi VRAM 監控 thread）
- ⏳ 等 PyTorch + 模型 → 執行 PoC 壓測

## 目前進行中
- **WO-20260308-Singer-Quality-Fix**：✅ 全部完成！354 測試通過
  - ✅ DEV-1~3 + Pipeline + TDD 全部完成
  - ✅ demucs + mediapipe 已安裝
  - ⏳ DEV-4 情緒控制（EDTalk PoC 進行中）
  - Scout 探勘報告：docs/research/sadtalker-replacement-scout-2026-03-08.md
  - 首選：EDTalk（8種情緒標籤CLI）、備選：LivePortrait + MuseTalk 組合
- **R&D 研發部門成立**：
  - ✅ @Technology-Scout 角色建立（.claude/roles/technology-scout.md）
  - ✅ 技術碰壁協議寫入 CLAUDE.md
  - ✅ 決策記錄到 decisions.md
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
- ✅ Commit bb9428f + Push 完成（5 commits 一次推上 GitHub）
- ✅ run_singer_pipeline.py E2E 進入點（--audio/--image/--meta/--dry-run）
- ✅ test_inputs/ 目錄已建立，dry-run 驗證通過
- ⏳ 等 CEO 放入 MP3 + 角色圖片，準備實彈測試
