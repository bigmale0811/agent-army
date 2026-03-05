"""
後製腳本：為 SadTalker 生成的 MV 加上身體動態效果
- 身體微晃（模擬唱歌時的律動）
- 呼吸感（zoompan 微縮放）
- 整體浮動感

使用方式:
    python scripts/postprocess_mv.py <input_video> <output_video>
"""
import subprocess
import sys
import os


def find_ffmpeg() -> str:
    """自動偵測 FFmpeg 路徑"""
    search_paths = [
        r"C:\Users\goldbricks\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
    ]
    for p in search_paths:
        if os.path.isfile(p):
            return p
    # 嘗試 PATH
    return "ffmpeg"


def postprocess_video(input_path: str, output_path: str, audio_path: str | None = None) -> str:
    """
    為 SadTalker 輸出影片加上動態效果

    效果說明：
    1. 微晃（水平 sin 擺動）：模擬唱歌時身體律動
    2. 呼吸縮放（zoompan）：微妙的放大縮小
    3. 垂直浮動：輕微的上下漂浮感

    Args:
        input_path: SadTalker 輸出的影片路徑
        output_path: 後製完成的影片路徑
        audio_path: 原始音檔路徑（可選，用於替換音軌確保品質）

    Returns:
        輸出影片路徑
    """
    ffmpeg = find_ffmpeg()

    # 取得影片資訊
    probe_cmd = [
        ffmpeg.replace("ffmpeg", "ffprobe"),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration",
        "-of", "csv=p=0",
        input_path
    ]
    result = subprocess.run(
        probe_cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace"
    )
    parts = result.stdout.strip().split(",")

    if len(parts) >= 2:
        w, h = int(parts[0]), int(parts[1])
    else:
        w, h = 1024, 1024  # 預設值

    # 輸出尺寸（確保為偶數，且至少 720p 寬度）
    out_w = max(w, 720)
    out_h = max(h, 720)
    # 確保偶數
    out_w = out_w + (out_w % 2)
    out_h = out_h + (out_h % 2)

    # FFmpeg 濾鏡：
    # 1. 放大畫面一點（給搖晃留空間）
    # 2. 加上 sin 水平擺動（模擬身體律動，週期 3 秒）
    # 3. 加上 sin 垂直浮動（週期 4 秒）
    # 4. 微縮放呼吸效果（週期 5 秒）
    filter_complex = (
        # 先放大 10% 讓搖晃時不露邊
        f"[0:v]scale={int(out_w*1.1)}:{int(out_h*1.1)}[scaled];"
        # 呼吸縮放 + 搖晃 + 浮動
        f"[scaled]zoompan="
        f"z='1.0+0.015*sin(2*PI*in/125)':"  # 呼吸縮放（5秒週期 @25fps）
        f"x='iw/2-(iw/zoom/2)+8*sin(2*PI*in/75)':"  # 水平擺動（3秒週期，幅度 8px）
        f"y='ih/2-(ih/zoom/2)+6*sin(2*PI*in/100)':"  # 垂直浮動（4秒週期，幅度 6px）
        f"d=1:s={out_w}x{out_h}:fps=25[out]"
    )

    cmd = [ffmpeg, "-y"]

    if audio_path:
        # 用原始音檔替換音軌（品質更好）
        cmd += ["-i", input_path, "-i", audio_path]
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "1:a",  # 用原始音檔
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]
    else:
        cmd += ["-i", input_path]
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-c:a", "copy",
            output_path
        ]

    print(f"執行後製: {' '.join(cmd[:6])}...")
    proc = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=600
    )

    if proc.returncode != 0:
        print(f"FFmpeg 錯誤:\n{proc.stderr}")
        raise RuntimeError(f"FFmpeg 後製失敗: {proc.stderr[-500:]}")

    # 檢查輸出
    size = os.path.getsize(output_path)
    print(f"後製完成！輸出: {output_path} ({size / 1024 / 1024:.1f} MB)")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python postprocess_mv.py <input_video> <output_video> [audio_path]")
        sys.exit(1)

    inp = sys.argv[1]
    out = sys.argv[2]
    audio = sys.argv[3] if len(sys.argv) > 3 else None
    postprocess_video(inp, out, audio)
