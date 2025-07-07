import logging
from openai import OpenAI
from config import OPENAI_API_KEY
import re
import json

client = OpenAI(api_key=OPENAI_API_KEY)


def stream_chat_completion(prompt, model="gpt-3.5-turbo", max_tokens=4096, temperature=0.7, system_message=None):
    """
    Stream a chat completion from OpenAI, yielding content chunks.
    """
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            yield content
    except Exception as e:
        logging.error(f"OpenAI stream error: {str(e)}")
        yield f"Error: {str(e)}"


def chat_completion(prompt, model="gpt-3.5-turbo", max_tokens=600, temperature=0.7, system_message=None):
    """
    Get a non-streaming chat completion from OpenAI.
    """
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI chat completion error: {str(e)}")
        return f"Error: {str(e)}"


def parse_suggested_questions_response(text):
    """
    Parse and validate the OpenAI response for suggested questions.
    Returns a list of 5 question dicts, using fallback/defaults if needed.
    """
    logging.info(f"OpenAI suggested-questions raw response: {text}")
    text = re.sub(r'^```(json)?\n|\n```$', '', text or '').strip()
    questions = []
    try:
        questions = json.loads(text)
        if not isinstance(questions, list):
            raise ValueError("Not a list")
    except Exception as e:
        logging.error(f"Failed to parse questions: {str(e)}, response: {text[:200]}...")
        json_pattern = r'\{\s*"topic":\s*"[^\"]+",\s*"question":\s*"[^\"]+"\s*\}'
        matches = re.findall(json_pattern, text or '')
        for match in matches:
            try:
                q = json.loads(match)
                questions.append(q)
            except Exception:
                continue
    # Final filter: only keep dicts with both keys
    questions = [q for q in questions if isinstance(q, dict) and 'topic' in q and 'question' in q]
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
    logging.info(f"Final suggested questions: {questions}")
    return questions 