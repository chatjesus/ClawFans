# -*- coding: utf-8 -*-
"""
Stage 5 — Assemble video clips, narration audio, and subtitles into final MP4.

Uses ffmpeg (via imageio-ffmpeg) to:
  - Concatenate scene clips
  - Overlay narration audio per scene
  - Burn subtitles (ASS style)
  - Add fade transitions between scenes

Usage:
  python scripts/manga_assemble.py --char-id 53
  python scripts/manga_assemble.py --char-id 53 --episode 1 --no-subs
"""

import sys, os, json, argparse, subprocess, tempfile
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32":
    import ctypes; ctypes.windll.kernel32.SetConsoleOutputCP(65001)

from pathlib import Path

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
os.chdir(BACKEND_DIR)

OUTPUT_BASE = Path("uploads/manga")


def _get_ffmpeg() -> str:
    """Get path to ffmpeg binary."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def _get_duration(ffmpeg: str, filepath: str) -> float:
    """Get duration of a media file in seconds."""
    result = subprocess.run(
        [ffmpeg, "-i", filepath],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    import re
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 4.0


def _generate_ass_subtitles(scenes: list, scene_starts: list, output_path: str):
    """Generate ASS subtitle file from scene narrations."""
    header = """[Script Info]
Title: Manga Drama
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,58,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,30,30,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "") or scene.get("dialogue", "")
        if not narration:
            continue
        start = scene_starts[i]
        dur = scene.get("duration_sec", 4)
        end = start + dur

        def _ts(sec):
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = sec % 60
            return f"{h}:{m:02d}:{s:05.2f}"

        events.append(
            f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{narration}"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))


def assemble_episode(char_id: int, episode: int = 1, burn_subs: bool = True) -> str:
    """Assemble all scene clips + audio + subtitles into final episode MP4."""
    ffmpeg = _get_ffmpeg()
    work_dir = OUTPUT_BASE / str(char_id)
    script_path = work_dir / f"script_ep{episode}.json"

    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    scenes = script["scenes"]
    clips = []
    audios = []
    scene_starts = []
    current_time = 0.0

    for scene in scenes:
        sid = scene["id"]
        clip_path = work_dir / f"clip_ep{episode}_s{sid}.mp4"
        audio_path = work_dir / f"narration_ep{episode}_s{sid}.wav"
        if not audio_path.exists():
            audio_path = work_dir / f"narration_ep{episode}_s{sid}.mp3"

        if not clip_path.exists():
            print(f"  Scene {sid}: clip missing, skipping")
            continue

        clips.append(str(clip_path))
        scene_starts.append(current_time)

        if audio_path.exists():
            audios.append((str(audio_path), current_time))

        clip_dur = _get_duration(ffmpeg, str(clip_path))
        current_time += clip_dur

    if not clips:
        raise RuntimeError("No clips found to assemble")

    # Transition duration (seconds) and type per mood
    TRANSITION_DUR = 0.4
    MOOD_TRANSITIONS = {
        "warm":       "dissolve",
        "romantic":   "fadewhite",
        "tense":      "fadeblack",
        "mysterious": "fadeblack",
        "melancholy": "fadegrays",
    }
    DEFAULT_TRANSITION = "fadeblack"

    # Build per-scene transition list (n-1 transitions for n clips)
    transitions = []
    for i in range(len(clips) - 1):
        mood = scenes[i].get("mood", "warm") if i < len(scenes) else "warm"
        transitions.append(MOOD_TRANSITIONS.get(mood, DEFAULT_TRANSITION))

    print(f"[Assemble] {len(clips)} clips, {len(audios)} audio tracks, total ~{current_time:.1f}s")
    print(f"[Assemble] Transitions: {transitions}")

    concat_video = str(work_dir / f"_concat_ep{episode}.mp4")

    if len(clips) == 1:
        import shutil
        shutil.copy2(clips[0], concat_video)
    else:
        # First re-encode all clips to ensure same format (fps, resolution, pixel format)
        # then chain xfade transitions
        reenc_clips = []
        for idx, clip in enumerate(clips):
            reenc = str(work_dir / f"_reenc_{idx}.mp4")
            subprocess.run([
                ffmpeg, "-y", "-i", clip,
                "-vf", "fps=24,scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-r", "24", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-an", reenc
            ], check=True, capture_output=True)
            reenc_clips.append(reenc)

        # Get accurate durations of re-encoded clips
        durations = [_get_duration(ffmpeg, c) for c in reenc_clips]

        # Build xfade filter chain
        inputs = []
        for c in reenc_clips:
            inputs.extend(["-i", c])

        filter_parts = []
        offset = 0.0
        prev_label = "[0:v]"
        for i, ttype in enumerate(transitions):
            offset += durations[i] - TRANSITION_DUR
            next_label = f"[v{i+1}]" if i < len(transitions) - 1 else "[vout]"
            filter_parts.append(
                f"{prev_label}[{i+1}:v]xfade=transition={ttype}:"
                f"duration={TRANSITION_DUR}:offset={offset:.3f}{next_label}"
            )
            prev_label = f"[v{i+1}]"
            offset += TRANSITION_DUR  # advance by full clip duration minus the overlap

        filter_str = ";".join(filter_parts)
        subprocess.run([
            ffmpeg, "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", "[vout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-r", "24", concat_video
        ], check=True, capture_output=True)

        for r in reenc_clips:
            try: os.unlink(r)
            except Exception: pass

    print(f"  Concatenated video → {concat_video}")

    # Step 2: Mix in narration audio tracks
    if audios:
        inputs = ["-i", concat_video]
        filter_parts = []
        for i, (audio_path, start_time) in enumerate(audios):
            inputs.extend(["-i", audio_path])
            idx = i + 1
            filter_parts.append(
                f"[{idx}:a]adelay={int(start_time*1000)}|{int(start_time*1000)}[a{i}]"
            )

        audio_mix = ";".join(filter_parts)
        audio_streams = "".join(f"[a{i}]" for i in range(len(audios)))
        audio_mix += f";{audio_streams}amix=inputs={len(audios)}:duration=longest[aout]"

        mixed_video = str(work_dir / f"_mixed_ep{episode}.mp4")
        cmd = [ffmpeg, "-y"] + inputs + [
            "-filter_complex", audio_mix,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            mixed_video
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  Mixed audio → {mixed_video}")
    else:
        mixed_video = concat_video

    # Step 3: Burn subtitles
    final_output = str(work_dir / f"episode_{episode}.mp4")
    if burn_subs:
        ass_path = str(work_dir / f"subs_ep{episode}.ass")
        # Only pass scenes that have clips (scene_starts is parallel to clips, not all scenes)
        assembled_scenes = [s for s in scenes if (work_dir / f"clip_ep{episode}_s{s['id']}.mp4").exists()]
        _generate_ass_subtitles(assembled_scenes, scene_starts, ass_path)
        print(f"  Generated subtitles → {ass_path}")

        # ffmpeg subtitle burning uses forward slashes and escaped colons on Windows
        ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
        subprocess.run([
            ffmpeg, "-y", "-i", mixed_video,
            "-vf", f"subtitles={ass_escaped}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "copy",
            final_output
        ], check=True, capture_output=True)
    else:
        if mixed_video != final_output:
            import shutil
            shutil.copy2(mixed_video, final_output)

    # Cleanup temp files
    for tmp in [concat_video, mixed_video]:
        if tmp != final_output and os.path.exists(tmp):
            os.unlink(tmp)

    size_mb = os.path.getsize(final_output) / 1024 / 1024
    print(f"\n[Assemble] Final output: {final_output} ({size_mb:.1f} MB)")
    return final_output


def main():
    parser = argparse.ArgumentParser(description="Assemble manga drama episode")
    parser.add_argument("--char-id", type=int, required=True)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--no-subs", action="store_true", help="Skip subtitle burning")
    args = parser.parse_args()

    output = assemble_episode(args.char_id, args.episode, burn_subs=not args.no_subs)
    print(f"Done: {output}")


if __name__ == "__main__":
    main()
