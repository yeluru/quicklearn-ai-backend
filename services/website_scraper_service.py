import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from newspaper import Article
from readability import Document
import re
import logging
import PyPDF2
import io
import bs4

VIDEO_PATTERNS = [
    r'youtube\.com/watch\?v=[\w-]+',
    r'youtu\.be/[\w-]+',
    r'vimeo\.com/\d+',
    r'dailymotion\.com/video/[\w-]+'
]

PDF_MIME_TYPES = [
    'application/pdf',
    'application/x-pdf',
    'application/acrobat',
    'applications/vnd.pdf',
    'text/pdf',
    'text/x-pdf'
]

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def is_pdf_response(response):
    content_type = response.headers.get('content-type', '').lower()
    return any(mime in content_type for mime in PDF_MIME_TYPES)

def extract_pdf_text(response):
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(response.content))
        text = "\n".join(page.extract_text() or '' for page in pdf_reader.pages)
        return text.strip()
    except Exception as e:
        logging.error(f"PDF extraction error: {e}")
        return ""

def extract_main_text(html, url):
    texts = []
    # Try newspaper3k
    try:
        article = Article(url)
        article.set_html(html)
        article.parse()
        if article.text.strip():
            texts.append(article.text.strip())
    except Exception:
        pass
    # Readability-lxml
    try:
        doc = Document(html)
        content = doc.summary()
        soup = BeautifulSoup(content, 'lxml')
        text = soup.get_text(separator='\n', strip=True)
        if text.strip():
            texts.append(text.strip())
    except Exception:
        pass
    # All visible text (removing nav, footer, etc.)
    try:
        soup = BeautifulSoup(html, 'lxml')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'form', 'noscript']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        if text.strip():
            texts.append(text.strip())
    except Exception:
        pass
    # All <p>, <li>, and heading tags
    try:
        soup = BeautifulSoup(html, 'lxml')
        elements = soup.find_all(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        element_texts = [el.get_text(separator=' ', strip=True) for el in elements if el.get_text(strip=True)]
        if element_texts:
            texts.append('\n'.join(element_texts))
    except Exception:
        pass
    # Remove duplicates and join
    seen = set()
    unique_texts = []
    for t in texts:
        if t not in seen:
            unique_texts.append(t)
            seen.add(t)
    return '\n\n'.join(unique_texts)

def find_video_links(html, base_url):
    soup = BeautifulSoup(html, 'lxml')
    links = []
    for a in soup.find_all('a', href=True):
        if not isinstance(a, bs4.element.Tag):
            continue
        href = a.get('href')
        if not href:
            continue
        href = urljoin(base_url, str(href))
        for pattern in VIDEO_PATTERNS:
            if re.search(pattern, href):
                links.append(href)
    return links

def get_links(html, base_url):
    soup = BeautifulSoup(html, 'lxml')
    links = set()
    for a in soup.find_all('a', href=True):
        if not isinstance(a, bs4.element.Tag):
            continue
        href = a.get('href')
        if not href:
            continue
        href = urljoin(base_url, str(href))
        if urlparse(href).netloc == urlparse(base_url).netloc:
            links.add(href)
    return list(links)

def try_url_variants(base_url):
    """
    Try all common variants of a URL (http, https, www, non-www) and return the first that works.
    """
    variants = []
    parsed = urlparse(base_url)
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ''
    if not netloc:
        logging.error(f"No netloc found in base_url: {base_url}")
        return None
    # Try https and http, with and without www
    for scheme in ['https', 'http']:
        for prefix in ['', 'www.']:
            url = f"{scheme}://{prefix}{netloc}{path}"
            variants.append(url)
    last_error = None
    for url in variants:
        try:
            resp = requests.get(url, timeout=10, headers=BROWSER_HEADERS)
            if resp.status_code == 200:
                return url
        except Exception as e:
            last_error = e
            logging.error(f"Failed to connect to {url}: {e}")
            continue
    if last_error:
        logging.error(f"All URL variants failed for {base_url}: {last_error}")
    return None

def scrape_website(url, max_depth=2, max_pages=10):
    try:
        if not url.startswith('http'):
            url_variant = try_url_variants(url)
            if not url_variant:
                raise Exception(f"Could not resolve a valid URL variant for scraping: {url}")
            url = url_variant
        visited = set()
        to_visit = [(url, 0)]
        transcript_sections = []
        video_links = set()
        pages_scraped = 0
        while to_visit and pages_scraped < max_pages:
            current_url, depth = to_visit.pop(0)
            if current_url in visited or depth > max_depth:
                continue
            try:
                try:
                    resp = requests.get(current_url, timeout=10, headers=BROWSER_HEADERS)
                except requests.exceptions.SSLError:
                    resp = requests.get(current_url, timeout=10, headers=BROWSER_HEADERS, verify=False)
                    logging.warning(f"SSL verification disabled for {current_url}")
                if resp.status_code != 200:
                    logging.error(f"Non-200 status code {resp.status_code} for {current_url}")
                    continue
                visited.add(current_url)
                if is_pdf_response(resp):
                    text = extract_pdf_text(resp)
                    if text:
                        transcript_sections.append(text)
                else:
                    html = resp.text
                    main_text = extract_main_text(html, current_url)
                    if main_text:
                        transcript_sections.append(main_text)
                    video_links.update(find_video_links(html, current_url))
                    if depth < max_depth:
                        links = get_links(html, current_url)
                        for link in links:
                            if link not in visited:
                                to_visit.append((link, depth + 1))
                pages_scraped += 1
            except Exception as e:
                logging.error(f"Error scraping {current_url}: {e}")
                continue
        transcript = "\n\n".join(transcript_sections)
        if video_links:
            transcript += "\n\n[Video Links Found]\n" + "\n".join(video_links)
        return transcript
    except Exception as e:
        logging.error(f"Scraping failed for {url}: {e}")
        raise 