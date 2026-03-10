# 🧠 Active Context
更新：2026-03-10 19:00

## 🚀 Singer V3.0 — Stage 5 審查完成，進入 Stage 6 遞迴驗證

### ✅ Stage 5 審查結果（2026-03-10）
- ✅ **測試**：62/62 全部通過（24.90s）
- ✅ **Python Code Review**：已修復所有問題
- ✅ **Security Review**：3 CRITICAL + 4 HIGH 全部修復
  - CRIT-02: exp_type 白名單驗證（`_sanitize_exp_type`）
  - CRIT-03: retarget 腳本路徑穿越防護（`_assert_safe_path`）
  - HIGH-01: YAML f-string → JSON 安全序列化
  - HIGH-02: SINGER_RENDERER / MUSETALK_VERSION 白名單
  - HIGH-03: 錯誤訊息不再洩漏內部路徑
  - HIGH-04: audio_path 副檔名 + 存在性驗證
  - Python: tempfile leak 修復、FFmpeg timeout 處理
- ✅ **QA Review**：測試計畫已產出（16 TC + 10 BC + 4 DG）
- ⚠️ CRIT-01（.env 密鑰曝光）為既有問題，建議輪換但不阻擋 V3.0
- 📋 5 個 MEDIUM + 3 個 LOW 問題已記錄，列入後續 hardening

### CEO 決策（2026-03-10）
- 方案 1：LivePortrait（表情動態）+ MuseTalk（嘴唇同步）
- 版本號：V3.0（全新架構）
- 情緒來源：先做全曲單一情緒，時間軸留後續
- EDTalk (V2.0) 保留為降級方案

### ✅ LivePortrait PoC 壓測 — PASS！(2026-03-10)
- ✅ git clone → D:\Projects\LivePortrait
- ✅ liveportrait_env (Python 3.10.11) + PyTorch 2.10.0+cu128
- ✅ 模型權重 18 檔案已下載（HuggingFace KlingTeam/LivePortrait）
- ✅ **PoC 壓測結果：**
  - **VRAM 峰值：1,554 MB (1.5GB)** — 極低，12GB 紅線的 13%
  - 推理時間：11.9 秒（78 frames, 3.1s 影片）
  - 輸出：512×512, 25fps
  - 首次載入 342 秒（ONNX warmup），後續快速
  - 產出：D:\Projects\LivePortrait\results\poc\s0--d0_concat.mp4
- ✅ 表情控制能力：內建 smile/blink/eyebrow/wink 參數，不需參考圖
- ✅ MIT 授權，17.9k stars

### VRAM 分時管控預算
| 元件 | VRAM | 時序 |
|------|------|------|
| LivePortrait | 1.5 GB | Stage 1: 表情動態 |
| MuseTalk | 8.2 GB | Stage 2: 嘴唇同步 |
| 合計（分時） | max = 8.2 GB | 安全空間 3.8 GB |

### 下一步
- ⏳ 等 CEO 確認 PoC 結果
- ⏳ 進入 FSM Stage 2（架構設計 + 開發計畫）
- ⏳ 設計 LivePortrait → MuseTalk 串接管線

### 部署狀態
- ✅ V2.0 Bot 已啟動（EDTalk 引擎）
- ✅ V2.1 MuseTalk 雙引擎整合完成
- 🟢 透過 `SINGER_RENDERER=musetalk` 環境變數切換

### ✅ MuseTalk Pipeline 整合 (2026-03-10)
- ✅ `config.py`: 新增 SINGER_RENDERER / MUSETALK_DIR / MUSETALK_PYTHON / MUSETALK_VERSION
- ✅ `video_renderer.py`: 新增 `_render_musetalk()` + 雙引擎分派
- ✅ `test_video_renderer.py`: 新增 11 個 MuseTalk 測試（共 35 測試全過）
- ✅ `pipeline.py`: 無需修改（render() 簽名不變）
- 🔑 切換方式：`set SINGER_RENDERER=musetalk` → 啟動 Bot

### ✅ 2026-03-09 清理完成
- ✅ Stock Analyzer 整個專案已從 repo 移除（commit `4ad6616`，-3477 行）
- ✅ git push 完成 (b1baef4..4ad6616 master → master)

