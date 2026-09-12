import os
import json
import re
import tempfile
from pathlib import Path

import gradio as gr
import ffmpeg
import yt_dlp
import whisper
from openai import OpenAI

NUMBER_OF_CLIPS = 5
MIN_CLIP_LENGTH = 20
MAX_CLIP_LENGTH = 60
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing. Add it as a secret/environment variable.")

client = OpenAI(api_key=OPENAI_API_KEY)
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model("base")
    return _whisper_model

def download_video(url, workdir):
    master = str(Path(workdir) / "master_video.mp4")
    opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": master,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    if not os.path.exists(master):
        raise RuntimeError("Video download failed.")
    return master

def transcribe_video(video):
    return get_whisper_model().transcribe(video, word_timestamps=True)

def find_best_clips(transcript):
    transcript_text = "\n".join(
        f"[{s['start']:.2f} - {s['end']:.2f}] {s['text'].strip()}"
        for s in transcript["segments"] if s["text"].strip()
    )
    prompt = f"""
You are an expert short-form video editor.
Select exactly {NUMBER_OF_CLIPS} strong moments from this transcript for TikTok,
Instagram Reels, or YouTube Shorts.

Prioritize strong hooks, surprising statements, emotion, useful information,
interesting opinions, humor, stories, and curiosity.
Avoid greetings, silence, repetition, and incomplete sentences.
Each clip must be {MIN_CLIP_LENGTH}-{MAX_CLIP_LENGTH} seconds.

Return ONLY valid JSON:
[
  {{"start": 120.5, "end": 158.2, "title": "Short title",
    "reason": "Why this moment is interesting"}}
]

TRANSCRIPT:
{transcript_text}
"""
    response = client.responses.create(model=OPENAI_MODEL, input=prompt)
    text = re.sub(r"```json|```", "", response.output_text).strip()
    clips = json.loads(text)
    return clips

def timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def create_srt(transcript, start_time, end_time, filename):
    counter = 1
    with open(filename, "w", encoding="utf-8") as f:
        for s in transcript["segments"]:
            if s["end"] < start_time or s["start"] > end_time:
                continue
            text = s["text"].strip()
            if not text:
                continue
            local_start = max(0, s["start"] - start_time)
            local_end = min(end_time - start_time, s["end"] - start_time)
            f.write(f"{counter}\n{timestamp(local_start)} --> {timestamp(local_end)}\n{text}\n\n")
            counter += 1

def create_vertical_clip(video_path, start, end, output, subtitle_file):
    duration = end - start
    inp = ffmpeg.input(video_path, ss=start, t=duration)
    video = inp.video.filter("crop", "ih*9/16", "ih", "(iw-ih*9/16)/2", 0)
    video = video.filter("scale", 1080, 1920)
    video = video.filter("unsharp", 5, 5, 0.5, 5, 5, 0)
    # Escape Windows-style paths if needed; hosted Linux paths normally work directly.
    video = video.filter("subtitles", subtitle_file)
    out = ffmpeg.output(
        video, inp.audio, output,
        vcodec="libx264", acodec="aac",
        video_bitrate="5M", audio_bitrate="192k",
        movflags="+faststart"
    )
    ffmpeg.run(out, overwrite_output=True, quiet=True)

def generate(url, progress=gr.Progress()):
    if not url or "http" not in url:
        raise gr.Error("Please paste a valid video URL.")
    with tempfile.TemporaryDirectory() as workdir:
        progress(0.1, desc="Downloading video...")
        video = download_video(url, workdir)

        progress(0.3, desc="Transcribing with Whisper...")
        transcript = transcribe_video(video)

        progress(0.55, desc="AI is selecting the best moments...")
        clips = find_best_clips(transcript)

        files = []
        info = []
        total = min(len(clips), NUMBER_OF_CLIPS)

        for i, clip in enumerate(clips[:NUMBER_OF_CLIPS], 1):
            start = float(clip["start"])
            end = float(clip["end"])
            if end <= start:
                continue
            end = min(end, start + MAX_CLIP_LENGTH)
            if end - start < MIN_CLIP_LENGTH:
                end = start + MIN_CLIP_LENGTH

            srt = str(Path(workdir) / f"clip_{i}.srt")
            output = str(Path(workdir) / f"clip_{i}.mp4")
            create_srt(transcript, start, end, srt)
            progress(0.55 + 0.4 * i / max(total, 1), desc=f"Creating clip {i}/{total}...")
            create_vertical_clip(video, start, end, output, srt)
            files.append(output)
            info.append(f"**Clip {i}: {clip.get('title','Untitled')}** — {clip.get('reason','')}")

        if not files:
            raise gr.Error("No clips were created.")

        # Copy files to persistent temp output for Gradio download components.
        final_dir = Path(tempfile.mkdtemp(prefix="ai_clips_"))
        final_files = []
        for f in files:
            dest = final_dir / Path(f).name
            dest.write_bytes(Path(f).read_bytes())
            final_files.append(str(dest))

        return final_files, "\n\n".join(info)

with gr.Blocks(title="AI Viral Video Agent") as demo:
    gr.Markdown("# 🎬 AI Viral Video Agent\nTurn a long video into 5 vertical short clips with AI-selected moments and subtitles.")
    url = gr.Textbox(label="Long video URL", placeholder="Paste your YouTube/video URL here")
    button = gr.Button("🚀 Generate 5 Clips", variant="primary")
    gallery = gr.File(label="Generated clips", file_count="multiple")
    details = gr.Markdown()
    button.click(generate, inputs=url, outputs=[gallery, details])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")))
