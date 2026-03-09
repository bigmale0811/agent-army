#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MuseTalk PoC VRAM 壓測腳本

目的：驗證 MuseTalk 在 GFX 5070 (12GB VRAM) 上的可行性。
- 在 subprocess 中執行 MuseTalk 推論
- 在主進程開 thread 每 0.5 秒記錄 VRAM（透過 nvidia-smi）
- 測量 VRAM 峰值、執行時間、產出影片品質

使用方式：
    D:\\Projects\\MuseTalk\\musetalk_env\\Scripts\\python.exe ^
        D:\\Projects\\agent-army\\scripts\\poc\\poc_musetalk.py

    # 自訂素材
    D:\\Projects\\MuseTalk\\musetalk_env\\Scripts\\python.exe ^
        D:\\Projects\\agent-army\\scripts\\poc\\poc_musetalk.py ^
        --image path/to/face.jpg ^
        --audio path/to/audio.wav

    # 使用 v1.0 模型
    D:\\Projects\\MuseTalk\\musetalk_env\\Scripts\\python.exe ^
        D:\\Projects\\agent-army\\scripts\\poc\\poc_musetalk.py ^
        --version v1

前置條件：
    1. MuseTalk 已 clone 到 D:\\Projects\\MuseTalk
    2. musetalk_env 虛擬環境已建立且依賴已安裝
    3. 模型權重已下載到 D:\\Projects\\MuseTalk\\models\\
    4. ffmpeg 已安裝且在 PATH 中

作者：@Technology-Scout PoC
日期：2026-03-09
"""

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


# ============================================================
# 常數設定
# ============================================================
MUSETALK_DIR = Path(r"D:\Projects\MuseTalk")
MUSETALK_ENV_PYTHON = MUSETALK_DIR / "musetalk_env" / "Scripts" / "python.exe"

# 模型路徑（v1.0 和 v1.5）
MODEL_PATHS = {
    "v1": {
        "unet_model_path": "./models/musetalk/pytorch_model.bin",
        "unet_config": "./models/musetalk/musetalk.json",
        "version_arg": "v1",
    },
    "v15": {
        "unet_model_path": "./models/musetalkV15/unet.pth",
        "unet_config": "./models/musetalkV15/musetalk.json",
        "version_arg": "v15",
    },
}

# 預設測試素材（MuseTalk 內建示例）
DEFAULT_VIDEO = "data/video/yongen.mp4"
DEFAULT_AUDIO = "data/audio/yongen.wav"
DEFAULT_VERSION = "v15"

# VRAM 監控間隔（秒）
VRAM_POLL_INTERVAL = 0.5

# 推論超時（秒）
INFERENCE_TIMEOUT = 600


# ============================================================
# VRAM 監控器（背景 Thread）— 和 EDTalk PoC 共用邏輯
# ============================================================
class VRAMMonitor:
    """在背景 thread 中每隔固定時間以 nvidia-smi 記錄 GPU VRAM 使用量。"""

    def __init__(self, poll_interval: float = VRAM_POLL_INTERVAL, gpu_index: int = 0):
        self._poll_interval = poll_interval
        self._gpu_index = gpu_index
        self._stop_event = threading.Event()
        self._thread = None
        self._samples: list[dict] = []
        self._peak_used_mb: float = 0.0
        self._baseline_mb: float = 0.0

    def _query_nvidia_smi(self) -> dict:
        """透過 nvidia-smi 查詢 VRAM。"""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    f"--id={self._gpu_index}",
                    "--query-gpu=memory.used,memory.total,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                used = float(parts[0].strip())
                total = float(parts[1].strip())
                free = float(parts[2].strip())
                return {"used_mb": used, "total_mb": total, "free_mb": free}
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
            pass
        return {"used_mb": 0.0, "total_mb": 0.0, "free_mb": 0.0}

    def _poll_loop(self):
        """背景輪詢迴圈。"""
        while not self._stop_event.is_set():
            sample = self._query_nvidia_smi()
            sample["timestamp"] = time.time()
            self._samples.append(sample)
            if sample["used_mb"] > self._peak_used_mb:
                self._peak_used_mb = sample["used_mb"]
            self._stop_event.wait(self._poll_interval)

    def start(self):
        """啟動監控。先記錄基線 VRAM。"""
        baseline = self._query_nvidia_smi()
        self._baseline_mb = baseline["used_mb"]
        self._peak_used_mb = self._baseline_mb
        print(f"[VRAM Monitor] 基線: {self._baseline_mb:.0f} MB / {baseline['total_mb']:.0f} MB total")
        print(f"[VRAM Monitor] 每 {self._poll_interval}s 取樣一次，開始監控...")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> dict:
        """停止監控，回傳摘要。"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        delta_peak = self._peak_used_mb - self._baseline_mb
        summary = {
            "baseline_mb": round(self._baseline_mb, 1),
            "peak_used_mb": round(self._peak_used_mb, 1),
            "delta_peak_mb": round(delta_peak, 1),
            "num_samples": len(self._samples),
        }
        print(f"[VRAM Monitor] 已停止。共 {summary['num_samples']} 筆取樣。")
        return summary


