import base64
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(monkeypatch):
    # Mock heavy initialize to no-op and other service methods
    from app.services.transcription_service import transcription_service

    # Ensure health endpoint reports model loaded
    transcription_service.model = object()

    async def fake_initialize():
        transcription_service.model = object()
        return None

    async def fake_transcribe_audio_file(audio_data: bytes, file_extension: str = "wav", task: str = "translate", language: str | None = None):
        from app.models.schemas import TranscriptionResponse
        from datetime import datetime
        return TranscriptionResponse(
            text="dummy transcription",
            language=language or "pt",
            confidence=0.9,
            duration=1.23,
            processed_at=datetime.now(),
        )

    async def fake_transcribe_audio_chunk(audio_chunk: bytes, task: str = "translate"):
        return "dummy chunk transcription"

    async def fake_transcribe_audio_stream(audio_stream, chunk_duration: int = 5000, language: str | None = None, task: str = "transcribe"):
        # Yield exactly one item to simulate streaming
        yield "stream part 1"

    # Apply monkeypatches on the service instance
    monkeypatch.setattr(transcription_service, "initialize", fake_initialize)
    monkeypatch.setattr(transcription_service, "transcribe_audio_file", fake_transcribe_audio_file)
    monkeypatch.setattr(transcription_service, "transcribe_audio_chunk", fake_transcribe_audio_chunk)
    monkeypatch.setattr(transcription_service, "transcribe_audio_stream", fake_transcribe_audio_stream)

    return TestClient(app)
