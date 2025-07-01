import subprocess
import glob
import os
import tempfile
import logging
from openai import OpenAI
from config import OPENAI_API_KEY, YOUTUBE_API_KEY
import math

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

def split_mp4_ffmpeg(mp4_file, max_size=24*1024*1024):
    """
    Split MP4 file into MP3 chunks for Whisper transcription.
    """
    file_size = os.path.getsize(mp4_file)
    if file_size <= max_size:
        return [mp4_file]
    
    # Get duration in seconds
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
         'default=noprint_wrappers=1:nokey=1', mp4_file],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())
    
    # Estimate number of chunks
    num_chunks = math.ceil(file_size / max_size)
    chunk_duration = duration / num_chunks
    chunk_paths = []
    
    for i in range(num_chunks):
        start = i * chunk_duration
        chunk_path = f"{mp4_file}_chunk_{i}.mp3"
        
        # Convert MP4 chunk to MP3 for Whisper
        cmd = [
            'ffmpeg', '-y', '-i', mp4_file,
            '-ss', str(int(start)),
            '-t', str(int(chunk_duration)),
            '-vn',  # No video
            '-acodec', 'libmp3lame',  # Use MP3 codec
            '-ar', '16000',  # Sample rate
            '-ac', '1',  # Mono audio
            '-b:a', '128k',  # Bitrate
            chunk_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            chunk_paths.append(chunk_path)
        else:
            logging.error(f"Failed to create chunk {i}: {result.stderr}")
    
    return chunk_paths

def split_audio_ffmpeg(audio_file, max_size=24*1024*1024):
    file_size = os.path.getsize(audio_file)
    if file_size <= max_size:
        return [audio_file]
    # Get duration in seconds
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
         'default=noprint_wrappers=1:nokey=1', audio_file],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())
    # Estimate number of chunks
    num_chunks = math.ceil(file_size / max_size)
    chunk_duration = duration / num_chunks
    chunk_paths = []
    for i in range(num_chunks):
        start = i * chunk_duration
        chunk_path = f"{audio_file}_chunk_{i}.mp3"
        cmd = [
            'ffmpeg', '-y', '-i', audio_file,
            '-ss', str(int(start)),
            '-t', str(int(chunk_duration)),
            '-acodec', 'libmp3lame',  # Use MP3 codec instead of copy
            '-ar', '16000',  # Sample rate
            '-ac', '1',  # Mono audio
            '-b:a', '128k',  # Bitrate
            chunk_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            chunk_paths.append(chunk_path)
        else:
            logging.error(f"Failed to create chunk {i}: {result.stderr}")
    return chunk_paths

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
                    max_size = 24 * 1024 * 1024  # 24MB for safety
                    chunk_paths = split_audio_ffmpeg(audio_file, max_size)
                    full_transcript = ""
                    for chunk_path in chunk_paths:
                        with open(chunk_path, "rb") as f:
                            logging.info(f"Transcribing audio chunk {chunk_path} with OpenAI Whisper...")
                            transcription = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=f,
                                response_format="text"
                            )
                        if transcription:
                            full_transcript += transcription + "\n"
                        if chunk_path != audio_file:
                            os.remove(chunk_path)
                    return {"content": full_transcript}
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
        content = response.choices[0].message.content
        if content:
            return content.strip()
        else:
            first_words = text.split()[:6]
            return "_".join(first_words).replace(" ", "_")
    except Exception as e:
        logging.error(f"Error generating title: {str(e)}")
        first_words = text.split()[:6]
        return "_".join(first_words).replace(" ", "_")