from fastapi import APIRouter, Request, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import json
import requests
import io
from PyPDF2 import PdfReader
from docx import Document
from config import YOUTUBE_API_KEY
from utils.url_utils import extract_video_id, extract_playlist_id, normalize_youtube_url
from utils.text_utils import clean_transcript_text, parse_vtt_content, format_transcript
from utils.youtube_utils import get_transcript_via_ytdlp, get_transcript_via_audio, generate_title
from exceptions.custom_exceptions import TranscriptError
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter()

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
        raise TranscriptError(str(e), status_code=500)

@router.get("/single")
def get_youtube_transcript(url: str):
    try:
        logging.info(f"Received request for transcript with URL: {url}")
        
        playlist_id = extract_playlist_id(url)
        if playlist_id:
            logging.info(f"Detected playlist URL with ID: {playlist_id}, routing to playlist handler")
            return get_playlist_transcript(playlist_id)
        
        video_id = extract_video_id(url)
        if not video_id:
            logging.error(f"Invalid YouTube URL: {url}")
            raise TranscriptError("Invalid YouTube URL")

        logging.info(f"Extracted video ID: {video_id}")
        
        transcript_result = get_transcript_via_ytdlp(url)
        if transcript_result.get("content"):
            transcript_text = clean_transcript_text(parse_vtt_content(transcript_result["content"]))
            logging.info(f"Successfully retrieved transcript via yt-dlp for video ID: {video_id}")
            return {
                "transcript": transcript_text,
                "title": generate_title(transcript_text),
                "method": "yt-dlp_subtitles"
            }
        
        logging.info(f"No subtitles found, trying audio transcription for video ID: {video_id}")
        audio_result = get_transcript_via_audio(url)
        if audio_result.get("content"):
            transcript_text = clean_transcript_text(audio_result["content"])
            logging.info(f"Successfully retrieved transcript via audio for video ID: {video_id}")
            return {
                "transcript": transcript_text,
                "title": generate_title(transcript_text),
                "method": "whisper_audio"
            }
        
        logging.error(f"All methods failed for video ID: {video_id}")
        raise TranscriptError("No transcript available for this video. Try a different video with captions or clear audio.")
        
    except TranscriptError as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise TranscriptError(str(e))

@router.get("/playlist")
def get_playlist_transcript(playlist_id: str):
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
                raise TranscriptError("Failed to fetch playlist items from YouTube API.")

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
                    result = get_transcript_via_ytdlp(video_url)
                    if result.get("content"):
                        transcript_text = clean_transcript_text(parse_vtt_content(result["content"]))
                        all_text.append(f"=== {video_title} ===\n\n{transcript_text}")
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

            if "nextPageToken" in data:
                page_token = data["nextPageToken"]
                logging.info(f"Moving to next page with token: {page_token}")
            else:
                break

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
                    "failed_videos": failed_videos[:10]
                },
                "method": "enhanced_playlist_processing"
            }
        else:
            logging.error(f"No transcripts could be extracted from any of the {video_count} videos in the playlist")
            raise TranscriptError(f"No transcripts available for any of the {video_count} videos in this playlist.")
        
    except TranscriptError as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error while fetching playlist transcript: {str(e)}")
        raise TranscriptError(str(e))

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        if file.filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(contents))
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif file.filename.endswith(".docx"):
            doc = Document(io.BytesIO(contents))
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            text = contents.decode("utf-8")
        title = generate_title(text)
        return {"transcript": text, "title": title}
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        raise TranscriptError(str(e))