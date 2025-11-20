from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from src.core.config import settings
from src.routes import transcription, websocket

app = FastAPI(
    title="Audio Translation API",
    description="API for real-time audio transcription and translation",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Routes
app.include_router(transcription.router, prefix="/api/v1", tags=["transcription"])
app.include_router(websocket.router, tags=["websocket"])


@app.get("/")
async def read_index():
    return FileResponse('src/static/index.html')


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "audio-translation-api"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD
    )
