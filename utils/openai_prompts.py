# Prompt templates for OpenAI usage in chat_service.py

SUGGESTED_QUESTIONS_PROMPT = """
You are a helpful AI assistant. Read the following transcript and generate 5 distinct educational topics, each with one thoughtful question.

Output format (JSON array, exactly 5 items):
[
  { "topic": "string", "question": "string" },
  { "topic": "string", "question": "string" },
  { "topic": "string", "question": "string" },
  { "topic": "string", "question": "string" },
  { "topic": "string", "question": "string" }
]

Transcript:
{transcript}
"""

SUMMARIZE_VIDEO_PROMPT = """Based on this transcript excerpt: '{transcript}...', provide a 3-4 sentence summary in plain text. In the summary, do not start with 'The text' or 'The excerpt' or 'The excerpt discusses' or 'transcript excerpt discusses' or 'video discusses' mention anything about speaker, instead generalize the summary."""

SUMMARIZE_STREAM_PROMPT = """
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
"""

QNA_STREAM_PROMPT = """
You are an expert AI tutor creating study material for learners mastering complex technical concepts.

Based on the following transcript, generate a thoughtful set of educational **question-and-answer pairs**:

{chunk}

Guidelines:
- Format each Q&A pair using **Markdown**: `### Question` for questions, `**Answer:**` for answers.
- Write concise questions (1-2 sentences) probing meaningful technical concepts, mechanisms, or use cases.
- Provide detailed answers (3-5 sentences) with clear examples, analogies, or technical explanations.
- Ensure each Q&A pair is separated by a blank line for clarity.
- Avoid duplicate questions or shallow/trivial content; focus on depth and real-world relevance.
- Use impersonal, objective language; avoid first-person ("I", "we") or second-person ("you").
- Maintain a professional, learner-friendly tone suitable for a technical handbook or exam prep guide.
- Use vivid analogies (e.g., agents as detectives, tools as Swiss army knives) to explain abstract ideas.
- Provide detailed walkthroughs for complex processes, like step-by-step debugging logic.
- Avoid narrative clichés (e.g., "let's explore") or excessive whitespace.
- Ensure the output is engaging, insightful, and ready for publication on a professional learning platform.
"""

EXTRACT_KEY_INFO_PROMPT = (
    "Analyze the following text and extract the most relevant structured information for its context. "
    "- If it is a job description, extract skills, technologies, and requirements. "
    "- If it is an article, extract key entities, dates, organizations, and people. "
    "- If it is a story, extract main characters, events, and locations. "
    "- For any other text, extract the most important facts, entities, or concepts. "
    "For each extracted item, provide a brief explanation in plain English. "
    "Return the results as a list of items with explanations.\n\nText:\n{{text}}\n\nExtracted Information:"
) 