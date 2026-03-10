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
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.singer_agent import config
from src.singer_agent.models import (
    PipelineRequest, ProjectState, SongSpec,
)
from src.singer_agent.audio_preprocessor import (
    separate_vocals, apply_noise_gate, mood_to_exp_type,
)
from src.singer_agent.researcher import SongResearcher
from src.singer_agent.copywriter import Copywriter
from src.singer_agent.background_gen import BackgroundGenerator
from src.singer_agent.compositor import Compositor
from src.singer_agent.precheck import QualityPrecheck
from src.singer_agent.quality_checker import QualityChecker
from src.singer_agent.video_renderer import VideoRenderer
from src.singer_agent.project_store import ProjectStore
from src.singer_agent.vram_monitor import log_vram, check_vram_safety

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

    # 管線總步驟數（新增 Step 7 音訊前處理 + Step 9 QA 品質檢驗）
    _TOTAL_STEPS = 10

    def _notify(self, step: int, description: str) -> None:
        """發送進度通知。"""
        _logger.info("Step %d/%d: %s", step, self._TOTAL_STEPS, description)
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
        # HIGH-04 修復：音訊路徑驗證（副檔名 + 存在性）
        _ALLOWED_AUDIO_EXTS: set[str] = {
            ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma",
        }
        audio_ext = request.audio_path.suffix.lower()
        if audio_ext not in _ALLOWED_AUDIO_EXTS:
            raise ValueError(
                f"不支援的音訊格式：{audio_ext}（允許：{_ALLOWED_AUDIO_EXTS}）"
            )
        if not request.audio_path.exists():
            raise FileNotFoundError(
                f"音訊檔案不存在：{request.audio_path}"
            )

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

        current_step = 0  # 步驟追蹤（錯誤時顯示在哪一步失敗）
        try:
            # Step 1: 歌曲研究
            current_step = 1
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
            current_step = 2
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
            current_step = 3
            self._notify(3, "產出 YouTube 文案")
            copywriter = Copywriter()
            copy_spec = copywriter.write(song_spec, dry_run=self.dry_run)
            state.copy_spec = copy_spec

            # Step 4: 背景生成（GPU 密集：ComfyUI SDXL ~7-8GB VRAM）
            current_step = 4
            log_vram("Step 4 開始前")
            self._notify(4, "生成背景圖")
            bg_path = config.BACKGROUNDS_DIR / f"{project_id}.png"
            bg_gen = BackgroundGenerator()
            bg_gen.generate(
                research.background_prompt, bg_path, dry_run=self.dry_run,
            )
            state.background_image = str(bg_path)
            # generate() 內部已呼叫 POST /free 卸載 SDXL
            log_vram("Step 4 完成後（ComfyUI 已卸載）")

            # Step 5: 去背 + 合成（GPU 密集：rembg U²-Net ~170MB）
            current_step = 5
            log_vram("Step 5 開始前")
            self._notify(5, "角色去背與合成")
            comp = Compositor()
            nobg_path = config.COMPOSITES_DIR / f"{project_id}_nobg.png"
            comp.remove_background(
                self.character_image, nobg_path, dry_run=self.dry_run,
            )
            # remove_background() 內部已呼叫 force_cleanup()
            composite_path = config.COMPOSITES_DIR / f"{project_id}.png"
            comp.composite(
                bg_path, nobg_path, composite_path, dry_run=self.dry_run,
            )
            state.composite_image = str(composite_path)
            log_vram("Step 5 完成後")

            # Step 6: 品質預檢
            current_step = 6
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

            # Step 7: 音訊前處理（Demucs 人聲分離 + noise gate）
            # Demucs 以 subprocess 隔離，VRAM ~3-4GB，結束後自動釋放
            current_step = 7
            self._notify(7, "音訊前處理（人聲分離）")
            demucs_dir = config.DATA_DIR / "demucs" / project_id
            vocals_path = separate_vocals(
                request.audio_path, demucs_dir, dry_run=self.dry_run,
            )
            # noise gate：將人聲軌殘留的低能量段落強制靜音
            gated_path = demucs_dir / "vocals_gated.wav"
            vocals_for_edtalk = apply_noise_gate(
                vocals_path, gated_path, dry_run=self.dry_run,
            )
            _logger.info(
                "音訊前處理完成：原始=%s → 人聲=%s → gated=%s",
                request.audio_path.name, vocals_path.name,
                vocals_for_edtalk.name,
            )

            # 從 mood_hint 推斷 EDTalk 情緒類型
            exp_type = mood_to_exp_type(request.mood_hint)

            # Step 8: 影片渲染（V3.0 三引擎：EDTalk / MuseTalk / LP+MT）
            current_step = 8
            # 使用人聲軌道（非原始混音）+ 情緒 exp_type
            # 各引擎內部已有 _pre_launch_cleanup()
            #
            # ⚠️ 重要：EDTalk / LivePortrait 需要「臉部肖像」作為 source，
            #    不是合成後的全場景圖（1920x1080）！
            #    必須餵入 character_image（原始 avatar），
            #    否則臉部偵測失敗。
            log_vram("Step 8 開始前")
            check_vram_safety("Step 8 渲染啟動前")
            renderer_label = {
                "edtalk": "EDTalk",
                "musetalk": "MuseTalk",
                "liveportrait_musetalk": "LivePortrait+MuseTalk",
            }.get(config.SINGER_RENDERER, config.SINGER_RENDERER)
            self._notify(8, f"影片渲染（{renderer_label}）")
            video_path = config.VIDEOS_DIR / f"{project_id}.mp4"
            renderer = VideoRenderer()
            _, render_mode = renderer.render(
                self.character_image, vocals_for_edtalk,
                video_path, dry_run=self.dry_run,
                exp_type=exp_type,
            )
            state.final_video = str(video_path)
            state.render_mode = render_mode
            log_vram(f"Step 8 完成後（{render_mode} subprocess 已結束）")

            # Step 9: QA 品質檢驗（嘴唇同步分析）
            current_step = 9
            # 使用 MediaPipe Face Mesh（CPU only，0 VRAM）
            # QA 為非關鍵步驟：失敗時跳過，不阻擋 MV 輸出
            self._notify(9, "品質檢驗（嘴唇同步）")
            try:
                qa = QualityChecker()
                qa_result = qa.check(
                    video_path, vocals_path, dry_run=self.dry_run,
                )
                state.metadata["qa_result"] = {
                    "passed": qa_result.passed,
                    "lip_sync_score": qa_result.lip_sync_score,
                    "silent_motion_ratio": qa_result.silent_motion_ratio,
                    "total_frames": qa_result.total_frames,
                    "silent_frames": qa_result.silent_frames,
                }
                if not qa_result.passed:
                    _logger.warning(
                        "QA 品質檢驗未通過：lip_sync=%.1f, "
                        "靜音段運動比率=%.1f%%",
                        qa_result.lip_sync_score,
                        qa_result.silent_motion_ratio * 100,
                    )
                    state.metadata["qa_warning"] = (
                        f"靜音段嘴唇運動比率 "
                        f"{qa_result.silent_motion_ratio:.1%} "
                        f"超過閾值，lip_sync_score="
                        f"{qa_result.lip_sync_score:.1f}"
                    )
            except Exception as qa_exc:
                _logger.warning(
                    "QA 品質檢驗跳過（非致命）：%s", qa_exc,
                )
                state.metadata["qa_skipped"] = str(qa_exc)

            # Step 10: 儲存專案
            current_step = 10
            self._notify(10, "儲存專案狀態")
            state.status = "completed"
            state.completed_at = datetime.now().isoformat()

            store = ProjectStore()
            store.save(state)
            _logger.info("管線完成：%s", project_id)

        except Exception as exc:
            # 取得完整 traceback（含檔案名 + 行號）
            tb_text = traceback.format_exc()
            _logger.error(
                "管線失敗（Step %d 中斷, %s）：%s\n%s",
                current_step, type(exc).__name__, exc, tb_text,
            )
            # HIGH-03 修復：分離內部日誌與使用者訊息
            # 完整 traceback 僅記錄到日誌（含檔案路徑，供開發者除錯）
            # 使用者訊息不包含內部路徑，避免洩漏系統資訊
            state.status = "failed"
            state.error_message = (
                f"[Step {current_step}/10] "
                f"處理失敗（{type(exc).__name__}），請聯繫管理員查看日誌。"
            )

        return state
