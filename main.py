from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from config import ALLOWED_ORIGINS
from services.transcript_service import router as transcript_router
from services.summary_service import router as summary_router
from services.chat_service import router as chat_router
from services.website_scraper_service import scrape_website
from fastapi.responses import JSONResponse
import logging

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(transcript_router, prefix="/transcript")
app.include_router(summary_router, prefix="/summary")
app.include_router(chat_router, prefix="/chat")

@app.get("/")
async def root():
    return {"message": "Welcome to QuickLearn.AI Backend"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "QuickLearn.AI Backend"}

@app.post("/scrape")
async def scrape_website_endpoint(request: Request):
    data = await request.json()
    url = data.get("url")
    if not url:
        logging.error("No URL provided to /scrape endpoint.")
        return JSONResponse({"error": "No URL provided."}, status_code=400)
    try:
        transcript = scrape_website(url)
        logging.debug(f"Returning transcript (first 500 chars): {transcript[:500]}")
        return {"transcript": transcript}
    except ValueError as ve:
        logging.error(f"User error in /scrape endpoint for {url}: {ve}")
        logging.debug(f"Returning error: {str(ve)}")
        return JSONResponse({"error": str(ve)}, status_code=400)
    except Exception as e:
        logging.error(f"Error in /scrape endpoint for {url}: {e}")
        logging.debug(f"Returning generic error for {url}")
        return JSONResponse({"error": "An unexpected error occurred while scraping the website."}, status_code=500)