import os
import requests
import whisper
import yt_dlp

# --- CONFIGURATION ---
LONG_VIDEO_URL = "YOUR_LONG_VIDEO_URL_HERE"  # Paste your long video link here
TIKTOK_ACCESS_TOKEN = (  # Paste your TikTok Access Token here
    "YOUR_TIKTOK_ACCESS_TOKEN"
)


def download_video(url):
  print("Step 1: Downloading long video...")
  ydl_opts = {
      "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
      "outtmpl": "master_video.mp4",
  }
  with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
  print("-> Video downloaded successfully as 'master_video.mp4'.")


def transcribe_video():
  print("Step 2: Transcribing audio with OpenAI Whisper...")
  model = whisper.load_model("base")
  result = model.transcribe("master_video.mp4", word_timestamps=True)
  print("-> Transcription complete!")
  return result


def upload_to_tiktok(video_url, caption_text):
  print("Step 3: Uploading clip to TikTok automatically...")
  endpoint = "https://open.tiktokapis.com/v2/post/publish/video/init/"

  headers = {
      "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
      "Content-Type": "application/json; charset=UTF-8",
  }

  body = {
      "post_info": {
          "privacy_level": "SELF_ONLY",
          "title": caption_text,
          "is_aigc": True,
      },
      "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
  }

  response = requests.post(endpoint, headers=headers, json=body)
  if response.status_code == 200:
    print("-> Successfully uploaded to TikTok!")
    print(response.json())
  else:
    print(f"-> Upload failed: {response.text}")


if __name__ == "__main__":
  # Uncomment the lines below to run functions:
  # download_video(LONG_VIDEO_URL)
  # transcript = transcribe_video()
  print("Pipeline is ready!")
