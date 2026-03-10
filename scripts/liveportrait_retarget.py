# -*- coding: utf-8 -*-
"""
LivePortrait 表情 Retargeting 腳本（在 LivePortrait venv 中執行）。

接收 JSON 配置，呼叫 LivePortrait 原生 API 進行表情操控。
支援兩種模式：
  - 靜態模式：產出帶表情的單張 PNG
  - 批量模式：產出帶自然動態的 MP4 影片

用法（靜態）：
    cd D:\\Projects\\LivePortrait
    liveportrait_env\\Scripts\\python.exe ^
        D:\\Projects\\agent-army\\scripts\\liveportrait_retarget.py ^
        --config retarget_config.json

用法（批量）：
    同上，config 中設定 "mode": "batch"

靜態 JSON 配置：
    {
        "source": "D:/tmp/singer_xxx.png",
        "output_dir": "D:/tmp/liveportrait_out/",
        "smile": 8.0, "eyebrow": 3.0, "wink": 0.0,
        "eyeball_direction_x": 0.0, "eyeball_direction_y": 0.0,
        "head_pitch": 0.0, "head_yaw": 0.0, "head_roll": 0.0
    }

批量 JSON 配置：
    {
        "source": "D:/tmp/singer_xxx.png",
        "output_dir": "D:/tmp/liveportrait_out/",
        "mode": "batch",
        "fps": 10,
        "frames": [
            {"smile": 0.0, "eyebrow": 0.0, "wink": 0.0, ...},
            {"smile": 0.0, "eyebrow": 0.2, "wink": 12.0, ...},
            ...
        ]
    }

輸出：
    靜態：{output_dir}/retargeted.png
    批量：{output_dir}/motion.mp4
"""

import argparse
import json
import os
import pathlib
import sys
import tempfile
import time

# Windows cp950 編碼修復
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 將 LivePortrait 加入 sys.path
LIVEPORTRAIT_DIR = os.path.dirname(os.path.abspath(__file__))
# 如果腳本不在 LivePortrait 目錄下，使用 cwd
if not os.path.exists(os.path.join(LIVEPORTRAIT_DIR, "src", "live_portrait_pipeline.py")):
    LIVEPORTRAIT_DIR = os.getcwd()

sys.path.insert(0, LIVEPORTRAIT_DIR)

import cv2
import numpy as np
import torch


# ─────────────────────────────────────────────────
# 表情參數名稱
# ─────────────────────────────────────────────────
_EXPRESSION_KEYS = [
    "smile", "eyebrow", "wink",
    "eyeball_direction_x", "eyeball_direction_y",
    "head_pitch", "head_yaw", "head_roll",
]


def load_pipeline():
    """載入 LivePortrait pipeline（含模型權重）。"""
    from src.config.inference_config import InferenceConfig
    from src.config.crop_config import CropConfig
    from src.gradio_pipeline import GradioPipeline
    from src.config.argument_config import ArgumentConfig

    inference_cfg = InferenceConfig()
    crop_cfg = CropConfig()
    args = ArgumentConfig()

    pipeline = GradioPipeline(
        inference_cfg=inference_cfg,
        crop_cfg=crop_cfg,
        args=args,
    )
    return pipeline


def _apply_head_pose(pipeline, source_rgb, head_pitch, head_yaw, head_roll):
    """
    Phase 1: 套用頭部姿態 retargeting。

    使用 execute_image_retargeting() API 進行頭部旋轉，
    同時初始化 pipeline 的 source 特徵（f_s, x_s, x_s_info）。

    Returns:
        output_img (np.ndarray): 帶頭部姿態的 RGB 圖片
    """
    result = pipeline.execute_image_retargeting(
        input_image=source_rgb,
        input_lip_ratio=0.0,
        input_eye_ratio=0.0,
        input_head_pitch=head_pitch,
        input_head_yaw=head_yaw,
        input_head_roll=head_roll,
        retargeting_source_scale=1.0,
        flag_do_crop=True,
        flag_do_rot=True,
    )

    if isinstance(result, tuple):
        return result[0]
    return result


