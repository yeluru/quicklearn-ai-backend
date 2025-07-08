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
import asyncio
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
import nest_asyncio

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

def is_text_response(response):
    content_type = response.headers.get('content-type', '').lower()
    return 'text/html' in content_type or 'application/xhtml+xml' in content_type or 'text/plain' in content_type

def is_mostly_binary(text, threshold=0.3):
    # Returns True if more than threshold fraction of characters are non-printable
    if not text:
        return True
    non_printable = sum(1 for c in text if ord(c) < 9 or (ord(c) > 13 and ord(c) < 32) or ord(c) > 126)
    return (non_printable / len(text)) > threshold

def scrape_website_playwright(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            # Wait for network to be idle or a reasonable time
            page.wait_for_load_state('networkidle', timeout=15000)
            # Extract visible text from the body
            content = page.inner_text('body')
            browser.close()
            # Clean up excessive whitespace
            content = '\n'.join([line.strip() for line in content.splitlines() if line.strip()])
            return content
    except Exception as e:
        logging.error(f"Playwright scraping failed for {url}: {e}")
        return ""

async def scrape_website_playwright_async(url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state('networkidle', timeout=15000)
            content = await page.inner_text('body')
            await browser.close()
            content = '\n'.join([line.strip() for line in content.splitlines() if line.strip()])
            return content
    except Exception as e:
        logging.error(f"Playwright scraping failed for {url}: {e}")
        return ""

def run_async_playwright(coro):
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)

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
        used_playwright = False
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
                content_type = resp.headers.get('content-type', 'unknown')
                logging.debug(f"Scraping {current_url} - Content-Type: {content_type}, First 100 bytes: {resp.content[:100]}")
                if resp.status_code != 200:
                    logging.error(f"Non-200 status code {resp.status_code} for {current_url}")
                    continue
                visited.add(current_url)
                if is_pdf_response(resp):
                    text = extract_pdf_text(resp)
                    if text:
                        transcript_sections.append(text)
                elif is_text_response(resp):
                    html = resp.text
                    main_text = extract_main_text(html, current_url)
                    # Check for empty or mostly binary output
                    if not main_text or is_mostly_binary(main_text):
                        # Fallback to Playwright for JS-heavy or protected sites
                        logging.info(f"Falling back to Playwright for {current_url}")
                        main_text = run_async_playwright(scrape_website_playwright_async(current_url))
                        used_playwright = True
                        if not main_text or is_mostly_binary(main_text):
                            raise ValueError(
                                f"The provided URL did not yield extractable text content, even after browser rendering. "
                                f"It may be protected, binary, or unsupported."
                            )
                    transcript_sections.append(main_text)
                    # Only try to find video links if not using Playwright (to avoid extra requests)
                    if not used_playwright:
                        video_links.update(find_video_links(html, current_url))
                    if depth < max_depth:
                        links = get_links(html, current_url)
                        for link in links:
                            if link not in visited:
                                to_visit.append((link, depth + 1))
                else:
                    # Not a supported content type
                    raise ValueError(
                        f"The provided URL does not contain extractable text content. "
                        f"Content-Type: {resp.headers.get('content-type', 'unknown')}. "
                        f"This may be a protected, binary, or unsupported file type."
                    )
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