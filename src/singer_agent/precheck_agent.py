# -*- coding: utf-8 -*-
"""Singer Agent — 預檢 Agent（v0.3）

在 SadTalker 動畫生成前，對所有素材執行品質驗證。

檢查項目：
    1. 合成圖尺寸/比例
    2. 人臉偵測
    3. SadTalker 可用性
    4. FFmpeg 可用性
    5. 音檔格式/長度
    6. Gemini 多模態審查（可選）

設計原則：
    預檢失敗不中斷流程，記錄警告讓使用者決定是否重做。
"""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import (
    PRECHECK_GEMINI_ENABLED,
    PRECHECK_MIN_FACE_RATIO,
    PRECHECK_MAX_AUDIO_DURATION,
    GEMINI_API_KEY,
)

logger = logging.getLogger(__name__)


@dataclass
class PrecheckResult:
    """預檢結果"""
    passed: bool = True
    checks: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    gemini_feedback: str = ""
    gemini_score: int = 0

    def summary(self) -> str:
        """產出預檢摘要文字"""
        status = "✅ 通過" if self.passed else "❌ 未通過"
        lines = [f"預檢結果：{status}"]

        if self.errors:
            lines.append(f"  錯誤（{len(self.errors)} 項）：")
            for e in self.errors:
                lines.append(f"    ❌ {e}")

        if self.warnings:
            lines.append(f"  警告（{len(self.warnings)} 項）：")
            for w in self.warnings:
                lines.append(f"    ⚠️ {w}")

        if self.gemini_feedback:
            lines.append(f"  🤖 Gemini 評分：{self.gemini_score}/10")
            lines.append(f"  💬 {self.gemini_feedback}")

        return "\n".join(lines)


