# VibeKnowing Worker

## 🔥 Project Overview
**VibeKnowing Worker** is a specialized FastAPI service designed to handle YouTube video processing and transcription. It runs locally with a residential IP address to bypass YouTube's bot detection and data center IP restrictions, ensuring reliable video transcript extraction.

## 🎯 Core Features
- **YouTube Video Processing**: Download and extract transcripts from YouTube videos
- **Playlist Support**: Process entire YouTube playlists
- **Subtitle Extraction**: Extract VTT subtitle files when available
- **Audio Transcription**: Fallback to OpenAI Whisper for videos without subtitles
- **Large File Handling**: Split large audio files into chunks for processing
- **Residential IP**: Bypass YouTube bot detection using home network IP

## 🧠 Tech Stack
- **Python 3.11+**
- **FastAPI** - Modern web framework for building APIs
- **yt-dlp** - YouTube video downloading and processing
- **OpenAI Whisper** - Audio transcription (via OpenAI API)
- **ffmpeg-python** - Audio/video processing
- **Pydantic** - Data validation and serialization

## 📁 Project Structure
```
vibeknowing-worker/
├── worker.py                  # FastAPI worker application
├── requirements.txt           # Python dependencies
├── Procfile                  # Render deployment configuration
├── runtime.txt               # Python version specification
├── README.md                 # This file
├── test_worker.py            # Worker testing script
└── .gitignore               # Git ignore file
```

## ⚙️ Environment Setup

### Prerequisites
- Python 3.11 or higher
- FFmpeg installed on your system
- OpenAI API key
- ngrok account (for tunneling)

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd vibeknowing-worker
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install FFmpeg** (if not already installed)
   
   **macOS (using Homebrew):**
   ```bash
   brew install ffmpeg
   ```
   
   **Ubuntu/Debian:**
   ```bash
   sudo apt update
   sudo apt install ffmpeg
   ```
   
   **Windows:**
   - Download from https://ffmpeg.org/download.html
   - Add to system PATH

5. **Set environment variables**
   ```bash
   export OPENAI_API_KEY="your_openai_api_key_here"
   ```

## 🚀 Running the Worker

### Development Mode
```bash
# Start the development server
uvicorn worker:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
# Start the production server
uvicorn worker:app --host 0.0.0.0 --port 8000
```

### Using ngrok for Tunneling
```bash
# Install ngrok if not already installed
# Download from https://ngrok.com/download

# Start ngrok tunnel
ngrok http 8000

# Note the ngrok URL (e.g., https://abc123.ngrok-free.app)
# Update your backend's WORKER_URL environment variable with this URL
```

## 📚 API Documentation

### Base URL
- Local: `http://localhost:8000`
- Tunnelled: `https://your-ngrok-url.ngrok-free.app`

### Health Check
```bash
GET /health
Response: {"status": "healthy", "service": "VibeKnowing Worker"}
```

### Transcript Service (`/transcribe`)

#### Transcribe YouTube Video
```bash
POST /transcribe
Content-Type: application/json

Body:
{
  "url": "https://youtube.com/watch?v=VIDEO_ID"
}

Response:
{
  "transcript": "extracted transcript text...",
  "source": "subtitles" | "whisper",
  "duration": "video duration in seconds"
}
```

#### Transcribe YouTube Playlist
```bash
POST /transcribe
Content-Type: application/json

Body:
{
  "url": "https://youtube.com/playlist?list=PLAYLIST_ID"
}

Response:
{
  "transcripts": [
    {
      "title": "Video Title",
      "url": "https://youtube.com/watch?v=VIDEO_ID",
      "transcript": "extracted transcript text...",
      "source": "subtitles" | "whisper"
    }
  ],
  "total_videos": 10
}
```

## 🧪 Testing

### Manual Testing
1. **Health Check**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Test YouTube Video**
   ```bash
   curl -X POST http://localhost:8000/transcribe \
     -H "Content-Type: application/json" \
     -d '{"url": "https://youtube.com/watch?v=VIDEO_ID"}'
   ```

