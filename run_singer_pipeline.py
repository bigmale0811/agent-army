# -*- coding: utf-8 -*-
"""
Singer MV 管線 E2E 進入點。

用法：
  python run_singer_pipeline.py \
    --audio test_inputs/song.mp3 \
    --image test_inputs/character.png \
    --meta '{"title": "告白氣球", "artist": "周杰倫", "genre": "pop ballad"}'

  # dry-run 模式（不呼叫 ComfyUI / SadTalker，用假資料跑完整流程）
  python run_singer_pipeline.py \
    --audio test_inputs/song.mp3 \
    --image test_inputs/character.png \
    --meta '{"title": "test", "artist": "test"}' \
    --dry-run

全程啟用 VRAM 監控，終端機實時印出每個階段的 GPU 消耗量。
"""
import argparse
import json
import logging
import sys
from pathlib import Path

# Windows 終端機 UTF-8 支援（解決 cp950 不支援中文/特殊字元的問題）
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 確保專案根目錄在 sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.singer_agent.models import PipelineRequest
from src.singer_agent.pipeline import Pipeline
from src.singer_agent.vram_monitor import log_vram, check_vram_safety


def _setup_logging() -> None:
    """設定 logging：所有 singer_agent 與 vram_monitor 的 log 都印到終端機。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _parse_args() -> argparse.Namespace:
    """解析命令列參數。"""
    parser = argparse.ArgumentParser(
        description="Singer MV 管線 E2E 進入點",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--audio", type=str, required=True,
        help="MP3 音訊檔案路徑",
    )
    parser.add_argument(
        "--image", type=str, required=True,
        help="靜態人物圖片路徑（PNG/JPG）",
    )
    parser.add_argument(
        "--meta", type=str, required=True,
        help='JSON 字串，包含 title, artist, 可選 genre/mood/language/notes',
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="啟用 dry-run 模式（不呼叫 ComfyUI / SadTalker）",
    )
    return parser.parse_args()


def _build_request(
    audio_path: str,
    meta: dict,
) -> PipelineRequest:
    """從命令列參數建立 PipelineRequest。"""
    return PipelineRequest(
        audio_path=Path(audio_path).resolve(),
        title=meta.get("title", "Untitled"),
        artist=meta.get("artist", "Unknown"),
        language=meta.get("language", "zh-TW"),
        genre_hint=meta.get("genre", ""),
        mood_hint=meta.get("mood", ""),
        notes=meta.get("notes", ""),
    )


def _progress_callback(step: int, description: str) -> None:
    """終端機進度回報。"""
    print(f"\n{'='*60}")
    print(f"  🎬 Step {step}/8: {description}")
    print(f"{'='*60}")
    # 每個步驟開始時印出 VRAM 狀態
    log_vram(f"Step {step} 開始")


def main() -> int:
    """主程式進入點。"""
    _setup_logging()
    args = _parse_args()

    # 驗證輸入檔案
    audio_path = Path(args.audio).resolve()
    image_path = Path(args.image).resolve()

    if not audio_path.exists():
        print(f"❌ 音訊檔案不存在：{audio_path}")
        return 1
    if not image_path.exists():
        print(f"❌ 圖片檔案不存在：{image_path}")
        return 1

    # 解析 meta JSON
    try:
        meta = json.loads(args.meta)
    except json.JSONDecodeError as exc:
        print(f"❌ --meta JSON 解析失敗：{exc}")
        return 1

    # 建立 PipelineRequest
    request = _build_request(str(audio_path), meta)

    # 印出啟動資訊
    mode = "🧪 DRY-RUN" if args.dry_run else "🔥 LIVE"
    print(f"\n{'='*60}")
    print(f"  🎤 Singer MV Pipeline — {mode}")
    print(f"{'='*60}")
    print(f"  音訊：{audio_path}")
    print(f"  圖片：{image_path}")
    print(f"  歌名：{meta.get('title', 'N/A')}")
    print(f"  歌手：{meta.get('artist', 'N/A')}")
    print(f"  曲風：{meta.get('genre', 'N/A')}")
    print(f"{'='*60}\n")

    # 啟動前 VRAM 基準
    print("📊 啟動前 VRAM 狀態：")
    log_vram("管線啟動前")
    check_vram_safety("管線啟動前")

    # 執行管線
    pipeline = Pipeline(
        character_image=image_path,
        progress_callback=_progress_callback,
        dry_run=args.dry_run,
    )
    state = pipeline.run(request)

    # 結果報告
    print(f"\n{'='*60}")
    if state.status == "completed":
        print(f"  ✅ MV 產出成功！")
        print(f"  影片：{state.final_video}")
        print(f"  渲染模式：{state.render_mode}")
    else:
        print(f"  ❌ 管線失敗")
        print(f"  錯誤：{state.error_message}")
    print(f"  專案 ID：{state.project_id}")
    print(f"{'='*60}")

    # 結束前 VRAM 狀態
    print("\n📊 結束後 VRAM 狀態：")
    log_vram("管線結束後")

    return 0 if state.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
