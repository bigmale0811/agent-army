# -*- coding: utf-8 -*-
"""
DEV-13: Singer Agent CLI 進入點。

提供命令列介面：
- 執行 MV 產出管線（--title, --artist, --audio）
- 列出已儲存專案（--list）
- 乾跑模式（--dry-run）
- 自動回答提示（--auto）

Usage:
    python -m singer_agent --title "歌名" --artist "歌手" --audio song.mp3
    python -m singer_agent --list
    python -m singer_agent --title "歌名" --artist "歌手" --audio song.mp3 --dry-run
"""
import argparse
import logging
import sys
from pathlib import Path

from src.singer_agent import config
from src.singer_agent.models import PipelineRequest
from src.singer_agent.pipeline import Pipeline
from src.singer_agent.project_store import ProjectStore

_logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """
    建立 argparse 解析器。

    --list 可單獨使用，不需要其他參數。
    其餘模式需要 --title, --artist, --audio 三個必填參數。
    """
    parser = argparse.ArgumentParser(
        prog="singer-agent",
        description="虛擬歌手 MV 自動產出系統 CLI",
    )

    # 列出專案模式（獨立使用，不需其他參數）
    parser.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="列出所有已儲存的專案",
    )

    # 管線執行參數（--list 模式下非必填）
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="歌曲標題（必填，除非使用 --list）",
    )
    parser.add_argument(
        "--artist",
        type=str,
        default=None,
        help="歌手名稱（必填，除非使用 --list）",
    )
    parser.add_argument(
        "--audio",
        type=str,
        default=None,
        help="音訊檔案路徑（MP3，必填，除非使用 --list）",
    )

    # 選填參數
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="角色圖片路徑（選填，預設使用 config.CHARACTER_IMAGE）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="乾跑模式：各步驟使用 stub 資料，不呼叫外部服務",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        default=False,
        help="自動回答所有互動提示",
    )

    return parser


def _validate_run_args(args: argparse.Namespace) -> str | None:
    """
    驗證管線執行模式的必填參數。

    Returns:
        錯誤訊息字串，若無錯誤則回傳 None
    """
    missing = []
    if not args.title:
        missing.append("--title")
    if not args.artist:
        missing.append("--artist")
    if not args.audio:
        missing.append("--audio")
    if missing:
        return f"缺少必填參數：{', '.join(missing)}"
    return None


def _handle_list() -> int:
    """
    處理 --list 模式：列出所有已儲存專案。

    Returns:
        exit code（0 = 成功）
    """
    store = ProjectStore()
    projects = store.list_projects()

    if not projects:
        print("目前沒有已儲存的專案。")
        return 0

    # 輸出專案列表（表格格式）
    print(f"{'專案 ID':<20} {'狀態':<12} {'建立時間':<25} {'音訊來源'}")
    print("-" * 80)
    for proj in projects:
        print(
            f"{proj.project_id:<20} "
            f"{proj.status:<12} "
            f"{proj.created_at:<25} "
            f"{proj.source_audio}"
        )

    print(f"\n共 {len(projects)} 個專案。")
    return 0


def _handle_run(args: argparse.Namespace) -> int:
    """
    處理管線執行模式。

    驗證參數、建立 PipelineRequest、執行管線。

    Returns:
        exit code（0 = 成功，1 = 失敗）
    """
    # 驗證必填參數
    error = _validate_run_args(args)
    if error:
        print(error, file=sys.stderr)
        return 1

    # 驗證音訊檔案存在
    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(
            f"錯誤：音訊檔案不存在 — {audio_path}",
            file=sys.stderr,
        )
        return 1

    # 決定角色圖片路徑（自訂或預設）
    character_image: Path
    if args.image:
        character_image = Path(args.image)
        if not character_image.exists():
            print(
                f"錯誤：圖片檔案不存在 — {character_image}",
                file=sys.stderr,
            )
            return 1
    else:
        character_image = config.CHARACTER_IMAGE

    # 建立 PipelineRequest
    request = PipelineRequest(
        audio_path=audio_path,
        title=args.title,
        artist=args.artist,
    )

    # 建立並執行 Pipeline
    # 進度回調：在 CLI 模式下直接印出步驟資訊
    def progress_callback(step: int, description: str) -> None:
        print(f"[{step}/8] {description}")

    pipeline = Pipeline(
        character_image=character_image,
        progress_callback=progress_callback,
        dry_run=args.dry_run,
    )

    result = pipeline.run(request)

    # 根據結果決定 exit code
    if result.status == "completed":
        print(f"\n管線完成！專案 ID：{result.project_id}")
        return 0
    else:
        print(
            f"\n管線失敗：{result.error_message}",
            file=sys.stderr,
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    """
    CLI 主函式。

    Args:
        argv: 命令列參數列表（None 時使用 sys.argv[1:]）

    Returns:
        exit code（0 = 成功，1 = 失敗）
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.list:
            return _handle_list()
        return _handle_run(args)
    except Exception as exc:
        _logger.error("CLI 未預期錯誤：%s", exc)
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
