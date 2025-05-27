from fastapi import FastAPI, UploadFile, File, Request
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
    if 'youtube' in parsed.netloc:
        return parse_qs(parsed.query).get('v', [None])[0]
    elif 'youtu.be' in parsed.netloc:
        return parsed.path.strip('/')
    return None

@app.get("/playlist-transcript")
def get_playlist_transcript(playlist_id: str):
    try:
        all_text = []
        page_token = ""

        while True:
            yt_api_url = (
                f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50"
                f"&playlistId={playlist_id}&key={YOUTUBE_API_KEY}"
            )
            if page_token:
                yt_api_url += f"&pageToken={page_token}"

            response = requests.get(yt_api_url).json()
            items = response.get("items", [])
            for item in items:
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_url = f"https://youtu.be/{video_id}"
                video_text = get_youtube_transcript(video_url)
                if "transcript" in video_text:
                    all_text.append(video_text["transcript"])

            if "nextPageToken" in response:
                page_token = response["nextPageToken"]
            else:
                break

        full_transcript = "\n\n".join(all_text)
        return {"transcript": full_transcript}
    except Exception as e:
        return {"error": str(e)}

@app.get("/transcript")
def get_youtube_transcript(url: str):
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        query_params = parse_qs(urlparse(url).query)
        playlist_id = query_params.get('list', [None])[0]

        if playlist_id:
            return get_playlist_transcript(playlist_id)

        video_id = extract_video_id(url)
        if video_id:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            lines = [x['text'].strip() for x in transcript if x['text'].strip()]
            text = " ".join(lines)
            paragraphs = re.split(r'(\.|\?|!)(?=\s+[A-Z])', text)
            formatted = []
            temp = ""
            for segment in paragraphs:
                temp += segment
                if segment.strip().endswith(('.', '?', '!')):
                    formatted.append(temp.strip())
                    temp = ""
            if temp:
                formatted.append(temp.strip())
            clean_text = "\n\n".join(formatted)
            # Extract a topic title from the first line or ask OpenAI for a better one
            first_line = clean_text.strip().split('\n')[0]
            try:
                title_prompt = f"Generate a short, clear title (5-8 words) for the following content:\n\n{clean_text[:1500]}"
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": title_prompt}],
                    max_tokens=20
                )
                topic_title = response.choices[0].message.content.strip().replace(" ", "_")
            except Exception:
                topic_title = first_line[:50].replace(" ", "_")

            return {
                "transcript": clean_text,
                "title": topic_title
            }

        return {"error": "Invalid YouTube URL"}
    except Exception as e:
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
- ❌ Do NOT use first-person (“I”, “we”), second-person (“you”), or narrative phrases like “let’s explore” or “our journey”.
- ✅ Use **impersonal, objective language**. Focus on clear technical statements using passive or neutral voice.
- Write as if the content is being published in a technical handbook or formal exam prep guide.
- Make the writing engaging and thought-provoking like a great teacher.
- Avoid filler and narrative clichés like “Let’s embark” or “This journey shows us…”.
- Use vivid, real-world analogies to explain abstract ideas. For example, compare agents to detectives, tools to Swiss army knives, or tracing to surveillance cameras.
- Use detailed walkthroughs to explain how things work. Show how an agent thinks step-by-step like debugging logic.
- Make every paragraph teach something — avoid summaries that merely rephrase.
- Do NOT use first-person (“we”, “let’s”, “I”). Avoid vague phrases like “the conversation explored…”.
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

@app.get("/transcript-stream")
def stream_youtube_transcript(url: str):
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        video_id = extract_video_id(url)
        if video_id:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            lines = [x['text'].strip() for x in transcript if x['text'].strip()]
            def generate():
                for line in lines:
                    yield line + "\n"
            return StreamingResponse(generate(), media_type="text/plain")

        query_params = parse_qs(urlparse(url).query)
        playlist_id = query_params.get('list', [None])[0]
        if playlist_id:
            return get_playlist_transcript(playlist_id)

        return {"error": "Invalid YouTube URL"}
    except Exception as e:
        return {"error": str(e)}

from fastapi import Request
from pydantic import BaseModel

class SummaryInput(BaseModel):
    summary: str

@app.post("/suggested-questions")
def suggested_questions(req: SummaryInput):
    from openai import OpenAI
    import json
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

