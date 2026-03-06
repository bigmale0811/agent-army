# -*- coding: utf-8 -*-
"""
DEV-12: 管線編排器。

Pipeline 將 8 個步驟串接為完整的 MV 產出流程：
1. researcher → SongResearch
2. song_spec → SongSpec
3. copywriter → CopySpec
4. background_gen → 背景圖
5. compositor → 去背 + 合成
6. precheck → 品質預檢
7. video_renderer → 影片
8. project_store → 儲存專案

支援 dry_run、progress_callback、例外捕獲不閃退。
"""
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.singer_agent import config
from src.singer_agent.models import (
    PipelineRequest, ProjectState, SongSpec,
)
from src.singer_agent.researcher import SongResearcher
from src.singer_agent.copywriter import Copywriter
from src.singer_agent.background_gen import BackgroundGenerator
from src.singer_agent.compositor import Compositor
from src.singer_agent.precheck import QualityPrecheck
from src.singer_agent.video_renderer import VideoRenderer
from src.singer_agent.project_store import ProjectStore

_logger = logging.getLogger(__name__)

# progress_callback 型別：(step_number: int, step_description: str) → None
ProgressCallback = Callable[[int, str], None]


class Pipeline:
    """
    MV 產出管線編排器。

    將 PipelineRequest 通過 8 個步驟轉化為完成的 ProjectState。
    任何步驟失敗都會被捕獲，設定 status="failed" 並記錄錯誤。

    Args:
        character_image: 角色圖片路徑
        progress_callback: 進度回調函式（可選）
        dry_run: True 時各步驟使用 stub 資料
    """

    def __init__(
        self,
        character_image: Path,
        progress_callback: ProgressCallback | None = None,
        dry_run: bool = False,
    ) -> None:
        self.character_image = character_image
        self.progress_callback = progress_callback
        self.dry_run = dry_run

    def _notify(self, step: int, description: str) -> None:
        """發送進度通知。"""
        _logger.info("Step %d/8: %s", step, description)
        if self.progress_callback:
            self.progress_callback(step, description)

    def run(self, request: PipelineRequest) -> ProjectState:
        """
        同步執行 8 步管線。

        任何步驟失敗都會被捕獲，不閃退。
        失敗時 status="failed"，已完成的步驟資料保留。

        Args:
            request: 管線執行請求

        Returns:
            ProjectState（completed 或 failed）
        """
        project_id = f"proj-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        # 初始化 ProjectState
        state = ProjectState(
            project_id=project_id,
            source_audio=str(request.audio_path),
            status="running",
            metadata={},
            song_spec=None,
            copy_spec=None,
            background_image="",
            composite_image="",
            precheck_result=None,
            final_video="",
            render_mode="",
            error_message="",
            created_at=now,
            completed_at="",
        )

        try:
            # Step 1: 歌曲研究
            self._notify(1, "歌曲風格研究")
            researcher = SongResearcher()
            research = researcher.research(
                title=request.title,
                artist=request.artist,
                language=request.language,
                genre_hint=request.genre_hint,
                mood_hint=request.mood_hint,
                notes=request.notes,
                dry_run=self.dry_run,
            )

            # Step 2: 建立 SongSpec
            self._notify(2, "建立歌曲規格")
            song_spec = SongSpec(
                title=request.title,
                artist=request.artist,
                language=request.language or "zh-TW",
                research=research,
                created_at=now,
            )
            state.song_spec = song_spec

            # Step 3: YouTube 文案
            self._notify(3, "產出 YouTube 文案")
            copywriter = Copywriter()
            copy_spec = copywriter.write(song_spec, dry_run=self.dry_run)
            state.copy_spec = copy_spec

            # Step 4: 背景生成
            self._notify(4, "生成背景圖")
            bg_path = config.BACKGROUNDS_DIR / f"{project_id}.png"
            bg_gen = BackgroundGenerator()
            bg_gen.generate(
                research.background_prompt, bg_path, dry_run=self.dry_run,
            )
            state.background_image = str(bg_path)

            # Step 5: 去背 + 合成
            self._notify(5, "角色去背與合成")
            comp = Compositor()
            nobg_path = config.COMPOSITES_DIR / f"{project_id}_nobg.png"
            comp.remove_background(
                self.character_image, nobg_path, dry_run=self.dry_run,
            )
            composite_path = config.COMPOSITES_DIR / f"{project_id}.png"
            comp.composite(
                bg_path, nobg_path, composite_path, dry_run=self.dry_run,
            )
            state.composite_image = str(composite_path)

            # Step 6: 品質預檢
            self._notify(6, "品質預檢")
            precheck = QualityPrecheck()
            precheck_result = precheck.run(
                composite_path, request.audio_path,
                song_spec=song_spec, dry_run=self.dry_run,
            )
            state.precheck_result = precheck_result

            if not precheck_result.passed:
                state.status = "failed"
                state.error_message = (
                    f"品質預檢未通過：{precheck_result.warnings}"
                )
                return state

            # Step 7: 影片渲染
            self._notify(7, "影片渲染")
            video_path = config.VIDEOS_DIR / f"{project_id}.mp4"
            renderer = VideoRenderer()
            _, render_mode = renderer.render(
                composite_path, request.audio_path,
                video_path, dry_run=self.dry_run,
            )
            state.final_video = str(video_path)
            state.render_mode = render_mode

            # Step 8: 儲存專案
            self._notify(8, "儲存專案狀態")
            store = ProjectStore()
            store.save(state)

            state.status = "completed"
            state.completed_at = datetime.now().isoformat()
            _logger.info("管線完成：%s", project_id)

        except Exception as exc:
            _logger.error("管線失敗（Step 中斷）：%s", exc)
            state.status = "failed"
            state.error_message = str(exc)

        return state