### ✅ Singer V2.1 MuseTalk PoC — PASS！(2026-03-10)
- ✅ CUDA Toolkit 12.8 已安裝
- ✅ musetalk_env (Python 3.10) venv 建立完成
- ✅ PyTorch 2.10.0+cu128（CUDA 12.8, sm_120）
- ✅ **mmcv 2.1.0 + CUDA ops 編譯成功**（5 項 patch）
  - tensorview.h: std::vector overload 改 inline（sm_120 相容）
  - cudabind.cpp + pybind.cpp: #ifndef MMCV_EXCLUDE_SPCONV
  - setup.py: -DMMCV_EXCLUDE_SPCONV 編譯旗標
  - mmcv/ops/__init__.py: try/except 包裹 sparse_conv import
  - mmdet/__init__.py: mmcv 版本上限放寬至 < 2.2.0
  - mmengine checkpoint.py + MuseTalk 6 處: torch.load weights_only=False
- ✅ 模型權重全部到位（V1.5 unet 3.2GB + V1.0 3.2GB + sd-vae + whisper + dwpose + face-parse）
- ✅ PoC 壓測結果：
  - **VRAM 峰值：8,258 MB**（安全，離 12GB 紅線還有 ~4GB）
  - VRAM 增量：7,385 MB
  - 執行時間：143.8 秒（8 秒影片）
  - **輸出解析度：704×1216**（EDTalk 僅 256×256）
  - 推理速度：~9 it/s
  - 產出：D:\Projects\MuseTalk\results\poc\v15\yongen_yongen.mp4
- ⚠️ Windows 卡死 Bug（Issue #40）尚未驗證是否影響長影片
- ⚠️ 與 ComfyUI 並行需 VRAM 時間分割（MuseTalk 7.4GB + SDXL 7-8GB > 12GB）
- ⏳ 待 CEO 決定：是否用 MuseTalk 取代 EDTalk 作為 V2.1 渲染引擎

### 📦 2026-03-09 全面清理完成
- ✅ .gitignore 更新：排除執行時資料 + 外部依賴（4 大類）
- ✅ Stock Analyzer commit：Telegram 通知 + PDF 生成 + 編碼修復
- ✅ Singer V2.1 文件 commit：emotion dynamics 規劃 + EDTalk 探勘報告 + PoC
- ✅ 記憶檔案 commit：active_context + decisions + compaction-log
- ✅ git push 成功（4 commits 一次推上 GitHub）
- 🟢 **工作目錄乾淨，所有待處理項目已清空**

### V2.0 EDTalk 整合完成 ✅
- ✅ video_renderer.py 完整重寫：SadTalker → EDTalk subprocess
- ✅ audio_preprocessor.py: EMOTION_EDTALK_MAP (70+ 關鍵字 → 8 種情緒)
- ✅ config.py: EDTalk 路徑常數 (EDTALK_DIR/PYTHON/DEMO_SCRIPT/POSE_VIDEO)
- ✅ pipeline.py: Step 8 改用 mood_to_exp_type() + EDTalk
- ✅ test_video_renderer.py: 完整重寫 EDTalk 測試
- ✅ **962 tests passed, 0 failed** (31.41s)
- ✅ Commit `1e3abb1` 已提交
- 🏆 VRAM 峰值 2.4GB（比 SadTalker 省 50%+）
- 🏆 8 種原生情緒支援：sad/happy/angry/surprised/fear/disgusted/contempt/neutral

### V1.0 → V2.0 升級摘要
| 項目 | V1.0 (SadTalker) | V2.0 (EDTalk) |
|------|-----------------|---------------|
| VRAM | 4-5GB | 2.4GB |
| 情緒 | expression_scale 0.3-1.2 | 8 種原生標籤 |
| 穩定性 | Popen + polling（卡 cleanup） | subprocess.run（乾淨退出） |
| 授權 | 非商用限制 | Apache 2.0 |

### 軌道一：V1.0 產線 (已被 V2.0 取代)
- ✅ demucs 4.0.1 已安裝於 SadTalker venv
- ✅ mediapipe 已安裝於 Bot venv
- ✅ V1.0 品質防線保留：Demucs + noise gate + MediaPipe QA

### EDTalk PoC 概念驗證 ✅ PASS！
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

## 待處理
- ⏳ vendor prompts 中文化（6 個檔案）— 尚未開始
- ⏳ trader prompt 結構化輸出（跨週金股風格）— 尚未開始
- ⚠️ 結構化格式需重跑分析才生效

## 最近完成
- ✅ Singer Agent 全部 14 DEV 項目（283 測試，94% 覆蓋率）
- ✅ Telegram Bot 整合 + PDF 報告 + 中文化 prompt
- ✅ run_analysis.py Bug 修復 + Code Review
- ✅ WO-001 Stock Analyzer Bug 修復
- ✅ FSM 狀態機 + Kanban 派工系統

## Git 狀態
- ✅ master 與 origin/master 同步（b1baef4）
- ✅ 工作目錄乾淨，無未提交修改

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
