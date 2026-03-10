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
        V3.0 混合管線：LivePortrait 表情注入 + MuseTalk 嘴唇同步。

        Phase A: LivePortrait retarget（~15s, ~1.5GB VRAM）
        閘門:    VRAM 安全檢查 + 強制清理
        Phase B: MuseTalk inference（~25min, ~8.2GB VRAM）

        降級策略：
        - LivePortrait 失敗 → 跳過表情，直接用原圖餵 MuseTalk
        - MuseTalk 也失敗 → fallback 為 EDTalk
        """
        from src.singer_agent.audio_preprocessor import EMOTION_LIVEPORTRAIT_MAP
        from src.singer_agent.liveportrait_adapter import LivePortraitAdapter

        _logger.info(
            "開始 LivePortrait+MuseTalk 混合管線（exp_type=%s）", exp_type,
        )

        # Phase A: LivePortrait 表情注入
        intermediate_image = composite_image  # 降級預設：使用原圖
        lp_output_dir: Path | None = None  # 追蹤暫存目錄，確保清理

        try:
            self._pre_launch_cleanup()

            adapter = LivePortraitAdapter(
                liveportrait_dir=self.liveportrait_dir,
            )

            # 取得表情參數
            expression = EMOTION_LIVEPORTRAIT_MAP.get(
                exp_type, EMOTION_LIVEPORTRAIT_MAP["neutral"],
            )

            # 建立暫存目錄（使用模組層級 tempfile，避免重複 import）
            lp_output_dir = Path(tempfile.mkdtemp(prefix="liveportrait_"))

            intermediate_image = adapter.retarget(
                source_image=composite_image,
                expression=expression,
                output_dir=lp_output_dir,
            )
            _logger.info(
                "LivePortrait 表情注入完成：%s", intermediate_image,
            )
        except Exception as exc:
            _logger.warning(
                "LivePortrait 失敗（%s），降級為純 MuseTalk（無表情）", exc,
            )
            # intermediate_image 保持為原始 composite_image

        # VRAM 閘門：Phase A → Phase B
        self._vram_gate("LivePortrait -> MuseTalk")

        # Phase B: MuseTalk 嘴唇同步（複用既有方法）
        try:
            return self._render_musetalk(
                intermediate_image, audio_path, output_path,
                exp_type=exp_type,
            )
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