# ============================================================
# 前置條件檢查
# ============================================================
def check_prerequisites(version: str) -> bool:
    """檢查 MuseTalk 環境、模型權重、素材是否就緒。"""
    print("\n" + "=" * 60)
    print("[前置檢查] 開始驗證 MuseTalk 環境...")
    print("=" * 60)

    all_ok = True

    # 1. MuseTalk 目錄
    if MUSETALK_DIR.exists():
        print(f"  [OK] MuseTalk 目錄存在: {MUSETALK_DIR}")
    else:
        print(f"  [FAIL] MuseTalk 目錄不存在: {MUSETALK_DIR}")
        all_ok = False

    # 2. musetalk_env Python
    if MUSETALK_ENV_PYTHON.exists():
        print(f"  [OK] musetalk_env Python: {MUSETALK_ENV_PYTHON}")
    else:
        print(f"  [FAIL] musetalk_env Python 不存在: {MUSETALK_ENV_PYTHON}")
        all_ok = False

    # 3. 模型權重
    model_cfg = MODEL_PATHS.get(version, MODEL_PATHS["v15"])
    unet_path = MUSETALK_DIR / model_cfg["unet_model_path"]
    unet_config = MUSETALK_DIR / model_cfg["unet_config"]

    for label, path in [("UNet 模型", unet_path), ("UNet 配置", unet_config)]:
        if path.exists():
            size_mb = path.stat().st_size / (1024 ** 2)
            print(f"  [OK] {label}: {path.name} ({size_mb:.1f} MB)")
        else:
            print(f"  [FAIL] {label}缺失: {path}")
            all_ok = False

    # 4. 共用模型
    shared_models = [
        ("SD VAE config", "models/sd-vae/config.json"),
        ("SD VAE model", "models/sd-vae/diffusion_pytorch_model.bin"),
        ("Whisper config", "models/whisper/config.json"),
        ("Whisper model", "models/whisper/pytorch_model.bin"),
        ("DWPose", "models/dwpose/dw-ll_ucoco_384.pth"),
        ("face-parse-bisent", "models/face-parse-bisent/79999_iter.pth"),
    ]
    for label, rel_path in shared_models:
        full_path = MUSETALK_DIR / rel_path
        if full_path.exists():
            size_mb = full_path.stat().st_size / (1024 ** 2)
            print(f"  [OK] {label}: ({size_mb:.1f} MB)")
        else:
            print(f"  [FAIL] {label}缺失: {rel_path}")
            all_ok = False

    # 5. nvidia-smi 可用性
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            gpu_name = result.stdout.strip()
            print(f"  [OK] GPU: {gpu_name}")
    except FileNotFoundError:
        print("  [WARN] nvidia-smi 不在 PATH 中")

    # 6. ffmpeg 可用性
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            print(f"  [OK] ffmpeg: {version_line[:60]}")
    except FileNotFoundError:
        print("  [FAIL] ffmpeg 不在 PATH 中，MuseTalk 需要 ffmpeg")
        all_ok = False

    # 7. 測試素材
    for label, rel_path in [
        ("測試影片/圖片", DEFAULT_VIDEO),
        ("測試音訊", DEFAULT_AUDIO),
    ]:
        full_path = MUSETALK_DIR / rel_path
        if full_path.exists():
            size_kb = full_path.stat().st_size / 1024
            print(f"  [OK] {label}: {rel_path} ({size_kb:.0f} KB)")
        else:
            print(f"  [WARN] {label}不存在: {full_path}")

    print("=" * 60)
    if all_ok:
        print("[前置檢查] 全部通過!")
    else:
        print("[前置檢查] 有項目失敗，請先修正。")
    print()

    return all_ok


