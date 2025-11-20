from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TranscriptionRequest(BaseModel):
    language: Optional[str] = None
    task: str = "transcribe"  # translate or transcribe
    beam_size: Optional[int] = 5


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    confidence: Optional[float] = None
    duration: float
    processed_at: datetime


class WebSocketMessage(BaseModel):
    type: str  # "audio_chunk", "transcription", "error"
    data: dict
    timestamp: datetime


class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None
    timestamp: datetime
