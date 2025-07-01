from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import ALLOWED_ORIGINS
from services.transcript_service import router as transcript_router
from services.summary_service import router as summary_router
from services.chat_service import router as chat_router

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