# ============================================================
# 建立推論配置
# ============================================================
def create_poc_config(
    video_or_image: str,
    audio: str,
    config_path: Path,
) -> None:
    """產生 PoC 用的 YAML 配置檔。"""
    yaml_content = f"""poc_task:
  video_path: "{video_or_image}"
  audio_path: "{audio}"
"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml_content, encoding="utf-8")
    print(f"[PoC] 配置已寫入: {config_path}")


# ============================================================
# MuseTalk 推論執行
# ============================================================
def run_musetalk(
    video_or_image: str,
    audio: str,
    version: str = "v15",
    use_float16: bool = True,
    batch_size: int = 4,
    output_name: str = None,
) -> dict:
    """在 subprocess 中啟動 MuseTalk，同時用 VRAMMonitor 監控。

    Args:
        video_or_image: 源影片/圖片路徑
        audio: 驅動音訊路徑
        version: 模型版本 (v1 或 v15)
        use_float16: 是否使用 fp16 降低 VRAM
        batch_size: 推論批次大小
        output_name: 輸出影片名稱

    Returns:
        dict: 包含 success, vram_peak_mb, elapsed_sec 等
    """
    model_cfg = MODEL_PATHS.get(version, MODEL_PATHS["v15"])

    # 建立 PoC 配置
    poc_config = MUSETALK_DIR / "configs" / "inference" / "poc_test.yaml"
    create_poc_config(video_or_image, audio, poc_config)

    result_dir = str(MUSETALK_DIR / "results" / "poc")

    # 建構命令列
    cmd = [
        str(MUSETALK_ENV_PYTHON),
        "-m", "scripts.inference",
        "--inference_config", str(poc_config),
        "--unet_model_path", model_cfg["unet_model_path"],
        "--unet_config", model_cfg["unet_config"],
        "--version", model_cfg["version_arg"],
        "--result_dir", result_dir,
        "--batch_size", str(batch_size),
    ]

    if use_float16:
        cmd.append("--use_float16")

    if output_name:
        cmd.extend(["--output_vid_name", output_name])

    print("\n" + "=" * 60)
    print("[MuseTalk] 推論設定")
    print("=" * 60)
    print(f"  Python:      {MUSETALK_ENV_PYTHON}")
    print(f"  版本:        {version}")
    print(f"  源素材:      {video_or_image}")
    print(f"  音訊:        {audio}")
    print(f"  FP16:        {use_float16}")
    print(f"  Batch Size:  {batch_size}")
    print(f"  結果目錄:    {result_dir}")
    print(f"  超時限制:    {INFERENCE_TIMEOUT}s")
    print()
    print("[MuseTalk] 執行命令:")
    print(f"  {' '.join(cmd)}")
    print()

    # 啟動 VRAM 監控 thread
    monitor = VRAMMonitor(poll_interval=VRAM_POLL_INTERVAL)
    monitor.start()

    start_time = time.time()
    success = False
    proc_stdout = ""
    proc_stderr = ""

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=INFERENCE_TIMEOUT,
            cwd=str(MUSETALK_DIR),
        )
        proc_stdout = proc.stdout
        proc_stderr = proc.stderr
        success = (proc.returncode == 0)

        if not success:
            print(f"\n[MuseTalk] 推論失敗! Exit code: {proc.returncode}")

    except subprocess.TimeoutExpired:
        print(f"\n[MuseTalk] 推論超時 (>{INFERENCE_TIMEOUT}s)!")
    except Exception as exc:
        print(f"\n[MuseTalk] 例外: {exc}")

    elapsed = time.time() - start_time

    # 停止 VRAM 監控
    vram_summary = monitor.stop()

    # 印出 subprocess 輸出（最後 2000 字元）
    if proc_stdout:
        trimmed = proc_stdout[-2000:] if len(proc_stdout) > 2000 else proc_stdout
        print("\n[MuseTalk stdout]")
        print(trimmed)
    if proc_stderr:
        trimmed = proc_stderr[-2000:] if len(proc_stderr) > 2000 else proc_stderr
        print("\n[MuseTalk stderr]")
        print(trimmed)

    # 檢查輸出影片
    result_path = Path(result_dir)
    output_files = list(result_path.glob("*.mp4")) if result_path.exists() else []
    output_path = output_files[0] if output_files else None
    output_size_mb = output_path.stat().st_size / (1024 ** 2) if output_path else 0.0

    result = {
        "success": success and bool(output_path),
        "vram_baseline_mb": vram_summary["baseline_mb"],
        "vram_peak_mb": vram_summary["peak_used_mb"],
        "vram_delta_mb": vram_summary["delta_peak_mb"],
        "vram_samples": vram_summary["num_samples"],
        "elapsed_sec": round(elapsed, 1),
        "output_path": str(output_path) if output_path else "N/A",
        "output_size_mb": round(output_size_mb, 2),
        "version": version,
        "use_float16": use_float16,
        "batch_size": batch_size,
    }

    return result


# ============================================================
# 結果報告
# ============================================================
def print_report(result: dict) -> None:
    """印出格式化的測試結果報告。"""
    print("\n" + "=" * 60)
    print("  MuseTalk PoC VRAM 壓測結果")
    print("=" * 60)
    print(f"  模型版本:       {result['version']}")
    print(f"  FP16:           {result['use_float16']}")
    print(f"  Batch Size:     {result['batch_size']}")
    print(f"  是否成功:       {'PASS' if result['success'] else 'FAIL'}")
    print(f"  執行時間:       {result['elapsed_sec']} 秒")
    print(f"  VRAM 基線:      {result['vram_baseline_mb']:.0f} MB")
    print(f"  VRAM 峰值:      {result['vram_peak_mb']:.0f} MB")
    print(f"  VRAM 增量峰值:  {result['vram_delta_mb']:.0f} MB")
    print(f"  取樣數:         {result['vram_samples']}")
    print(f"  產出影片路徑:   {result['output_path']}")
    print(f"  產出影片大小:   {result['output_size_mb']:.2f} MB")

    # 12GB 紅線判定
    vram_limit_mb = 12 * 1024  # 12288 MB
    safe_threshold_mb = 10 * 1024  # 10240 MB
    peak = result["vram_peak_mb"]

    if peak <= safe_threshold_mb:
        verdict = "✅ SAFE - 在 10GB 安全線內"
    elif peak <= vram_limit_mb:
        verdict = "⚠️ WARNING - 超過 10GB 安全線但未超過 12GB 硬限制"
    else:
        verdict = "❌ DANGER - 超過 12GB 硬限制，有 OOM 風險!"

    print(f"  12GB 紅線判定:  {verdict}")

    # EDTalk vs MuseTalk 對比（如果 EDTalk 基準已知）
    edtalk_peak = 2381  # EDTalk PoC 的已知 VRAM 峰值
    edtalk_delta = 1653  # EDTalk PoC 的已知增量
    if result["success"]:
        print()
        print("  [與 EDTalk PoC 對比]")
        print(f"  EDTalk VRAM 峰值:  {edtalk_peak} MB (增量 {edtalk_delta} MB)")
        print(f"  MuseTalk VRAM 峰值: {result['vram_peak_mb']:.0f} MB (增量 {result['vram_delta_mb']:.0f} MB)")
        if result["vram_peak_mb"] < edtalk_peak:
            print("  結論: MuseTalk VRAM 更省 👍")
        elif result["vram_peak_mb"] > edtalk_peak:
            diff = result["vram_peak_mb"] - edtalk_peak
            print(f"  結論: MuseTalk VRAM 多用 {diff:.0f} MB，但仍在安全範圍")
        else:
            print("  結論: 兩者 VRAM 使用量相當")

    print("=" * 60)


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="MuseTalk PoC VRAM 壓測腳本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 使用預設素材（v1.5, fp16）
  python poc_musetalk.py

  # 使用 v1.0 模型
  python poc_musetalk.py --version v1

  # 自訂音訊
  python poc_musetalk.py --audio path/to/custom.wav

  # 關閉 fp16
  python poc_musetalk.py --no-float16

  # 只檢查前置條件
  python poc_musetalk.py --check-only
        """,
    )
    parser.add_argument(
        "--image", type=str, default=None,
        help="源圖路徑（如提供，優先使用靜態圖片）",
    )
    parser.add_argument(
        "--video", type=str, default=DEFAULT_VIDEO,
        help=f"源影片路徑 (預設: {DEFAULT_VIDEO})",
    )
    parser.add_argument(
        "--audio", type=str, default=DEFAULT_AUDIO,
        help=f"驅動音訊路徑 (預設: {DEFAULT_AUDIO})",
    )
    parser.add_argument(
        "--version", type=str, default=DEFAULT_VERSION,
        choices=["v1", "v15"],
        help=f"模型版本 (預設: {DEFAULT_VERSION})",
    )
    parser.add_argument(
        "--no-float16", action="store_true",
        help="關閉 fp16（更好品質但更多 VRAM）",
    )
    parser.add_argument(
        "--batch-size", type=int, default=4,
        help="推論批次大小 (預設: 4)",
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="只檢查前置條件，不執行推論",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  MuseTalk PoC VRAM 壓測腳本")
    print("  CEO 指令：驗證 MuseTalk 在 RTX 5070 上的可行性")
    print(f"  目標 GPU: RTX 5070 12GB")
    print(f"  VRAM 安全線: 10GB / 硬限制: 12GB")
    print("=" * 60)

    # 決定使用影片還是圖片
    video_or_image = args.image if args.image else args.video

    # ---- 前置條件檢查 ----
    version_key = args.version
    if not check_prerequisites(version_key):
        print("\n前置條件檢查失敗，中止執行。")
        sys.exit(1)

    if args.check_only:
        print("\n--check-only 模式，跳過推論。")
        sys.exit(0)

    # ---- 執行推論 ----
    result = run_musetalk(
        video_or_image=video_or_image,
        audio=args.audio,
        version=version_key,
        use_float16=not args.no_float16,
        batch_size=args.batch_size,
    )

    # ---- 印出結果報告 ----
    print_report(result)

    # 以 exit code 反映結果
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
