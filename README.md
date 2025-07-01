# QuickLearn.AI

## 🚀 Complete AI-Powered Learning Platform

**QuickLearn.AI** is a comprehensive learning platform that transforms any video, audio, text, or document into interactive learning materials. The platform consists of a React frontend and FastAPI backend, working together to provide AI-powered content analysis, summarization, quiz generation, and interactive chat capabilities.

### 📋 Project Overview
- **Frontend**: Modern React application with Tailwind CSS
- **Backend**: FastAPI server with OpenAI integration
- **Features**: Multi-modal input processing, AI summarization, quiz generation, interactive chat
- **Deployment**: Ready for cloud deployment on Railway, Render, Vercel, and more

### 🎯 Quick Start

#### Prerequisites
- Python 3.11+ and Node.js 16+
- OpenAI API key
- FFmpeg installed on your system

#### Complete Setup Guide

1. **Clone and Setup Backend**
   ```bash
   git clone <repository-url>
   cd quicklearn-ai-backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Install FFmpeg**
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # Windows: Download from https://ffmpeg.org/download.html
   ```

3. **Configure Backend Environment**
   ```bash
   # Create .env file
   echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
   echo "ALLOWED_ORIGINS=http://localhost:3000" >> .env
   ```

4. **Setup Frontend**
   ```bash
   cd quicklearn-ai-frontend
   npm install
   
   # Create .env file
   echo "REACT_APP_API_BASE_URL=http://localhost:8000" > .env
   ```

5. **Run Both Services**
   ```bash
   # Terminal 1 - Backend
   cd quicklearn-ai-backend
   source venv/bin/activate
   uvicorn main:app --reload --port 8000
   
   # Terminal 2 - Frontend
   cd quicklearn-ai-frontend
   npm start
   ```

6. **Access the Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

#### Testing Your Setup

1. **Test Backend Health**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "healthy", "service": "QuickLearn.AI Backend"}
   ```

2. **Test Frontend**
   - Open http://localhost:3000 in your browser
   - You should see the QuickLearn.AI landing page
   - Click "Get Started" to access the main application

3. **Test Video Processing**
   - Paste a YouTube URL (e.g., https://youtube.com/watch?v=dQw4w9WgXcQ)
   - Click "Analyze" and wait for transcript generation
   - Verify that Notes, Quiz, and Chat tabs appear

4. **Test File Upload**
   - Upload a PDF or audio file
   - Verify content extraction and processing
   - Test the download functionality

#### Troubleshooting
- **Backend won't start**: Check Python version (3.11+) and virtual environment
- **Frontend won't start**: Check Node.js version (16+) and npm install
- **API errors**: Verify OpenAI API key and CORS settings
- **File upload fails**: Check FFmpeg installation and file size limits

#### Detailed Documentation
- **Backend Setup**: Follow the [Backend README](./README.md#-environment-setup) below
- **Frontend Setup**: Follow the [Frontend README](./quicklearn-ai-frontend/README.md)
- **Deployment**: See [DEPLOYMENT.md](./DEPLOYMENT.md)

### 🔗 Repository Structure
```
quicklearn-ai/
├── README.md                    # This file (Backend + Project Overview)
├── DEPLOYMENT.md               # Deployment instructions
├── main.py                     # FastAPI application
├── requirements.txt            # Python dependencies
├── config.py                   # Environment configuration
├── services/                   # Backend API services
├── utils/                      # Backend utilities
├── exceptions/                 # Custom exceptions
└── quicklearn-ai-frontend/     # React frontend application
    ├── README.md              # Frontend documentation
    ├── package.json           # Node.js dependencies
    ├── src/                   # React source code
    └── public/                # Static assets
