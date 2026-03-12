"""Sprite Sheet 拆解器 — 根據 atlas JSON 將合圖拆為獨立圖片"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from PIL import Image
from slot_cloner.models.asset import SpriteFrame, SpriteSheet

logger = logging.getLogger(__name__)


class SpriteSplitter:
    """Sprite Sheet 拆解器

    支援 TexturePacker JSON (Hash/Array) 格式。
    將合圖拆解為獨立的 PNG 圖片。
    """

    def split(
        self,
        image_path: Path,
        atlas_path: Path,
        output_dir: Path,
    ) -> SpriteSheet:
        """拆解 Sprite Sheet

        Args:
            image_path: 合圖路徑
            atlas_path: atlas JSON 路徑
            output_dir: 輸出目錄（拆解後的獨立圖片）

        Returns:
            SpriteSheet 物件（含 frames 資訊）
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # 讀取 atlas JSON
        with open(atlas_path, encoding="utf-8") as f:
            atlas_data = json.load(f)

        # 解析 frames（支援 TexturePacker Hash 和 Array 格式）
        frames_data = self._parse_atlas(atlas_data)

        # 開啟合圖
        sheet_image = Image.open(image_path)

        frames: list[SpriteFrame] = []
        for frame_name, frame_info in frames_data.items():
            x = frame_info["x"]
            y = frame_info["y"]
            w = frame_info["w"]
            h = frame_info["h"]

            # 裁切並儲存
            cropped = sheet_image.crop((x, y, x + w, y + h))
            safe_name = self._safe_filename(frame_name)
            out_path = output_dir / f"{safe_name}.png"
            cropped.save(out_path, "PNG")

            frames.append(SpriteFrame(
                name=frame_name,
                x=x,
                y=y,
                width=w,
                height=h,
            ))
            logger.debug("拆解: %s → %s (%dx%d)", frame_name, out_path, w, h)

        logger.info("拆解完成: %d 個 frame 從 %s", len(frames), image_path.name)

        return SpriteSheet(
            name=image_path.stem,
            image_path=image_path,
            atlas_path=atlas_path,
            frames=tuple(frames),
        )

    @staticmethod
    def _parse_atlas(atlas_data: dict) -> dict[str, dict]:
        """解析 TexturePacker JSON 格式

        支援兩種格式：
        1. Hash 格式：{"frames": {"name": {"frame": {"x":0,"y":0,"w":64,"h":64}}}}
        2. Array 格式：{"frames": [{"filename":"name","frame":{"x":0,...}}]}
        """
        frames_raw = atlas_data.get("frames", {})
        result = {}

        if isinstance(frames_raw, dict):
            # Hash 格式
            for name, data in frames_raw.items():
                frame = data.get("frame", data)
                result[name] = {
                    "x": frame.get("x", 0),
                    "y": frame.get("y", 0),
                    "w": frame.get("w", frame.get("width", 0)),
                    "h": frame.get("h", frame.get("height", 0)),
                }
        elif isinstance(frames_raw, list):
            # Array 格式
            for item in frames_raw:
                name = item.get("filename", item.get("name", "unknown"))
                frame = item.get("frame", item)
                result[name] = {
                    "x": frame.get("x", 0),
                    "y": frame.get("y", 0),
                    "w": frame.get("w", frame.get("width", 0)),
                    "h": frame.get("h", frame.get("height", 0)),
                }

        return result

    @staticmethod
    def _safe_filename(name: str) -> str:
        """產生安全的檔名"""
        # 移除副檔名和路徑分隔符
        name = name.replace("\\", "/").split("/")[-1]
        name = name.rsplit(".", 1)[0] if "." in name else name
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
