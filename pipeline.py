import os
import ffmpeg
import whisper
import yt_dlp

# --- CONFIGURATION ---
LONG_VIDEO_URL = (
    "YOUR_LONG_VIDEO_URL_HERE"  # Paste your long-form video link here
)


def download_video(url):
  print("Step 1: Downloading long video...")
  ydl_opts = {
      "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
      "outtmpl": "master_video.mp4",
  }
  with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
  print("-> Video downloaded successfully.")


def transcribe_video():
  print("Step 2: Transcribing audio with OpenAI Whisper...")
  model = whisper.load_model("base")
  result = model.transcribe("master_video.mp4", word_timestamps=True)
  print("-> Transcription complete!")
  return result


def slice_vertical_clip(start_time, end_time, output_filename):
  print(
      f"Step 3: Slicing clip ({start_time}s to {end_time}s) and converting to"
      " 9:16 vertical..."
  )

  input_stream = ffmpeg.input("master_video.mp4", ss=start_time, to=end_time)

  # Center-crop widescreen (16:9) to vertical (9:16) format (1080x1920)
  video_stream = (
      input_stream.video.filter("crop", "ih*(9/16)", "ih", "(iw-ih*(9/16))/2", 0)
      .filter("scale", 1080, 1920)
  )

  audio_stream = input_stream.audio

  output_stream = ffmpeg.output(
      video_stream, audio_stream, output_filename, vcodec="libx264", acodec="aac"
  )
  ffmpeg.run(output_stream, overwrite_output=True, quiet=True)
  print(
      f"-> Vertical short video saved successfully as '{output_filename}'!"
  )


if __name__ == "__main__":
  # Uncomment the functions below to run your local test:
  # download_video(LONG_VIDEO_URL)
  # transcript = transcribe_video()
  # slice_vertical_clip(start_time=10, end_time=40, output_filename="my_short_video.mp4")

  print("Local Video Processing Pipeline is ready!")