```

---

# QuickLearn.AI Backend

## 🔥 Project Overview
**QuickLearn.AI Backend** is a powerful FastAPI-based server that provides AI-powered learning assistance. It extracts transcripts from videos, audio, and documents, then generates summaries, quizzes, and enables contextual chat interactions using OpenAI's language models.

## 🎯 Core Features
- **Multi-Modal Input Processing**: YouTube videos, audio files, documents (PDF, DOCX, TXT), and raw text
- **AI-Powered Summarization**: Generate detailed notes and insights from content
- **Quiz Generation**: Create context-aware questions and answers
- **Interactive Chat**: Ask questions about processed content
- **Streaming Responses**: Real-time content processing with progress updates
- **File Upload Support**: Handle various document and audio formats
- **YouTube Integration**: Extract transcripts from YouTube videos and playlists

## 🧠 Tech Stack
- **Python 3.10+**
- **FastAPI** - Modern web framework for building APIs
- **OpenAI API** - GPT models for AI-powered features
- **yt-dlp** - YouTube video processing
- **Whisper** - Audio transcription (local or OpenAI)
- **PyPDF2 & python-docx** - Document processing
- **ffmpeg-python** - Audio/video processing
- **Pydantic** - Data validation and serialization

## 📁 Project Structure
```
quicklearn-ai-backend/
├── main.py                     # FastAPI application entry point
├── config.py                   # Environment configuration
├── requirements.txt            # Python dependencies
├── Procfile                    # Heroku deployment configuration
├── runtime.txt                 # Python version specification
├── services/                   # API service modules
│   ├── transcript_service.py   # Transcript extraction endpoints
│   ├── summary_service.py      # AI summarization and quiz generation
│   └── chat_service.py         # Interactive chat functionality
├── utils/                      # Utility modules
│   ├── youtube_utils.py        # YouTube-specific processing
│   ├── url_utils.py            # URL validation and processing
│   └── text_utils.py           # Text processing utilities
├── exceptions/                 # Custom exception handling
│   └── custom_exceptions.py    # Application-specific exceptions
└── DEPLOYMENT.md              # Deployment instructions
```

## ⚙️ Environment Setup

### Prerequisites
- Python 3.10 or higher
- FFmpeg installed on your system
- OpenAI API key
- YouTube API key (optional, for enhanced features)

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd quicklearn-ai-backend
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

5. **Create environment file**
   ```bash
   cp .env.example .env  # if .env.example exists
   # or create .env manually
   ```

6. **Configure environment variables**
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   YOUTUBE_API_KEY=your_youtube_api_key_here  # Optional
   ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend-domain.com
   API_BASE_URL=http://localhost:8000
   ```

## 🚀 Running the Application

### Development Mode
```bash
# Start the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
# Start the production server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Using Docker (if Dockerfile exists)
```bash
docker build -t quicklearn-backend .
docker run -p 8000:8000 quicklearn-backend
```

## 📚 API Documentation

### Base URL
- Development: `http://localhost:8000`
- Production: `https://your-backend-domain.com`

### Health Check
```bash
GET /health
Response: {"status": "healthy", "service": "QuickLearn.AI Backend"}
```

### Transcript Service (`/transcript`)

#### Upload File for Transcription
```bash
POST /transcript/upload
Content-Type: multipart/form-data

Parameters:
- file: Audio/video file (MP3, MP4, WAV, etc.) or document (PDF, DOCX, TXT)
```

#### Stream Transcript from URL
```bash
POST /transcript/stream
Content-Type: application/json

Body:
{
  "url": "https://youtube.com/watch?v=..."
}
```

#### Get Transcript Segments (with timestamps)
```bash
POST /transcript/segments
Content-Type: application/json

Body:
{
  "url": "https://youtube.com/watch?v=..."
}
```

### Summary Service (`/summary`)

#### Generate Streaming Summary
```bash
POST /summary/summarize-stream
Content-Type: application/json

Body:
{
  "transcript": "text content...",
  "refresh": false,
  "use_openai": true
}
```

#### Generate Quiz Questions
```bash
POST /summary/qna-stream
Content-Type: application/json

Body:
{
  "transcript": "text content...",
  "refresh": false,
  "use_openai": true
}
```

