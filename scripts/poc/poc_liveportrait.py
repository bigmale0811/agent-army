"""
LivePortrait PoC 壓測腳本
========================
目的：驗證 LivePortrait 在 RTX 5070 (12GB VRAM) 上的可用性

測試項目：
1. 基本推理：源圖 + driving video -> 動畫影片
2. VRAM 峰值量測
3. 執行時間
4. 輸出品質（解析度、fps）

用法：
    cd D:\\Projects\\LivePortrait
    liveportrait_env\\Scripts\\python.exe D:\\Projects\\agent-army\\scripts\\poc\\poc_liveportrait.py
"""

import os
import sys
import time
import threading

# Windows cp950 編碼修復
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 將 LivePortrait 加入 sys.path
LIVEPORTRAIT_DIR = r"D:\Projects\LivePortrait"
sys.path.insert(0, LIVEPORTRAIT_DIR)
os.chdir(LIVEPORTRAIT_DIR)

import torch
import numpy as np


# === VRAM 監控 Thread ===
class VRAMMonitor:
    """背景執行緒，每秒記錄 VRAM 使用量"""

    def __init__(self):
        self.peak_mb = 0
        self.baseline_mb = 0
        self.running = False
        self._thread = None

    def start(self):
        if not torch.cuda.is_available():
            print("[WARN] CUDA not available, skipping VRAM monitor")
            return

        self.baseline_mb = torch.cuda.memory_allocated(0) / 1024 / 1024
        torch.cuda.reset_peak_memory_stats(0)
        self.running = True
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()

    def _monitor(self):
        while self.running:
            current_mb = torch.cuda.memory_allocated(0) / 1024 / 1024
            if current_mb > self.peak_mb:
                self.peak_mb = current_mb
            time.sleep(0.5)

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)

        # 也用 PyTorch 內建的 peak 統計
        pytorch_peak_mb = torch.cuda.max_memory_allocated(0) / 1024 / 1024
        self.peak_mb = max(self.peak_mb, pytorch_peak_mb)

    def report(self):
        delta = self.peak_mb - self.baseline_mb
        return {
            "baseline_mb": round(self.baseline_mb, 1),
            "peak_mb": round(self.peak_mb, 1),
            "delta_mb": round(delta, 1),
        }


def test_basic_inference():
    """測試 1：基本推理 -- 源圖 + driving video"""

    print("\n" + "=" * 60)
    print("[TEST 1] Basic Inference (source image + driving video)")
    print("=" * 60)

    from src.config.inference_config import InferenceConfig
    from src.config.crop_config import CropConfig
    from src.live_portrait_pipeline import LivePortraitPipeline
    from src.config.argument_config import ArgumentConfig

    # 設定
    source_img = os.path.join(LIVEPORTRAIT_DIR, "assets", "examples", "source", "s0.jpg")
    driving_video = os.path.join(LIVEPORTRAIT_DIR, "assets", "examples", "driving", "d0.mp4")
    output_dir = os.path.join(LIVEPORTRAIT_DIR, "results", "poc")
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(source_img):
        print(f"[ERROR] Source image not found: {source_img}")
        return None
    if not os.path.exists(driving_video):
        print(f"[ERROR] Driving video not found: {driving_video}")
        return None

    print(f"  Source: {source_img}")
    print(f"  Driving: {driving_video}")
    print(f"  Output dir: {output_dir}")

    # 建立 config
    inference_cfg = InferenceConfig()
    crop_cfg = CropConfig()

    # 啟動 VRAM 監控
    monitor = VRAMMonitor()
    monitor.start()

    # 載入 pipeline
    t_load_start = time.time()
    pipeline = LivePortraitPipeline(
        inference_cfg=inference_cfg,
        crop_cfg=crop_cfg
    )
    t_load = time.time() - t_load_start
    print(f"  [TIME] Model load: {t_load:.1f}s")

    # 執行推理
    # 建立模擬的 args 物件
    class SimpleArgs:
        def __init__(self):
            self.source = source_img
            self.driving = driving_video
            self.output_dir = output_dir
            self.flag_relative_motion = True
            self.flag_do_crop = True
            self.flag_pasteback = True
            self.flag_do_rot = True
            self.driving_multiplier = 1.0
            self.flag_stitching = True
            self.flag_eye_retargeting = False
            self.flag_lip_retargeting = False
            self.animation_region = "all"
            self.flag_write_result = True
            self.flag_write_gif = False
            self.output_fps = 25
            self.flag_source_video_eye_retargeting = False
            self.driving_option = "pose-friendly"
            self.driving_smooth_observation_variance = 3e-7

    args = SimpleArgs()

    t_infer_start = time.time()
    try:
        pipeline.execute(args)
        t_infer = time.time() - t_infer_start
        print(f"  [TIME] Inference: {t_infer:.1f}s")
    except Exception as e:
        t_infer = time.time() - t_infer_start
        print(f"  [FAIL] Inference failed ({t_infer:.1f}s): {e}")
        import traceback
        traceback.print_exc()
        monitor.stop()
        return {"error": str(e), "vram": monitor.report()}

    # 停止 VRAM 監控
    monitor.stop()
    vram = monitor.report()

    # 檢查輸出
    output_files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
    output_info = {}
    if output_files:
        output_path = os.path.join(output_dir, output_files[-1])
        import cv2
        cap = cv2.VideoCapture(output_path)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        output_info = {
            "path": output_path,
            "resolution": f"{w}x{h}",
            "fps": fps,
            "frames": frames,
            "duration_s": round(frames / fps, 1) if fps > 0 else 0,
        }
        print(f"  [OUTPUT] {output_path}")
        print(f"  [OUTPUT] Resolution: {w}x{h}, {fps}fps, {frames} frames ({output_info['duration_s']}s)")

    result = {
        "test": "basic_inference",
        "model_load_time_s": round(t_load, 1),
        "inference_time_s": round(t_infer, 1),
        "vram": vram,
        "output": output_info,
    }

    print(f"\n  [VRAM] Results:")
    print(f"     Baseline: {vram['baseline_mb']} MB")
    print(f"     Peak:     {vram['peak_mb']} MB")
    print(f"     Delta:    {vram['delta_mb']} MB")

    # 釋放 GPU 記憶體
    del pipeline
    torch.cuda.empty_cache()

    return result


