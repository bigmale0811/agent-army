# Singer V3.0 架構設計文件
日期：2026-03-10
狀態：待 CEO 審查
版本：V3.0 — LivePortrait + MuseTalk 混合管線

## 1. 架構概覽

### 1.1 設計理念

V3.0 的核心思路是「分時串接」（Time-Division Sequential Pipeline）：

1. **LivePortrait** 負責「表情注入」— 讀取源圖，根據情緒參數操控 delta_new keypoint，產出帶表情的中間靜態圖（PNG）。
2. **MuseTalk** 負責「嘴唇同步」— 以 LivePortrait 的產出幀作為輸入源圖，結合音訊驅動嘴唇動作，產出最終影片。
3. 兩個模型**絕不同時佔用 GPU**，以 subprocess 隔離 + VRAM 閘門機制確保 VRAM 安全。

### 1.2 高層架構圖

```
Pipeline Step 8（video_renderer.render()）
│
├─ renderer == "edtalk"                → _render_edtalk()          [V2.0 保留]
├─ renderer == "musetalk"              → _render_musetalk()        [V2.1 保留]
└─ renderer == "liveportrait_musetalk" → _render_liveportrait_musetalk()  [V3.0 新增]
                                            │
                                            ├─ Phase A: LivePortrait 表情注入
                                            │   ├─ 1. _pre_launch_cleanup()（VRAM 清理）
                                            │   ├─ 2. 建構 expression_params（情緒 → delta_new 偏移）
                                            │   ├─ 3. subprocess 呼叫 LivePortrait retarget 腳本
                                            │   ├─ 4. 產出：帶表情的靜態圖（PNG, 512x512）
                                            │   └─ 5. 確認 subprocess 結束 → VRAM 已釋放
                                            │
                                            ├─ VRAM 閘門：force_cleanup() + check_vram_safety()
                                            │
                                            └─ Phase B: MuseTalk 嘴唇同步
                                                ├─ 1. _pre_launch_cleanup()（二次清理確認）
                                                ├─ 2. 以 LivePortrait 產出作為 MuseTalk 源圖輸入
                                                ├─ 3. subprocess 呼叫 MuseTalk inference
                                                ├─ 4. 產出：最終影片（MP4）
                                                └─ 5. 清理暫存檔案

## 2. V3.0 核心洞察：靜態圖模式

LivePortrait 的 `execute_image_retargeting()` API 接收一張靜態圖片，套用表情參數（smile、eyebrow、wink 等），輸出一張帶表情的靜態圖。

這正好與 MuseTalk 的工作模式互補：
- MuseTalk 接收「靜態圖 + 音訊」，自行驅動嘴唇動作
- LivePortrait 負責讓那張靜態圖「帶有表情」（微笑、挑眉等）

因此 V3.0 的 LivePortrait 步驟只產出**一張靜態 PNG**，而非影片。這大幅簡化架構。

## 3. 模組分解

### 3.1 需要修改的現有檔案

| 檔案 | 修改內容 | 影響程度 |
|------|---------|---------|
| `config.py` | 新增 LIVEPORTRAIT_DIR / PYTHON / SCRIPT 常數 | 低 — 僅新增常數 |
| `video_renderer.py` | 新增 `_render_liveportrait_musetalk()` + dispatch 邏輯 | 中 — 新增方法，不修改現有方法 |
| `audio_preprocessor.py` | 新增 `LivePortraitExpression` + `EMOTION_LIVEPORTRAIT_MAP` | 低 — 僅新增 |

### 3.2 需要新建的檔案

| 檔案 | 職責 | 行數估計 |
|------|------|---------|
| `liveportrait_adapter.py` | LivePortrait subprocess 適配器 | ~200 行 |
| `scripts/liveportrait_retarget.py` | LivePortrait venv 中執行的 retarget 腳本 | ~180 行 |

### 3.3 不需修改的檔案（向後相容）

- `pipeline.py` — render() 簽名不變
- `vram_monitor.py` — 現有函式足夠
- `models.py`、`path_utils.py` — 直接複用

## 4. 資料流圖

```
character_image (PNG, 任意尺寸) + emotion_label ("sad")
        │
        ▼
┌──────────────────────────────────┐
│ Phase A: LivePortrait 表情注入    │
│                                  │
│ 1. mood_to_liveportrait_params() │
│    → LivePortraitExpression(     │
│        smile=-3.0, eyebrow=-5.0) │
│ 2. subprocess → retarget 腳本    │
│ 3. 產出 PNG (512x512, 帶表情)    │
└──────────────────────────────────┘
        │
        ▼ intermediate_image.png
┌──────────────────────────────────┐
│ VRAM 閘門                        │
│ force_cleanup() +                │
│ check_vram_safety()              │
└──────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────┐
│ Phase B: MuseTalk 嘴唇同步       │
│                                  │
│ 1. 複用 _render_musetalk()       │
│ 2. 源圖 = intermediate_image     │
│ 3. 產出 MP4 (704x1216, 對嘴)    │
└──────────────────────────────────┘
        │
        ▼
