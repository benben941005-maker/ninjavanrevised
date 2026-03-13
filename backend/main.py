"""
AI Senior Driver Copilot — FastAPI Backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
import os

from routes.chat import router as chat_router
from routes.ocr import router as ocr_router
from routes.voice import router as voice_router
from routes.navigation import router as navigation_router
from routes.weather import router as weather_router
from routes.notifications import router as notifications_router

app = FastAPI(
    title="AI Senior Driver Copilot",
    description="AI-powered logistics assistant for last-mile delivery drivers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
INDEX_FILE = os.path.join(FRONTEND_DIR, "index.html")

# API Routes
app.include_router(chat_router, prefix="/api/chat", tags=["AI Assistant"])
app.include_router(ocr_router, prefix="/api/ocr", tags=["Parcel OCR"])
app.include_router(voice_router, prefix="/api/voice", tags=["Voice"])
app.include_router(navigation_router, prefix="/api/navigation", tags=["Navigation"])
app.include_router(weather_router, prefix="/api/weather", tags=["Weather"])
app.include_router(notifications_router, prefix="/api/notify", tags=["Notifications"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Senior Driver Copilot"}


@app.get("/")
async def serve_frontend():
    if os.path.exists(INDEX_FILE):
        return FileResponse(INDEX_FILE)
    return {"message": "Frontend not found. Please make sure frontend/index.html is included in the deployment."}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
