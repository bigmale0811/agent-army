# -*- coding: utf-8 -*-
"""
DEV-11: 影片合成模組（V3.0 — EDTalk / MuseTalk / LivePortrait+MuseTalk 三引擎）。

VideoRenderer 提供：
- EDTalk 路徑（subprocess，8 種情緒，256x256，VRAM ~2.4GB）
- MuseTalk 路徑（subprocess，高解析度 704x1216，VRAM ~8.2GB）
- LivePortrait+MuseTalk 混合管線（表情動態 + 嘴唇同步，分時 VRAM ~8.2GB）
- FFmpeg 靜態降級（靜態圖片 + 音訊合成影片）
- 非 ASCII 路徑自動處理（透過 path_utils）

V3.0 變更：
- 新增 LivePortrait + MuseTalk 混合管線（表情注入 + 嘴唇同步）
- LivePortrait 僅產出帶表情的靜態 PNG，再由 MuseTalk 驅動嘴唇
- VRAM 分時管控：兩模型不同時載入

V3.1 變更：
- LivePortrait 產出帶自然表情的 MP4 影片（眨眼、眉毛、微笑）
- MuseTalk 以動態影片為輸入，實現表情+嘴唇同步
- 新增 NaturalMotionEngine 生成逐幀表情參數序列

V3.2 變更：
- 頭部擺動改為 2D 後處理（LivePortrait + MuseTalk 無法保留頭部旋轉）
- MuseTalk 產出後用 OpenCV 逐幀旋轉模擬頭部自然微動
- Haar cascade 臉部偵測 + 橢圓漸層遮罩 → 只旋轉頭部，背景不動
"""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.singer_agent import config
from src.singer_agent.path_utils import to_ascii_temp, cleanup_temp

_logger = logging.getLogger(__name__)

# exp_type 白名單（防止未驗證的字串進入 subprocess 參數）
_VALID_EXP_TYPES: frozenset[str] = frozenset({
    "angry", "contempt", "disgusted", "fear",
    "happy", "neutral", "sad", "surprised",
})


def _sanitize_exp_type(exp_type: str) -> str:
    """驗證 exp_type 是否在白名單內，不合法時降級為 neutral。"""
    if exp_type in _VALID_EXP_TYPES:
        return exp_type
    _logger.warning(
        "無效的 exp_type '%s'，降級為 'neutral'（允許值：%s）",
        exp_type, ", ".join(sorted(_VALID_EXP_TYPES)),
    )
    return "neutral"