#### Extract Key Information
```bash
POST /summary/extract
Content-Type: application/json

Body:
{
  "text": "content to extract from..."
}
```

### Chat Service (`/chat`)

#### On-Topic Chat
```bash
POST /chat/on-topic
Content-Type: application/json

Body:
{
  "transcript": "content context...",
  "chatHistory": [
    {"role": "user", "content": "question"},
    {"role": "assistant", "content": "answer"}
  ]
}
```

#### Get Suggested Questions
```bash
POST /chat/suggested-questions
Content-Type: application/json

Body:
{
  "summary": "content summary..."
}
```

## 🧪 Testing

### Manual Testing
1. **Health Check**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Test File Upload**
   ```bash
   curl -X POST http://localhost:8000/transcript/upload \
     -F "file=@test_audio.mp3"
   ```

3. **Test YouTube URL**
   ```bash
   curl -X POST http://localhost:8000/transcript/stream \
     -H "Content-Type: application/json" \
     -d '{"url": "https://youtube.com/watch?v=VIDEO_ID"}'
   ```

### Automated Testing
```bash
# Run tests (if test files exist)
python -m pytest tests/

# Run with coverage
python -m pytest --cov=services tests/
```

## 🔧 Configuration

### Environment Variables
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key for AI features | Yes | - |
| `YOUTUBE_API_KEY` | YouTube API key for enhanced features | No | - |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | Yes | `http://localhost:3000` |
| `API_BASE_URL` | Backend API base URL | No | `http://localhost:8000` |

### CORS Configuration
The application is configured to allow cross-origin requests from the frontend. Update `ALLOWED_ORIGINS` in your environment variables to include your frontend domain.

## 🚨 Troubleshooting

### Common Issues

#### 1. FFmpeg Not Found
**Error**: `ffmpeg command not found`
**Solution**: Install FFmpeg and ensure it's in your system PATH

#### 2. OpenAI API Key Issues
**Error**: `Invalid API key` or `Rate limit exceeded`
**Solution**: 
- Verify your OpenAI API key is correct
- Check your OpenAI account balance
- Implement rate limiting if needed

#### 3. YouTube Transcript Extraction Fails
**Error**: `No transcript found`
**Solution**:
- Ensure the video has captions/subtitles
- Check if the video is publicly accessible
- Try with a different YouTube video

#### 4. File Upload Issues
**Error**: `File too large` or `Unsupported file type`
**Solution**:
- Check file size limits (default: 100MB)
- Ensure file format is supported
- Verify file is not corrupted

#### 5. CORS Errors
**Error**: `CORS policy blocked`
**Solution**:
- Update `ALLOWED_ORIGINS` to include your frontend URL
- Restart the server after changing environment variables

### Performance Optimization

#### 1. Large File Processing
- Implement file size limits
- Use streaming for large files
- Consider background processing for heavy operations

#### 2. API Rate Limiting
- Implement rate limiting for OpenAI API calls
- Add request queuing for high-traffic scenarios

#### 3. Caching
- Cache frequently requested transcripts
- Implement Redis for session management

## 📊 Monitoring and Logging

### Logging Configuration
The application uses Python's built-in logging. Configure log levels in your deployment environment.

### Health Monitoring
- Use the `/health` endpoint for health checks
- Monitor API response times
- Track OpenAI API usage and costs

### Error Tracking
- Implement error tracking (e.g., Sentry)
- Monitor failed transcript extractions
- Track user interaction patterns

## 🔒 Security Considerations

### API Security
- Use HTTPS in production
- Implement API key rotation
- Add request validation and sanitization

### File Upload Security
- Validate file types and sizes
- Scan uploaded files for malware
- Implement secure file storage

### Data Privacy
- Don't log sensitive user data
- Implement data retention policies
- Ensure GDPR compliance if applicable

## 🚀 Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions to various platforms including:
- Railway
- Render
- Heroku
- AWS
- Docker

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

**QuickLearn.AI Backend** - Empowering learning through AI-powered content analysis and interaction.
