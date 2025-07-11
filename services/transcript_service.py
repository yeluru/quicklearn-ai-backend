from fastapi import APIRouter, Request, File, UploadFile, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import json
import requests
import io
import tempfile
import os
from PyPDF2 import PdfReader
from docx import Document
from config import YOUTUBE_API_KEY, OPENAI_API_KEY
from utils.url_utils import extract_video_id, extract_playlist_id, normalize_youtube_url
from utils.text_utils import clean_transcript_text, parse_vtt_content, format_transcript, parse_vtt_with_timestamps, clean_and_aggregate_transcript
from utils.youtube_utils import get_transcript_via_ytdlp, get_transcript_via_audio, generate_title, split_audio_ffmpeg, split_mp4_ffmpeg, get_transcript_from_worker
from exceptions.custom_exceptions import TranscriptError
from openai import OpenAI
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter()
client = OpenAI(api_key=OPENAI_API_KEY)

def is_audio_file_url(url: str) -> bool:
    """Check if URL points to a direct audio file"""
    try:
        url_lower = url.lower()
        # Check for common audio file extensions (including MP4 which can contain audio)
        audio_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma', '.aiff', '.mp4']
        return any(ext in url_lower for ext in audio_extensions)
    except:
        return False

def is_audio_platform_url(url: str) -> bool:
    """Check if URL is from an audio streaming platform"""
    try:
        url_lower = url.lower()
        audio_platforms = [
            'spotify.com', 'soundcloud.com', 'apple.co', 'music.apple.com',
            'deezer.com', 'tidal.com', 'amazon.com/music', 'youtube.com/music',
            'bandcamp.com', 'audiomack.com', 'reverbnation.com'
        ]
        return any(platform in url_lower for platform in audio_platforms)
    except:
        return False

