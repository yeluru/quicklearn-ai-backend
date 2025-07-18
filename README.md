# VibeKnowing Backend API

## 🔥 Project Overview
**VibeKnowing Backend API** is a FastAPI-based service that provides AI-powered content analysis capabilities. It handles transcript extraction, summary generation, quiz creation, and interactive chat functionality for various content types including videos, audio, documents, and websites.

## 🎯 Core Features
- **Transcript Processing**: Extract and process transcripts from various sources
- **AI Summarization**: Generate intelligent summaries with streaming responses
- **Quiz Generation**: Create context-aware questions and answers
- **Interactive Chat**: Enable conversational AI interactions about content
- **Website Scraping**: Extract and analyze web content
- **Multi-format Support**: Handle videos, audio, documents, and text input

## 🧠 Tech Stack
- **Python 3.11+**
- **FastAPI** - Modern web framework for building APIs
- **OpenAI GPT-4** - AI-powered content analysis and generation
- **Streaming Responses** - Real-time content delivery
- **CORS Support** - Cross-origin resource sharing
- **Pydantic** - Data validation and serialization

## 📁 Project Structure
```
quicklearn-ai-backend/
├── main.py                    # FastAPI application entry point
├── config.py                  # Configuration settings
├── requirements.txt           # Python dependencies
├── Procfile                  # Render deployment configuration
├── runtime.txt               # Python version specification
├── DEPLOYMENT.md             # Deployment guide
├── services/                 # API service modules
│   ├── transcript_service.py # Transcript processing endpoints
│   ├── summary_service.py    # Summary generation endpoints
│   ├── chat_service.py       # Chat interaction endpoints
│   └── website_scraper_service.py # Web scraping functionality
├── utils/                    # Utility modules
│   ├── openai_utils.py       # OpenAI API integration
│   ├── openai_prompts.py     # AI prompt templates
│   ├── text_utils.py         # Text processing utilities
│   ├── url_utils.py          # URL validation and processing
│   └── youtube_utils.py      # YouTube-specific utilities
├── exceptions/               # Custom exception handling
│   └── custom_exceptions.py  # Custom exception classes
└── tests/                    # Test suite
    ├── conftest.py           # Test configuration
    ├── test_main.py          # Main API tests
    ├── test_transcript.py    # Transcript service tests
    ├── test_summary.py       # Summary service tests
    └── test_chat.py          # Chat service tests
```

## ⚙️ Environment Setup

### Prerequisites
- Python 3.11 or higher
- OpenAI API key
- Worker service running (for YouTube processing)
- ngrok tunnel (for worker communication)

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

4. **Set environment variables**
   ```bash
   export OPENAI_API_KEY="your_openai_api_key_here"
   export WORKER_URL="https://your-ngrok-url.ngrok-free.app/transcribe"
   export ALLOWED_ORIGINS="http://localhost:3000,https://your-frontend-url.com"
   ```

## 🚀 Running the Backend

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

## 📚 API Documentation

### Base URL
- Local: `http://localhost:8000`
- Production: `https://your-backend-url.onrender.com`

### Health Check
```bash
GET /health
Response: {"status": "healthy", "service": "QuickLearn.AI Backend"}
```

### Transcript Service (`/transcript`)

#### Process Transcript
```bash
POST /transcript/process
Content-Type: application/json

Body:
{
  "transcript": "transcript text content...",
  "source_type": "video" | "audio" | "document" | "text"
}

Response:
{
  "transcript": "processed transcript text...",
  "word_count": 1500,
  "processing_time": 0.5
}
```

### Summary Service (`/summary`)

#### Generate Summary (Streaming)
```bash
POST /summary/summarize-stream
Content-Type: application/json

Body:
{
  "transcript": "transcript text content...",
  "summary_type": "comprehensive" | "concise" | "bullet_points"
}

Response: Streaming text chunks
```

#### Generate Quiz (Streaming)
```bash
POST /summary/qna-stream
Content-Type: application/json

Body:
{
  "transcript": "transcript text content...",
  "num_questions": 5,
  "difficulty": "easy" | "medium" | "hard"
}

Response: Streaming Q&A content
```

### Chat Service (`/chat`)

#### Send Message (Streaming)
```bash
POST /chat/send
Content-Type: application/json

Body:
{
  "message": "user question...",
  "context": "transcript or content context...",
  "conversation_history": []
}

Response: Streaming chat response
```

### Website Scraping (`/scrape`)

#### Scrape Website
```bash
POST /scrape
Content-Type: application/json

Body:
{
  "url": "https://example.com"
}

Response:
{
  "transcript": "extracted website content..."
}
```

## 🧪 Testing

### Manual Testing
1. **Health Check**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Test Summary Generation**
   ```bash
   curl -X POST http://localhost:8000/summary/summarize-stream \
     -H "Content-Type: application/json" \
     -d '{"transcript": "Sample transcript content...", "summary_type": "comprehensive"}'
   ```

3. **Test Chat**
   ```bash
   curl -X POST http://localhost:8000/chat/send \
     -H "Content-Type: application/json" \
     -d '{"message": "What is this about?", "context": "Sample context..."}'
   ```

### Automated Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_summary.py

# Run with coverage
pytest --cov=services
```

## 🔧 Configuration

### Environment Variables
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key for AI services | Yes | - |
| `WORKER_URL` | Worker service URL for YouTube processing | Yes | - |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | Yes | `http://localhost:3000` |
| `YOUTUBE_API_KEY` | YouTube API key (optional) | No | - |

### API Configuration
The backend is designed to:
- Handle streaming responses for real-time content delivery
- Process multiple content types (video, audio, document, text)
- Integrate with worker service for YouTube processing
- Provide comprehensive error handling and logging
- Support CORS for frontend integration

## 🚨 Troubleshooting

### Common Issues

#### 1. OpenAI API Issues
**Error**: `Invalid API key` or `Rate limit exceeded`
**Solution**:
- Verify your OpenAI API key is correct
- Check your OpenAI account balance
- Implement rate limiting if needed

#### 2. Worker Connection Issues
**Error**: `Connection refused` or worker not responding
**Solution**:
- Ensure worker service is running
- Check ngrok tunnel is active
- Verify WORKER_URL environment variable

#### 3. CORS Issues
**Error**: `CORS policy` or cross-origin errors
**Solution**:
- Check ALLOWED_ORIGINS configuration
- Ensure frontend URL is included
- Verify HTTPS/HTTP protocol matching

#### 4. Streaming Issues
**Error**: `Streaming response broken` or incomplete content
**Solution**:
- Check OpenAI API response format
- Verify streaming implementation
- Monitor network connectivity

#### 5. Memory Issues
**Error**: `Memory exceeded` or timeout
**Solution**:
- Implement content chunking
- Monitor memory usage
- Optimize response processing

## 📊 Performance Optimization

### Streaming Responses
- Implement proper chunking for large content
- Use async processing for better performance
- Monitor response times and optimize

### Memory Management
- Process content in chunks
- Implement proper cleanup
- Monitor memory usage

### Caching Strategy
- Consider implementing response caching
- Cache frequently requested content
- Use Redis for session management

## 🔒 Security Considerations

### API Security
- Use HTTPS in production
- Implement API key rotation
- Add request validation and sanitization

### Content Processing
- Validate and sanitize user inputs
- Implement content size limits
- Monitor for malicious content

### Environment Variables
- Never commit API keys to version control
- Use environment variables for sensitive data
- Validate configuration in production

## 🚀 Deployment

See `DEPLOYMENT.md` for detailed deployment instructions to Render or other platforms.

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

**VibeKnowing Backend API** - Powering AI-driven content analysis and learning.
