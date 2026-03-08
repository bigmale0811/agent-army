# WO-20260308: Singer VRAM Optimization（GPU 時間分割 + 主動記憶體回收）

## 狀態：[DONE]
## 優先級：HIGH
## 建立日期：2026-03-08
## 來源：智囊團辯論（Qwen3 提案 → Sonnet 攻擊 → Opus 裁決）

---

## 背景

Singer Agent 管線在 12GB VRAM (GFX 5070) 環境下存在 OOM 風險：
- ComfyUI server 常駐 SDXL checkpoint (~7-8GB VRAM)
- SadTalker subprocess 需要 ~4-5GB VRAM
- rembg (U²-Net) 在 Singer 進程內不釋放 (~170MB+)
- 三者 VRAM 疊加 = 爆炸 💥

## 智囊團辯論結論

| 方案 | 裁決 | 原因 |
|------|------|------|
| 方案一：模型量化 | ❌ 否決 | Singer 不控制 SD 模型載入，量化需在 ComfyUI 側配置，控制權不在我方 |
| 方案二：序列化獨佔 | ✅ 採用（修正版） | 架構正確，但需補 3 個 VRAM 釋放補丁 |
| 方案三：換輕量模型 | ❌ 否決 | 已是 FP16，換 SD1.5 會打爛 SDXL workflow 節點定義 |

## 修正版方案：GPU 時間分割 + 主動記憶體回收

### 核心原則
管線已序列化 → 確保每階段結束後主動釋放 VRAM → 下一階段獨佔 GPU

### VRAM 時間線（修正後）
```
Step 1-3: Ollama (CPU/少量 VRAM) ........... ~2GB
Step 4:   ComfyUI SDXL 生圖 ................ ~7-8GB (峰值)
          ↓ POST /free 卸載模型
Step 5a:  rembg 去背 ....................... ~1GB
          ↓ torch.cuda.empty_cache()
Step 5b:  Composite (PIL, CPU only) ........ ~0GB
Step 7:   SadTalker 渲染 ................... ~4-5GB (峰值)
          ↓ subprocess 結束自動釋放
```
**修正後峰值：~7-8GB（Step 4），安全餘量 4-5GB** ✅

---

## 任務執行日誌

### DEV-1: ComfyUI 模型卸載機制
- [x] Planner 規劃
- [x] Architect 設計
- [x] TDD 開發
- [x] Code Review
- [x] 測試通過

**描述**：在 `background_gen.py` 的 `generate()` 完成後，呼叫 ComfyUI REST API `POST /free` (`{"unload_models": true}`) 強制卸載 SDXL checkpoint。

**修改檔案**：`src/singer_agent/background_gen.py`

**驗收標準**：
- AC-1: Step 4 完成後，ComfyUI VRAM 使用降至 <500MB
- AC-2: 卸載失敗時 log warning 但不中斷管線（graceful degradation）
- AC-3: 有對應單元測試（mock REST API）

---

### DEV-2: rembg 模型釋放機制
- [x] Planner 規劃
- [x] Architect 設計
- [x] TDD 開發
- [x] Code Review
- [x] 測試通過

**描述**：在 `compositor.py` 的 `remove_background()` 執行後，釋放 rembg session 並呼叫 `torch.cuda.empty_cache()`。

**修改檔案**：`src/singer_agent/compositor.py`

**驗收標準**：
- AC-1: rembg 執行後 VRAM 增量 <50MB
- AC-2: 使用 `rembg.new_session()` 管理生命週期，用完即棄
- AC-3: 有對應單元測試

---

### DEV-3: Pipeline VRAM 監控與 OOM 防護
- [x] Planner 規劃
- [x] Architect 設計
- [x] TDD 開發
- [x] Code Review
- [x] 測試通過

**描述**：在 `pipeline.py` 每個 GPU 密集步驟前後加入 VRAM 監控 log，並在 VRAM >10GB 時觸發 warning。

**修改檔案**：`src/singer_agent/pipeline.py`（新增 `src/singer_agent/vram_monitor.py`）

**驗收標準**：
- AC-1: 每個 GPU 步驟前後 log 顯示 VRAM 使用量
- AC-2: VRAM >10GB 時 log WARNING 並嘗試 `torch.cuda.empty_cache()`
- AC-3: VRAM >11.5GB 時 log CRITICAL 並暫停管線等待釋放（5 秒 timeout）
- AC-4: 有對應單元測試（mock torch.cuda）

---

### DEV-4: SadTalker 前置 VRAM 清理
- [x] Planner 規劃
- [x] Architect 設計
- [x] TDD 開發
- [x] Code Review
- [x] 測試通過

**描述**：在 `video_renderer.py` 啟動 SadTalker subprocess 前，確保所有其他 GPU 模型已卸載。

**修改檔案**：`src/singer_agent/video_renderer.py`

**驗收標準**：
- AC-1: SadTalker 啟動前 VRAM <2GB
- AC-2: 如果 VRAM >4GB，先執行 emergency cleanup（ComfyUI /free + gc.collect + empty_cache）
- AC-3: 有對應單元測試

---

## 專家角色需求
- `generative-video-specialist.md` — VRAM 安全審查
- `multimedia-pipeline-engineer.md` — 管線完整性審查
- `developer.md` — TDD 開發
- `reviewer.md` — Code Review

## 風險評估
| 風險 | 等級 | 緩解措施 |
|------|------|---------|
| ComfyUI `/free` API 不存在或行為不同 | MEDIUM | 先手動測試 API，準備 fallback（重啟 ComfyUI server） |
| rembg 不使用 CUDA（純 CPU） | LOW | 偵測 backend，若 CPU 則跳過 empty_cache |
| SadTalker VRAM 超過預估 | MEDIUM | 加入 `--size 256` 參數限制解析度作為 fallback |
