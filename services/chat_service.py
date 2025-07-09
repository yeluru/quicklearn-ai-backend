from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from config import OPENAI_API_KEY
from exceptions.custom_exceptions import ChatError
import json
import logging
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
client = OpenAI(api_key=OPENAI_API_KEY)

router = APIRouter()

class SummaryInput(BaseModel):
    summary: str

class ChatInput(BaseModel):
    transcript: str | None = None  # Allow None
    chatHistory: list

@router.post("/suggested-questions")
async def suggested_questions(req: SummaryInput):
    try:
        prompt = f"""
You are a helpful AI assistant. Read the following transcript and generate 5 distinct educational topics, each with one thoughtful question.

Output format (JSON array, exactly 5 items):
[
  {{ "topic": "string", "question": "string" }},
  {{ "topic": "string", "question": "string" }},
  {{ "topic": "string", "question": "string" }},
  {{ "topic": "string", "question": "string" }},
  {{ "topic": "string", "question": "string" }}
]

Transcript:
\"\"\"
{req.summary[:10000]}
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

        text = response.choices[0].message.content.strip()
        text = re.sub(r'^```(json)?\n|\n```$', '', text).strip()
        try:
            questions = json.loads(text)
            if not isinstance(questions, list) or len(questions) != 5 or not all(isinstance(q, dict) and 'topic' in q and 'question' in q for q in questions):
                raise ValueError("Invalid questions format")
        except Exception as e:
            logging.error(f"Failed to parse questions: {str(e)}, response: {text[:200]}...")
            questions = []
            json_pattern = r'\{\s*"topic":\s*"[^"]+",\s*"question":\s*"[^"]+"\s*\}'
            matches = re.findall(json_pattern, text)
            for match in matches:
                try:
                    questions.append(json.loads(match))
                except:
                    continue
            if len(questions) < 5:
                default_questions = [
                    {"topic": "Main Idea", "question": "What is the main idea of the content?"},
                    {"topic": "Key Details", "question": "What are the key details discussed?"},
                    {"topic": "Context", "question": "What is the context of the content?"},
                    {"topic": "Implications", "question": "What are the implications of the content?"},
                    {"topic": "Applications", "question": "How can the content be applied?"}
                ]
                questions.extend(default_questions[:5 - len(questions)])
            questions = questions[:5]

        return {"questions": questions}
    except Exception as e:
        logging.error(f"Error in suggested-questions: {str(e)}")
        raise ChatError(str(e))

@router.post("/on-topic")
async def chat_on_topic(req: ChatInput):
    try:
        transcript = req.transcript or ""
        chat_history = req.chatHistory or []
        logging.info(f"Chat input: transcript_length={len(transcript)}, chatHistory_length={len(chat_history)}")

        if not chat_history:
            logging.error("Empty chat history provided")
            raise ChatError("Chat history cannot be empty.")

        # Validate chat_history format
        for msg in chat_history:
            if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                logging.error(f"Invalid chat history entry: {msg}")
                raise ChatError("Invalid chat history format.")

        system_prompt = {
            "role": "system",
            "content": f"You are a helpful assistant. Use the following transcript to answer questions. When you mention mathematical expressions or formulas, always use LaTeX syntax and wrap them in $...$ for inline math or $$...$$ for block math. If the question is about a mathematical or technical concept, answer in a tutorial style, with step-by-step reasoning, formulas, and examples.\n\n{transcript[:10000] if transcript else 'No transcript provided.'}"
        }

        messages = [system_prompt] + chat_history
        def generate():
            try:
                stream = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    stream=True,
                    max_tokens=1024
                )
                for chunk in stream:
                    content = chunk.choices[0].delta.content or ""
                    yield content
            except Exception as e:
                logging.error(f"OpenAI stream error: {str(e)}")
                yield f"Error: {str(e)}"
        logging.info("Streaming response for /chat/on-topic")
        return StreamingResponse(generate(), media_type="text/plain")
    except ChatError as e:
        logging.error(f"ChatError in chat-on-topic: {str(e)}")
        raise e
    except Exception as e:
        logging.error(f"Error in chat-on-topic: {str(e)}")
        raise ChatError(str(e))