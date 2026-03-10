# Singer V3.0 需求規格書
日期：2026-03-10
狀態：CEO 已確認

## 概述

Singer Agent V3.0 — LivePortrait + MuseTalk 混合管線。
在現有 V2.1 雙引擎（EDTalk + MuseTalk）基礎上，新增第三渲染引擎：
LivePortrait（表情動態）+ MuseTalk（嘴唇同步）串接管線。

## CEO 決策

- 方案 1：LivePortrait + MuseTalk 混合管線
- 版本號：V3.0（全新架構，大版本號）
- 情緒來源：先做全曲單一情緒（Qwen3 時間軸留後續版本）
- EDTalk (V2.0) 保留為降級方案

## PoC 驗證結果

| 引擎 | VRAM 峰值 | 解析度 | 推理速度 | 狀態 |
|------|----------|--------|---------|------|
| LivePortrait | 1,554 MB | 512x512 | 11.9s/78frames | PASS |
| MuseTalk V1.5 | 8,258 MB | 704x1216 | 143.8s/8s影片 | PASS |
| EDTalk (降級) | 2,381 MB | 256x256 | 11s/10s影片 | PASS |

VRAM 分時管控：max(1.5GB, 8.2GB) = 8.2GB < 12GB 紅線 ✅

## 功能需求

### FR-1：LivePortrait + MuseTalk 串接管線
- LivePortrait 先處理源圖，產生帶表情的中間影片/幀序列
- MuseTalk 再對中間產物進行嘴唇同步
- 兩個模型分時載入，不同時佔用 VRAM

### FR-2：表情控制（內建參數模式）
- 使用 LivePortrait 內建表情參數控制表情
- 支援參數：smile, blink, eyebrow, wink
- 全曲使用單一情緒設定（V3.0 scope）
- 情緒類型由 pipeline 傳入（如 sad/happy/neutral）

### FR-3：渲染引擎切換
- 新增 `SINGER_RENDERER=liveportrait_musetalk` 環境變數選項
- 保留現有引擎選項：`edtalk` (V2.0), `musetalk` (V2.1)
- 降級順序：liveportrait_musetalk → musetalk → edtalk

### FR-4：VRAM 分時管控
- LivePortrait 推理完成後，主動釋放 GPU 記憶體
- 確認 VRAM 已釋放後，再載入 MuseTalk
- 使用現有 vram_monitor.py 監控

## 非功能需求

### NFR-1：VRAM 安全
- 任何時刻 VRAM 使用不超過 10GB（留 2GB 系統）
- 12GB 為絕對紅線

### NFR-2：效能
- 總推理時間 < 原 MuseTalk 單獨推理時間的 2 倍
- 首次模型載入可接受較長時間（ONNX warmup）

### NFR-3：向後相容
- 不破壞現有 V2.0/V2.1 引擎的功能
- pipeline.py 的 render() 簽名不變

## 驗收標準（AC）

- AC-1：`SINGER_RENDERER=liveportrait_musetalk` 時，產生帶表情 + 嘴唇同步的影片
- AC-2：輸出影片的嘴唇動作與音訊同步（MuseTalk 品質）
- AC-3：輸出影片的表情符合指定情緒（如 smile 參數 > 0 時可見微笑）
- AC-4：VRAM 峰值不超過 10GB
- AC-5：切換回 edtalk 或 musetalk 渲染器時，功能正常不受影響
- AC-6：所有既有測試繼續通過

## 不做的事（Out of Scope）

- ❌ 時間軸情緒切換（每段歌曲不同情緒）— 留 V3.1
- ❌ LivePortrait 動物模型支援
- ❌ ComfyUI 整合
- ❌ 即時推理（real-time inference）
- ❌ 多人臉偵測