def _apply_expression_delta(pipeline, smile, eyebrow, wink, eyeball_x, eyeball_y):
    """
    Phase 2: 在 pipeline 已初始化的 source 上套用表情 delta。

    需要 pipeline 已經執行過 execute_image_retargeting()
    （以初始化 f_s, x_s, x_s_info 等內部狀態）。

    Returns:
        output_img (np.ndarray | None): 帶表情的 RGB 圖片，
                                        失敗時返回 None
    """
    # 檢查 pipeline 內部狀態是否可用
    if not hasattr(pipeline, 'source_lmk_crop') or pipeline.source_lmk_crop is None:
        print("[Expression Delta] WARNING: source_lmk_crop 不可用，跳過表情 delta")
        return None

    if not hasattr(pipeline, 'f_s') or pipeline.f_s is None:
        print("[Expression Delta] WARNING: f_s 不可用，跳過表情 delta")
        return None

    # 建構 delta_new 張量
    delta_new = torch.zeros(1, 21, 3).to(pipeline.live_portrait_wrapper.device)

    if smile != 0:
        pipeline.update_delta_new_smile(smile, delta_new)
    if eyebrow != 0:
        pipeline.update_delta_new_eyebrow(eyebrow, delta_new)
    if wink != 0:
        pipeline.update_delta_new_wink(wink, delta_new)
    if eyeball_x != 0 or eyeball_y != 0:
        pipeline.update_delta_new_eyeball_direction(
            eyeball_x, eyeball_y, delta_new,
        )

    x_s = pipeline.x_s
    f_s = pipeline.f_s
    x_s_info = pipeline.x_s_info

    # 合併 delta 到 keypoints
    x_d_new = x_s_info['kp'] + delta_new

    # 使用 stitching 確保自然銜接
    if hasattr(pipeline.live_portrait_wrapper, 'stitching'):
        x_d_new = pipeline.live_portrait_wrapper.stitching(x_s, x_d_new)

    # 生成圖片
    out = pipeline.live_portrait_wrapper.warp_decode(f_s, x_s, x_d_new)
    output_img = np.clip(
        out[0].cpu().numpy().transpose(1, 2, 0) * 255,
        0, 255,
    ).astype(np.uint8)

    return output_img


def _to_bgr(output_img):
    """RGB np.ndarray → BGR（cv2 格式）。"""
    if isinstance(output_img, np.ndarray) and len(output_img.shape) == 3:
        if output_img.shape[2] == 3:
            return cv2.cvtColor(output_img, cv2.COLOR_RGB2BGR)
    return output_img


