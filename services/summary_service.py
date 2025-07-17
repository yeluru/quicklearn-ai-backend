from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from openai import OpenAI
from config import OPENAI_API_KEY
from exceptions.custom_exceptions import SummaryError
import logging
import json
import openai

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
client = OpenAI(api_key=OPENAI_API_KEY)

router = APIRouter()

class VideoInput(BaseModel):
    transcript: str
    url: str

@router.post("/summarize-video")
async def summarize_video(input: VideoInput):
    try:
        logging.info(f"Processing video URL: {input.url}, transcript length: {len(input.transcript)}")
        
        summary = "No summary available."
        
        if input.transcript:
            truncated_transcript = input.transcript[:10000]
            logging.info(f"Truncated transcript length: {len(truncated_transcript)}")
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes videos."},
                    {"role": "user", "content": (
                        f"Based on this transcript excerpt: '{truncated_transcript}...', "
                        f"provide a 3-4 sentence summary in plain text. "
                        f"In the summary, do not start with 'The text' or 'The excerpt' or 'The excerpt discusses' or 'transcript excerpt discusses' or 'video discusses' mention anything about speaker, instead generalize the summary. "
                        f"When you mention mathematical expressions or formulas, always use LaTeX syntax and wrap them in $...$ for inline math or $$...$$ for block math. "
                        f"If the transcript discusses a mathematical or technical concept, explain it as a teacher would, using formulas, step-by-step reasoning, and examples where appropriate. Prefer a tutorial style over a generic summary when the content is instructional. "
                        f"For each key concept, provide at least one worked example with numbers and formulas, step by step. Ignore repeated or filler phrases from the transcript; focus on unique mathematical explanations and problem-solving steps. Minimize motivational or generic language; focus on clear, logical, and example-driven teaching."
                    )}
                ],
                max_tokens=100,
                temperature=0.7
            )
            content = response.choices[0].message.content
            summary = content.strip() if content else "No summary available."
            logging.info(f"OpenAI summary: {summary[:200]}...")
        
        logging.info(f"Returning summary: {summary[:50]}...")
        return {"summary": summary}
    except Exception as e:
        logging.error(f"Error in summarize-video: {str(e)}", exc_info=True)
        raise SummaryError(f"Error generating video summary: {str(e)}")

@router.post("/summarize-stream")
async def summarize_stream(request: Request):
    try:
        body = await request.json()
        transcript = body.get("transcript")
        if not transcript:
            raise SummaryError("Transcript is required.")

        max_chunk_chars = 12000
        chunks = [transcript[i:i+max_chunk_chars] for i in range(0, len(transcript), max_chunk_chars)]

        def chunk_stream():
            for index, chunk in enumerate(chunks):
                prompt = f"""
You are an expert AI technical educator.

Write a highly engaging, well-structured, and richly informative educational article based on the following transcript segment:

{chunk}

Guidelines:
- Use **Markdown headings** (`##` for main sections, `###` for subsections) to clearly structure content.
- Ensure headings are meaningful and not empty; avoid standalone `#` or `##` without text.
- Write concise paragraphs (3-5 sentences each) with smooth, storytelling transitions between sections.
- Use proper list formatting: `-` for unordered lists, `1.` for ordered lists, with consistent indentation.
- Explain technical concepts clearly using real-world metaphors, analogies, and examples.
- Include inline code explanations (e.g., `code`) when referencing code.
- Break down complex topics into approachable, logically flowing paragraphs.
- Maintain a professional, approachable, and slightly conversational tone, like a great teacher guiding a learner.
- Continue from prior sections naturally, as if writing part of a larger publication.
- Avoid motivational filler, excessive metaphors, or redundant whitespace.
- Ensure the output is ready-to-publish, highly engaging, and clear for intelligent general readers.
- When including mathematical expressions or formulas, always use LaTeX syntax and wrap them in $...$ for inline math or $$...$$ for block math.
- If the transcript covers a mathematical or technical concept, include a clear, step-by-step explanation, with formulas and worked examples as a teacher would. Favor a tutorial style over a generic summary when the content is instructional.
- For each key concept, provide at least one worked example with numbers and formulas, step by step.
- Ignore repeated or filler phrases from the transcript; focus on unique mathematical explanations and problem-solving steps.
- Minimize motivational or generic language; focus on clear, logical, and example-driven teaching.
"""
                stream = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    max_tokens=4096
                )
                buffer = ""
                for chunk in stream:
                    content = chunk.choices[0].delta.content or ""
                    buffer += content
                    # Yield only when a double newline is found (end of Markdown block)
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        yield block + "\n\n"
                # Yield any remaining content after the stream ends
                if buffer.strip():
                    yield buffer

        return StreamingResponse(chunk_stream(), media_type="text/plain")
    except SummaryError as e:
        raise e
    except Exception as e:
        logging.error(f"Error in summarize-stream: {str(e)}")
        raise SummaryError(str(e))