class VideoRenderer:
    """
    影片渲染器（V3.0 — EDTalk / MuseTalk / LivePortrait+MuseTalk 三引擎）。

    主路徑：由 SINGER_RENDERER 環境變數決定渲染引擎。
    降級路徑：FFmpeg 靜態圖片迴圈 + 音訊合成。

    Args:
        edtalk_dir: EDTalk 安裝目錄
        musetalk_dir: MuseTalk 安裝目錄
        liveportrait_dir: LivePortrait 安裝目錄（V3.0）
        ffmpeg_bin: FFmpeg 執行檔路徑
        renderer: 渲染引擎選擇（"edtalk" / "musetalk" / "liveportrait_musetalk"）
    """

    def __init__(
        self,
        edtalk_dir: Path | None = None,
        musetalk_dir: Path | None = None,
        liveportrait_dir: Path | None = None,
        ffmpeg_bin: Path | None = None,
        renderer: str | None = None,
    ) -> None:
        # 渲染引擎選擇
        self.renderer = renderer or config.SINGER_RENDERER

        # EDTalk 設定
        self.edtalk_dir = edtalk_dir or config.EDTALK_DIR
        self.ffmpeg_bin = ffmpeg_bin or config.FFMPEG_BIN
        self._edtalk_python = config.EDTALK_PYTHON
        self._edtalk_demo = config.EDTALK_DEMO_SCRIPT
        self._pose_video = config.EDTALK_POSE_VIDEO

        # MuseTalk 設定
        self.musetalk_dir = musetalk_dir or config.MUSETALK_DIR
        self._musetalk_python = config.MUSETALK_PYTHON
        self._musetalk_version = config.MUSETALK_VERSION

        # LivePortrait 設定（V3.0）
        self.liveportrait_dir = liveportrait_dir or config.LIVEPORTRAIT_DIR

    # 推論超時（秒）
    _RENDER_TIMEOUT: int = 600       # EDTalk（短片段，~11s/10s 影片）
    _MUSETALK_TIMEOUT: int = 1800    # MuseTalk（完整歌曲需 15-25 分鐘推理）
    _LP_MUSETALK_TIMEOUT: int = 2400 # LivePortrait(~15s) + MuseTalk(~25min)

    def render(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
        dry_run: bool = False,
        exp_type: str = "neutral",
        expression_scale: float = 1.0,
    ) -> tuple[Path, str]:
        """
        渲染影片。

        Args:
            composite_image: 合成圖片路徑（角色 + 背景）
            audio_path: 音訊檔案路徑（應為 Demucs 純人聲）
            output_path: 輸出影片路徑
            dry_run: True 時建立佔位檔
            exp_type: EDTalk 情緒類型（8 種之一）
            expression_scale: V1.0 相容參數（V2.0 已忽略）

        Returns:
            (輸出路徑, 渲染模式) — 模式為 "edtalk"、"ffmpeg_static" 或 "dry_run"
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # CRIT-02 修復：exp_type 白名單驗證
        exp_type = _sanitize_exp_type(exp_type)

        if dry_run:
            _logger.info("dry_run 模式：建立佔位影片檔")
            output_path.write_bytes(b"\x00" * 100)
            return output_path, "dry_run"

        # 根據渲染引擎分派
        if self.renderer == "wan_s2v":
            from src.singer_agent.wan_adapter import render_s2v
            result_path, mode = render_s2v(
                composite_image, audio_path, output_path,
            )
            if mode == "wan_s2v":
                return result_path, mode
            _logger.warning("Wan2.2-S2V 渲染失敗，降級到 FLOAT/EDTalk")

        if self.renderer in ("float", "wan_s2v"):
            from src.singer_agent.float_adapter import render_float
            result_path, mode = render_float(
                composite_image, audio_path, output_path,
                exp_type=exp_type,
            )
            if mode == "float":
                return result_path, mode
            _logger.warning("FLOAT 渲染失敗，降級到 EDTalk")

        if self.renderer == "liveportrait_musetalk":
            return self._render_liveportrait_musetalk(
                composite_image, audio_path, output_path,
                exp_type=exp_type,
            )

        if self.renderer == "musetalk":
            return self._render_musetalk(
                composite_image, audio_path, output_path,
                exp_type=exp_type,
            )

        # EDTalk 主路徑（預設）
        return self._render_edtalk(
            composite_image, audio_path, output_path,
            exp_type=exp_type,
        )

    def _render_edtalk(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
        exp_type: str = "neutral",
    ) -> tuple[Path, str]:
        """
        透過 EDTalk subprocess 渲染對嘴動畫。

        EDTalk 特點：
        - 原生支援 8 種情緒標籤（--exp_type）
        - VRAM ~2.4GB（比 SadTalker 省 50%）
        - 執行速度接近即時（10 秒影片 ~11 秒推論）
        """
        _logger.info(
            "開始 EDTalk 渲染（exp_type=%s）", exp_type,
        )

        # 前置 VRAM 清理
        self._pre_launch_cleanup()

        # 處理非 ASCII 路徑（EDTalk 可能不支援中文路徑）
        ascii_img = to_ascii_temp(composite_image)
        ascii_audio = to_ascii_temp(audio_path)

        try:
            # 檢查 EDTalk 環境
            if not self._edtalk_python.exists():
                raise FileNotFoundError(
                    f"EDTalk venv Python 不存在：{self._edtalk_python}"
                )
            if not self._edtalk_demo.exists():
                raise FileNotFoundError(
                    f"EDTalk demo 腳本不存在：{self._edtalk_demo}"
                )

            # EDTalk 輸出到暫存路徑（res/ 目錄下）
            edtalk_output = self.edtalk_dir / "res" / f"singer_{output_path.stem}.mp4"
            edtalk_output.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                str(self._edtalk_python),
                str(self._edtalk_demo),
                "--source_path", str(ascii_img),
                "--audio_driving_path", str(ascii_audio),
                "--pose_driving_path", str(self._pose_video),
                "--exp_type", exp_type,
                "--save_path", str(edtalk_output),
            ]

            _logger.info("EDTalk 命令：%s", " ".join(cmd))

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._RENDER_TIMEOUT,
                cwd=str(self.edtalk_dir),
            )

            if result.returncode != 0:
                _logger.error(
                    "EDTalk 推論失敗（exit=%d）：%s",
                    result.returncode,
                    result.stderr[-500:] if result.stderr else "無 stderr",
                )
                raise RuntimeError(
                    f"EDTalk 推論失敗（exit={result.returncode}）"
                )

            # 確認輸出影片存在
            if not edtalk_output.exists():
                raise RuntimeError(
                    f"EDTalk 未產出影片：{edtalk_output}"
                )

            # 搬移到目標路徑
            if output_path.exists():
                output_path.unlink()
            shutil.move(str(edtalk_output), str(output_path))

            size_mb = output_path.stat().st_size / (1024 ** 2)
            _logger.info(
                "EDTalk 渲染完成：%s（%.2f MB, exp_type=%s）",
                output_path, size_mb, exp_type,
            )
            return output_path, "edtalk"

        except subprocess.TimeoutExpired:
            _logger.error("EDTalk 推論超時（>%ds）", self._RENDER_TIMEOUT)
            raise RuntimeError(
                f"EDTalk 推論超時（>{self._RENDER_TIMEOUT}s）"
            )

        finally:
            # 清理暫存 ASCII 路徑
            cleanup_temp(ascii_img)
            cleanup_temp(ascii_audio)

    def _pre_launch_cleanup(self) -> None:
        """
        EDTalk 啟動前的 VRAM 清理。

        確保 ComfyUI SDXL 模型已卸載、rembg 殘留已清理，
        讓 EDTalk 能獨佔 GPU。
        """
        from src.singer_agent.vram_monitor import (
            free_comfyui_models, force_cleanup, log_vram, check_vram_safety,
        )

        _logger.info("EDTalk 前置清理：卸載 ComfyUI 模型 + 清理 VRAM")
        free_comfyui_models(
            getattr(config, "COMFYUI_URL", "http://localhost:8188")
        )
        force_cleanup()
        log_vram("EDTalk 啟動前")
        check_vram_safety("EDTalk 啟動前")

    def _render_musetalk(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
        exp_type: str = "neutral",
    ) -> tuple[Path, str]:
        """
        透過 MuseTalk subprocess 渲染高解析度對嘴動畫。

        MuseTalk 特點：
        - 高解析度輸出（704×1216 vs EDTalk 的 256×256）
        - VRAM ~8.2GB（需確保 ComfyUI 已卸載）
        - 不支援情緒標籤（exp_type 僅記錄，不影響渲染）
        """
        _logger.info(
            "開始 MuseTalk 渲染（version=%s, exp_type=%s 不影響渲染）",
            self._musetalk_version, exp_type,
        )
        if exp_type != "neutral":
            _logger.warning(
                "MuseTalk 不支援情緒控制，exp_type='%s' 將被忽略", exp_type,
            )

        # 前置 VRAM 清理（MuseTalk 需要更多 VRAM）
        self._pre_launch_cleanup()

        # 處理非 ASCII 路徑
        ascii_img = to_ascii_temp(composite_image)
        ascii_audio = to_ascii_temp(audio_path)

        # 建立暫存輸出目錄
        result_dir = Path(tempfile.mkdtemp(prefix="musetalk_"))

        try:
            # 檢查 MuseTalk 環境
            if not self._musetalk_python.exists():
                raise FileNotFoundError(
                    f"MuseTalk venv Python 不存在：{self._musetalk_python}"
                )

            # 產生 MuseTalk inference YAML 配置
            # HIGH-01 修復：使用 json 安全序列化取代 f-string 建構
            # JSON 是合法 YAML 子集，避免 YAML 注入風險
            import json as _json
            yaml_config = result_dir / "inference_config.yaml"
            # Windows 路徑反斜線統一轉為正斜線
            yaml_data = {
                "singer_task": {
                    "video_path": str(ascii_img).replace("\\", "/"),
                    "audio_path": str(ascii_audio).replace("\\", "/"),
                }
            }
            yaml_config.write_text(
                _json.dumps(yaml_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # MuseTalk 模型路徑（根據版本）
            model_paths = {
                "v15": {
                    "unet_model_path": "./models/musetalkV15/unet.pth",
                    "unet_config": "./models/musetalkV15/musetalk.json",
                },
                "v1": {
                    "unet_model_path": "./models/musetalk/pytorch_model.bin",
                    "unet_config": "./models/musetalk/musetalk.json",
                },
            }
            model_cfg = model_paths.get(
                self._musetalk_version, model_paths["v15"],
            )

            cmd = [
                str(self._musetalk_python),
                "-m", "scripts.inference",
                "--inference_config", str(yaml_config),
                "--unet_model_path", model_cfg["unet_model_path"],
                "--unet_config", model_cfg["unet_config"],
                "--version", self._musetalk_version,
                "--result_dir", str(result_dir),
                "--batch_size", "4",
                "--use_float16",
            ]

            _logger.info("MuseTalk 命令：%s", " ".join(cmd))

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._MUSETALK_TIMEOUT,
                cwd=str(self.musetalk_dir),
            )

            if result.returncode != 0:
                _logger.error(
                    "MuseTalk 推論失敗（exit=%d）：%s",
                    result.returncode,
                    result.stderr[-500:] if result.stderr else "無 stderr",
                )
                raise RuntimeError(
                    f"MuseTalk 推論失敗（exit={result.returncode}）"
                )

            # 尋找產出 MP4（MuseTalk 存在 result_dir/<version>/ 下）
            mp4_files = list(result_dir.rglob("*.mp4"))
            if not mp4_files:
                raise RuntimeError(
                    f"MuseTalk 未產出影片（搜尋：{result_dir}）"
                )

            musetalk_output = mp4_files[0]
            _logger.info("MuseTalk 產出：%s", musetalk_output)

            # 搬移到目標路徑
            if output_path.exists():
                output_path.unlink()
            shutil.move(str(musetalk_output), str(output_path))

            size_mb = output_path.stat().st_size / (1024 ** 2)
            _logger.info(
                "MuseTalk 渲染完成：%s（%.2f MB）",
                output_path, size_mb,
            )
            return output_path, "musetalk"

        except subprocess.TimeoutExpired:
            _logger.error("MuseTalk 推論超時（>%ds）", self._MUSETALK_TIMEOUT)
            raise RuntimeError(
                f"MuseTalk 推論超時（>{self._MUSETALK_TIMEOUT}s）"
            )

        finally:
            # 清理暫存檔案
            cleanup_temp(ascii_img)
            cleanup_temp(ascii_audio)
            # 清理暫存輸出目錄（忽略錯誤）
            shutil.rmtree(str(result_dir), ignore_errors=True)

    def _render_liveportrait_musetalk(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
        exp_type: str = "neutral",
    ) -> tuple[Path, str]:
        """
        V3.1 混合管線：LivePortrait 自然動態影片 + MuseTalk 嘴唇同步。

        Phase A: LivePortrait 批量 retarget（自然動態影片，~1.5GB VRAM）
          - NaturalMotionEngine 生成逐幀表情參數（眨眼/頭部/眉毛/眼球）
          - LivePortrait 批量 retarget 產出 motion.mp4
        閘門:    VRAM 安全檢查 + 強制清理
        Phase B: MuseTalk inference（以動態影片為輸入，~8.2GB VRAM）

        降級策略：
        - LivePortrait 失敗 → 跳過動態，直接用靜態原圖餵 MuseTalk
        - MuseTalk 也失敗 → fallback 為 EDTalk
        """
        from src.singer_agent.audio_preprocessor import EMOTION_LIVEPORTRAIT_MAP
        from src.singer_agent.liveportrait_adapter import LivePortraitAdapter
        from src.singer_agent.natural_motion import (
            NaturalMotionEngine,
            get_audio_duration_seconds,
        )

        _logger.info(
            "開始 LivePortrait+MuseTalk V3.1 管線（exp_type=%s）", exp_type,
        )

        # Phase A: LivePortrait 自然動態影片
        # 降級預設：使用靜態原圖（與 V3.0 相同行為）
        intermediate_source = composite_image
        lp_output_dir: Path | None = None
        use_motion_video = False
        head_motion_params: list[tuple[float, float, float]] = []
        motion_fps = 10

        try:
            self._pre_launch_cleanup()

            adapter = LivePortraitAdapter(
                liveportrait_dir=self.liveportrait_dir,
            )

            # 取得基礎表情參數（來自情緒映射）
            base_expression = EMOTION_LIVEPORTRAIT_MAP.get(
                exp_type, EMOTION_LIVEPORTRAIT_MAP["neutral"],
            )

            # 取得音訊時長
            duration = get_audio_duration_seconds(str(audio_path))
            _logger.info("音訊時長：%.1f 秒", duration)

            # 生成自然動作序列（10fps）
            motion_fps = 10
            engine = NaturalMotionEngine(seed=42)
            motion_frames = engine.generate_sequence(
                duration_seconds=duration,
                fps=motion_fps,
                base_expression=base_expression,
            )

            _logger.info(
                "自然動作序列已生成：%d 幀 @ %dfps",
                len(motion_frames), motion_fps,
            )

            # ★ LivePortrait 只處理表情（頭部歸零）
            # 頭部旋轉由 MuseTalk 後的 2D 後處理完成
            from dataclasses import replace as dc_replace
            expression_only_frames = [
                dc_replace(f, head_pitch=0.0, head_yaw=0.0, head_roll=0.0)
                for f in motion_frames
            ]

            # 保存頭部動態參數供後處理用
            head_motion_params = [
                (f.head_pitch, f.head_yaw, f.head_roll)
                for f in motion_frames
            ]

            # 建立暫存目錄
            lp_output_dir = Path(tempfile.mkdtemp(prefix="liveportrait_"))

            # 批量 retarget → 表情動態影片（無頭部旋轉）
            motion_video = adapter.retarget_video(
                source_image=composite_image,
                frames=expression_only_frames,
                output_dir=lp_output_dir,
                fps=motion_fps,
            )

            intermediate_source = motion_video
            use_motion_video = True
            _logger.info(
                "LivePortrait 表情影片完成：%s", motion_video,
            )

        except Exception as exc:
            _logger.warning(
                "LivePortrait 動態影片失敗（%s），降級為靜態圖片 MuseTalk",
                exc,
            )
            # intermediate_source 保持為原始 composite_image

        # VRAM 閘門：Phase A → Phase B
        self._vram_gate("LivePortrait -> MuseTalk")

        # Phase B: MuseTalk 嘴唇同步
        try:
            result = self._render_musetalk(
                intermediate_source, audio_path, output_path,
                exp_type=exp_type,
            )
            render_mode = "liveportrait_musetalk" if use_motion_video else "musetalk"

            # Phase C: 2D 頭部動態後處理
            if use_motion_video and head_motion_params:
                try:
                    final_path = self._apply_head_motion_2d(
                        video_path=Path(result[0]),
                        head_params=head_motion_params,
                        motion_fps=motion_fps,
                    )
                    _logger.info("2D 頭部動態後處理完成：%s", final_path)
                    return str(final_path), render_mode
                except Exception as exc:
                    _logger.warning(
                        "2D 頭部動態後處理失敗（%s），使用無頭動版本",
                        exc,
                    )

            return result[0], render_mode
        except Exception as exc:
            _logger.warning(
                "MuseTalk 失敗（%s），降級為 EDTalk", exc,
            )
            return self._render_edtalk(
                composite_image, audio_path, output_path,
                exp_type=exp_type,
            )
        finally:
            # 清理 LivePortrait 暫存目錄（防止 tempfile leak）
            if lp_output_dir and lp_output_dir.exists():
                shutil.rmtree(str(lp_output_dir), ignore_errors=True)

    def _apply_head_motion_2d(
        self,
        video_path: Path,
        head_params: list[tuple[float, float, float]],
        motion_fps: int = 10,
    ) -> Path:
        """
        2D 頭部動態後處理（僅旋轉頭部區域，背景不動）。

        在 MuseTalk 產出的影片上，偵測臉部區域後建立橢圓漸層遮罩，
        僅對頭部區域套用 2D 仿射旋轉，背景和身體保持靜止。

        LivePortrait + MuseTalk 管線無法保留頭部旋轉
        （MuseTalk face stabilization 會抹平），
        因此頭部動態改由後處理階段完成。

        Args:
            video_path: MuseTalk 產出的影片路徑
            head_params: 每幀 (pitch, yaw, roll) 列表（motion_fps 取樣）
            motion_fps: head_params 的幀率

        Returns:
            後處理完成的影片路徑（原地覆寫）
        """
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"無法開啟影片：{video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        _logger.info(
            "2D 頭部動態：%d 幀 @ %.1ffps（%dx%d），"
            "motion 參數 %d 幀 @ %dfps",
            total_frames, video_fps, w, h,
            len(head_params), motion_fps,
        )

        # ── Step 1: 在第一幀偵測臉部區域 ──
        ret, first_frame = cap.read()
        if not ret:
            raise RuntimeError(f"無法讀取影片第一幀：{video_path}")

        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50),
        )

        if len(faces) > 0:
            # 取最大臉
            fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            # 頭部橢圓中心（略偏上方，涵蓋髮型）
            head_cx = fx + fw // 2
            head_cy = fy + fh // 2 - int(fh * 0.15)
            # ★ 橢圓半徑要夠大，完全包覆頭部+頭髮+耳朵
            # 這樣 mask=1.0 的區域涵蓋整顆頭，羽化過渡帶
            # 落在肩膀/背景上（無臉部特徵 → 不會有殘影）
            head_rx = int(fw * 1.4)
            head_ry = int(fh * 1.3)
            # 旋轉軸心在下巴/脖子處（自然的頭部旋轉支點）
            rot_cx = float(head_cx)
            rot_cy = float(fy + fh)
            _logger.info(
                "臉部偵測成功：bbox=(%d,%d,%d,%d) → "
                "頭部中心=(%d,%d) 半徑=(%d,%d) 旋轉軸=(%d,%d)",
                fx, fy, fw, fh, head_cx, head_cy,
                head_rx, head_ry, int(rot_cx), int(rot_cy),
            )
        else:
            # 降級：假設臉在畫面上半部中央
            head_cx = w // 2
            head_cy = h // 4
            head_rx = w // 3
            head_ry = h // 4
            rot_cx = float(w // 2)
            rot_cy = float(h // 2)
            _logger.warning(
                "未偵測到臉部，使用預設頭部區域："
                "中心=(%d,%d) 半徑=(%d,%d)",
                head_cx, head_cy, head_rx, head_ry,
            )

        # ── Step 2: 建立橢圓漸層遮罩 ──
        # 頭部區域=1.0（完全套用旋轉），邊緣漸變到 0.0（保持原始）
        mask = np.zeros((h, w), dtype=np.float32)
        cv2.ellipse(
            mask, (head_cx, head_cy), (head_rx, head_ry),
            0, 0, 360, 1.0, -1,
        )
        # 高斯模糊實現羽化邊緣（適度模糊，避免銳利分界線但不要太寬）
        blur_size = max(head_rx, head_ry) // 4 * 2 + 1  # 橢圓半徑的 1/4
        blur_size = max(blur_size, 21)  # 最小 21
        blur_size = min(blur_size, 101)  # 最大 101（避免過寬的過渡帶）
        mask = cv2.GaussianBlur(mask, (blur_size, blur_size), blur_size / 4)
        # 擴展到 3 通道
        mask_3ch = np.stack([mask, mask, mask], axis=-1)

        # ── Step 3: 逐幀處理 ──
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        output_path = video_path.with_name("motion_head.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(output_path), fourcc, video_fps, (w, h))

        for i in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break

            # 將影片幀 index 映射到 motion_fps 的參數 index
            t = i / video_fps
            param_idx = min(int(t * motion_fps), len(head_params) - 1)
            pitch, yaw, roll = head_params[param_idx]

            # 2D 仿射變換（以脖子為軸心旋轉）：
            # - roll → 旋轉角度（頭部傾斜）
            # - yaw → 水平平移（左右轉頭）
            # - pitch → 垂直平移（抬低頭）
            angle = roll
            tx = yaw * 2.0
            ty = -pitch * 1.5

            M = cv2.getRotationMatrix2D((rot_cx, rot_cy), angle, 1.0)
            M[0, 2] += tx
            M[1, 2] += ty

            # 旋轉整個畫面（暫存用）
            rotated = cv2.warpAffine(
                frame, M, (w, h),
                borderMode=cv2.BORDER_REPLICATE,
            )

            # ★ 核心：用遮罩混合 — 頭部用旋轉版，背景用原始版
            frame_f = frame.astype(np.float32)
            rotated_f = rotated.astype(np.float32)
            blended = rotated_f * mask_3ch + frame_f * (1.0 - mask_3ch)
            writer.write(blended.astype(np.uint8))

        cap.release()
        writer.release()

        # 用 ffmpeg 合併原始音軌 + H.264 重新編碼（mp4v 太大，Telegram 限 50MB）
        final_path = video_path.with_name("motion_head_audio.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(output_path),
            "-i", str(video_path),
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-map", "0:v:0",
            "-map", "1:a:0?",
            str(final_path),
        ]
        try:
            subprocess.run(
                cmd, capture_output=True, timeout=600,
                encoding="utf-8", errors="replace",
            )
        except Exception:
            final_path = output_path

        # 覆寫原始檔案
        import os
        if final_path.exists():
            os.replace(str(final_path), str(video_path))
        elif output_path.exists():
            os.replace(str(output_path), str(video_path))

        # 清理暫存
        for tmp in [output_path, final_path]:
            if tmp.exists() and tmp != video_path:
                tmp.unlink(missing_ok=True)

        return video_path

    def _vram_gate(self, checkpoint_name: str) -> None:
        """
        VRAM 分時管控閘門。

        在兩個 GPU 模型之間強制執行 VRAM 清理 + 安全檢查，
        確保下一個模型有足夠 VRAM。
        """
        from src.singer_agent.vram_monitor import (
            free_comfyui_models, force_cleanup, log_vram, check_vram_safety,
        )

        _logger.info("VRAM 閘門：%s", checkpoint_name)
        force_cleanup()
        log_vram(checkpoint_name)

        if not check_vram_safety(checkpoint_name):
            _logger.warning(
                "VRAM 閘門 '%s' 安全檢查未通過，嘗試卸載 ComfyUI",
                checkpoint_name,
            )
            free_comfyui_models(
                getattr(config, "COMFYUI_URL", "http://localhost:8188"),
            )
            force_cleanup()
            if not check_vram_safety(f"{checkpoint_name} (retry)"):
                _logger.error(
                    "VRAM 閘門 '%s' 二次檢查仍未通過，強制繼續但可能 OOM",
                    checkpoint_name,
                )
                # 記錄警告但不阻擋（降級策略會在 OOM 時 fallback）
                # 生產環境若嚴格要求可改為 raise RuntimeError

    def _render_ffmpeg(
        self,
        composite_image: Path,
        audio_path: Path,
        output_path: Path,
    ) -> tuple[Path, str]:
        """透過 FFmpeg 建立靜態圖片 + 音訊影片（降級方案）。"""
        _logger.info("開始 FFmpeg 靜態渲染")

        cmd = [
            str(self.ffmpeg_bin),
            "-y",
            "-loop", "1",
            "-i", str(composite_image),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output_path),
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg 靜態渲染超時（>300s）")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"FFmpeg 靜態渲染失敗（exit={e.returncode}）"
            )

        _logger.info("FFmpeg 靜態渲染完成：%s", output_path)
        return output_path, "ffmpeg_static"
