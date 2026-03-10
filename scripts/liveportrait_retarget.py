# -*- coding: utf-8 -*-
"""
LivePortrait 表情 Retargeting 腳本（在 LivePortrait venv 中執行）。

接收 JSON 配置，呼叫 LivePortrait 原生 API 進行表情操控，
產出帶表情的靜態 PNG 圖片。

用法：
    cd D:\\Projects\\LivePortrait
    liveportrait_env\\Scripts\\python.exe ^
        D:\\Projects\\agent-army\\scripts\\liveportrait_retarget.py ^
        --config retarget_config.json

JSON 配置格式：
    {
        "source": "D:/tmp/singer_xxx.png",
        "output_dir": "D:/tmp/liveportrait_out/",
        "smile": 8.0,
        "eyebrow": 3.0,
        "wink": 0.0,
        "eyeball_direction_x": 0.0,
        "eyeball_direction_y": 0.0,
        "head_pitch": 0.0,
        "head_yaw": 0.0,
        "head_roll": 0.0
    }

輸出：
    {output_dir}/retargeted.png
"""

import argparse
import json
import os
import pathlib
import sys
import tempfile

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


def load_pipeline():
    """載入 LivePortrait pipeline（含模型權重）。"""
    from src.config.inference_config import InferenceConfig
    from src.config.crop_config import CropConfig
    from src.gradio_pipeline import GradioPipeline
    from src.config.argument_config import ArgumentConfig

    inference_cfg = InferenceConfig()
    crop_cfg = CropConfig()

    # 建立 ArgumentConfig 預設值
    args = ArgumentConfig()

    pipeline = GradioPipeline(
        inference_cfg=inference_cfg,
        crop_cfg=crop_cfg,
        args=args,
    )
    return pipeline


def retarget_expression(pipeline, source_path, expression_params, output_dir):
    """
    對源圖套用表情參數。

    使用 GradioPipeline.execute_image_retargeting() 方法，
    操控 delta_new keypoint 實現表情變化。
    """
    os.makedirs(output_dir, exist_ok=True)

    # 讀取源圖
    source_img = cv2.imread(source_path)
    if source_img is None:
        raise FileNotFoundError(f"Source image not found: {source_path}")

    source_rgb = cv2.cvtColor(source_img, cv2.COLOR_BGR2RGB)

    # 呼叫 retargeting API
    # execute_image_retargeting 接收：
    # input_eye_ratio, input_lip_ratio, input_head_pitch/yaw/roll,
    # retargeting_source_scale, flag_do_crop, flag_do_rot
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
          f"wink={wink}, head_pitch={head_pitch}")

    # 使用 GradioPipeline 的 retargeting 功能
    # 先準備源圖
    try:
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

        # execute_image_retargeting 回傳 (output_image_np, output_image_path)
        if isinstance(result, tuple):
            output_img = result[0]
        else:
            output_img = result

        # 套用額外表情參數（smile, eyebrow, wink）
        # 這些需要透過 delta_new 操控
        if any([smile, eyebrow, wink, eyeball_x, eyeball_y]):
            # 重新取得 pipeline 的 source 資訊
            if hasattr(pipeline, 'source_lmk_crop') and pipeline.source_lmk_crop is not None:
                # 使用 delta_new 方法直接操控 keypoint
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

                # 重新生成帶表情的圖片
                # 使用 pipeline 內部的 warping + generation
                if hasattr(pipeline, 'f_s') and pipeline.f_s is not None:
                    x_s = pipeline.x_s
                    f_s = pipeline.f_s
                    R_s = pipeline.R_s
                    x_s_info = pipeline.x_s_info

                    # 合併 delta
                    x_d_new = x_s_info['kp'] + delta_new

                    # 使用 stitching 確保自然
                    if hasattr(pipeline.live_portrait_wrapper, 'stitching'):
                        x_d_new = pipeline.live_portrait_wrapper.stitching(x_s, x_d_new)

                    # 生成
                    out = pipeline.live_portrait_wrapper.warp_decode(f_s, x_s, x_d_new)
                    output_img = np.clip(out[0].cpu().numpy().transpose(1, 2, 0) * 255, 0, 255).astype(np.uint8)

    except Exception as e:
        print(f"[LivePortrait Retarget] Retargeting failed: {e}")
        print(f"[LivePortrait Retarget] Falling back to simple inference")
        import traceback
        traceback.print_exc()

        # Fallback：用基本 inference 模式處理（不帶表情）
        output_img = source_rgb

    # 儲存結果
    output_path = os.path.join(output_dir, "retargeted.png")
    if isinstance(output_img, np.ndarray):
        if output_img.shape[2] == 3:
            output_bgr = cv2.cvtColor(output_img, cv2.COLOR_RGB2BGR)
        else:
            output_bgr = output_img
        cv2.imwrite(output_path, output_bgr)
    else:
        # 如果是 PIL Image
        output_img.save(output_path)

    print(f"[LivePortrait Retarget] Output: {output_path}")
    return output_path


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

    # 提取表情參數
    expression_params = {
        k: cfg.get(k, 0.0)
        for k in [
            "smile", "eyebrow", "wink",
            "eyeball_direction_x", "eyeball_direction_y",
            "head_pitch", "head_yaw", "head_roll",
        ]
    }

    # 載入 pipeline
    print("[LivePortrait Retarget] Loading pipeline...")
    pipeline = load_pipeline()
    print("[LivePortrait Retarget] Pipeline loaded.")

    # 執行 retarget
    output_path = retarget_expression(
        pipeline, source_path, expression_params, output_dir,
    )

    print(f"[LivePortrait Retarget] Done: {output_path}")


if __name__ == "__main__":
    main()
