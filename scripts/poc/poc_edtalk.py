#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDTalk PoC VRAM 壓測腳本
軌道二：新世代武器概念驗證

目的：驗證 EDTalk 在 GFX 5070 (12GB VRAM) 上的可行性。
- 在 subprocess 中執行 EDTalk 推論
- 在主進程開 thread 每 0.5 秒記錄 VRAM（透過 nvidia-smi）
- 測量 VRAM 峰值、執行時間、產出影片路徑

使用方式：
    D:\\Projects\\EDTalk\\edtalk_env\\Scripts\\python.exe ^
        D:\\Projects\\agent-army\\scripts\\poc\\poc_edtalk.py ^
        --exp_type sad

    # 自訂素材
    D:\\Projects\\EDTalk\\edtalk_env\\Scripts\\python.exe ^
        D:\\Projects\\agent-army\\scripts\\poc\\poc_edtalk.py ^
        --image test_data/identity_source.jpg ^
        --audio test_data/mouth_source.wav ^
        --exp_type sad

前置條件：
    1. EDTalk 已 clone 到 D:\\Projects\\EDTalk
    2. edtalk_env 虛擬環境已建立且依賴已安裝
    3. Checkpoint 已下載到 D:\\Projects\\EDTalk\\ckpts\\
       - EDTalk.pt
       - Audio2Lip.pt
       - predefined_exp_weights/*.npy

作者：@Technology-Scout PoC
日期：2026-03-08
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
EDTALK_DIR = Path(r"D:\Projects\EDTalk")
EDTALK_ENV_PYTHON = EDTALK_DIR / "edtalk_env" / "Scripts" / "python.exe"
DEMO_SCRIPT = EDTALK_DIR / "demo_EDTalk_A_using_predefined_exp_weights.py"

# 預設測試素材（EDTalk 內建示例檔案）
DEFAULT_IMAGE = "test_data/identity_source.jpg"
DEFAULT_AUDIO = "test_data/mouth_source.wav"
DEFAULT_POSE_VIDEO = "test_data/pose_source1.mp4"
DEFAULT_EXP_TYPE = "sad"
DEFAULT_OUTPUT = "res/poc_edtalk_output.mp4"

# 有效的表情類型
VALID_EXP_TYPES = [
    "angry", "contempt", "disgusted", "fear",
    "happy", "sad", "surprised", "neutral",
]

# VRAM 監控間隔（秒）
VRAM_POLL_INTERVAL = 0.5

# 推論超時（秒）
INFERENCE_TIMEOUT = 600


# ============================================================
# VRAM 監控器（背景 Thread）
# ============================================================
class VRAMMonitor:
    """在背景 thread 中每隔固定時間以 nvidia-smi 記錄 GPU VRAM 使用量。

    因為推論在 subprocess 中執行，主進程的 torch.cuda 無法觀測子進程的 VRAM。
    所以使用 nvidia-smi 查詢系統層級的 GPU 記憶體使用量。
    """

    def __init__(self, poll_interval: float = VRAM_POLL_INTERVAL, gpu_index: int = 0):
        self._poll_interval = poll_interval
        self._gpu_index = gpu_index
        self._stop_event = threading.Event()
        self._thread = None
        self._samples: list[dict] = []
        self._peak_used_mb: float = 0.0
        self._baseline_mb: float = 0.0

    def _query_nvidia_smi(self) -> dict:
        """透過 nvidia-smi 查詢 VRAM（支援沒有 pynvml 的環境）。"""
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

        # 計算推論增量峰值
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
def check_prerequisites() -> bool:
    """檢查 edtalk_env、模型權重、示例素材是否就緒。"""
    print("\n" + "=" * 60)
    print("[前置檢查] 開始驗證環境...")
    print("=" * 60)

    all_ok = True

    # 1. EDTalk 目錄
    if EDTALK_DIR.exists():
        print(f"  [OK] EDTalk 目錄存在: {EDTALK_DIR}")
    else:
        print(f"  [FAIL] EDTalk 目錄不存在: {EDTALK_DIR}")
        all_ok = False

    # 2. edtalk_env Python
    if EDTALK_ENV_PYTHON.exists():
        print(f"  [OK] edtalk_env Python: {EDTALK_ENV_PYTHON}")
    else:
        print(f"  [FAIL] edtalk_env Python 不存在: {EDTALK_ENV_PYTHON}")
        print(f"         請先建立虛擬環境: python -m venv {EDTALK_DIR / 'edtalk_env'}")
        all_ok = False

    # 3. Demo 腳本
    if DEMO_SCRIPT.exists():
        print(f"  [OK] Demo 腳本: {DEMO_SCRIPT.name}")
    else:
        print(f"  [FAIL] Demo 腳本不存在: {DEMO_SCRIPT}")
        all_ok = False

    # 4. 模型權重
    required_ckpts = ["EDTalk.pt", "Audio2Lip.pt"]
    ckpts_dir = EDTALK_DIR / "ckpts"
    for ckpt_name in required_ckpts:
        ckpt_path = ckpts_dir / ckpt_name
        if ckpt_path.exists():
            size_mb = ckpt_path.stat().st_size / (1024 ** 2)
            print(f"  [OK] 模型權重: {ckpt_name} ({size_mb:.1f} MB)")
        else:
            print(f"  [FAIL] 模型權重缺失: {ckpt_name}")
            print(f"         下載: https://huggingface.co/tanhshuai0219/EDTalk/tree/main")
            all_ok = False

    # 5. 預定義表情權重
    exp_dir = ckpts_dir / "predefined_exp_weights"
    if exp_dir.exists():
        found_exps = [f.stem for f in exp_dir.glob("*.npy")]
        missing = [e for e in VALID_EXP_TYPES if e not in found_exps]
        if not missing:
            print(f"  [OK] 表情權重: {len(found_exps)} 種全部就緒")
        else:
            print(f"  [WARN] 缺少表情權重: {', '.join(missing)}")
    else:
        print(f"  [FAIL] 表情權重目錄不存在: {exp_dir}")
        all_ok = False

    # 6. nvidia-smi 可用性
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            gpu_name = result.stdout.strip()
            print(f"  [OK] GPU: {gpu_name}")
        else:
            print("  [WARN] nvidia-smi 執行失敗，VRAM 監控可能不準確")
    except FileNotFoundError:
        print("  [WARN] nvidia-smi 不在 PATH 中，VRAM 監控可能不準確")

    # 7. 測試素材
    for label, rel_path in [
        ("測試圖片", DEFAULT_IMAGE),
        ("測試音訊", DEFAULT_AUDIO),
        ("姿態影片", DEFAULT_POSE_VIDEO),
    ]:
        full_path = EDTALK_DIR / rel_path
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
# EDTalk 推論執行
# ============================================================
def run_edtalk(
    image: str,
    audio: str,
    exp_type: str,
    pose_video: str,
    output: str,
) -> dict:
    """在 subprocess 中啟動 EDTalk，同時在主進程用 VRAMMonitor thread 監控 VRAM。

    Args:
        image: 源圖路徑（相對於 EDTALK_DIR 或絕對路徑）
        audio: 驅動音訊路徑
        exp_type: 表情類型（強制 sad，或使用者指定）
        pose_video: 姿態驅動影片路徑
        output: 輸出影片路徑

    Returns:
        dict: 包含 success, vram_peak_mb, elapsed_sec, output_path
    """
    # 建構命令列
    cmd = [
        str(EDTALK_ENV_PYTHON),
        str(DEMO_SCRIPT),
        "--source_path", image,
        "--audio_driving_path", audio,
        "--pose_driving_path", pose_video,
        "--exp_type", exp_type,
        "--save_path", output,
    ]

    print("\n" + "=" * 60)
    print("[EDTalk] 推論設定")
    print("=" * 60)
    print(f"  Python:      {EDTALK_ENV_PYTHON}")
    print(f"  腳本:        {DEMO_SCRIPT.name}")
    print(f"  源圖:        {image}")
    print(f"  音訊:        {audio}")
    print(f"  姿態影片:    {pose_video}")
    print(f"  表情類型:    {exp_type}")
    print(f"  輸出路徑:    {output}")
    print(f"  超時限制:    {INFERENCE_TIMEOUT}s")
    print()
    print("[EDTalk] 執行命令:")
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
        # 在 subprocess 中執行推論，cwd 設為 EDTALK_DIR
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=INFERENCE_TIMEOUT,
            cwd=str(EDTALK_DIR),
        )
        proc_stdout = proc.stdout
        proc_stderr = proc.stderr
        success = (proc.returncode == 0)

        if not success:
            print(f"\n[EDTalk] 推論失敗! Exit code: {proc.returncode}")

    except subprocess.TimeoutExpired:
        print(f"\n[EDTalk] 推論超時 (>{INFERENCE_TIMEOUT}s)!")
    except Exception as exc:
        print(f"\n[EDTalk] 例外: {exc}")

    elapsed = time.time() - start_time

    # 停止 VRAM 監控
    vram_summary = monitor.stop()

    # 印出 subprocess 輸出（最後 2000 字元）
    if proc_stdout:
        trimmed = proc_stdout[-2000:] if len(proc_stdout) > 2000 else proc_stdout
        print("\n[EDTalk stdout]")
        print(trimmed)
    if proc_stderr:
        trimmed = proc_stderr[-2000:] if len(proc_stderr) > 2000 else proc_stderr
        print("\n[EDTalk stderr]")
        print(trimmed)

    # 檢查輸出影片
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = EDTALK_DIR / output
    output_exists = output_path.exists()
    output_size_mb = output_path.stat().st_size / (1024 ** 2) if output_exists else 0.0

    result = {
        "success": success and output_exists,
        "vram_baseline_mb": vram_summary["baseline_mb"],
        "vram_peak_mb": vram_summary["peak_used_mb"],
        "vram_delta_mb": vram_summary["delta_peak_mb"],
        "vram_samples": vram_summary["num_samples"],
        "elapsed_sec": round(elapsed, 1),
        "output_path": str(output_path) if output_exists else "N/A",
        "output_size_mb": round(output_size_mb, 2),
        "exp_type": exp_type,
    }

    return result


# ============================================================
# 結果報告
# ============================================================
def print_report(result: dict) -> None:
    """印出格式化的測試結果報告。"""
    print("\n" + "=" * 60)
    print("  EDTalk PoC VRAM 壓測結果")
    print("=" * 60)
    print(f"  表情類型:       {result['exp_type']}")
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
    safe_threshold_mb = 10 * 1024  # 10240 MB（保留 2GB 給系統）
    peak = result["vram_peak_mb"]

    if peak <= safe_threshold_mb:
        verdict = "SAFE - 在 10GB 安全線內"
    elif peak <= vram_limit_mb:
        verdict = "WARNING - 超過 10GB 安全線但未超過 12GB 硬限制"
    else:
        verdict = "DANGER - 超過 12GB 硬限制，有 OOM 風險!"

    print(f"  12GB 紅線判定:  {verdict}")
    print("=" * 60)


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="EDTalk PoC VRAM 壓測腳本 - 軌道二概念驗證",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 使用預設素材，強制 sad 表情
  python poc_edtalk.py

  # 指定表情類型
  python poc_edtalk.py --exp_type happy

  # 自訂音訊
  python poc_edtalk.py --audio path/to/custom.wav --exp_type sad

  # 只檢查前置條件
  python poc_edtalk.py --check-only
        """,
    )
    parser.add_argument(
        "--image", type=str, default=DEFAULT_IMAGE,
        help=f"源圖路徑，相對於 EDTalk 目錄 (預設: {DEFAULT_IMAGE})",
    )
    parser.add_argument(
        "--audio", type=str, default=DEFAULT_AUDIO,
        help=f"驅動音訊路徑，相對於 EDTalk 目錄 (預設: {DEFAULT_AUDIO})",
    )
    parser.add_argument(
        "--exp_type", type=str, default=DEFAULT_EXP_TYPE,
        choices=VALID_EXP_TYPES,
        help=f"表情類型 (預設: {DEFAULT_EXP_TYPE})",
    )
    parser.add_argument(
        "--pose_video", type=str, default=DEFAULT_POSE_VIDEO,
        help=f"姿態驅動影片路徑 (預設: {DEFAULT_POSE_VIDEO})",
    )
    parser.add_argument(
        "--output", type=str, default=DEFAULT_OUTPUT,
        help=f"輸出影片路徑 (預設: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="只檢查前置條件，不執行推論",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  EDTalk PoC VRAM 壓測腳本")
    print("  軌道二：新世代武器概念驗證")
    print(f"  目標 GPU: GFX 5070 12GB")
    print(f"  VRAM 安全線: 10GB / 硬限制: 12GB")
    print("=" * 60)

    # ---- 前置條件檢查 ----
    if not check_prerequisites():
        print("\n前置條件檢查失敗，中止執行。")
        sys.exit(1)

    if args.check_only:
        print("\n--check-only 模式，跳過推論。")
        sys.exit(0)

    # ---- 執行推論 ----
    result = run_edtalk(
        image=args.image,
        audio=args.audio,
        exp_type=args.exp_type,
        pose_video=args.pose_video,
        output=args.output,
    )

    # ---- 印出結果報告 ----
    print_report(result)

    # 以 exit code 反映結果
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
