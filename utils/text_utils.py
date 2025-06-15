import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def clean_transcript_text(text: str) -> str:
    text = re.sub(r'^Kind:\s*captions\s*Language:\s*\w+\s*', '', text, flags=re.IGNORECASE)
    sentences = re.split(r'([.!?]+)', text)
    cleaned_sentences = []
    seen_sentences = set()
    
    current_sentence = ""
    for segment in sentences:
        current_sentence += segment
        if segment.strip().endswith(('.', '!', '?')) or len(current_sentence) > 200:
            clean_sentence = re.sub(r'\s+', ' ', current_sentence).strip()
            words = clean_sentence.split()
            unique_words = []
            prev_word = ""
            for word in words:
                if word != prev_word:
                    unique_words.append(word)
                    prev_word = word
            clean_sentence = ' '.join(unique_words)
            if (clean_sentence not in seen_sentences and 
                len(clean_sentence) > 10 and 
                not clean_sentence.lower().startswith('kind:')):
                cleaned_sentences.append(clean_sentence)
                seen_sentences.add(clean_sentence)
            current_sentence = ""
    
    if current_sentence.strip():
        clean_sentence = re.sub(r'\s+', ' ', current_sentence).strip()
        if len(clean_sentence) > 10:
            cleaned_sentences.append(clean_sentence)
    
    full_text = ' '.join(cleaned_sentences)
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    paragraphs = []
    current_paragraph = []
    for sentence in sentences:
        current_paragraph.append(sentence)
        if len(current_paragraph) >= 3:
            paragraphs.append(' '.join(current_paragraph))
            current_paragraph = []
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    return '\n\n'.join(paragraphs)

def parse_vtt_content(content: str) -> str:
    lines = content.split('\n')
    transcript_lines = []
    for line in lines:
        line = line.strip()
        if (line and 
            not line.startswith('WEBVTT') and 
            '-->' not in line and 
            not line.isdigit() and
            not line.startswith('NOTE') and
            not line.startswith('STYLE')):
            clean_line = remove_vtt_tags(line)
            if clean_line:
                transcript_lines.append(clean_line)
    text = ' '.join(transcript_lines)
    return format_transcript(text)

def remove_vtt_tags(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def format_transcript(text: str) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    paragraphs = []
    current_paragraph = []
    for sentence in sentences:
        current_paragraph.append(sentence)
        if len(current_paragraph) >= 3:
            paragraphs.append(' '.join(current_paragraph))
            current_paragraph = []
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    return '\n\n'.join(paragraphs)