class PrecheckAgent:
    """預檢 Agent — 影片生成前的素材驗證"""

    # =============================================================
    # 執行所有檢查
    # =============================================================

    async def run_all_checks(
        self,
        composite_image: str = "",
        audio_path: str = "",
        spec=None,
        skip_gemini: bool = False,
    ) -> PrecheckResult:
        """執行所有預檢項目

        Args:
            composite_image: 合成圖路徑
            audio_path: 音檔路徑
            spec: SongSpec 物件（供 Gemini 檢查用）
            skip_gemini: 跳過 Gemini 多模態檢查

        Returns:
            PrecheckResult 預檢結果
        """
        result = PrecheckResult()

        logger.info("🔎 開始預檢驗證...")

        # 1. 圖片規格
        if composite_image:
            img_check = self.check_image_spec(composite_image)
            result.checks["image"] = img_check
            if not img_check["passed"]:
                for issue in img_check.get("issues", []):
                    result.warnings.append(f"圖片: {issue}")

        # 2. 人臉偵測
        if composite_image:
            face_check = self.check_face_detection(composite_image)
            result.checks["face"] = face_check
            if not face_check["passed"]:
                result.errors.append("未偵測到人臉，SadTalker 可能無法運作")
                result.passed = False

        # 3. 音檔規格
        if audio_path:
            audio_check = self.check_audio_spec(audio_path)
            result.checks["audio"] = audio_check
            if not audio_check["passed"]:
                for issue in audio_check.get("issues", []):
                    result.errors.append(f"音檔: {issue}")
                    result.passed = False
            for w in audio_check.get("warnings", []):
                result.warnings.append(f"音檔: {w}")

        # 4. SadTalker 可用性
        st_check = self.check_sadtalker()
        result.checks["sadtalker"] = st_check
        if not st_check["passed"]:
            result.warnings.append("SadTalker 不可用，將降級為靜態 FFmpeg")

        # 5. FFmpeg 可用性
        ff_check = self.check_ffmpeg()
        result.checks["ffmpeg"] = ff_check
        if not ff_check["passed"]:
            result.errors.append("FFmpeg 不可用，無法合成影片")
            result.passed = False

        # 6. Gemini 多模態檢查（可選）
        use_gemini = (
            PRECHECK_GEMINI_ENABLED
            and not skip_gemini
            and composite_image
            and spec
            and GEMINI_API_KEY
        )
        if use_gemini:
            try:
                gemini_check = await self.check_with_gemini(
                    composite_image, spec
                )
                result.checks["gemini"] = gemini_check
                result.gemini_feedback = gemini_check.get("feedback", "")
                result.gemini_score = gemini_check.get("score", 0)
                if not gemini_check.get("passed", True):
                    result.warnings.append(
                        f"Gemini 審查: {gemini_check.get('feedback', '?')}"
                    )
            except Exception as e:
                logger.warning("⚠️ Gemini 檢查失敗: %s", e)

        status = "通過" if result.passed else "未通過"
        logger.info("🔎 預檢完成: %s（%d 警告, %d 錯誤）",
                     status, len(result.warnings), len(result.errors))
        return result

    # =============================================================
    # 個別檢查項目
    # =============================================================

    @staticmethod
    def check_image_spec(image_path: str) -> dict:
        """檢查圖片規格

        Returns:
            {"passed": bool, "width": int, "height": int,
             "aspect_ratio": str, "file_size_mb": float, "issues": []}
        """
        result = {
            "passed": True,
            "width": 0,
            "height": 0,
            "aspect_ratio": "",
            "file_size_mb": 0.0,
            "issues": [],
        }

        path = Path(image_path)
        if not path.exists():
            result["passed"] = False
            result["issues"].append(f"圖片不存在: {image_path}")
            return result

        try:
            from PIL import Image
            img = Image.open(str(path))
            result["width"] = img.width
            result["height"] = img.height
            result["file_size_mb"] = path.stat().st_size / 1024 / 1024

            # 計算比例
            ratio = img.width / img.height
            if abs(ratio - 16 / 9) < 0.05:
                result["aspect_ratio"] = "16:9"
            elif abs(ratio - 4 / 3) < 0.05:
                result["aspect_ratio"] = "4:3"
            elif abs(ratio - 1) < 0.05:
                result["aspect_ratio"] = "1:1"
            else:
                result["aspect_ratio"] = f"{ratio:.2f}:1"

            # 尺寸檢查
            if img.width < 512 or img.height < 512:
                result["issues"].append(
                    f"圖片太小 ({img.width}x{img.height})，建議至少 512x512"
                )

        except Exception as e:
            result["passed"] = False
            result["issues"].append(f"無法讀取圖片: {e}")

        if result["issues"]:
            result["passed"] = False

        return result

    @staticmethod
    def check_face_detection(image_path: str) -> dict:
        """人臉偵測（OpenCV Haar Cascade）

        Returns:
            {"passed": bool, "face_count": int, "face_area_ratio": float}
        """
        result = {
            "passed": False,
            "face_count": 0,
            "face_area_ratio": 0.0,
        }

        try:
            import cv2
            import numpy as np
            from PIL import Image

            img = Image.open(image_path).convert("RGB")
            cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
            )

            result["face_count"] = len(faces)
            result["passed"] = len(faces) > 0

            if len(faces) > 0:
                max_area = max(w * h for (x, y, w, h) in faces)
                total_area = img.width * img.height
                result["face_area_ratio"] = max_area / total_area

                if result["face_area_ratio"] < PRECHECK_MIN_FACE_RATIO:
                    logger.warning(
                        "人臉面積比太小: %.4f (最小 %.4f)",
                        result["face_area_ratio"],
                        PRECHECK_MIN_FACE_RATIO,
                    )

        except ImportError:
            logger.warning("OpenCV 未安裝，跳過人臉偵測")
            result["passed"] = True  # 無法偵測時不阻擋
        except Exception as e:
            logger.warning("人臉偵測失敗: %s", e)
            result["passed"] = True  # 失敗不阻擋

        return result

    @staticmethod
    def check_audio_spec(audio_path: str) -> dict:
        """檢查音檔規格

        Returns:
            {"passed": bool, "format": str, "duration_sec": float,
             "file_size_mb": float, "issues": [], "warnings": []}
        """
        result = {
            "passed": True,
            "format": "",
            "duration_sec": 0.0,
            "file_size_mb": 0.0,
            "issues": [],
            "warnings": [],
        }

        path = Path(audio_path)
        if not path.exists():
            result["passed"] = False
            result["issues"].append(f"音檔不存在: {audio_path}")
            return result

        result["format"] = path.suffix.lower().lstrip(".")
        result["file_size_mb"] = path.stat().st_size / 1024 / 1024

        # 格式檢查
        supported = {".mp3", ".wav", ".flac", ".m4a", ".ogg"}
        if path.suffix.lower() not in supported:
            result["passed"] = False
            result["issues"].append(
                f"不支援的格式: {path.suffix}（支援: {', '.join(supported)}）"
            )

        # 檔案大小警告
        if result["file_size_mb"] > 50:
            result["warnings"].append(
                f"音檔較大 ({result['file_size_mb']:.1f} MB)，處理可能較慢"
            )

        # 嘗試用 mutagen 取得時長（如果有安裝）
        try:
            import mutagen
            audio = mutagen.File(str(path))
            if audio and audio.info:
                result["duration_sec"] = audio.info.length
                if result["duration_sec"] > PRECHECK_MAX_AUDIO_DURATION:
                    result["warnings"].append(
                        f"音檔較長 ({result['duration_sec']:.0f}秒)，"
                        f"SadTalker 處理可能需要很久"
                    )
        except ImportError:
            pass  # mutagen 未安裝，跳過時長檢查
        except Exception:
            pass

        return result

    @staticmethod
    def check_sadtalker() -> dict:
        """檢查 SadTalker 可用性

        Returns:
            {"passed": bool, "inference_exists": bool,
             "checkpoints_exist": bool, "python_exists": bool}
        """
        try:
            from .sadtalker_runner import (
                is_sadtalker_available,
                SADTALKER_INFERENCE,
                SADTALKER_CHECKPOINTS,
            )
            from .config import SADTALKER_PYTHON

            return {
                "passed": is_sadtalker_available(),
                "inference_exists": SADTALKER_INFERENCE.exists(),
                "checkpoints_exist": SADTALKER_CHECKPOINTS.exists(),
                "python_exists": Path(SADTALKER_PYTHON).exists(),
            }
        except Exception as e:
            return {
                "passed": False,
                "inference_exists": False,
                "checkpoints_exist": False,
                "python_exists": False,
                "error": str(e),
            }

    @staticmethod
    def check_ffmpeg() -> dict:
        """檢查 FFmpeg 可用性

        Returns:
            {"passed": bool, "path": str, "version": str}
        """
        result = {"passed": False, "path": "", "version": ""}

        # 嘗試找 FFmpeg
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            # 檢查 WinGet 路徑
            winget = Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"
            if winget.exists():
                ffmpeg_path = str(winget)

        if ffmpeg_path:
            result["passed"] = True
            result["path"] = ffmpeg_path
            # 取得版本
            try:
                import subprocess
                proc = subprocess.run(
                    [ffmpeg_path, "-version"],
                    capture_output=True, text=True, timeout=10,
                )
                first_line = proc.stdout.splitlines()[0] if proc.stdout else ""
                result["version"] = first_line[:80]
            except Exception:
                result["version"] = "unknown"

        return result

    # =============================================================
    # Gemini 多模態檢查
    # =============================================================

    async def check_with_gemini(
        self,
        composite_image: str,
        spec,
    ) -> dict:
        """使用 Gemini Pro Vision 多模態檢查合成圖品質

        讓 Gemini 看一眼合成圖，檢查角色與背景是否協調。

        Args:
            composite_image: 合成圖路徑
            spec: SongSpec 物件

        Returns:
            {"passed": bool, "score": int, "feedback": str}
        """
        import json as json_module
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)

        # 讀取圖片
        img_path = Path(composite_image)
        img_data = img_path.read_bytes()

        prompt = (
            "你是專業的 MV 畫面品質檢查員。請檢查這張合成圖片是否適合用於音樂影片。\n\n"
            f"歌曲：{spec.title} - {spec.artist}\n"
            f"風格：{spec.genre} / {spec.mood}\n"
            f"預期場景：{spec.scene_description}\n\n"
            "請用 JSON 回答（不要加 markdown 標記）：\n"
            '{"score": 1-10, "character_visible": true/false, '
            '"style_match": true/false, "composition_ok": true/false, '
            '"feedback": "簡短中文建議"}'
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {"inline_data": {"mime_type": "image/png", "data": img_data}},
                prompt,
            ],
        )

        # 解析 JSON 回應
        text = response.text.strip()
        # 去除可能的 markdown 標記
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        try:
            data = json_module.loads(text)
        except json_module.JSONDecodeError:
            return {
                "passed": True,
                "score": 5,
                "feedback": text[:200],
            }

        score = data.get("score", 5)
        return {
            "passed": score >= 5,
            "score": score,
            "character_visible": data.get("character_visible", True),
            "style_match": data.get("style_match", True),
            "composition_ok": data.get("composition_ok", True),
            "feedback": data.get("feedback", ""),
        }
