import os
import json
import re
import subprocess
from pathlib import Path

import ffmpeg
import yt_dlp
import whisper
from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

VIDEO_URL = "YOUR_LONG_VIDEO_URL_HERE"

NUMBER_OF_CLIPS = 5
MIN_CLIP_LENGTH = 20
MAX_CLIP_LENGTH = 60

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

MASTER_VIDEO = "master_video.mp4"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is missing. Add it to your Replit Secrets."
    )

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# 1. DOWNLOAD LONG VIDEO
# ============================================================

def download_video(url):
    print("\n[1/5] Downloading long video...")

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": MASTER_VIDEO,
        "merge_output_format": "mp4",
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if not os.path.exists(MASTER_VIDEO):
        raise RuntimeError("Video download failed.")

    print("✓ Video downloaded")


# ============================================================
# 2. TRANSCRIBE VIDEO
# ============================================================

def transcribe_video():
    print("\n[2/5] Transcribing video with Whisper...")

    model = whisper.load_model("base")

    result = model.transcribe(
        MASTER_VIDEO,
        word_timestamps=True
    )

    print("✓ Transcription complete")

    return result


# ============================================================
# 3. ASK AI TO FIND BEST CLIPS
# ============================================================

def find_best_clips(transcript):
    print("\n[3/5] AI is finding the strongest moments...")

    segments = transcript["segments"]

    transcript_text = ""

    for segment in segments:
        start = segment["start"]
        end = segment["end"]
        text = segment["text"].strip()

        transcript_text += (
            f"[{start:.2f} - {end:.2f}] {text}\n"
        )

    prompt = f"""
You are an expert short-form video editor.

Analyze this long-form video transcript.

Your job is to select the most interesting moments that could work
as TikTok, Instagram Reels, or YouTube Shorts.

Prioritize:

- strong hooks
- surprising statements
- emotional moments
- useful information
- controversial or interesting opinions
- funny moments
- stories
- moments that create curiosity
- moments that make viewers continue watching

Do NOT select boring introductions, greetings, silence,
repeated information, or incomplete sentences.

Choose exactly {NUMBER_OF_CLIPS} clips.

Each clip must be between {MIN_CLIP_LENGTH} and {MAX_CLIP_LENGTH} seconds.

The beginning of each clip should be strong enough to work as a hook.

Return ONLY valid JSON in this format:

[
  {{
    "start": 120.5,
    "end": 158.2,
    "title": "Short title",
    "reason": "Why this moment is interesting"
  }}
]

TRANSCRIPT:

{transcript_text}
"""

    response = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt
    )

    text = response.output_text.strip()

    # Remove accidental markdown fences
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text).strip()

    try:
        clips = json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(
            "AI returned invalid clip data:\n" + text
        )

    print(f"✓ AI selected {len(clips)} clips")

    return clips


# ============================================================
# 4. FIND CAPTIONS FOR EACH CLIP
# ============================================================

def get_caption_text(transcript, start_time, end_time):
    lines = []

    for segment in transcript["segments"]:
        segment_start = segment["start"]
        segment_end = segment["end"]

        if segment_end >= start_time and segment_start <= end_time:
            text = segment["text"].strip()

            if text:
                lines.append(text)

    return " ".join(lines)


# ============================================================
# 5. CREATE SUBTITLE FILE
# ============================================================

def create_srt(transcript, start_time, end_time, filename):
    counter = 1

    with open(filename, "w", encoding="utf-8") as f:

        for segment in transcript["segments"]:

            if (
                segment["end"] < start_time
                or segment["start"] > end_time
            ):
                continue

            text = segment["text"].strip()

            if not text:
                continue

            local_start = max(
                0,
                segment["start"] - start_time
            )

            local_end = min(
                end_time - start_time,
                segment["end"] - start_time
            )

            def timestamp(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                millis = int((seconds - int(seconds)) * 1000)

                return (
                    f"{hours:02}:{minutes:02}:"
                    f"{secs:02},{millis:03}"
                )

            f.write(f"{counter}\n")
            f.write(
                f"{timestamp(local_start)} --> "
                f"{timestamp(local_end)}\n"
            )
            f.write(text + "\n\n")

            counter += 1


# ============================================================
# 6. CREATE VERTICAL SHORT
# ============================================================

def create_vertical_clip(
    start_time,
    end_time,
    output_filename,
    subtitle_file
):

    print(
        f"Creating clip: "
        f"{start_time:.1f}s → {end_time:.1f}s"
    )

    duration = end_time - start_time

    input_stream = ffmpeg.input(
        MASTER_VIDEO,
        ss=start_time,
        t=duration
    )

    video = input_stream.video

    # Center crop to 9:16
    video = video.filter(
        "crop",
        "ih*9/16",
        "ih",
        "(iw-ih*9/16)/2",
        0
    )

    # Vertical resolution
    video = video.filter(
        "scale",
        1080,
        1920
    )

    # Slight sharpening
    video = video.filter(
        "unsharp",
        5,
        5,
        0.5,
        5,
        5,
        0
    )

    # Burn subtitles
    video = video.filter(
        "subtitles",
        subtitle_file
    )

    audio = input_stream.audio

    output = ffmpeg.output(
        video,
        audio,
        output_filename,
        vcodec="libx264",
        acodec="aac",
        video_bitrate="5M",
        audio_bitrate="192k",
        movflags="+faststart"
    )

    ffmpeg.run(
        output,
        overwrite_output=True
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():

    print("=" * 60)
    print("       AI VIRAL VIDEO CLIP AGENT")
    print("=" * 60)

    if VIDEO_URL == "YOUR_LONG_VIDEO_URL_HERE":
        raise RuntimeError(
            "Put your long-video URL in VIDEO_URL first."
        )

    # STEP 1
    download_video(VIDEO_URL)

    # STEP 2
    transcript = transcribe_video()

    # STEP 3
    clips = find_best_clips(transcript)

    # STEP 4 + 5
    for index, clip in enumerate(clips, start=1):

        start = float(clip["start"])
        end = float(clip["end"])

        # Safety check
        if end <= start:
            continue

        if end - start < MIN_CLIP_LENGTH:
            end = start + MIN_CLIP_LENGTH

        if end - start > MAX_CLIP_LENGTH:
            end = start + MAX_CLIP_LENGTH

        subtitle_file = (
            OUTPUT_DIR /
            f"clip_{index}.srt"
        )

        output_file = (
            OUTPUT_DIR /
            f"clip_{index}.mp4"
        )

        create_srt(
            transcript,
            start,
            end,
            str(subtitle_file)
        )

        create_vertical_clip(
            start,
            end,
            str(output_file),
            str(subtitle_file)
        )

        print(
            f"✓ Clip {index} finished: "
            f"{output_file}"
        )

    print("\n" + "=" * 60)
    print("ALL CLIPS CREATED")
    print("=" * 60)
    print(f"Check the '{OUTPUT_DIR}' folder.")


if __name__ == "__main__":
    main()
