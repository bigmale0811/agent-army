# 測試計畫 — Singer V3.0 LivePortrait + MuseTalk 混合管線

> 本文件由 Phase 5: QA 的 qa-reviewer agent 產出。
> **規則：只讀 `01_spec.md` 的驗收標準，不讀實作程式碼。**
> 輸入：`01_spec.md`（驗收標準）
> 建立日期：2026-03-10

---

## 基本資訊

| 欄位 | 內容 |
|------|------|
| 功能名稱 | Singer V3.0 — LivePortrait + MuseTalk 混合管線 |
| QA 負責人 | qa-reviewer agent |
| 建立日期 | 2026-03-10 |
| 版本 | V3.0 |

---

## 測試範圍

| 驗收標準 | 說明 | 測試類型 | 測試案例數 |
|---------|------|---------|-----------|
| AC-1 | liveportrait_musetalk 渲染器產出帶表情+嘴唇同步影片 | E2E 整合測試 | 2 |
| AC-2 | 輸出影片嘴唇動作與音訊同步（MuseTalk 品質） | E2E + 視覺驗證 | 2 |
| AC-3 | 輸出影片表情符合指定情緒 | E2E + 視覺驗證 | 3 |
| AC-4 | VRAM 峰值不超過 10GB | 效能監控測試 | 2 |
| AC-5 | 切回 edtalk/musetalk 引擎時功能正常 | 回歸測試 | 3 |
| AC-6 | 所有既有測試繼續通過 | 回歸測試 | 1 |
| FR-3 | 環境變數引擎切換機制 | 單元/整合測試 | 3 |
| FR-4 | VRAM 分時管控（LivePortrait 完成後釋放再載入 MuseTalk） | 行為驗證測試 | 2 |
| NFR-3 | 向後相容性（render() 簽名不變） | 介面測試 | 1 |

---

## 測試案例

### TC-1: liveportrait_musetalk 渲染器正常啟動並產出影片

| 欄位 | 內容 |
|------|------|
| 對應 | AC-1 |
| 前置條件 | 環境變數 `SINGER_RENDERER=liveportrait_musetalk` 已設定；提供有效的音訊檔（wav/mp3）與源圖（jpg/png）；GPU 可用且 VRAM >= 10GB |
| 步驟 | 1. 設定 `SINGER_RENDERER=liveportrait_musetalk`<br>2. 以有效音訊與源圖呼叫 pipeline.render()<br>3. 等待管線執行完成<br>4. 檢查輸出目錄 |
| 預期結果 | 輸出目錄存在一個有效的影片檔案（.mp4 或規格定義格式）；檔案大小 > 0 bytes；影片時長與音訊時長一致（誤差 ±0.5 秒）|
| 通過標準 | 影片檔案存在且可播放；無 Python traceback；exit code == 0 |

---

### TC-2: liveportrait_musetalk 輸出影片包含人臉動態

| 欄位 | 內容 |
|------|------|
| 對應 | AC-1 |
| 前置條件 | 同 TC-1 |
| 步驟 | 1. 以 `liveportrait_musetalk` 渲染器產出影片<br>2. 對輸出影片進行幀間差異分析（或目視檢查） |
| 預期結果 | 影片中人臉有動態變化（非靜態圖片）；至少有嘴唇區域的動態（非全幀靜止） |
| 通過標準 | 影片幀間差異 > 閾值（可設定）；人臉區域有明顯動態 |

---

### TC-3: MuseTalk 嘴唇同步與音訊對齊

| 欄位 | 內容 |
|------|------|
| 對應 | AC-2 |
| 前置條件 | 準備包含清晰語音的測試音訊（中文或英文）；源圖為正面人臉照片 |
| 步驟 | 1. 以 `liveportrait_musetalk` 渲染器產出影片<br>2. 播放輸出影片，觀察嘴唇開合時機<br>3. 對照音訊波形與嘴唇動作時間點 |
| 預期結果 | 嘴唇開合時機與音訊的有聲/無聲段落對應；可感知嘴唇動作與語音同步（觀察者主觀可感知） |
| 通過標準 | 嘴唇動作與音訊同步誤差在視覺可接受範圍內（≤ 1 幀 @ 25fps = 40ms）|