@router.post("/qna-stream")
async def qna_stream(request: Request):
    try:
        body = await request.json()
        transcript = body.get("transcript")
        if not transcript:
            raise SummaryError("Transcript is required.")

        max_chunk_chars = 12000
        chunks = [transcript[i:i+max_chunk_chars] for i in range(0, len(transcript), max_chunk_chars)]

        def chunk_stream():
            for chunk in chunks:
                prompt = f"""
You are an expert AI tutor creating study material for learners mastering complex technical concepts.

Based on the following transcript, generate a thoughtful set of educational **question-and-answer pairs**:

{chunk}

Guidelines:
- Format each Q&A pair using **Markdown**: start with '### Question', then a blank line, then '**Answer:**', then the answer.
- Each Q&A pair must be a complete block, and must be separated from the next by exactly two newlines (\n\n). Do not break a Q&A pair across multiple blocks.
- Only output a Q&A pair if both the question and answer are complete. If you cannot complete a pair, do not output it.
- Never use placeholders like "s", "-", or incomplete sentences. Each answer must be a complete, well-formed paragraph.
- Never use 's' as a placeholder. Always use the full word, such as 'answer', 'solution', or the appropriate term for the context. If you see a variable like 's' in the transcript, replace it with the full word in your output.
- Do not truncate questions or answers. If you reach the end of the chunk, finish the current Q&A pair before stopping.
- Avoid duplicate questions or shallow/trivial content; focus on depth and real-world relevance.
- Use impersonal, objective language; avoid first-person ("I", "we") or second-person ("you").
- Maintain a professional, learner-friendly tone suitable for a technical handbook or exam prep guide.
- Use vivid analogies (e.g., agents as detectives, tools as Swiss army knives) to explain abstract ideas.
- Provide detailed walkthroughs for complex processes, like step-by-step debugging logic.
- Avoid narrative clichés (e.g., "let's explore") or excessive whitespace.
- Ensure the output is engaging, insightful, and ready for publication on a professional learning platform.
- When including mathematical expressions or formulas, always use LaTeX syntax and wrap them in $...$ for inline math or $$...$$ for block math.
- For questions about mathematical or technical concepts, provide detailed, step-by-step answers with formulas and worked examples, as a tutor would.
- For each key concept, provide at least one worked example with numbers and formulas, step by step.
- Ignore repeated or filler phrases from the transcript; focus on unique mathematical explanations and problem-solving steps.
- Minimize motivational or generic language; focus on clear, logical, and example-driven teaching.
"""
                stream = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    max_tokens=2048
                )
                buffer = ""
                for chunk in stream:
                    content = chunk.choices[0].delta.content or ""
                    buffer += content
                    # Yield only when a double newline is found (end of Markdown block)
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        yield block + "\n\n"
                # Yield any remaining content after the stream ends
                if buffer.strip():
                    yield buffer

        return StreamingResponse(chunk_stream(), media_type="text/plain")
    except SummaryError as e:
        raise e
    except Exception as e:
        logging.error(f"Error in qna-stream: {str(e)}")
        raise SummaryError(str(e))

@router.post('/extract')
async def extract_key_info(request: Request):
    data = await request.json()
    text = data.get('text', '')
    if not text:
        return JSONResponse({'error': 'No text provided.'}, status_code=400)

    prompt = (
        "Analyze the following text and extract the most relevant structured information for its context. "
        "- If it is a job description, extract skills, technologies, and requirements. "
        "- If it is an article, extract key entities, dates, organizations, and people. "
        "- If it is a story, extract main characters, events, and locations. "
        "- For any other text, extract the most important facts, entities, or concepts. "
        "For each extracted item, provide a brief explanation in plain English. "
        "Return the results as a list of items with explanations.\n\nText:\n" + text + "\n\nExtracted Information:"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
        )
        result = response.choices[0].message.content
        return {"extracted": result}
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)