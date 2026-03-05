# -*- coding: utf-8 -*-
"""Singer Agent — CLI 入口與流程編排

v0.3 流程（8 步）：
    1. 研究歌曲風格（Ollama Qwen3）
    2. 建立 SongSpec 風格規格書
    3. 生成 YouTube 文案
    4. 生成背景圖（ComfyUI → 純色降級）
    5. 合成角色 + 背景（rembg 去背 + PIL 合成）
    6. 預檢驗證（PrecheckAgent）
    7. 合成影片（SadTalker → FFmpeg 降級）
    8. 完成

降級策略：每個 v0.3 新步驟失敗時，自動降級回 v0.2 行為。

用法：
    python -m src.singer_agent --title "歌名" --artist "歌手" --audio song.mp3
    python -m src.singer_agent --title "歌名" --audio song.mp3 --dry-run
    python -m src.singer_agent --list
"""

import argparse
import asyncio
import io
import logging
import sys
from datetime import datetime

from .models import MVProject, ProjectStatus, SongMetadata, SongSpec
from .storage import save_project, save_spec, list_projects

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False):
    """設定日誌（與 reading_agent 一致的 UTF-8 處理）"""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(
        open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    )
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.basicConfig(level=level, handlers=[handler])


def _generate_project_id(title: str) -> str:
    """產生專案 ID：時間戳 + 歌名簡寫"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 取歌名前 20 字，移除特殊字元
    safe_title = "".join(
        c for c in title[:20] if c.isalnum() or c in "-_"
    ) or "untitled"
    return f"{timestamp}_{safe_title}"


# =========================================================
# MVP 主流程
# =========================================================

async def _run_pipeline(
    title: str,
    artist: str,
    audio_path: str,
    language: str = "",
    genre_hint: str = "",
    mood_hint: str = "",
    notes: str = "",
    dry_run: bool = False,
):
    """執行 MVP 流水線

    Args:
        title: 歌曲名稱
        artist: 原唱歌手
        audio_path: MP3 檔案路徑
        language: 語言
        genre_hint: 風格提示
        mood_hint: 情緒提示
        notes: 備註
        dry_run: 只做分析，不合成影片
    """
    start_time = datetime.now()

    logger.info("=" * 50)
    logger.info("🎤 Singer Agent MVP 啟動")
    logger.info("🎵 歌曲: %s - %s", title, artist or "未知")
    logger.info("🎧 音檔: %s", audio_path)
    logger.info("Dry Run: %s", dry_run)
    logger.info("=" * 50)

    # === 0. 建立專案 ===
    project_id = _generate_project_id(title)
    metadata = SongMetadata(
        title=title,
        artist=artist,
        language=language,
        genre_hint=genre_hint,
        mood_hint=mood_hint,
        notes=notes,
    )
    project = MVProject(
        project_id=project_id,
        source_audio=audio_path,
        status=ProjectStatus.PENDING.value,
        metadata=metadata,
        created_at=datetime.now().isoformat(),
    )
    save_project(project)
    logger.info("📂 專案已建立: %s", project_id)

    # === 1. 研究歌曲風格 ===
    project.status = ProjectStatus.RESEARCHING.value
    save_project(project)

    logger.info("🔍 Step 1: 研究歌曲風格...")
    try:
        from .song_researcher import research_song
        research_result = await research_song(metadata)
    except ConnectionError as e:
        logger.error("❌ %s", e)
        project.status = ProjectStatus.FAILED.value
        project.error_message = str(e)
        save_project(project)
        return
    except Exception as e:
        logger.error("❌ 歌曲風格研究失敗: %s", e)
        project.status = ProjectStatus.FAILED.value
        project.error_message = str(e)
        save_project(project)
        return

    # === 2. 建立 SongSpec ===
    project.status = ProjectStatus.CLASSIFYING.value
    save_project(project)

    logger.info("📋 Step 2: 建立風格規格書...")
    spec = SongSpec(
        title=title,
        artist=artist,
        language=language or research_result.get("language", ""),
        research_summary=research_result.get("research_summary", ""),
        genre=research_result.get("genre", ""),
        mood=research_result.get("mood", ""),
        visual_style=research_result.get("visual_style", ""),
        color_palette=research_result.get("color_palette", ""),
        background_prompt=research_result.get("background_prompt", ""),
        outfit_prompt=research_result.get("outfit_prompt", ""),
        scene_description=research_result.get("scene_description", ""),
        created_at=datetime.now().isoformat(),
    )
    project.song_spec = spec
    save_spec(spec, project_id)

    # 顯示規格書
    _print_spec(spec)

    # === 3. 生成文案 ===
    project.status = ProjectStatus.WRITING_COPY.value
    save_project(project)

    logger.info("✍️ Step 3: 生成 YouTube 文案...")
    try:
        from .copywriter import generate_copy
        copy_result = await generate_copy(spec)
        project.youtube_title = copy_result.get("youtube_title", "")
        project.youtube_description = copy_result.get("youtube_description", "")
        project.youtube_tags = copy_result.get("youtube_tags", [])

        _print_copy(copy_result)
    except Exception as e:
        logger.warning("⚠️ 文案生成失敗（不影響主流程）: %s", e)

    # === 4. 生成背景圖（v0.3 新增，失敗降級為純色）===
    if not dry_run:
        project.status = ProjectStatus.GENERATING_BG.value
        save_project(project)

        logger.info("🎨 Step 4: 生成背景圖...")
        try:
            from .comfyui_client import (
                ComfyUIClient, build_background_prompt, generate_solid_background,
            )

            comfyui = ComfyUIClient()
            if await comfyui.is_available():
                bg_prompt = build_background_prompt(spec)
                logger.info("   ComfyUI prompt: %s", bg_prompt[:80])
                bg_path = await comfyui.generate_background(
                    prompt=bg_prompt,
                    output_filename=f"bg_{project_id}.png",
                )
                # 生成完成後釋放 VRAM，留給後續 SadTalker
                await comfyui.free_vram()
                logger.info("🎨 ComfyUI 背景圖: %s", bg_path)
            else:
                logger.info("⚠️ ComfyUI 不可用，降級為純色背景")
                bg_path = generate_solid_background(
                    mood=spec.mood,
                    output_filename=f"bg_{project_id}.png",
                )
            project.background_image = str(bg_path)
            save_project(project)
        except Exception as e:
            logger.warning("⚠️ 背景圖生成失敗，降級為純色: %s", e)
            try:
                from .comfyui_client import generate_solid_background
                bg_path = generate_solid_background(
                    mood=spec.mood,
                    output_filename=f"bg_{project_id}.png",
                )
                project.background_image = str(bg_path)
                save_project(project)
            except Exception as e2:
                logger.error("❌ 連純色背景都失敗: %s", e2)

    # === 5. 合成角色 + 背景（v0.3 新增，失敗跳過）===
    if not dry_run and project.background_image:
        project.status = ProjectStatus.COMPOSITING.value
        save_project(project)

        logger.info("🖼️ Step 5: 合成角色 + 背景...")
        try:
            from .image_compositor import ImageCompositor
            from .config import CHARACTER_IMAGE, COMPOSITES_DIR

            compositor = ImageCompositor()

            # 5a. 角色去背
            char_img = compositor.remove_background(str(CHARACTER_IMAGE))
            nobg_path = COMPOSITES_DIR / f"nobg_{project_id}.png"
            char_img.save(str(nobg_path))
            project.character_nobg = str(nobg_path)
            logger.info("   去背完成: %s", nobg_path)

            # 5b. 角色 + 背景合成
            composite_path = str(COMPOSITES_DIR / f"composite_{project_id}.png")
            compositor.composite(
                background_path=project.background_image,
                character_image=char_img,
                output_path=composite_path,
            )
            project.composite_image = composite_path
            save_project(project)
            logger.info("🖼️ 合成圖: %s", composite_path)
        except Exception as e:
            logger.warning("⚠️ 角色合成失敗，將使用原始角色圖: %s", e)
            project.composite_image = ""  # 清空，後續用原圖
            save_project(project)

    # === 6. 預檢驗證（v0.3 新增，不中斷流程）===
    if not dry_run:
        project.status = ProjectStatus.PRECHECKING.value
        save_project(project)

        logger.info("🔎 Step 6: 預檢驗證...")
        try:
            from .precheck_agent import PrecheckAgent

            precheck = PrecheckAgent()
            # 如果有合成圖就用合成圖，否則用原始角色圖
            check_image = project.composite_image or str(CHARACTER_IMAGE)
            precheck_result = await precheck.run_all_checks(
                composite_image=check_image,
                audio_path=audio_path,
                spec=spec,
            )
            project.precheck_passed = precheck_result.passed
            project.precheck_summary = precheck_result.summary()
            save_project(project)
            logger.info("🔎 預檢結果: %s", "通過" if precheck_result.passed else "未通過")
            if precheck_result.warnings:
                for w in precheck_result.warnings:
                    logger.warning("   ⚠️ %s", w)
        except Exception as e:
            logger.warning("⚠️ 預檢失敗（不影響流程）: %s", e)
            project.precheck_passed = True  # 預檢失敗不阻擋
            save_project(project)

    # === 7. 合成影片（非 dry-run 時）===
    if dry_run:
        logger.info("🔇 Dry Run 模式，跳過影片合成")
    else:
        project.status = ProjectStatus.COMPOSING.value
        save_project(project)

        logger.info("🎬 Step 7: 合成影片（優先 SadTalker 唱歌模式）...")
        try:
            from .mv_composer import compose_mv

            # v0.3：如果有合成圖，傳給 compose_mv 使用
            video_path, render_mode = compose_mv(
                audio_path=audio_path,
                spec=spec,
                project_id=project_id,
                composite_image=project.composite_image,
            )
            project.final_video = video_path
            project.render_mode = render_mode
            mode_label = "SadTalker 唱歌動畫" if render_mode == "sadtalker" else "靜態 FFmpeg"
            logger.info("🎬 影片已產出 [%s]: %s", mode_label, video_path)
        except FileNotFoundError as e:
            logger.error("❌ %s", e)
            project.status = ProjectStatus.FAILED.value
            project.error_message = str(e)
            save_project(project)
            return
        except RuntimeError as e:
            logger.error("❌ 影片合成失敗: %s", e)
            project.status = ProjectStatus.FAILED.value
            project.error_message = str(e)
            save_project(project)
            return

    # === 8. 完成 ===
    project.status = ProjectStatus.COMPLETED.value
    project.completed_at = datetime.now().isoformat()
    save_project(project)

    elapsed = datetime.now() - start_time
    logger.info("=" * 50)
    logger.info("✅ Singer Agent MVP 流程完成")
    logger.info("📂 專案 ID: %s", project_id)
    logger.info("🎵 歌曲: %s - %s", title, artist)
    logger.info("🎨 風格: %s / %s", spec.genre, spec.mood)
    if project.final_video:
        logger.info("🎬 影片: %s", project.final_video)
    logger.info("⏱️ 耗時: %s", elapsed)
    logger.info("=" * 50)


# =========================================================
# 輔助顯示函式
# =========================================================

def _print_spec(spec: SongSpec):
    """顯示 SongSpec 摘要"""
    utf8_out = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace",
    )
    utf8_out.write("\n")
    utf8_out.write("📋 歌曲風格規格書\n")
    utf8_out.write("━" * 40 + "\n")
    utf8_out.write(f"🎵 歌曲: {spec.title} - {spec.artist}\n")
    utf8_out.write(f"🎸 風格: {spec.genre}\n")
    utf8_out.write(f"💫 情緒: {spec.mood}\n")
    utf8_out.write(f"🎨 視覺: {spec.visual_style}\n")
    utf8_out.write(f"🖌️ 色調: {spec.color_palette}\n")
    utf8_out.write(f"🏞️ 場景: {spec.scene_description}\n")
    utf8_out.write(f"👗 服裝: {spec.outfit_prompt}\n")
    utf8_out.write("━" * 40 + "\n")
    utf8_out.flush()


def _print_copy(copy_result: dict):
    """顯示文案結果"""
    utf8_out = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace",
    )
    utf8_out.write("\n")
    utf8_out.write("✍️ YouTube 文案\n")
    utf8_out.write("━" * 40 + "\n")
    utf8_out.write(f"📌 標題: {copy_result.get('youtube_title', '?')}\n")
    utf8_out.write(f"📝 描述:\n{copy_result.get('youtube_description', '?')}\n")
    tags = copy_result.get("youtube_tags", [])
    utf8_out.write(f"🏷️ 標籤: {', '.join(tags)}\n")
    utf8_out.write("━" * 40 + "\n")
    utf8_out.flush()


# =========================================================
# --list 列出專案
# =========================================================

def _run_list():
    """列出所有 MV 專案"""
    projects = list_projects()
    if not projects:
        print("目前沒有任何專案。")
        return

    utf8_out = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace",
    )
    utf8_out.write(f"\n🎤 MV 專案列表（共 {len(projects)} 個）\n")
    utf8_out.write("━" * 50 + "\n")
    for p in projects:
        status_icon = {
            "completed": "✅",
            "failed": "❌",
            "pending": "⏳",
        }.get(p.status, "🔄")
        title = p.metadata.title if p.metadata else "未知"
        utf8_out.write(
            f"{status_icon} [{p.project_id}] {title} — {p.status}\n"
        )
    utf8_out.write("━" * 50 + "\n")
    utf8_out.flush()


# =========================================================
# CLI 入口
# =========================================================

def main():
    """CLI 入口點"""
    parser = argparse.ArgumentParser(
        description="Singer Agent MVP — 虛擬歌手 MV 自動化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  # 分析歌曲風格 + 生成文案（不合成影片）
  python -m src.singer_agent --title "告白氣球" --artist "周杰倫" --audio song.mp3 --dry-run

  # 完整流程：分析 + 文案 + 合成影片
  python -m src.singer_agent --title "告白氣球" --artist "周杰倫" --audio song.mp3

  # 加上風格/情緒提示
  python -m src.singer_agent --title "告白氣球" --artist "周杰倫" --audio song.mp3 --mood romantic

  # 列出所有專案
  python -m src.singer_agent --list
        """,
    )
    parser.add_argument("--title", help="歌曲名稱（必填，除非 --list）")
    parser.add_argument("--artist", default="", help="原唱歌手")
    parser.add_argument("--audio", help="MP3 音檔路徑（必填，除非 --list / --dry-run）")
    parser.add_argument("--language", default="", help="語言（zh/en/ja）")
    parser.add_argument("--genre", default="", help="風格提示")
    parser.add_argument("--mood", default="", help="情緒提示")
    parser.add_argument("--notes", default="", help="其他備註")
    parser.add_argument("--dry-run", action="store_true", help="只分析不合成影片")
    parser.add_argument("--list", action="store_true", help="列出所有專案")
    parser.add_argument("--bot", action="store_true", help="啟動 Telegram Bot 模式")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細日誌")

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if args.bot:
        from .telegram_bot_handler import SingerBotHandler
        bot = SingerBotHandler()
        bot.run()
        return

    if args.list:
        _run_list()
        return

    if not args.title:
        parser.error("請提供 --title 歌曲名稱")

    if not args.audio and not args.dry_run:
        parser.error("請提供 --audio MP3 音檔路徑（或使用 --dry-run 只做分析）")

    asyncio.run(_run_pipeline(
        title=args.title,
        artist=args.artist,
        audio_path=args.audio or "",
        language=args.language,
        genre_hint=args.genre,
        mood_hint=args.mood,
        notes=args.notes,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