---

### TC-4: MuseTalk 嘴唇品質對比基準

| 欄位 | 內容 |
|------|------|
| 對應 | AC-2 |
| 前置條件 | 相同音訊與源圖分別以 `musetalk`（V2.1）和 `liveportrait_musetalk`（V3.0）渲染 |
| 步驟 | 1. 以 `SINGER_RENDERER=musetalk` 產出基準影片<br>2. 以 `SINGER_RENDERER=liveportrait_musetalk` 產出 V3 影片<br>3. 對比兩個影片的嘴唇同步品質 |
| 預期結果 | V3.0 嘴唇同步品質不劣於 V2.1（MuseTalk standalone）；主觀評分差異不超過可接受範圍 |
| 通過標準 | 兩影片嘴唇同步效果在肉眼觀察下無明顯退化 |

---

### TC-5: smile 情緒參數產生可見微笑

| 欄位 | 內容 |
|------|------|
| 對應 | AC-3 |
| 前置條件 | smile 參數設為 > 0（例如 0.5 或 1.0）；使用中性表情的源圖 |
| 步驟 | 1. 設定情緒為 happy（或直接設定 smile > 0）<br>2. 呼叫 `liveportrait_musetalk` 渲染器產出影片<br>3. 目視檢查輸出影片的臉部表情 |
| 預期結果 | 輸出影片中人臉可觀察到微笑表情（嘴角上揚）；與源圖中性表情有明顯差異 |
| 通過標準 | 目視確認有微笑表情；smile 參數 = 0 時無微笑（對照組驗證） |

---

### TC-6: neutral 情緒設定無額外表情

| 欄位 | 內容 |
|------|------|
| 對應 | AC-3 |
| 前置條件 | 情緒設定為 neutral；使用中性表情源圖 |
| 步驟 | 1. 設定情緒為 neutral<br>2. 呼叫 `liveportrait_musetalk` 渲染器<br>3. 目視檢查輸出影片 |
| 預期結果 | 輸出影片表情接近源圖；無額外誇張表情出現 |
| 通過標準 | 表情與源圖相近；無非預期的大幅表情變化 |

---

### TC-7: sad 情緒設定產生對應表情

| 欄位 | 內容 |
|------|------|
| 對應 | AC-3 |
| 前置條件 | 情緒設定為 sad；使用中性表情源圖 |
| 步驟 | 1. 設定情緒為 sad<br>2. 呼叫 `liveportrait_musetalk` 渲染器<br>3. 目視檢查輸出影片的臉部表情 |
| 預期結果 | 輸出影片中人臉表情呈現悲傷/憂愁（眉毛下垂、嘴角略下）；與 happy 情緒輸出有明顯差異 |
| 通過標準 | 目視可分辨 sad 與 happy 情緒的輸出差異 |

---

### TC-8: 完整管線 VRAM 峰值不超過 10GB

| 欄位 | 內容 |
|------|------|
| 對應 | AC-4 |
| 前置條件 | GPU 監控工具可用（vram_monitor.py 或 nvidia-smi）；`SINGER_RENDERER=liveportrait_musetalk` |
| 步驟 | 1. 啟動 VRAM 監控（每秒取樣一次）<br>2. 執行完整 liveportrait_musetalk 管線（從頭到尾）<br>3. 收集整個管線執行期間的 VRAM 峰值<br>4. 管線完成後讀取峰值記錄 |
| 預期結果 | 整個管線執行期間，GPU VRAM 使用量的最大值 < 10,240 MB（10GB） |
| 通過標準 | `max(vram_samples)` < 10,240 MB；12GB 從未被觸及 |

---

### TC-9: LivePortrait 推理後 VRAM 釋放

