import subprocess, json, os, sys

video = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53\a16377557b2b0cf183f3c8eaa154b0e3.mp4"

try:
    import imageio_ffmpeg
    ffprobe = imageio_ffmpeg.get_ffmpeg_exe().replace("ffmpeg", "ffprobe")
except Exception:
    ffprobe = "ffprobe"

size_mb = os.path.getsize(video) / 1e6
cmd = [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video]
result = subprocess.run(cmd, capture_output=True, text=True)
info = json.loads(result.stdout)

fmt = info.get("format", {})
duration = float(fmt.get("duration", 0))
print(f"File: {os.path.basename(video)}")
print(f"Size: {size_mb:.1f} MB")
print(f"Duration: {duration:.1f}s")
print(f"Format: {fmt.get('format_long_name', '?')}")

for s in info.get("streams", []):
    codec = s.get("codec_type", "?")
    if codec == "video":
        w, h = s.get("width", "?"), s.get("height", "?")
        fps = s.get("r_frame_rate", "?")
        vcodec = s.get("codec_name", "?")
        nb_frames = s.get("nb_frames", "?")
        print(f"Video: {w}x{h}, {vcodec}, fps={fps}, frames={nb_frames}")
    elif codec == "audio":
        acodec = s.get("codec_name", "?")
        sr = s.get("sample_rate", "?")
        ch = s.get("channels", "?")
        print(f"Audio: {acodec}, {sr}Hz, {ch}ch")
