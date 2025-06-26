from urllib.parse import urlparse, parse_qs
import logging
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def extract_video_id(url: str) -> str:
    try:
        parsed = urlparse(url)
        # Handle youtu.be short links
        if 'youtu.be' in parsed.netloc:
            return parsed.path.strip('/').split('/')[0]
        # Handle youtube.com URLs
        if 'youtube.com' in parsed.netloc:
            # Try watch?v=VIDEO_ID
            video_id = parse_qs(parsed.query).get('v', [''])[0]
            if video_id:
                return video_id
            # Try /live/VIDEO_ID, /embed/VIDEO_ID, /v/VIDEO_ID
            match = re.search(r'/((live|embed|v)/)?([\w-]{11})', parsed.path)
            if match:
                return match.group(3)
        return ''
    except Exception as e:
        logging.error(f"Error extracting video ID from URL {url}: {str(e)}")
        return ''

def extract_playlist_id(url: str) -> str:
    try:
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
            query_params = parse_qs(parsed.query)
            return query_params.get('list', [''])[0]
        return ''
    except Exception as e:
        logging.error(f"Error extracting playlist ID from URL {url}: {str(e)}")
        return ''

def normalize_youtube_url(url: str) -> str:
    video_id = extract_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url