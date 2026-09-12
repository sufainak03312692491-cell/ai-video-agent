# AI Video Agent

A Gradio web app that:
1. Downloads a long video from a URL
2. Transcribes it with Whisper
3. Uses an OpenAI model to select 5 strong short-form moments
4. Creates 9:16 vertical clips
5. Burns subtitles into the clips

## Required
- Python
- FFmpeg installed on the host
- `OPENAI_API_KEY` environment variable
- Optional `OPENAI_MODEL` environment variable

## Run
```bash
pip install -r requirements.txt
python app.py
```

The app listens on port 7860 (or `$PORT`).

## Important
Hosting may be free, but OpenAI API usage and heavy video processing may not be free.
