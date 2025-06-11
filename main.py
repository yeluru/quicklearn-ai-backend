from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv
import os
import io
import tempfile
from typing import Optional
from PyPDF2 import PdfReader
from docx import Document
from urllib.parse import urlparse, parse_qs
import requests
import textwrap
import re
import logging
import subprocess
import json
import glob
from pathlib import Path
from pydantic import BaseModel
import time
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
origins = os.getenv("ALLOWED_ORIGINS", "").split(",")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_video_id(url):
    parsed = urlparse(url)
    if 'youtu.be' in parsed.netloc:
        # Handles: https://youtu.be/VIDEOID?params
        return parsed.path.strip('/').split('/')[0]
    if 'youtube.com' in parsed.netloc:
        # Handles: https://www.youtube.com/watch?v=VIDEOID
        return parse_qs(parsed.query).get('v', [None])[0]
    return None

def extract_playlist_id(url: str) -> Optional[str]:
    """
    Extract playlist ID from various YouTube playlist URL formats
    """
    try:
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
            query_params = parse_qs(parsed.query)
            return query_params.get('list', [None])[0]
        return None
    except Exception as e:
        logging.error(f"Error extracting playlist ID from URL {url}: {str(e)}")
        return None

def normalize_youtube_url(url):
    video_id = extract_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url

# Transcript Streaming Endpoints and Functions

@app.get("/transcript-stream")
async def stream_video_transcript_get(url: str):
    """
    Stream transcript extraction with real-time progress updates (GET version)
    """
    return await stream_video_transcript({"url": url})

