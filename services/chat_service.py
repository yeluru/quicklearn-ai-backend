from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from config import OPENAI_API_KEY
from exceptions.custom_exceptions import ChatError
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
client = OpenAI(api_key=OPENAI_API_KEY)

router = APIRouter()

class SummaryInput(BaseModel):
    summary: str

@router.post("/suggested-questions")
async def suggested_questions(req: SummaryInput):
    try:
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
            questions = []
            for line in text.split("\n"):
                if line.strip().startswith("{") and "topic" in line and "question" in line:
                    try:
                        questions.append(json.loads(line.strip().rstrip(",")))
                    except:
                        continue

        return {"questions": questions}
    except Exception as e:
        logging.error(f"Error in suggested-questions: {str(e)}")
        raise ChatError(str(e))

@router.post("/on-topic")
async def chat_on_topic(request: Request):
    try:
        body = await request.json()
        summary = body.get("summary", "")
        chat_history = body.get("chatHistory", [])

        if not summary or not isinstance(chat_history, list):
            raise ChatError("Missing or invalid fields.")

        system_prompt = {
            "role": "system",
            "content": f"You are a helpful assistant. Use the following topic summary to answer questions:\n\n{summary}"
        }

        messages = [system_prompt] + chat_history
        def generate():
            stream = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                stream=True,
                max_tokens=1024
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                yield content
        return StreamingResponse(generate(), media_type="text/plain")
    except ChatError as e:
        raise e
    except Exception as e:
        logging.error(f"Error in chat-on-topic: {str(e)}")
        raise ChatError(str(e))