final_video.mp4 (704x1216, 帶表情 + 對嘴)
```

## 5. VRAM 分時管控策略

### 5.1 VRAM 預算分析

| 階段 | 模型 | VRAM 峰值 | 12GB 餘量 |
|------|------|----------|----------|
| Phase A | LivePortrait (subprocess) | 1,554 MB | 10,446 MB |
| 閘門 | subprocess 結束 → VRAM 歸零 | ~0 MB | ~12,000 MB |
| Phase B | MuseTalk (subprocess) | 8,258 MB | 3,742 MB |

**關鍵保證**：兩模型以 subprocess 執行，進程結束後 VRAM 由 OS 強制回收。閘門機制是額外安全護網。

### 5.2 閘門協議

Phase A 結束與 Phase B 開始之間，三道關卡：
1. 確認 LivePortrait subprocess 已結束（subprocess.run 同步）
2. force_cleanup()：gc.collect() + torch.cuda.empty_cache()
3. check_vram_safety()：若超 10GB 嘗試卸載 ComfyUI

## 6. 表情參數映射

### 6.1 LivePortrait 原生參數

| 參數 | 作用 | 範圍 |
|------|------|------|
| smile | 微笑程度 | -20 ~ 20 |
| eyebrow | 眉毛挑起/皺起 | -20 ~ 20 |
| wink | 眨眼 | -20 ~ 20 |
| eyeball_direction_x/y | 眼球方向 | -20 ~ 20 |
| head_pitch/yaw/roll | 頭部旋轉 | -20 ~ 20 |

### 6.2 情緒標籤映射表

```python
@dataclass(frozen=True)
class LivePortraitExpression:
    smile: float = 0.0
    eyebrow: float = 0.0
    wink: float = 0.0
    eyeball_direction_x: float = 0.0
    eyeball_direction_y: float = 0.0
    head_pitch: float = 0.0

EMOTION_LIVEPORTRAIT_MAP = {
    "happy":     LivePortraitExpression(smile=8.0, eyebrow=3.0),
    "sad":       LivePortraitExpression(smile=-3.0, eyebrow=-5.0, head_pitch=3.0),
    "angry":     LivePortraitExpression(smile=-5.0, eyebrow=-8.0),
    "surprised": LivePortraitExpression(eyebrow=10.0, eyeball_direction_y=-3.0),
    "fear":      LivePortraitExpression(eyebrow=6.0, eyeball_direction_y=-4.0, smile=-2.0),
    "contempt":  LivePortraitExpression(smile=2.0, eyebrow=-3.0, wink=3.0),
    "disgusted": LivePortraitExpression(smile=-4.0, eyebrow=-6.0),
    "neutral":   LivePortraitExpression(),
}
```

### 6.3 映射鏈

```
mood_hint → mood_to_exp_type() → EDTalk 標籤 → EMOTION_LIVEPORTRAIT_MAP → LivePortraitExpression
```

## 7. 降級策略

```
liveportrait_musetalk（V3.0 首選）
    │
    ├─ LivePortrait 失敗 → 原始圖片直接餵入 MuseTalk（無表情但有嘴唇同步）
    │
    └─ MuseTalk 也失敗 → fallback 為 edtalk
                              └─ EDTalk 也失敗 → ffmpeg_static
```

## 8. 介面定義

### 8.1 config.py 新增

```python
LIVEPORTRAIT_DIR = Path(os.environ.get("LIVEPORTRAIT_DIR", "D:/Projects/LivePortrait"))
LIVEPORTRAIT_PYTHON = LIVEPORTRAIT_DIR / "liveportrait_env" / "Scripts" / "python.exe"
LIVEPORTRAIT_RETARGET_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "liveportrait_retarget.py"
```

### 8.2 liveportrait_adapter.py

```python
class LivePortraitAdapter:
    def retarget(self, source_image: Path, expression: LivePortraitExpression, output_dir: Path) -> Path:
        """產出帶表情的中間圖片（PNG, 512x512）"""
```

### 8.3 video_renderer.py 修改

```python
# render() dispatch 新增
if self.renderer == "liveportrait_musetalk":
    return self._render_liveportrait_musetalk(composite_image, audio_path, output_path, exp_type=exp_type)

# 新增方法
def _render_liveportrait_musetalk(self, ...) -> tuple[Path, str]:
    # Phase A: LivePortrait retarget → 中間 PNG
    # VRAM 閘門
    # Phase B: 複用 _render_musetalk()（源圖 = 中間 PNG）
```

### 8.4 render() 簽名不變（NFR-3）

`exp_type` 在不同引擎中的行為：
- `edtalk`：傳遞為 `--exp_type` CLI 參數
- `musetalk`：僅記錄 log
- `liveportrait_musetalk`：映射為 LivePortraitExpression 參數集

## 9. 風險評估

| 風險 | 嚴重度 | 可能性 | 緩解措施 |
|------|--------|--------|---------|
| LivePortrait retarget 腳本 import 問題 | 高 | 中 | cwd=LIVEPORTRAIT_DIR 確保 sys.path |
| 表情參數值過大導致臉部扭曲 | 中 | 中 | 初始值保守設定，迭代調試 |
| subprocess VRAM 未完全釋放 | 高 | 低 | OS 強制回收 + 三道閘門 |
| video_renderer.py 膨脹超 800 行 | 中 | 中 | LivePortrait 邏輯抽取到 adapter |

## 10. 與 V2.x 差異摘要

| 面向 | V2.0 (EDTalk) | V2.1 (MuseTalk) | V3.0 (混合管線) |
|------|--------------|----------------|----------------|
| 表情控制 | 8 種離散情緒 | 無 | 連續參數（可微調） |
| 嘴唇同步 | EDTalk 驅動 | MuseTalk 高精度 | MuseTalk 高精度 |
| 解析度 | 256x256 | 704x1216 | 704x1216 |
| VRAM 峰值 | ~2.4GB | ~8.2GB | max(1.5, 8.2) = 8.2GB |
| 推理步驟 | 1 步 | 1 步 | 2 步串接 |