def retarget_expression(pipeline, source_path, expression_params, output_dir):
    """
    對源圖套用表情參數（靜態模式，產出單張 PNG）。

    V3.1 修復：分離頭部姿態與表情 delta 的 try-except，
    避免表情 delta 失敗時連頭部姿態結果也丟失。
    """
    os.makedirs(output_dir, exist_ok=True)

    source_img = cv2.imread(source_path)
    if source_img is None:
        raise FileNotFoundError(f"Source image not found: {source_path}")
    source_rgb = cv2.cvtColor(source_img, cv2.COLOR_BGR2RGB)

    smile = expression_params.get("smile", 0.0)
    eyebrow = expression_params.get("eyebrow", 0.0)
    wink = expression_params.get("wink", 0.0)
    eyeball_x = expression_params.get("eyeball_direction_x", 0.0)
    eyeball_y = expression_params.get("eyeball_direction_y", 0.0)
    head_pitch = expression_params.get("head_pitch", 0.0)
    head_yaw = expression_params.get("head_yaw", 0.0)
    head_roll = expression_params.get("head_roll", 0.0)

    print(f"[LivePortrait Retarget] Source: {source_path}")
    print(f"[LivePortrait Retarget] Params: smile={smile}, eyebrow={eyebrow}, "
          f"wink={wink}, head=({head_pitch:.1f},{head_yaw:.1f},{head_roll:.1f})")

    # Phase 1: 頭部姿態 retargeting（分離的 try-except）
    output_img = source_rgb  # 降級預設

    try:
        output_img = _apply_head_pose(
            pipeline, source_rgb,
            head_pitch, head_yaw, head_roll,
        )
        print("[LivePortrait Retarget] Phase 1 (head pose): OK")
    except Exception as e:
        print(f"[LivePortrait Retarget] Phase 1 (head pose) FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Phase 2: 表情 delta（smile/eyebrow/wink/eyeball）
    has_expression = any([smile, eyebrow, wink, eyeball_x, eyeball_y])
    if has_expression:
        try:
            expr_img = _apply_expression_delta(
                pipeline, smile, eyebrow, wink, eyeball_x, eyeball_y,
            )
            if expr_img is not None:
                output_img = expr_img
                print("[LivePortrait Retarget] Phase 2 (expression delta): OK")
            else:
                print("[LivePortrait Retarget] Phase 2 (expression delta): "
                      "SKIPPED (pipeline state not available)")
        except Exception as e:
            print(f"[LivePortrait Retarget] Phase 2 (expression delta) FAILED: {e}")
            import traceback
            traceback.print_exc()
            # 保留 Phase 1 的結果（頭部姿態仍有效）

    # 儲存結果
    output_path = os.path.join(output_dir, "retargeted.png")
    output_bgr = _to_bgr(output_img)
    cv2.imwrite(output_path, output_bgr)

    print(f"[LivePortrait Retarget] Output: {output_path}")
    return output_path


def retarget_batch(pipeline, source_path, frames_config, output_dir, fps=10):
    """
    批量 retarget：對同一源圖套用多組表情參數，產出 MP4 影片。

    每幀皆使用 execute_image_retargeting() + delta_new 方式處理，
    確保頭部姿態 + 表情均正確套用。

    Args:
        pipeline: 已載入的 GradioPipeline
        source_path: 源圖路徑
        frames_config: 每幀的表情參數列表 [{"smile": ..., "eyebrow": ..., ...}, ...]
        output_dir: 輸出目錄
        fps: 影片幀率（預設 10）

    Returns:
        輸出影片路徑（str）
    """
    os.makedirs(output_dir, exist_ok=True)

    source_img = cv2.imread(source_path)
    if source_img is None:
        raise FileNotFoundError(f"Source image not found: {source_path}")
    source_rgb = cv2.cvtColor(source_img, cv2.COLOR_BGR2RGB)

    total_frames = len(frames_config)
    video_path = os.path.join(output_dir, "motion.mp4")

    print(f"[LivePortrait Batch] 開始批量 retarget：{total_frames} 幀 @ {fps}fps")
    print(f"[LivePortrait Batch] 預計時長：{total_frames / fps:.1f}s")

    writer = None
    t_start = time.time()
    failed_count = 0

    for i, params in enumerate(frames_config):
        # 提取表情參數
        head_pitch = params.get("head_pitch", 0.0)
        head_yaw = params.get("head_yaw", 0.0)
        head_roll = params.get("head_roll", 0.0)
        smile = params.get("smile", 0.0)
        eyebrow = params.get("eyebrow", 0.0)
        wink = params.get("wink", 0.0)
        eyeball_x = params.get("eyeball_direction_x", 0.0)
        eyeball_y = params.get("eyeball_direction_y", 0.0)

        frame_img = source_rgb  # 降級預設

        # Phase 1: 頭部姿態
        try:
            frame_img = _apply_head_pose(
                pipeline, source_rgb,
                head_pitch, head_yaw, head_roll,
            )
        except Exception as e:
            if i == 0:
                print(f"[Batch] Frame 0 head pose FAILED: {e}")
            failed_count += 1

        # Phase 2: 表情 delta
        has_expression = any([smile, eyebrow, eyeball_x, eyeball_y])
        # 眨眼用 wink（透過 delta_new，不用 eye_ratio）
        if has_expression or wink != 0:
            try:
                expr_img = _apply_expression_delta(
                    pipeline, smile, eyebrow, wink, eyeball_x, eyeball_y,
                )
                if expr_img is not None:
                    frame_img = expr_img
            except Exception:
                if i == 0:
                    import traceback
                    traceback.print_exc()
                failed_count += 1

        # 轉換並寫入幀
        frame_bgr = _to_bgr(frame_img)

        if writer is None:
            h, w = frame_bgr.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(video_path, fourcc, fps, (w, h))
            print(f"[LivePortrait Batch] 輸出解析度：{w}x{h}")

        writer.write(frame_bgr)

        # 進度報告（每 100 幀或最後一幀）
        if (i + 1) % 100 == 0 or i == total_frames - 1:
            elapsed = time.time() - t_start
            fps_actual = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total_frames - i - 1) / fps_actual if fps_actual > 0 else 0
            print(
                f"[LivePortrait Batch] {i + 1}/{total_frames} "
                f"({fps_actual:.1f} fps, ETA {eta:.0f}s)"
            )

    if writer:
        writer.release()

    elapsed = time.time() - t_start
    print(
        f"[LivePortrait Batch] 完成：{video_path}\n"
        f"  幀數：{total_frames}，失敗：{failed_count}，"
        f"耗時：{elapsed:.1f}s"
    )

    return video_path