3. **Test YouTube Playlist**
   ```bash
   curl -X POST http://localhost:8000/transcribe \
     -H "Content-Type: application/json" \
     -d '{"url": "https://youtube.com/playlist?list=PLAYLIST_ID"}'
   ```

### Automated Testing
```bash
# Run the test script
python test_worker.py
```

## 🔧 Configuration

### Environment Variables
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key for Whisper transcription | Yes | - |

### Worker Configuration
The worker is designed to:
- Use residential IP for YouTube access
- Extract subtitles when available (no API key needed)
- Fall back to Whisper transcription for videos without subtitles
- Handle large files by splitting into chunks
- Process playlists efficiently

## 🚨 Troubleshooting

### Common Issues

#### 1. YouTube Access Issues
**Error**: `Video unavailable` or `Access denied`
**Solution**:
- Ensure you're using a residential IP (not data center)
- Check if video is publicly accessible
- Try with a different YouTube video
- Verify yt-dlp is up to date

#### 2. OpenAI API Key Issues
**Error**: `Invalid API key` or `Rate limit exceeded`
**Solution**:
- Verify your OpenAI API key is correct
- Check your OpenAI account balance
- Implement rate limiting if needed

#### 3. FFmpeg Not Found
**Error**: `ffmpeg command not found`
**Solution**: Install FFmpeg and ensure it's in your system PATH

#### 4. ngrok Tunnel Issues
**Error**: `Connection refused` or tunnel not working
**Solution**:
- Ensure worker is running on port 8000
- Check ngrok tunnel is active
- Verify ngrok URL is accessible
- Update backend WORKER_URL environment variable

#### 5. Large File Processing
**Error**: `File too large` or timeout
**Solution**:
- Worker automatically splits large files
- Check OpenAI API limits
- Monitor system resources

### Performance Optimization

#### 1. Large File Handling
- Files are automatically split into 25MB chunks
- Each chunk is processed separately
- Results are combined into final transcript

#### 2. Playlist Processing
- Videos are processed sequentially
- Progress tracking for each video
- Error handling for individual videos

#### 3. Caching
- Consider implementing transcript caching
- Cache frequently requested videos
- Implement Redis for session management

## 📊 Monitoring and Logging

### Logging Configuration
The worker uses Python's built-in logging. Configure log levels in your deployment environment.

### Health Monitoring
- Use the `/health` endpoint for health checks
- Monitor processing times
- Track OpenAI API usage and costs

### Error Tracking
- Monitor failed transcript extractions
- Track YouTube access issues
- Monitor ngrok tunnel stability

## 🔒 Security Considerations

### API Security
- Use HTTPS in production (via ngrok)
- Implement API key rotation
- Add request validation and sanitization

### YouTube Access
- Use residential IP to avoid bot detection
- Implement rate limiting
- Monitor for access restrictions

### Data Privacy
- Don't log sensitive user data
- Implement data retention policies
- Ensure GDPR compliance if applicable

## 🚀 Deployment Options

### Local Deployment (Recommended)
The worker is designed to run locally with ngrok tunneling:

1. **Run worker locally**
   ```bash
   uvicorn worker:app --host 0.0.0.0 --port 8000
   ```

2. **Start ngrok tunnel**
   ```bash
   ngrok http 8000
   ```

3. **Update backend configuration**
   - Set `WORKER_URL` to your ngrok URL
   - Include `/transcribe` endpoint

### Render Deployment (Alternative)
For cloud deployment (may face YouTube restrictions):

1. **Deploy to Render**
   - Connect GitHub repository
   - Set build command: `pip install -r requirements.txt`
   - Set start command: `uvicorn worker:app --host 0.0.0.0 --port $PORT`

2. **Configure environment variables**
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. **Update backend configuration**
   - Set `WORKER_URL` to your Render worker URL

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the API documentation
3. Open an issue on GitHub
4. Contact the development team

---

**VibeKnowing Worker** - Reliable YouTube processing with residential IP access.
