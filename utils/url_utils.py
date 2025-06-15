from urllib.parse import urlparse, parse_qs
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def extract_video_id(url: str) -> str:
    try:
        parsed = urlparse(url)
        if 'youtu.be' in parsed.netloc:
            return parsed.path.strip('/').split('/')[0]
        if 'youtube.com' in parsed.netloc:
            return parse_qs(parsed.query).get('v', [None])[0]
        return None
    except Exception as e:
        logging.error(f"Error extracting video ID from URL {url}: {str(e)}")
        return None

def extract_playlist_id(url: str) -> str:
    try:
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
            query_params = parse_qs(parsed.query)
            return query_params.get('list', [None])[0]
        return None
    except Exception as e:
        logging.error(f"Error extracting playlist ID from URL {url}: {str(e)}")
        return None

def normalize_youtube_url(url: str) -> str:
    video_id = extract_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url