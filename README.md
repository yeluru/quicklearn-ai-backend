# QuickLearn.ai Backend

## 🔥 Project Name
**QuickLearn.ai Backend**

## 📘 Project Description
This is the backend server for QuickLearn.ai — a modular, extensible Python-based API that powers AI summarization, transcription, quiz generation, and contextual question answering from user content.

The backend is designed to:
- Accept multi-modal inputs (video URL, audio file, text, uploaded documents)
- Transcribe and extract content
- Use advanced language models (via OpenAI or others) to generate insights
- Serve a structured response to the frontend

## 🎯 Features
- **Transcript Extraction**: Pulls transcripts from YouTube or uploads.
- **AI Summarization**: Generates detailed notes using GPT.
- **Quiz Generation**: Builds context-aware questions from content.
- **Suggested Questions**: Dynamically generates follow-up or curiosity-driven questions.
- **Clean API Design**: Easy to extend with more endpoints or models.

## 🧠 Tech Stack
- **Python 3.10+**
- **FastAPI** (web framework)
- **Pydantic** (data validation)
- **OpenAI API** (LLM integration)
- **LangChain** *(optional for future enhancements)*

## 🗂️ Folder Structure (Key Parts)
```
quicklearn-ai-backend/
├── main.py                  # FastAPI entry point
├── routers/
│   ├── transcript.py        # Transcript extraction
│   ├── notes.py             # AI-powered notes
│   ├── quiz.py              # Quiz generation
│   └── suggestions.py       # Suggested questions
├── utils/
│   └── youtube_utils.py     # YouTube transcript helper
├── models/                  # Pydantic request/response models
```

## ⚙️ Environment Variables (Backend)
Define the following in a `.env` file:
```
OPENAI_API_KEY=your_openai_key
ALLOWED_ORIGINS=http://localhost:3000
```

## 🚀 To Run Locally
```bash
git clone https://github.com/yeluru/quicklearn-ai-backend.git
cd quicklearn-ai-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## 📈 Upcoming Enhancements
- 🔐 Google/GitHub/Microsoft login
- 💾 User sessions & history
- 🧠 Model selection (GPT-3.5 vs GPT-4 vs Claude)
- 🗃️ Database integration for file tracking
- ☁️ Cloud-native deployment (Vercel + Render/AWS Lambda)