@app.post("/transcript-stream")
async def stream_video_transcript(request: Request):
    """
    Stream transcript extraction with real-time progress updates
    """
    try:
        body = await request.json()
        url = body.get("url")
        if not url:
            return JSONResponse(content={"error": "URL is required"}, status_code=400)
        
        logging.info(f"Starting streaming transcript for URL: {url}")
        
        async def transcript_generator():
            try:
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Analyzing URL...'})}\n\n"
                await asyncio.sleep(0.1)
                
                # Check for YouTube playlist
                playlist_id = extract_playlist_id(url)
                if playlist_id:
                    logging.info(f"Detected YouTube playlist ID: {playlist_id}")
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Playlist detected, processing videos...'})}\n\n"
                    async for chunk in stream_playlist_transcript(playlist_id):
                        yield chunk
                else:
                    logging.info(f"No YouTube playlist detected, processing as single video: {url}")
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Extracting transcript...'})}\n\n"
                    async for chunk in stream_single_video_transcript(url):
                        yield chunk
                        
            except Exception as e:
                logging.error(f"Error in transcript streaming: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(
            transcript_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        logging.error(f"Error setting up transcript stream: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
       
async def process_transcript_stream(url: str):
    """
    Shared logic for transcript streaming
    """
    try:
        logging.info(f"Starting streaming transcript for URL: {url}")
        
        async def transcript_generator():
            try:
                # Send initial status
                yield f"data: {json.dumps({'status': 'starting', 'message': 'Analyzing URL...'})}\n\n"
                await asyncio.sleep(0.1)
                
                # Check if it's a playlist URL
                playlist_id = extract_playlist_id(url)
                if playlist_id:
                    yield f"data: {json.dumps({'status': 'playlist_detected', 'message': 'Playlist detected, processing videos...'})}\n\n"
                    async for chunk in stream_playlist_transcript(playlist_id):
                        yield chunk
                else:
                    # Handle single video
                    video_id = extract_video_id(url)
                    if not video_id:
                        yield f"data: {json.dumps({'status': 'error', 'message': 'Invalid YouTube URL'})}\n\n"
                        return
                    
                    yield f"data: {json.dumps({'status': 'processing', 'message': 'Extracting transcript...'})}\n\n"
                    async for chunk in stream_single_video_transcript(url):
                        yield chunk
                        
            except Exception as e:
                logging.error(f"Error in transcript streaming: {str(e)}")
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(
            transcript_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )
        
    except Exception as e:
        logging.error(f"Error setting up transcript stream: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

async def stream_playlist_transcript(playlist_id: str):
    """
    Stream playlist transcript extraction with progress updates
    """
    try:
        page_token = ""
        video_count = 0
        success_count = 0
        
        yield f"data: {json.dumps({'type': 'progress', 'message': 'Fetching playlist videos...'})}\n\n"
        
        while True:
            yt_api_url = (
                f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50"
                f"&playlistId={playlist_id}&key={YOUTUBE_API_KEY}"
            )
            if page_token:
                yt_api_url += f"&pageToken={page_token}"

            response = await asyncio.to_thread(requests.get, yt_api_url)
            
            if response.status_code != 200:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to fetch playlist items'})}\n\n"
                return

            data = response.json()
            items = data.get("items", [])
            
            for item in items:
                video_count += 1
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_title = item["snippet"]["title"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Processing video {video_count}: {video_title}'})}\n\n"
                
                try:
                    result = await asyncio.to_thread(get_single_video_transcript, video_url)
                    
                    if result.get("transcript"):
                        success_count += 1
                        video_header = f"=== {video_title} ===\n\n"
                        yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': video_header})}\n\n"
                        
                        transcript = clean_transcript_text(result["transcript"])
                        chunk_size = 400
                        words = transcript.split(' ')
                        current_chunk = ""
                        
                        for word in words:
                            if len(current_chunk + word + " ") <= chunk_size:
                                current_chunk += word + " "
                            else:
                                if current_chunk.strip():
                                    yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': current_chunk.strip()})}\n\n"
                                    await asyncio.sleep(0.02)
                                current_chunk = word + " "
                        
                        if current_chunk.strip():
                            yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': current_chunk.strip()})}\n\n"
                        
                        separator = f"\n\n{'='*50}\n\n"
                        yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': separator})}\n\n"
                        
                        yield f"data: {json.dumps({'type': 'progress', 'message': f'✓ Completed: {video_title}'})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'progress', 'message': f'✗ Failed: {video_title}'})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'progress', 'message': f'✗ Error with {video_title}: {str(e)}'})}\n\n"
                    continue

            if "nextPageToken" in data:
                page_token = data["nextPageToken"]
            else:
                break

        summary = f"Playlist processing complete! Successfully transcribed {success_count}/{video_count} videos"
        yield f"data: {json.dumps({'type': 'complete', 'message': summary, 'stats': {'total': video_count, 'success': success_count}})}\n\n"
    except Exception as e:
        logging.error(f"Error in playlist streaming: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

def clean_transcript_text(text: str) -> str:
    """
    Clean transcript text to remove duplicates and formatting issues
    """
    import re
    # Remove metadata like "Kind: captions Language: en"
    text = re.sub(r'^Kind:\s*captions\s*Language:\s*\w+\s*', '', text, flags=re.IGNORECASE)
    # Split into sentences and remove duplicates
    sentences = re.split(r'([.!?]+)', text)
    cleaned_sentences = []
    seen_sentences = set()
    
    current_sentence = ""
    for segment in sentences:
        current_sentence += segment
        if segment.strip().endswith(('.', '!', '?')) or len(current_sentence) > 200:
            clean_sentence = re.sub(r'\s+', ' ', current_sentence).strip()
            words = clean_sentence.split()
            unique_words = []
            prev_word = ""
            for word in words:
                if word != prev_word:
                    unique_words.append(word)
                    prev_word = word
            clean_sentence = ' '.join(unique_words)
            if (clean_sentence not in seen_sentences and 
                len(clean_sentence) > 10 and 
                not clean_sentence.lower().startswith('kind:')):
                cleaned_sentences.append(clean_sentence)
                seen_sentences.add(clean_sentence)
            current_sentence = ""
    
    if current_sentence.strip():
        clean_sentence = re.sub(r'\s+', ' ', current_sentence).strip()
        if len(clean_sentence) > 10:
            cleaned_sentences.append(clean_sentence)
    
    # Join sentences and format into paragraphs
    full_text = ' '.join(cleaned_sentences)
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    paragraphs = []
    current_paragraph = []
    for sentence in sentences:
        current_paragraph.append(sentence)
        if len(current_paragraph) >= 3:
            paragraphs.append(' '.join(current_paragraph))
            current_paragraph = []
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    return '\n\n'.join(paragraphs)

def parse_vtt_content(content: str) -> str:
    """
    Parse VTT subtitle content and extract clean text
    """
    lines = content.split('\n')
    transcript_lines = []
    for line in lines:
        line = line.strip()
        # Skip VTT headers, timestamps, and empty lines
        if (line and 
            not line.startswith('WEBVTT') and 
            '-->' not in line and 
            not line.isdigit() and
            not line.startswith('NOTE') and
            not line.startswith('STYLE')):
            # Remove VTT formatting tags
            clean_line = remove_vtt_tags(line)
            if clean_line:
                transcript_lines.append(clean_line)
    # Join and format
    text = ' '.join(transcript_lines)
    return format_transcript(text)

# Keep your existing non-streaming endpoints for backward compatibility
@app.get("/transcript")
def get_youtube_transcript(url: str):
    """
    Enhanced transcript function - now properly handles playlists
    """
    try:
        logging.info(f"Received request for transcript with URL: {url}")
        
        # FIRST: Check if it's a playlist URL
        playlist_id = extract_playlist_id(url)
        if playlist_id:
            logging.info(f"Detected playlist URL with ID: {playlist_id}, routing to playlist handler")
            return get_playlist_transcript(playlist_id)
        
        # THEN: Handle individual video
        video_id = extract_video_id(url)
        if not video_id:
            logging.error(f"Invalid YouTube URL: {url}")
            return {"error": "Invalid YouTube URL"}

        logging.info(f"Extracted video ID: {video_id}")
        
        # Method 1: Try yt-dlp for subtitles
        transcript_result = get_transcript_via_ytdlp(url)
        if transcript_result.get("transcript"):
            logging.info(f"Successfully retrieved transcript via yt-dlp for video ID: {video_id}")
            return transcript_result
        
        # Method 2: Fall back to audio transcription
        logging.info(f"No subtitles found, trying audio transcription for video ID: {video_id}")
        audio_result = get_transcript_via_audio(url)
        if audio_result.get("transcript"):
            logging.info(f"Successfully retrieved transcript via audio for video ID: {video_id}")
            return audio_result
        
        # If both methods fail
        logging.error(f"All methods failed for video ID: {video_id}")
        return {"error": "No transcript available for this video. Try a different video with captions or clear audio."}
        
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return {"error": str(e)}

async def stream_single_video_transcript(url: str):
    """
    Stream transcript extraction for a single video with fallback to audio if subtitles are unavailable or empty.
    """
    try:
        yield f"data: {json.dumps({'type': 'progress', 'message': 'Checking for subtitles...'})}\n\n"
        await asyncio.sleep(0.1)
        
        subtitle_result = await asyncio.to_thread(get_transcript_via_ytdlp, url)
        
        if subtitle_result.get("transcript"):
            transcript = clean_transcript_text(subtitle_result["transcript"])
            logging.info(f"Subtitle transcript length after cleaning: {len(transcript)}")
            if transcript.strip():  # Ensure transcript is not empty or whitespace
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Subtitles found, processing...'})}\n\n"
                await asyncio.sleep(0.1)
                
                title = subtitle_result.get("title", "Unknown Title")
                yield f"data: {json.dumps({'type': 'title', 'content': title})}\n\n"
                
                chunk_size = 400
                words = transcript.split(' ')
                current_chunk = ""
                
                for word in words:
                    if len(current_chunk + word + " ") <= chunk_size:
                        current_chunk += word + " "
                    else:
                        if current_chunk.strip():
                            yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': current_chunk.strip()})}\n\n"
                            await asyncio.sleep(0.03)
                        current_chunk = word + " "
                
                if current_chunk.strip():
                    yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': current_chunk.strip()})}\n\n"
                
                yield f"data: {json.dumps({'type': 'complete', 'method': 'subtitles'})}\n\n"
                return
            else:
                logging.warning("Subtitle transcript is empty after cleaning, falling back to audio")
        
        # Fallback to audio transcription
        yield f"data: {json.dumps({'type': 'progress', 'message': 'No subtitles found or empty, downloading audio...'})}\n\n"
        await asyncio.sleep(0.1)
        
        audio_result = await asyncio.to_thread(get_transcript_via_audio, url)
        
        if audio_result.get("transcript"):
            transcript = clean_transcript_text(audio_result["transcript"])
            logging.info(f"Audio transcript length after cleaning: {len(transcript)}")
            if transcript.strip():  # Ensure audio transcript is not empty
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Audio transcribed, processing...'})}\n\n"
                
                title = audio_result.get("title", "Unknown Title")
                yield f"data: {json.dumps({'type': 'title', 'content': title})}\n\n"
                
                chunk_size = 400
                words = transcript.split(' ')
                current_chunk = ""
                
                for word in words:
                    if len(current_chunk + word + " ") <= chunk_size:
                        current_chunk += word + " "
                    else:
                        if current_chunk.strip():
                            yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': current_chunk.strip()})}\n\n"
                            await asyncio.sleep(0.03)
                        current_chunk = word + " "
                
                if current_chunk.strip():
                    yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': current_chunk.strip()})}\n\n"
                
                yield f"data: {json.dumps({'type': 'complete', 'method': 'audio'})}\n\n"
                return
            else:
                logging.warning("Audio transcript is empty after processing")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Audio transcript is empty after processing'})}\n\n"
        else:
            logging.error(f"Audio transcription failed: {audio_result.get('error', 'Unknown error')}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'No transcript available for this video'})}\n\n"
        
    except Exception as e:
        logging.error(f"Error in single video streaming: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

def get_transcript_via_ytdlp(url: str):
    """
    Extract subtitles using yt-dlp with detailed logging for debugging.
    """
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
                    transcript_text = parse_vtt_content(content)
                    logging.info(f"Parsed transcript length: {len(transcript_text)}")
                    if transcript_text:
                        title = generate_title(transcript_text)
                        return {
                            "transcript": transcript_text,
                            "title": title,
                            "method": "yt-dlp_subtitles"
                        }
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

def get_transcript_via_audio(url: str):
    """
    Download audio and transcribe using OpenAI Whisper
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download audio only
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
                # Find audio file
                audio_files = glob.glob(f'{temp_dir}/*.mp3')
                if audio_files:
                    audio_file = audio_files[0]
                    file_size = os.path.getsize(audio_file)
                    # Check file size (OpenAI has 25MB limit)
                    if file_size > 25 * 1024 * 1024:  # 25MB
                        return {"error": "Audio file too large for transcription"}
                    # Transcribe with OpenAI Whisper
                    with open(audio_file, "rb") as f:
                        logging.info("Transcribing audio with OpenAI Whisper...")
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                            response_format="text"
                        )
                    if transcription:
                        # Format the transcript
                        formatted_text = format_transcript(transcription)
                        title = generate_title(formatted_text)
                        return {
                            "transcript": formatted_text,
                            "title": title,
                            "method": "whisper_audio"
                        }
            logging.error(f"Audio download failed: {result.stderr}")
            return {"error": "Failed to download audio"}
    except subprocess.TimeoutExpired:
        logging.error("Audio download timed out")
        return {"error": "Audio download timed out"}
    except Exception as e:
        logging.error(f"Audio transcription error: {str(e)}")
        return {"error": str(e)}

def get_single_video_transcript(video_url: str):
    """
    Get transcript for a single video (used by playlist processing)
    """
    try:
        # Method 1: Try yt-dlp for subtitles
        result = get_transcript_via_ytdlp(video_url)
        if result.get("transcript"):
            return result
        
        # Method 2: Try audio transcription (more resource intensive)
        # Only attempt audio for shorter videos to avoid timeouts
        logging.info(f"No subtitles found, trying audio transcription for: {video_url}")
        audio_result = get_transcript_via_audio(video_url)
        if audio_result.get("transcript"):
            return audio_result
        
        return {"error": "No transcript available"}
        
    except Exception as e:
        logging.error(f"Error getting transcript for {video_url}: {str(e)}")
        return {"error": str(e)}

@app.get("/playlist-transcript")
def get_playlist_transcript(playlist_id: str):
    """
    Enhanced playlist transcript function with better error handling
    """
    try:
        all_text = []
        all_titles = []
        page_token = ""
        video_count = 0
        success_count = 0
        failed_videos = []

        logging.info(f"Starting playlist transcript extraction for playlist ID: {playlist_id}")

        while True:
            yt_api_url = (
                f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50"
                f"&playlistId={playlist_id}&key={YOUTUBE_API_KEY}"
            )
            if page_token:
                yt_api_url += f"&pageToken={page_token}"

            logging.info(f"Fetching playlist items from URL: {yt_api_url}")
            response = requests.get(yt_api_url)

            if response.status_code != 200:
                logging.error(f"Failed to fetch playlist items: {response.text}")
                return {"error": "Failed to fetch playlist items from YouTube API."}

            data = response.json()
            items = data.get("items", [])
            
            logging.info(f"Found {len(items)} videos in this batch")

            for item in items:
                video_count += 1
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_title = item["snippet"]["title"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                logging.info(f"Processing video {video_count}: {video_title} (ID: {video_id})")
                
                try:
                    # Get transcript for single video
                    result = get_single_video_transcript(video_url)
                    
                    if result.get("transcript"):
                        all_text.append(f"=== {video_title} ===\n\n{result['transcript']}")
                        all_titles.append(video_title)
                        success_count += 1
                        logging.info(f"✓ Successfully got transcript for: {video_title}")
                    else:
                        failed_videos.append({"title": video_title, "id": video_id, "error": result.get("error", "Unknown error")})
                        logging.warning(f"✗ Could not get transcript for: {video_title} - {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    failed_videos.append({"title": video_title, "id": video_id, "error": str(e)})
                    logging.warning(f"✗ Failed to fetch transcript for video '{video_title}' (ID: {video_id}): {str(e)}")
                    continue

            # Check for next page
            if "nextPageToken" in data:
                page_token = data["nextPageToken"]
                logging.info(f"Moving to next page with token: {page_token}")
            else:
                break

        # Compile results
        if all_text:
            full_transcript = "\n\n" + "="*50 + "\n\n".join(all_text)
            logging.info(f"✓ Playlist processing complete! Successfully transcribed {success_count}/{video_count} videos")
            
            return {
                "transcript": full_transcript,
                "summary": {
                    "total_videos": video_count,
                    "successful_transcripts": success_count,
                    "failed_transcripts": video_count - success_count,
                    "video_titles": all_titles,
                    "failed_videos": failed_videos[:10]  # Only show first 10 failures
                },
                "method": "enhanced_playlist_processing"
            }
        else:
            logging.error(f"No transcripts could be extracted from any of the {video_count} videos in the playlist")
            return {
                "error": f"No transcripts available for any of the {video_count} videos in this playlist. Videos may not have captions or clear audio.",
                "summary": {
                    "total_videos": video_count,
                    "successful_transcripts": 0,
                    "failed_transcripts": video_count,
                    "failed_videos": failed_videos[:10]
                }
            }
        
    except Exception as e:
        logging.error(f"Unexpected error while fetching playlist transcript: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

def parse_vtt_content(content: str) -> str:
    """
    Parse VTT subtitle content and extract clean text
    """
    lines = content.split('\n')
    transcript_lines = []
    
    for line in lines:
        line = line.strip()
        # Skip VTT headers, timestamps, and empty lines
        if (line and 
            not line.startswith('WEBVTT') and 
            '-->' not in line and 
            not line.isdigit() and
            not line.startswith('NOTE') and
            not line.startswith('STYLE')):
            
            # Remove VTT formatting tags
            clean_line = remove_vtt_tags(line)
            if clean_line:
                transcript_lines.append(clean_line)
    
    # Join and format
    text = ' '.join(transcript_lines)
    return format_transcript(text)

def remove_vtt_tags(text: str) -> str:
    """
    Remove VTT formatting tags like <c>, <i>, etc.
    """
    import re
    # Remove HTML-like tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def format_transcript(text: str) -> str:
    """
    Format transcript text into readable paragraphs
    """
    import re
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    paragraphs = []
    current_paragraph = []
    for sentence in sentences:
        current_paragraph.append(sentence)
        if len(current_paragraph) >= 3:
            paragraphs.append(' '.join(current_paragraph))
            current_paragraph = []
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    return '\n\n'.join(paragraphs)

def generate_title(text: str) -> str:
    """
    Generate a title using OpenAI
    """
    try:
        title_prompt = f"Generate a short, clear title (5-8 words) for the following content:\n\n{text[:1500]}"
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": title_prompt}],
            max_tokens=20
        )
        return response.choices[0].message.content.strip().replace(" ", "_")
    except Exception as e:
        logging.error(f"Error generating title: {str(e)}")
        # Fallback to first few words
        first_words = text.split()[:6]
        return "_".join(first_words).replace(" ", "_")

@app.get("/enhanced-transcript")
def get_enhanced_transcript(url: str):
    """
    Enhanced transcript endpoint that handles both individual videos and playlists
    """
    try:
        logging.info(f"Received enhanced transcript request for URL: {url}")
        
        # Check if it's a playlist URL
        playlist_id = extract_playlist_id(url)
        if playlist_id:
            logging.info(f"Detected playlist URL with ID: {playlist_id}")
            return get_playlist_transcript(playlist_id)
        
        # Check if it's a regular video URL
        video_id = extract_video_id(url)
        if video_id:
            logging.info(f"Detected video URL with ID: {video_id}")
            return get_youtube_transcript(url)
        
        return {"error": "Invalid YouTube URL. Please provide a valid video or playlist URL."}
        
    except Exception as e:
        logging.error(f"Error in enhanced transcript endpoint: {str(e)}")
        return {"error": str(e)}

@app.get("/transcribe-audio")
def transcribe_audio(url: str, use_openai: Optional[bool] = True):
    try:
        audio = requests.get(url).content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(audio)
            tmp_path = tmp.name

        if use_openai:
            with open(tmp_path, "rb") as f:
                result = client.audio.transcriptions.create(model="whisper-1", file=f)
            return {"transcript": result.text}
        else:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(tmp_path)
            return {"transcript": result['text']}
    except Exception as e:
        return {"error": str(e)}

@app.post("/upload")
def upload_file(file: UploadFile = File(...)):
    try:
        contents = file.file.read()
        if file.filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(contents))
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif file.filename.endswith(".docx"):
            doc = Document(io.BytesIO(contents))
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            text = contents.decode("utf-8")
        return {"transcript": text}
    except Exception as e:
        return {"error": str(e)}

@app.post("/summarize-stream")
async def summarize_stream(request: Request):
    body = await request.json()
    transcript = body.get("transcript")
    use_openai = body.get("use_openai", True)

    if not transcript:
        return JSONResponse(content={"error": "Transcript is required."}, status_code=400)

    max_chunk_chars = 12000
    chunks = [transcript[i:i+max_chunk_chars] for i in range(0, len(transcript), max_chunk_chars)]

    def chunk_stream():
        for index, chunk in enumerate(chunks):
            prompt = f"""
You are an expert AI technical educator.

Write a highly engaging, well-structured, and richly informative educational article based on the following transcript segment:

{chunk}

Guidelines:
- Use **Markdown headings** to clearly structure sections and improve readability.
- Use smooth, storytelling transitions between sections.
- Explain all technical concepts clearly, using real-world metaphors, analogies, and examples wherever helpful.
- Include inline code explanations when code is referenced.
- Break down complex topics into approachable, logically flowing paragraphs.
- Avoid lists unless necessary — prefer narrative and paragraph-style teaching.
- The tone should be professional, approachable, and slightly conversational — like a great teacher guiding a curious learner.
- Continue from prior section naturally, as if writing part of a larger publication.
- Do NOT include an introduction or conclusion unless this is the start or end of the article.
- Your goal is to create a ready-to-publish educational piece that is insightful, clear, and enjoyable to read.

Avoid motivational filler or overuse of metaphors. Keep the writing focused, informative, and highly engaging for intelligent general readers.
"""
            stream = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                max_tokens=4096
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                yield content

    return StreamingResponse(chunk_stream(), media_type="text/plain")

@app.post("/qna-stream")
async def qna_stream(request: Request):
    body = await request.json()
    transcript = body.get("transcript")
    use_openai = body.get("use_openai", True)

    if not transcript:
        return JSONResponse(content={"error": "Transcript is required."}, status_code=400)

    max_chunk_chars = 12000
    chunks = [transcript[i:i+max_chunk_chars] for i in range(0, len(transcript), max_chunk_chars)]

    def chunk_stream():
        for chunk in chunks:
            prompt = f"""
You are an expert AI tutor creating study material for learners who want to master complex technical concepts.

Based on the following transcript, generate a thoughtful set of educational **question-and-answer pairs** that help reinforce key ideas:

{chunk}

Guidelines:
- Each **question** should probe a meaningful technical concept, mechanism, use case, or decision-making point in the content.
- Each **answer** should be detailed, educational, and include clear examples, analogies, or simple technical explanations to aid understanding.
- Format the Q&A using **Markdown** — use `### Question` and `**Answer:**` for clean structure.
- Avoid shallow or trivial questions. Focus on depth, clarity, and real-world relevance.
- Do NOT refer to the original speaker, transcript, or video.
- Avoid quiz-style or trivia tone — aim for a professional, learner-friendly teaching style.
- Make the material engaging and insightful enough to be part of a study guide or interview prep resource.
- ❌ Do NOT use first-person ("I", "we"), second-person ("you"), or narrative phrases like "let's explore" or "our journey".
- ✅ Use **impersonal, objective language**. Focus on clear technical statements using passive or neutral voice.
- Write as if the content is being published in a technical handbook or formal exam prep guide.
- Make the writing engaging and thought-provoking like a great teacher.
- Avoid filler and narrative clichés like "Let's embark" or "This journey shows us…".
- Use vivid, real-world analogies to explain abstract ideas. For example, compare agents to detectives, tools to Swiss army knives, or tracing to surveillance cameras.
- Use detailed walkthroughs to explain how things work. Show how an agent thinks step-by-step like debugging logic.
- Make every paragraph teach something — avoid summaries that merely rephrase.
- Do NOT use first-person ("we", "let's", "I"). Avoid vague phrases like "the conversation explored…".
- The tone should feel like a deep but clear technical guide that could be published in a professional learning platform.

Your goal is to create a series of high-quality, standalone Q&A entries that someone could learn from without seeing the original transcript.
"""
            stream = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                max_tokens=2048
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                yield content

    return StreamingResponse(chunk_stream(), media_type="text/plain")

def stream_openai_response(messages, max_tokens=1024):
    def generate():
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=True,
            max_tokens=max_tokens
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            yield content
    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/chat-on-topic")
async def chat_on_topic(request: Request):
    body = await request.json()
    summary = body.get("summary", "")
    chat_history = body.get("chatHistory", [])

    if not summary or not isinstance(chat_history, list):
        raise HTTPException(status_code=400, detail="Missing or invalid fields.")

    system_prompt = {
        "role": "system",
        "content": f"You are a helpful assistant. Use the following topic summary to answer questions:\n\n{summary}"
    }

    messages = [system_prompt] + chat_history
    return stream_openai_response(messages)

class SummaryInput(BaseModel):
    summary: str

@app.post("/suggested-questions")
def suggested_questions(req: SummaryInput):
    prompt = f"""
You are a helpful AI assistant. Read the following summary and generate distinct educational topics, each with 1 thoughtful question underneath.

Output format:
[
  {{ "topic": "AI in Education", "question": "How does AI improve learning outcomes for students?" }},
  {{ "topic": "AI and Human Collaboration", "question": "What is the role of humans in an AI-driven coding future?" }},
  ...
]

Summary:
\"\"\"
{req.summary}
\"\"\"
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a topic-question suggestion assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    text = response.choices[0].message.content

    try:
        questions = json.loads(text)
    except Exception:
        # fallback: parse manually if LLM didn't return JSON
        questions = []
        for line in text.split("\n"):
            if line.strip().startswith("{") and "topic" in line and "question" in line:
                try:
                    questions.append(json.loads(line.strip().rstrip(",")))
                except:
                    continue

    return {"questions": questions}