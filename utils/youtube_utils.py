import subprocess
import glob
import os
import tempfile
import logging
from openai import OpenAI
from config import OPENAI_API_KEY, YOUTUBE_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
client = OpenAI(api_key=OPENAI_API_KEY)

def get_transcript_via_ytdlp(url: str) -> dict:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = [
                'yt-dlp',
                '--write-sub',
                '--write-auto-sub',
                '--sub-langs', 'en,en-US,en-GB',
                '--sub-format', 'vtt',
                '--skip-download',
                '--no-warnings',
                '-o', f'{temp_dir}/%(title)s.%(ext)s',
                url
            ]
            logging.info(f"Running yt-dlp command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                vtt_files = glob.glob(f'{temp_dir}/*.vtt')
                if vtt_files:
                    with open(vtt_files[0], 'r', encoding='utf-8') as f:
                        content = f.read()
                    logging.info(f"VTT content length: {len(content)}")
                    return {"content": content}
                else:
                    logging.info("No VTT files found")
            else:
                logging.warning(f"yt-dlp failed: {result.stderr}")
            return {"error": "No subtitles found"}
    except subprocess.TimeoutExpired:
        logging.error("yt-dlp command timed out")
        return {"error": "Request timed out"}
    except Exception as e:
        logging.error(f"yt-dlp error: {str(e)}")
        return {"error": str(e)}

def get_transcript_via_audio(url: str) -> dict:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = [
                'yt-dlp',
                '--extract-audio',
                '--audio-format', 'mp3',
                '--audio-quality', '192K',
                '--no-warnings',
                '-o', f'{temp_dir}/%(title)s.%(ext)s',
                url
            ]
            logging.info("Downloading audio for transcription...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                audio_files = glob.glob(f'{temp_dir}/*.mp3')
                if audio_files:
                    audio_file = audio_files[0]
                    file_size = os.path.getsize(audio_file)
                    if file_size > 25 * 1024 * 1024:  # 25MB
                        return {"error": "Audio file too large for transcription"}
                    with open(audio_file, "rb") as f:
                        logging.info("Transcribing audio with OpenAI Whisper...")
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                            response_format="text"
                        )
                    if transcription:
                        return {"content": transcription}
            logging.error(f"Audio download failed: {result.stderr}")
            return {"error": "Failed to download audio"}
    except subprocess.TimeoutExpired:
        logging.error("Audio download timed out")
        return {"error": "Audio download timed out"}
    except Exception as e:
        logging.error(f"Audio transcription error: {str(e)}")
        return {"error": str(e)}

def generate_title(text: str) -> str:
    try:
        title_prompt = f"Generate a short, clear title (5-8 words) for the following content:\n\n{text[:1500]}"
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": title_prompt}],
            max_tokens=20
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error generating title: {str(e)}")
        first_words = text.split()[:6]
        return "_".join(first_words).replace(" ", "_")