async def stream_audio_file_transcript(url: str):
    """Stream transcript from direct audio file URL"""
    try:
        yield f"data: {json.dumps({'type': 'progress', 'message': 'Downloading audio file...'})}\n\n"
        await asyncio.sleep(0.1)
        
        # Download the audio file with proper headers and redirect handling
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # First, try to get the actual download URL for services like Dropbox
        if 'dropbox.com' in url.lower():
            # For Dropbox, we need to modify the URL to force download
            if '?dl=0' in url:
                url = url.replace('?dl=0', '?dl=1')
            elif '&dl=0' in url:
                url = url.replace('&dl=0', '&dl=1')
            else:
                url += '&dl=1' if '?' in url else '?dl=1'
        elif 'drive.google.com' in url.lower():
            # For Google Drive, convert to direct download
            if '/file/d/' in url:
                file_id = url.split('/file/d/')[1].split('/')[0]
                url = f"https://drive.google.com/uc?export=download&id={file_id}"
            elif '/open?' in url:
                # Handle shared links with open parameter
                file_id = url.split('id=')[1].split('&')[0]
                url = f"https://drive.google.com/uc?export=download&id={file_id}"
            elif '/view?' in url:
                # Handle shared links with view parameter
                file_id = url.split('id=')[1].split('&')[0]
                url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            # Add additional headers for Google Drive
            headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
        elif '1drv.ms' in url.lower() or 'onedrive.live.com' in url.lower():
            # For OneDrive, we need to handle redirects properly
            # The URL will be handled by the redirect following
            pass
        elif 'box.com' in url.lower():
            # For Box, try to get direct download
            if '/s/' in url:
                # Convert shared link to direct download
                url = url.replace('/s/', '/s/') + '?dl=1'
        
        response = await asyncio.to_thread(requests.get, url, stream=True, timeout=60, headers=headers, allow_redirects=True)
        response.raise_for_status()
        
        # Handle Google Drive confirmation page for large files
        if 'drive.google.com' in url.lower() and 'text/html' in response.headers.get('content-type', '').lower():
            # Check if we got a confirmation page
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
            content_str = content.decode('utf-8', errors='ignore')
            
            if 'confirm=' in content_str:
                # Extract the confirmation token
                import re
                confirm_match = re.search(r'confirm=([^&"]+)', content_str)
                if confirm_match:
                    confirm_token = confirm_match.group(1)
                    # Make the actual download request with the confirmation token
                    download_url = f"{url}&confirm={confirm_token}"
                    response = await asyncio.to_thread(requests.get, download_url, stream=True, timeout=60, headers=headers, allow_redirects=True)
                    response.raise_for_status()
        
        # Check if we got an actual audio file
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type or 'text/plain' in content_type:
            # We got an HTML page instead of an audio file
            yield f"data: {json.dumps({'type': 'error', 'message': 'Unable to access audio file directly. Please ensure the URL provides direct file access.'})}\n\n"
            return
        
        # Get file extension from URL or content-type
        file_extension = 'mp3'  # Default
        if '.' in url:
            file_extension = url.split('.')[-1].lower().split('?')[0]  # Remove query params
        elif 'audio/' in content_type:
            # Extract extension from content-type
            if 'audio/mpeg' in content_type or 'audio/mp3' in content_type:
                file_extension = 'mp3'
            elif 'audio/wav' in content_type:
                file_extension = 'wav'
            elif 'audio/mp4' in content_type or 'audio/m4a' in content_type:
                file_extension = 'm4a'
            elif 'audio/ogg' in content_type:
                file_extension = 'ogg'
            elif 'audio/flac' in content_type:
                file_extension = 'flac'
        
        # Validate file extension
        valid_extensions = ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac', 'wma', 'aiff', 'mp4', 'mpeg', 'mpga', 'oga', 'webm']
        if file_extension not in valid_extensions:
            file_extension = 'mp3'  # Default to mp3 if invalid
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_file:
            # Download the file
            total_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
                total_size += len(chunk)
            
            temp_file_path = temp_file.name
        
        try:
            yield f"data: {json.dumps({'type': 'progress', 'message': f'Processing audio file ({total_size // 1024 // 1024}MB)...'})}\n\n"
            await asyncio.sleep(0.1)
            
            # Check file size and chunk if necessary
            file_size = os.path.getsize(temp_file_path)
            max_size = 24 * 1024 * 1024  # 24MB for safety
            
            if file_size > max_size:
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Large file detected, chunking for processing...'})}\n\n"
                await asyncio.sleep(0.1)
                
                # Use appropriate chunking method
                if file_extension in ['mp4', 'm4a']:
                    chunk_paths = split_mp4_ffmpeg(temp_file_path, max_size)
                else:
                    chunk_paths = split_audio_ffmpeg(temp_file_path, max_size)
                
                full_transcript = ""
                
                for i, chunk_path in enumerate(chunk_paths):
                    try:
                        yield f"data: {json.dumps({'type': 'progress', 'message': f'Transcribing chunk {i+1}/{len(chunk_paths)}...'})}\n\n"
                        await asyncio.sleep(0.1)
                        
                        with open(chunk_path, "rb") as audio_file:
                            transcription = await asyncio.to_thread(
                                client.audio.transcriptions.create,
                                model="whisper-1",
                                file=audio_file,
                                response_format="text"
                            )
                        
                        if transcription:
                            full_transcript += transcription + "\n"
                            # Stream the chunk
                            chunk_size = 400
                            words = transcription.split(' ')
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
                        
                        # Clean up chunk file
                        if chunk_path != temp_file_path:
                            os.remove(chunk_path)
                            
                    except Exception as chunk_error:
                        logging.error(f"Error transcribing chunk {i+1}: {str(chunk_error)}")
                        if chunk_path != temp_file_path and os.path.exists(chunk_path):
                            os.remove(chunk_path)
                
                if full_transcript.strip():
                    title = await asyncio.to_thread(generate_title, full_transcript)
                    yield f"data: {json.dumps({'type': 'title', 'content': title})}\n\n"
                    yield f"data: {json.dumps({'type': 'complete', 'method': 'audio_file'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'No transcript generated from audio file'})}\n\n"
                    
            else:
                # Small file, transcribe directly
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Transcribing audio file...'})}\n\n"
                await asyncio.sleep(0.1)
                
                with open(temp_file_path, "rb") as audio_file:
                    transcription = await asyncio.to_thread(
                        client.audio.transcriptions.create,
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )
                
                if transcription:
                    title = await asyncio.to_thread(generate_title, transcription)
                    yield f"data: {json.dumps({'type': 'title', 'content': title})}\n\n"
                    
                    # Stream the transcript
                    chunk_size = 400
                    words = transcription.split(' ')
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
                    
                    yield f"data: {json.dumps({'type': 'complete', 'method': 'audio_file'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'No transcript generated from audio file'})}\n\n"
                    
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        logging.error(f"Error in audio file streaming: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

async def stream_single_video_transcript(url: str):
    try:
        yield f"data: {json.dumps({'type': 'progress', 'message': 'Checking for subtitles...'})}\n\n"
        await asyncio.sleep(0.1)
        
        subtitle_result = await asyncio.to_thread(get_transcript_via_ytdlp, url)
        
        if subtitle_result.get("content"):
            transcript = clean_transcript_text(parse_vtt_content(subtitle_result["content"]))
            logging.info(f"Subtitle transcript length after cleaning: {len(transcript)}")
            if transcript.strip():
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Subtitles found, processing...'})}\n\n"
                await asyncio.sleep(0.1)
                
                title = generate_title(transcript)
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
        
        yield f"data: {json.dumps({'type': 'progress', 'message': 'No subtitles found or empty, downloading audio...'})}\n\n"
        await asyncio.sleep(0.1)
        
        audio_result = await asyncio.to_thread(get_transcript_via_audio, url)
        
        if audio_result.get("content"):
            transcript = clean_transcript_text(audio_result["content"])
            logging.info(f"Audio transcript length after cleaning: {len(transcript)}")
            if transcript.strip():
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Audio transcribed, processing...'})}\n\n"
                
                title = generate_title(transcript)
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

async def stream_playlist_transcript(playlist_id: str):
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
                    subtitle_result = await asyncio.to_thread(get_transcript_via_ytdlp, video_url)
                    
                    if subtitle_result.get("content"):
                        success_count += 1
                        transcript = clean_transcript_text(parse_vtt_content(subtitle_result["content"]))
                        video_header = f"=== {video_title} ===\n\n"
                        yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': video_header})}\n\n"
                        
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

@router.post("/stream")
async def stream_video_transcript(request: Request):
    try:
        body = await request.json()
        url = body.get("url")
        if not url:
            raise TranscriptError("URL is required")
        
        logging.info(f"Starting streaming transcript for URL: {url}")
        
        # Check if it's a direct audio file URL
        if is_audio_file_url(url):
            logging.info(f"Detected direct audio file URL: {url}")
            return StreamingResponse(
                stream_audio_file_transcript(url),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        
        # Check if it's an audio platform URL
        if is_audio_platform_url(url):
            logging.info(f"Detected audio platform URL: {url}")
            return StreamingResponse(
                stream_audio_file_transcript(url),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        
        # Check for YouTube playlist
        playlist_id = extract_playlist_id(url)
        if playlist_id:
            logging.info(f"Detected YouTube playlist ID: {playlist_id}")
            return StreamingResponse(
                stream_playlist_transcript(playlist_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        else:
            logging.info(f"No YouTube playlist detected, processing as single video: {url}")
            return StreamingResponse(
                stream_single_video_transcript(normalize_youtube_url(url)),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )
    except TranscriptError as e:
        raise e
    except Exception as e:
        logging.error(f"Error setting up transcript stream: {str(e)}")
        raise TranscriptError(str(e))

@router.get("/single")
def get_youtube_transcript(url: str):
    try:
        logging.info(f"Received request for transcript with URL: {url}")
        
        playlist_id = extract_playlist_id(url)
        video_id = extract_video_id(url)
        # If both playlist and video ID are present, treat as playlist
        if playlist_id and video_id:
            logging.info(f"Detected both playlist and video ID, routing to playlist handler for playlist ID: {playlist_id}")
            return get_playlist_transcript(playlist_id)
        if playlist_id and not video_id:
            logging.info(f"Detected playlist URL with ID: {playlist_id}, routing to playlist handler")
            return get_playlist_transcript(playlist_id)
        if not video_id:
            logging.error(f"Invalid YouTube URL: {url}")
            raise TranscriptError("Invalid YouTube URL")

        logging.info(f"Extracted video ID: {video_id}")
        
        # Use the worker for transcript extraction
        transcript_result = get_transcript_from_worker(url)
        if transcript_result.get("transcript"):
            # If the method is subtitles, parse as plaintext paragraphs and aggregate
            if transcript_result.get("method") == "subtitles":
                logging.info(f"Processing subtitles transcript, method: {transcript_result.get('method')}")
                logging.info(f"Raw transcript (first 200 chars): {transcript_result['transcript'][:200]}")
                transcript = parse_vtt_content(transcript_result["transcript"])
                logging.info(f"After parse_vtt_content (first 200 chars): {transcript[:200]}")
                transcript = clean_and_aggregate_transcript(transcript)
                logging.info(f"After clean_and_aggregate_transcript (first 200 chars): {transcript[:200]}")
                logging.info(f"Returning cleaned/aggregated transcript (first 500 chars): {transcript[:500]}")
            else:
                transcript = transcript_result["transcript"]
                logging.info(f"Returning plain transcript (first 500 chars): {transcript[:500]}")
            return {
                "transcript": transcript,
                "method": transcript_result.get("method", "worker"),
            }
        else:
            raise TranscriptError(transcript_result.get("error", "Failed to get transcript from worker."))
    
    except TranscriptError as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise TranscriptError(str(e))

@router.get("/playlist")
def get_playlist_transcript(playlist_id: str):
    """
    Streams playlist transcript extraction, yielding each video's transcript as it's processed.
    """
    from fastapi.responses import StreamingResponse
    import json
    from utils.youtube_utils import get_transcript_from_worker
    
    def stream_playlist():
        try:
            page_token = ""
            video_count = 0
            success_count = 0
            failed_videos = []

            logging.info(f"Starting playlist transcript extraction for playlist ID: {playlist_id}")
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Starting playlist processing...'})}\n\n"

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
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to fetch playlist items from YouTube API.'})}\n\n"
                    return

                data = response.json()
                items = data.get("items", [])
                
                logging.info(f"Found {len(items)} videos in this batch")

                for item in items:
                    video_count += 1
                    video_id = item["snippet"]["resourceId"]["videoId"]
                    video_title = item["snippet"]["title"]
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    logging.info(f"Processing video {video_count}: {video_title} (ID: {video_id})")
                    yield f"data: {json.dumps({'type': 'progress', 'message': f'Processing video {video_count}: {video_title}'})}\n\n"
                    
                    try:
                        # Use the worker for each video
                        result = get_transcript_from_worker(video_url)
                        if result.get("transcript"):
                            transcript_text = result["transcript"]
                            # If subtitles, parse as plaintext paragraphs and aggregate
                            if result.get("method") == "subtitles":
                                transcript_text = parse_vtt_content(transcript_text)
                                transcript_text = clean_and_aggregate_transcript(transcript_text)
                            video_header = f"=== {video_title} ===\n\n"
                            success_count += 1
                            logging.info(f"✓ Successfully got transcript for: {video_title}")
                            
                            # Stream the video header and transcript
                            yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': video_header})}\n\n"
                            yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': transcript_text})}\n\n"
                            chunk = '\n\n' + '='*50 + '\n\n'
                            yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': chunk})}\n\n"
                        else:
                            failed_videos.append({"title": video_title, "id": video_id, "error": result.get("error", "Unknown error")})
                            logging.warning(f"✗ Could not get transcript for: {video_title} - {result.get('error', 'Unknown error')}")
                            yield f"data: {json.dumps({'type': 'progress', 'message': f'✗ Failed: {video_title}'})}\n\n"
                    except Exception as e:
                        failed_videos.append({"title": video_title, "id": video_id, "error": str(e)})
                        logging.warning(f"✗ Exception for {video_title}: {str(e)}")
                        yield f"data: {json.dumps({'type': 'progress', 'message': f'✗ Exception: {video_title}'})}\n\n"

                # Check for next page
                page_token = data.get("nextPageToken", "")
                if not page_token:
                    break

            logging.info(f"Playlist processing complete. Success: {success_count}, Failed: {len(failed_videos)}")
            yield f"data: {json.dumps({'type': 'complete', 'success': success_count, 'failed': len(failed_videos), 'failed_videos': failed_videos})}\n\n"
        except Exception as e:
            logging.error(f"Playlist transcript extraction error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(stream_playlist(), media_type="text/event-stream")

def stream_playlist_generator(playlist_id: str):
    """
    Generator function for playlist streaming that can be yielded from.
    """
    try:
        page_token = ""
        video_count = 0
        success_count = 0
        failed_videos = []

        logging.info(f"Starting playlist transcript extraction for playlist ID: {playlist_id}")
        yield f"data: {json.dumps({'type': 'progress', 'message': 'Starting playlist processing...'})}\n\n"

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
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to fetch playlist items from YouTube API.'})}\n\n"
                return

            data = response.json()
            items = data.get("items", [])
            
            logging.info(f"Found {len(items)} videos in this batch")

            for item in items:
                video_count += 1
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_title = item["snippet"]["title"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                logging.info(f"Processing video {video_count}: {video_title} (ID: {video_id})")
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Processing video {video_count}: {video_title}'})}\n\n"
                
                try:
                    result = get_transcript_via_ytdlp(video_url)
                    if result.get("content"):
                        transcript_text = clean_transcript_text(parse_vtt_content(result["content"]))
                        # If subtitles, parse as plaintext paragraphs and aggregate
                        if result.get("method") == "subtitles":
                            transcript_text = parse_vtt_content(result["content"])
                            transcript_text = clean_and_aggregate_transcript(transcript_text)
                        video_header = f"=== {video_title} ===\n\n"
                        success_count += 1
                        logging.info(f"✓ Successfully got transcript for: {video_title}")
                        
                        # Stream the video header and transcript
                        yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': video_header})}\n\n"
                        yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': transcript_text})}\n\n"
                        chunk = '\n\n' + '='*50 + '\n\n'
                        yield f"data: {json.dumps({'type': 'transcript_chunk', 'content': chunk})}\n\n"
                    else:
                        failed_videos.append({"title": video_title, "id": video_id, "error": result.get("error", "Unknown error")})
                        logging.warning(f"✗ Could not get transcript for: {video_title} - {result.get('error', 'Unknown error')}")
                        yield f"data: {json.dumps({'type': 'progress', 'message': f'✗ Failed: {video_title}'})}\n\n"
                        
                except Exception as e:
                    failed_videos.append({"title": video_title, "id": video_id, "error": str(e)})
                    logging.warning(f"✗ Failed to fetch transcript for video '{video_title}' (ID: {video_id}): {str(e)}")
                    yield f"data: {json.dumps({'type': 'progress', 'message': f'✗ Error with {video_title}: {str(e)}'})}\n\n"
                    continue

            if "nextPageToken" in data:
                page_token = data["nextPageToken"]
                logging.info(f"Moving to next page with token: {page_token}")
            else:
                break

        summary = f"Playlist processing complete! Successfully transcribed {success_count}/{video_count} videos"
        logging.info(f"✓ {summary}")
        yield f"data: {json.dumps({'type': 'complete', 'message': summary, 'stats': {'total': video_count, 'success': success_count}})}\n\n"
        
    except Exception as e:
        logging.error(f"Error in playlist streaming: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        
        # Handle audio files with audio transcription
        audio_extensions = ['.mp4', '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma', '.aiff']
        if file and file.filename and any(file.filename.lower().endswith(ext) for ext in audio_extensions):
            import tempfile
            import os
            from openai import OpenAI
            from config import OPENAI_API_KEY
            
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            # Get the file extension
            file_extension = os.path.splitext(file.filename.lower())[1]
            
            # Save audio file to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                temp_file.write(contents)
                temp_file_path = temp_file.name
            
            try:
                # Check file size and chunk if necessary
                file_size = os.path.getsize(temp_file_path)
                max_size = 24 * 1024 * 1024  # 24MB for safety
                
                if file_size > max_size:
                    logging.info(f"Audio file is large ({file_size} bytes), chunking for transcription")
                    try:
                        # Use different chunking methods based on file type
                        if file_extension in ['.mp4', '.m4a']:
                            chunk_paths = split_mp4_ffmpeg(temp_file_path, max_size)
                        else:  # All other audio formats
                            chunk_paths = split_audio_ffmpeg(temp_file_path, max_size)
                        
                        full_transcript = ""
                        
                        for i, chunk_path in enumerate(chunk_paths):
                            try:
                                with open(chunk_path, "rb") as audio_file:
                                    logging.info(f"Transcribing audio chunk {i+1}/{len(chunk_paths)}: {chunk_path}")
                                    transcription = client.audio.transcriptions.create(
                                        model="whisper-1",
                                        file=audio_file,
                                        response_format="text"
                                    )
                                if transcription:
                                    full_transcript += transcription + "\n"
                                # Clean up chunk file
                                if chunk_path != temp_file_path:
                                    os.remove(chunk_path)
                            except Exception as chunk_error:
                                logging.error(f"Error transcribing chunk {i+1}: {str(chunk_error)}")
                                # Continue with other chunks
                                if chunk_path != temp_file_path and os.path.exists(chunk_path):
                                    os.remove(chunk_path)
                        
                        text = full_transcript if full_transcript else "No transcript available."
                    except Exception as chunking_error:
                        logging.error(f"Error during chunking: {str(chunking_error)}")
                        # Fallback to direct transcription (might fail for large files)
                        with open(temp_file_path, "rb") as audio_file:
                            logging.info(f"Fallback: Transcribing audio file directly: {file.filename}")
                            transcription = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                response_format="text"
                            )
                        text = transcription if transcription else "No transcript available."
                else:
                    # Small file, transcribe directly
                    with open(temp_file_path, "rb") as audio_file:
                        logging.info(f"Transcribing audio file: {file.filename}")
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            response_format="text"
                        )
                    text = transcription if transcription else "No transcript available."
                
                title = generate_title(text)
                return {"transcript": text, "title": title}
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        
        # Handle other file types
        elif file and file.filename and file.filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(contents))
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif file and file.filename and file.filename.endswith(".docx"):
            doc = Document(io.BytesIO(contents))
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            text = contents.decode("utf-8")
        
        title = generate_title(text)
        return {"transcript": text, "title": title}
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        raise TranscriptError(str(e))

def stream_audio_transcription(url: str):
    import glob, os, tempfile, logging, json
    from config import OPENAI_API_KEY
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    import subprocess
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
            logging.info("Downloading audio for streaming transcription...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                audio_files = glob.glob(f'{temp_dir}/*.mp3')
                if audio_files:
                    audio_file = audio_files[0]
                    max_size = 24 * 1024 * 1024  # 24MB for safety
                    from utils.youtube_utils import split_audio_ffmpeg
                    chunk_paths = split_audio_ffmpeg(audio_file, max_size)
                    for chunk_path in chunk_paths:
                        with open(chunk_path, "rb") as f:
                            logging.info(f"Transcribing audio chunk {chunk_path} with OpenAI Whisper (stream)...")
                            transcription = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=f,
                                response_format="text"
                            )
                        if transcription:
                            yield f"data: {{\"type\": \"transcript_chunk\", \"content\": {json.dumps(transcription)} }}\n\n"
                        if chunk_path != audio_file:
                            os.remove(chunk_path)
                    yield f"data: {{\"type\": \"complete\", \"method\": \"audio\"}}\n\n"
                    return
            logging.error(f"Audio download failed: {result.stderr}")
            yield f"data: {{\"type\": \"error\", \"message\": \"Failed to download audio\"}}\n\n"
    except Exception as e:
        logging.error(f"Audio streaming transcription error: {str(e)}")
        yield f"data: {{\"type\": \"error\", \"message\": {json.dumps(str(e))} }}\n\n"

@router.get("/segments")
def get_transcript_segments(url: str = Query(..., description="YouTube video URL or ID")):
    """
    Returns transcript segments with timestamps for a given video URL (YouTube, Vimeo, Instagram, etc.).
    Always uses the home worker for processing.
    """
    from utils.youtube_utils import get_transcript_from_worker
    try:
        if not url or not url.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid video URL")
        playlist_id = extract_playlist_id(url)
        video_id = extract_video_id(url)
        # If both playlist and video ID are present, treat as playlist
        if playlist_id and video_id:
            logging.info(f"Detected both playlist and video ID, routing to playlist handler for playlist ID: {playlist_id}")
            return get_playlist_transcript(playlist_id)
        if playlist_id and not video_id:
            logging.info(f"Detected playlist URL with ID: {playlist_id}, routing to playlist handler")
            return get_playlist_transcript(playlist_id)
        # Always use the worker for any video URL
        transcript_result = get_transcript_from_worker(url)
        if transcript_result.get("transcript"):
            if transcript_result.get("method") == "subtitles":
                logging.info(f"[SEGMENTS] Processing subtitles transcript, method: {transcript_result.get('method')}")
                logging.info(f"[SEGMENTS] Raw transcript (first 200 chars): {transcript_result['transcript'][:200]}")
                transcript = parse_vtt_content(transcript_result["transcript"])
                logging.info(f"[SEGMENTS] After parse_vtt_content (first 200 chars): {transcript[:200]}")
                transcript = clean_and_aggregate_transcript(transcript)
                logging.info(f"[SEGMENTS] After clean_and_aggregate_transcript (first 200 chars): {transcript[:200]}")
            else:
                transcript = transcript_result["transcript"]
            return {"segments": None, "transcript": transcript}
        else:
            raise HTTPException(status_code=500, detail=transcript_result.get("error", "Failed to get transcript from worker."))
    except Exception as e:
        logging.error(f"Transcript segment fetch error for {url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch transcript segments: {str(e)}")