| 欄位 | 內容 |
|------|------|
| 對應 | AC-4、FR-4 |
| 前置條件 | GPU 監控工具可用；`SINGER_RENDERER=liveportrait_musetalk` |
| 步驟 | 1. 啟動高頻率 VRAM 監控（每 0.5 秒取樣）<br>2. 執行完整管線<br>3. 分析 VRAM 曲線：找出 LivePortrait 階段結束後的 VRAM 下降點<br>4. 確認下降後才出現 MuseTalk 的 VRAM 上升 |
| 預期結果 | VRAM 曲線顯示兩個獨立的峰值（非同時峰值）；第一峰值（LivePortrait ~1.5GB）結束後 VRAM 回落；第二峰值（MuseTalk ~8.2GB）才出現 |
| 通過標準 | VRAM 時序圖顯示分時使用，兩個峰值不重疊 |

---

### TC-10: 切換至 edtalk 引擎功能正常

| 欄位 | 內容 |
|------|------|
| 對應 | AC-5 |
| 前置條件 | 環境變數 `SINGER_RENDERER=edtalk`；提供有效音訊與源圖 |
| 步驟 | 1. 設定 `SINGER_RENDERER=edtalk`<br>2. 呼叫 pipeline.render() 執行渲染<br>3. 檢查輸出影片 |
| 預期結果 | EDTalk 渲染器正常產出影片；輸出格式與 V2.0 相同；無錯誤訊息 |
| 通過標準 | 輸出影片存在且可播放；exit code == 0；無 Python traceback |

---

### TC-11: 切換至 musetalk 引擎功能正常

| 欄位 | 內容 |
|------|------|
| 對應 | AC-5 |
| 前置條件 | 環境變數 `SINGER_RENDERER=musetalk`；提供有效音訊與源圖 |
| 步驟 | 1. 設定 `SINGER_RENDERER=musetalk`<br>2. 呼叫 pipeline.render() 執行渲染<br>3. 檢查輸出影片 |
| 預期結果 | MuseTalk 渲染器（V2.1）正常產出影片；與 V3.0 導入前的行為一致 |
| 通過標準 | 輸出影片存在且可播放；exit code == 0；無 Python traceback |

---

### TC-12: 三個引擎均可在同一環境切換

| 欄位 | 內容 |
|------|------|
| 對應 | AC-5、FR-3 |
| 前置條件 | 三個引擎（liveportrait_musetalk、musetalk、edtalk）均已安裝 |
| 步驟 | 1. 依序設定並執行三個渲染引擎<br>2. 每次執行使用相同音訊與源圖<br>3. 確認三次均能正常完成 |
| 預期結果 | 三個渲染器均能獨立正常運作；每次切換不需要重啟服務或清除快取 |
| 通過標準 | 三次執行均 exit code == 0；各自產出有效影片 |

---

### TC-13: 所有既有測試通過（回歸測試）

| 欄位 | 內容 |
|------|------|
| 對應 | AC-6 |
| 前置條件 | Singer Agent 完整測試套件可執行 |
| 步驟 | 1. 執行 `python -m pytest tests/singer_agent/ -v`<br>2. 記錄所有測試結果 |
| 預期結果 | 所有 V2.0/V2.1 既有測試均通過；無新增的 FAIL 或 ERROR；通過率 100% |
| 通過標準 | pytest 輸出無 FAILED 或 ERROR；`X passed` 數量與導入 V3.0 前相同 |

---

### TC-14: render() 方法簽名向後相容

| 欄位 | 內容 |
|------|------|
| 對應 | NFR-3 |
| 前置條件 | 可讀取 pipeline.py 的公開介面（CLI --help 或 API 文件）；不讀實作碼 |
| 步驟 | 1. 查詢 pipeline.render() 的參數簽名（透過 `--help` 或文件）<br>2. 對比 V2.1 的已知簽名<br>3. 確認必要參數未改變 |
| 預期結果 | render() 函式接受與 V2.1 相同的參數；新增 renderer 類型不破壞原有呼叫方式 |
| 通過標準 | 以 V2.1 的呼叫方式（不指定新引擎）執行不報錯；既有呼叫端程式碼無需修改 |

