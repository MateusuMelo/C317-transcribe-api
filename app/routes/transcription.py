from typing import AsyncGenerator

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.models.schemas import TranscriptionRequest, TranscriptionResponse
from app.services.transcription_service import transcription_service
from app.utils.file_handlers import FileHandler

router = APIRouter()


async def chunk_generator(file: UploadFile, chunk_size: int = 1024 * 1024) -> AsyncGenerator[bytes, None]:
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        yield chunk


@router.post("/transcribe/file", response_model=TranscriptionResponse)
async def transcribe_audio_file(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        request: TranscriptionRequest = None
):
    if request is None:
        request = TranscriptionRequest()

    if not FileHandler.is_audio_file(file.filename):
        raise HTTPException(400, "File must be an audio file")

    audio_data = await file.read()
    max_size = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024

    if len(audio_data) > max_size:
        raise HTTPException(413, f"File too large. Maximum: {settings.MAX_AUDIO_SIZE_MB}MB")

    file_extension = FileHandler.get_file_extension(file.filename)
    try:
        result = await transcription_service.transcribe_audio_file(
            audio_data=audio_data,
            file_extension=file_extension,
            task=request.task,
            language=request.language
        )
        return result

    except Exception as e:
        raise HTTPException(500, f"Transcription error: {str(e)}")


@router.post("/transcribe/stream")
async def transcribe_audio_stream(
        file: UploadFile = File(...),
        chunk_duration: int = 5000,
        language: str = None
):
    if not FileHandler.is_audio_file(file.filename):
        raise HTTPException(400, "File must be an audio file")
    try:
        chunk_gen = chunk_generator(file)

        async def generate_transcriptions():
            async for transcription in transcription_service.transcribe_audio_stream(
                    audio_stream=chunk_gen,
                    chunk_duration=chunk_duration,
                    language=language,
                    task="transcribe"
            ):
                if transcription:
                    yield f"data: {transcription}\n\n"

        return StreamingResponse(
            generate_transcriptions(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except Exception as e:
        raise HTTPException(500, f"Streaming error: {str(e)}")


@router.get("/health")
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "service": "audio-translation-api",
        "model_loaded": transcription_service.model is not None
    }