def _assert_safe_path(p: str, label: str) -> pathlib.Path:
    """驗證路徑是否在允許的根目錄內，防止路徑穿越攻擊。"""
    _ALLOWED_ROOTS = [
        pathlib.Path(tempfile.gettempdir()),
        pathlib.Path("D:/Projects/agent-army/data"),
        pathlib.Path("D:/Projects/LivePortrait"),
    ]
    resolved = pathlib.Path(p).resolve()
    for root in _ALLOWED_ROOTS:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise ValueError(
        f"Path traversal detected in {label}: {p!r} "
        f"(allowed roots: {[str(r) for r in _ALLOWED_ROOTS]})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="LivePortrait Expression Retarget")
    parser.add_argument("--config", required=True, help="JSON config file path")
    args = parser.parse_args()

    # 讀取配置
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # CRIT-03 修復：路徑安全驗證
    if "source" not in cfg:
        raise ValueError("JSON config missing required key: 'source'")
    if "output_dir" not in cfg:
        raise ValueError("JSON config missing required key: 'output_dir'")

    source_path = str(_assert_safe_path(cfg["source"], "source"))
    output_dir = str(_assert_safe_path(cfg["output_dir"], "output_dir"))

    # 載入 pipeline
    print("[LivePortrait Retarget] Loading pipeline...")
    pipeline = load_pipeline()
    print("[LivePortrait Retarget] Pipeline loaded.")

    # 偵測模式：批量 or 靜態
    mode = cfg.get("mode", "single")

    if mode == "batch":
        # 批量模式：產出影片
        frames = cfg.get("frames", [])
        if not frames:
            raise ValueError("Batch mode requires 'frames' array in config")
        fps = cfg.get("fps", 10)

        output_path = retarget_batch(
            pipeline, source_path, frames, output_dir, fps=fps,
        )
    else:
        # 靜態模式：產出單張 PNG
        expression_params = {
            k: cfg.get(k, 0.0) for k in _EXPRESSION_KEYS
        }
        output_path = retarget_expression(
            pipeline, source_path, expression_params, output_dir,
        )

    print(f"[LivePortrait Retarget] Done: {output_path}")


if __name__ == "__main__":
    main()