---

### TC-15: SINGER_RENDERER 環境變數未設定時的預設行為

| 欄位 | 內容 |
|------|------|
| 對應 | FR-3 |
| 前置條件 | 未設定 `SINGER_RENDERER` 環境變數 |
| 步驟 | 1. 清除 `SINGER_RENDERER` 環境變數<br>2. 呼叫 pipeline.render()<br>3. 觀察使用哪個渲染器 |
| 預期結果 | 系統有明確的預設渲染器（非崩潰）；行為與文件一致 |
| 通過標準 | 無 KeyError 或環境變數缺失導致的錯誤；正常產出影片 |

---

### TC-16: 效能基準 — 總推理時間 < MuseTalk 單獨時間的 2 倍

| 欄位 | 內容 |
|------|------|
| 對應 | NFR-2 |
| 前置條件 | 8 秒測試影片的測試音訊與源圖；可測量執行時間 |
| 步驟 | 1. 測量 `musetalk` 單獨渲染 8 秒影片的時間（基準：~143.8 秒）<br>2. 測量 `liveportrait_musetalk` 渲染相同素材的時間<br>3. 計算比值 |
| 預期結果 | liveportrait_musetalk 總時間 < musetalk 單獨時間 × 2（即 < ~287.6 秒）|
| 通過標準 | 時間比值 < 2.0；若超過則記錄為 MEDIUM 效能問題 |

---

## 邊界條件測試

| # | 情境 | 預期行為 | 對應 spec 條件 |
|---|------|---------|---------------|
| BC-1 | VRAM 在 LivePortrait 完成後未完全釋放 | MuseTalk 應等待或拋出可識別的 OOM 錯誤，不可靜默崩潰 | NFR-1、FR-4 |
| BC-2 | 源圖不含人臉（純風景照）| 管線應拋出有意義的錯誤訊息，exit code != 0，不閃退 | AC-1 |
| BC-3 | 音訊為空檔案（0 秒）| 管線應拋出有意義的錯誤，不產出無效影片 | AC-1、AC-2 |
| BC-4 | 情緒參數值超出合理範圍（如 smile=999）| 管線應夾限（clamp）至最大值或拋出參數驗證錯誤 | AC-3、FR-2 |
| BC-5 | 指定 liveportrait_musetalk 但 LivePortrait 模型不存在 | 管線應嘗試降級至 musetalk，降級失敗再降至 edtalk（按 FR-3 降級順序）| FR-3 |
| BC-6 | 指定 liveportrait_musetalk 但 MuseTalk 模型不存在 | 管線應嘗試降級（不應無限等待）；降級行為需記錄日誌 | FR-3 |
| BC-7 | 高解析度源圖（4K 以上）| 不應 OOM；自動縮放或拋出清晰的解析度限制錯誤 | NFR-1 |
| BC-8 | 極短音訊（< 1 秒）| 不崩潰；產出極短影片或拋出最小時長限制錯誤 | AC-1 |
| BC-9 | 同時執行兩個渲染器（並行呼叫）| VRAM 不超過 12GB（絕對紅線）；或有排隊機制避免並行 | NFR-1 |
| BC-10 | 引擎降級時的日誌可視性 | 降級事件必須在日誌中明確記錄（如 WARN 級別）| FR-3 |

---

## 降級場景測試

| # | 情境 | 降級路徑 | 預期行為 |
|---|------|---------|---------|
| DG-1 | liveportrait_musetalk 失敗 | → musetalk（V2.1）| 自動降級，產出影片，日誌記錄降級原因 |
| DG-2 | musetalk 亦失敗 | → edtalk（V2.0）| 再次降級，產出影片，日誌記錄兩次降級 |
| DG-3 | 所有引擎均失敗 | 無可用引擎 | 管線拋出清晰的最終錯誤，不靜默失敗 |
| DG-4 | 手動指定 edtalk，V3 不影響其行為 | 直接使用 edtalk | EDTalk 的輸出與 V3.0 導入前完全相同 |

