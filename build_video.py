#!/usr/bin/env python3
"""
build_video.py
Synthesizes voiceover via edge-tts, fetches 6 vertical archival visuals from Pollinations.ai (Flux),
extracts word-level timestamps with faster-whisper, generates animated ASS subtitles,
and composites the final 1080x1920 MP4 via native FFmpeg CLI calls.
"""

import os
import json
import time
import random
import urllib.parse
import subprocess
from typing import List
import requests
from PIL import Image, ImageDraw
from faster_whisper import WhisperModel


def run_cmd(cmd: List[str]) -> None:
    """Executes a shell command and raises on error."""
    print(f"[CMD] {' '.join(cmd[:6])} ...")
    subprocess.run(cmd, check=True)


def get_audio_duration(audio_path: str) -> float:
    """Returns exact audio duration in seconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return float(res.stdout.strip())


def format_ass_timestamp(seconds: float) -> str:
    """Formats seconds into ASS subtitle timestamp H:MM:SS.cc."""
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int(round((seconds - int(seconds)) * 100))
    if centisecs >= 100:
        secs += 1
        centisecs = 0
    return f"{hrs}:{mins:02d}:{secs:02d}.{centisecs:02d}"


def create_fallback_noir_image(img_path: str) -> None:
    """Creates a gritty dark procedural fallback image if Pollinations.ai times out."""
    img = Image.new("RGB", (1080, 1920), color=(14, 15, 18))
    draw = ImageDraw.Draw(img)
    random.seed(42)
    for _ in range(18000):
        x = random.randint(0, 1079)
        y = random.randint(0, 1919)
        v = random.randint(18, 48)
        draw.point((x, y), fill=(v, v, v))
    img.save(img_path, "JPEG", quality=92)


def download_pollinations_image(prompt: str, img_path: str, idx: int) -> None:
    """Downloads a 1080x1920 Flux image from Pollinations.ai with retries and fallback."""
    styled_prompt = (
        f"{prompt}, dark gritty 35mm archival documentary photography, "
        f"chiaroscuro lighting, high contrast, heavy film grain, vertical 9:16, no text, no watermark"
    )
    encoded_prompt = urllib.parse.quote(styled_prompt)
    seed = random.randint(10000, 9999999)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width=1080&height=1920&model=flux&nologo=true&seed={seed}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) FenrionVideoPipeline/1.0"
    }

    for attempt in range(1, 5):
        try:
            print(f"[IMAGE] Scene {idx + 1}/6 (Attempt {attempt}/4)...")
            response = requests.get(url, headers=headers, timeout=75)
            if response.status_code == 200 and len(response.content) > 10240:
                with open(img_path, "wb") as f:
                    f.write(response.content)
                return
            print(f"[WARN] HTTP {response.status_code} or small payload, retrying...")
        except requests.RequestException as exc:
            print(f"[WARN] Image request failed: {exc}")
        time.sleep(4 * attempt)

    print(f"[WARN] Using procedural dark archival fallback for Scene {idx + 1}")
    create_fallback_noir_image(img_path)


def generate_ass_subtitles(audio_path: str, ass_path: str, words_per_chunk: int = 3) -> None:
    """Extracts word timestamps via faster-whisper and builds an impact .ass subtitle file."""
    print("[SUBTITLES] Running faster-whisper (tiny.en, int8 CPU)...")
    model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, word_timestamps=True, vad_filter=True)

    # ASS Header: PrimaryColour &H0000FFFF is bold Yellow in BGR (&HAAEGGGRR -> 00 FF FF = Yellow)
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Fenrion,DejaVu Sans,76,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1.5,0,1,6,4,2,70,70,540,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    words = []
    for seg in segments:
        if seg.words:
            for w in seg.words:
                cleaned = w.word.strip()
                if cleaned:
                    words.append((w.start, w.end, cleaned))

    dialogue_lines = []
    for i in range(0, len(words), words_per_chunk):
        chunk = words[i : i + words_per_chunk]
        start_ts = format_ass_timestamp(chunk[0][0])
        end_ts = format_ass_timestamp(chunk[-1][1])

        # Highlight final word in chunk in pure white (&H00FFFFFF&) and keep lead words yellow
        formatted_tokens = []
        for j, (_, _, token_text) in enumerate(chunk):
            upper_tok = token_text.upper()
            if j == len(chunk) - 1 and len(chunk) > 1:
                formatted_tokens.append(r"{\c&H00FFFFFF&}" + upper_tok + r"{\c&H0000FFFF&}")
            else:
                formatted_tokens.append(upper_tok)

        line_text = " ".join(formatted_tokens)
        pop_anim = r"{scx115scy115	(0,80,scx100scy100)}"
        dialogue_lines.append(
            f"Dialogue: 0,{start_ts},{end_ts},Fenrion,,0,0,0,,{pop_anim}{line_text}"
        )

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "
".join(dialogue_lines) + "
")

    print(f"[SUBTITLES] Wrote {len(dialogue_lines)} dynamic caption blocks to {ass_path}")


def main() -> None:
    os.makedirs("build", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    story_path = "build/story.json"
    if not os.path.exists(story_path):
        raise FileNotFoundError(f"{story_path} not found. Run generate_story.py first.")

    with open(story_path, "r", encoding="utf-8") as f:
        story = json.load(f)

    scenes = story["scenes"]
    full_narration = " ".join(s["narration"].strip() for s in scenes)
    audio_path = "build/voiceover.mp3"

    # Step 1: Synthesize Voiceover via Edge-TTS
    print("[TTS] Generating documentary voiceover via edge-tts...")
    run_cmd([
        "edge-tts",
        "--voice", "en-US-ChristopherNeural",
        "--rate=-5%",
        "--pitch=-5Hz",
        "--text", full_narration,
        "--write-media", audio_path,
    ])

    # Step 2: Download 6 Vertical Archival Visuals from Pollinations.ai
    image_paths = []
    for idx, scene in enumerate(scenes):
        img_path = f"build/scene_{idx}.jpg"
        download_pollinations_image(scene["image_prompt"], img_path, idx)
        image_paths.append(img_path)

    # Step 3: Generate Word-Level Animated ASS Subtitles
    ass_path = "build/captions.ass"
    generate_ass_subtitles(audio_path, ass_path)

    # Step 4: Render Individual Ken Burns Scene Clips
    total_duration = get_audio_duration(audio_path)
    scene_duration = total_duration / len(scenes)
    fps = 30
    frames_per_scene = max(1, int(round(scene_duration * fps)))

    concat_list_path = "build/clips.txt"
    with open(concat_list_path, "w", encoding="utf-8") as concat_file:
        for idx, img_path in enumerate(image_paths):
            clip_filename = f"clip_{idx}.mp4"
            clip_path = os.path.join("build", clip_filename)

            # Alternate slow zoom-in and slow zoom-out for visual variety
            if idx % 2 == 0:
                zoom_expr = "min(zoom+0.0012,1.16)"
            else:
                zoom_expr = "if(eq(on,1),1.16,max(1.0,zoom-0.0012))"

            vf_chain = (
                f"scale=1200:2134:force_original_aspect_ratio=increase,crop=1200:2134,"
                f"zoompan=z='{zoom_expr}':d={frames_per_scene}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
                f"eq=contrast=1.18:brightness=-0.05:saturation=0.70,"
                f"vignette=PI/4,"
                f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(0.1, scene_duration - 0.25):.2f}:d=0.25,"
                f"format=yuv420p"
            )

            run_cmd([
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", img_path,
                "-vf", vf_chain,
                "-t", f"{scene_duration:.3f}",
                "-r", str(fps),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                clip_path,
            ])
            concat_file.write(f"file '{clip_filename}'
")

    # Step 5: Concatenate Scene Clips, Burn ASS Subtitles, and Mix Ambient Sub-Bass Drone + Voiceover
    final_output = "output/fenrion_short.mp4"
    filter_complex = (
        f"[0:v]ass={ass_path}[vout];"
        f"aevalsrc='0.04*sin(2*PI*55*t)+0.02*sin(2*PI*110*t)':s=44100:d={total_duration:.3f}[drone];"
        f"[1:a]volume=1.0[vo];"
        f"[vo][drone]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    run_cmd([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_list_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        final_output,
    ])

    print(f"[SUCCESS] Final Fenrion short rendered to {final_output} ({total_duration:.1f}s)")


if __name__ == "__main__":
    main()