def main():
    print("=" * 60)
    print("LivePortrait PoC Stress Test")
    print("=" * 60)

    # 環境資訊
    print(f"\n[ENV] Python: {sys.version.split()[0]}")
    print(f"[ENV] PyTorch: {torch.__version__}")
    print(f"[ENV] CUDA: {torch.version.cuda}")
    if torch.cuda.is_available():
        print(f"[ENV] GPU: {torch.cuda.get_device_name(0)}")
        props = torch.cuda.get_device_properties(0)
        print(f"[ENV] VRAM: {props.total_memory / 1024**3:.1f} GB")
    else:
        print("[ERROR] CUDA not available!")
        return

    # 檢查模型權重
    weights_dir = os.path.join(LIVEPORTRAIT_DIR, "pretrained_weights")
    if not os.path.exists(weights_dir) or len(os.listdir(weights_dir)) <= 1:
        print(f"\n[ERROR] Model weights not found! Run:")
        print(f"  huggingface-cli download KlingTeam/LivePortrait --local-dir pretrained_weights")
        return

    results = {}

    # 測試 1：基本推理
    r1 = test_basic_inference()
    if r1:
        results["basic_inference"] = r1

    # === 最終報告 ===
    print("\n" + "=" * 60)
    print("PoC FINAL REPORT")
    print("=" * 60)

    for name, r in results.items():
        print(f"\n  [{name}]:")
        if "error" in r:
            print(f"     [FAIL] Error: {r['error']}")
        else:
            print(f"     Model load: {r.get('model_load_time_s', 'N/A')}s")
            print(f"     Inference:  {r.get('inference_time_s', 'N/A')}s")
            vram = r.get("vram", {})
            print(f"     VRAM peak:  {vram.get('peak_mb', 'N/A')} MB")
            print(f"     VRAM delta: {vram.get('delta_mb', 'N/A')} MB")
            output = r.get("output", {})
            if output:
                print(f"     Output:     {output.get('resolution', 'N/A')}, {output.get('fps', 'N/A')}fps")
                print(f"     File:       {output.get('path', 'N/A')}")

    # VRAM 安全判定
    if results:
        valid_results = [r for r in results.values() if "error" not in r]
        if valid_results:
            max_vram = max(
                r.get("vram", {}).get("peak_mb", 0) for r in valid_results
            )
            if max_vram > 0:
                safe = "PASS - SAFE" if max_vram < 10000 else "WARN - HIGH"
                redline = "PASS - WITHIN" if max_vram < 12000 else "FAIL - EXCEEDED"
                print(f"\n  [10GB CHECK] VRAM peak {max_vram:.0f} MB -> {safe}")
                print(f"  [12GB CHECK] VRAM peak {max_vram:.0f} MB -> {redline}")


if __name__ == "__main__":
    main()