---

## 測試環境需求

| 項目 | 要求 |
|------|------|
| OS | Windows 10（目標環境），Linux 相容 |
| Python | 3.12.8 |
| GPU | NVIDIA GFX 5070，12GB VRAM |
| CUDA | 需與 LivePortrait 和 MuseTalk 相容的版本 |
| 磁碟空間 | 至少 20GB 可用空間（模型 + 暫存影片）|
| 測試音訊 | 8 秒 WAV 或 MP3，包含清晰語音 |
| 測試源圖 | 正面人臉 JPG/PNG，解析度 512x512 以上 |
| 監控工具 | nvidia-smi 或 vram_monitor.py 可執行 |
| 網路 | 首次模型下載需要；測試本身不依賴網路 |

---

## 自動化方式

### E2E 測試腳本

```python
# 路徑：tests/test_singer_v3/test_qa_liveportrait_musetalk.py
import subprocess, sys, os, time

def test_ac1_liveportrait_musetalk_produces_video():
    """AC-1: SINGER_RENDERER=liveportrait_musetalk 時產生影片"""
    env = {**os.environ, "SINGER_RENDERER": "liveportrait_musetalk"}
    result = subprocess.run(
        [sys.executable, "src/singer_agent/pipeline.py",
         "--audio", "tests/fixtures/test_audio_8s.wav",
         "--image", "tests/fixtures/test_face.jpg",
         "--output", "tests/output/tc1_output.mp4"],
        capture_output=True, text=True, timeout=600,
        encoding="utf-8", errors="replace", env=env,
    )
    assert result.returncode == 0, f"Pipeline failed: {result.stderr}"
    assert os.path.exists("tests/output/tc1_output.mp4"), "Output video not found"

def test_ac5_edtalk_unaffected():
    """AC-5: 切換回 edtalk 時功能正常"""
    env = {**os.environ, "SINGER_RENDERER": "edtalk"}
    result = subprocess.run(
        [sys.executable, "src/singer_agent/pipeline.py",
         "--audio", "tests/fixtures/test_audio_8s.wav",
         "--image", "tests/fixtures/test_face.jpg",
         "--output", "tests/output/tc10_output.mp4"],
        capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace", env=env,
    )
    assert result.returncode == 0, f"EDTalk regression: {result.stderr}"

def test_ac6_existing_tests_pass():
    """AC-6: 所有既有測試通過"""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/singer_agent/", "-v", "--tb=short"],
        capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"Regression tests failed:\n{result.stdout}"
    assert "FAILED" not in result.stdout, "Some tests FAILED"
```

### VRAM 監控測試

```python
def test_ac4_vram_under_10gb():
    """AC-4: VRAM 峰值不超過 10GB"""
    # 啟動 VRAM 監控背景程序
    monitor = subprocess.Popen(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits",
         "-l", "1", "--filename=tests/output/vram_log.txt"],
    )
    try:
        # 執行管線
        env = {**os.environ, "SINGER_RENDERER": "liveportrait_musetalk"}
        subprocess.run([sys.executable, "src/singer_agent/pipeline.py", ...],
                       timeout=600, env=env)
    finally:
        monitor.terminate()

    # 分析 VRAM 記錄
    with open("tests/output/vram_log.txt") as f:
        samples = [int(line.strip()) for line in f if line.strip().isdigit()]
    peak_vram_mb = max(samples)
    assert peak_vram_mb < 10240, f"VRAM peak {peak_vram_mb}MB exceeded 10GB limit"
```

---

## 測試執行指令

```bash
# 執行全部 QA 測試
python -m pytest tests/test_singer_v3/test_qa_liveportrait_musetalk.py -v --tb=short

# 執行特定 AC 測試
python -m pytest tests/test_singer_v3/ -k "ac1 or ac2" -v

# 執行回歸測試
python -m pytest tests/singer_agent/ -v --tb=short

# 執行邊界條件測試
python -m pytest tests/test_singer_v3/ -k "bc" -v
```
