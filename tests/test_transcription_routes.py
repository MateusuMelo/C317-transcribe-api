import io
import json
import base64
import os
from datetime import datetime
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.models.schemas import TranscriptionResponse
from app.services.transcription_service import transcription_service


@pytest.fixture
def client(monkeypatch):
    transcription_service.model = object()

    async def fake_initialize():
        transcription_service.model = object()

    async def fake_transcribe_audio_chunk(audio_chunk: bytes, task="transcribe", language=None, sample_rate=16000, channels=1):
        return "mocked transcription"

    async def fake_process_realtime_stream(audio_stream, chunk_duration=5000, language=None, task="transcribe", sample_rate=16000, channels=1):
        yield "mocked stream transcription"

    monkeypatch.setattr(transcription_service, "initialize", fake_initialize)
    monkeypatch.setattr(transcription_service, "transcribe_audio_chunk", fake_transcribe_audio_chunk)
    monkeypatch.setattr(transcription_service, "process_realtime_stream", fake_process_realtime_stream)

    return TestClient(app)


# ---------------------- HTTP ROUTES ----------------------

def test_health_check(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert "model_loaded" in data


def test_transcribe_file_success(client):
    """Test successful file transcription with proper mocking"""

    # Mock the entire transcription service
    with patch('app.routes.transcription.transcription_service') as mock_service:
        # Create a mock response
        mock_response = TranscriptionResponse(
            text="Test transcription result",
            language="en",
            confidence=0.95,
            duration=3.0,
            processed_at=datetime.now()
        )

        # Mock the transcribe_audio_file method
        mock_service.transcribe_audio_file = AsyncMock(return_value=mock_response)

        # Prepare test data
        audio_bytes = b"fake_audio_data"
        files = {
            "file": ("test.ogg", audio_bytes, "audio/ogg"),
        }

        # Make the request
        response = client.post("/api/v1/transcribe/file", files=files)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Test transcription result"
        assert data["language"] == "en"
        assert data["confidence"] == 0.95
        assert data["duration"] == 3.0
        assert "processed_at" in data

        # Verify the service was called with correct parameters
        mock_service.transcribe_audio_file.assert_called_once()
        call_args = mock_service.transcribe_audio_file.call_args
        assert call_args[1]['audio_data'] == audio_bytes
        assert call_args[1]['file_extension'] == 'ogg'
        assert call_args[1]['task'] == 'transcribe'  # default value


def test_transcribe_file_with_custom_parameters(client):
    """Test transcription with custom task and language"""

    with patch('app.routes.transcription.transcription_service') as mock_service:
        mock_response = TranscriptionResponse(
            text="Transcrição em português",
            language="pt",
            confidence=0.92,
            duration=2.5,
            processed_at=datetime.now()
        )

        mock_service.transcribe_audio_file = AsyncMock(return_value=mock_response)

        audio_bytes = b"fake_audio_data"
        files = {"file": ("test.ogg", audio_bytes, "audio/ogg")}
        data = {
            "task": "transcribe",
            "language": "pt"
        }

        response = client.post("/api/v1/transcribe/file", files=files, data=data)

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Transcrição em português"
        assert data["language"] == "pt"

        # Verify custom parameters were passed
        call_args = mock_service.transcribe_audio_file.call_args
        assert call_args[1]['task'] == 'transcribe'


def test_transcribe_file_no_file_uploaded(client):
    """Test when no file is uploaded"""

    with patch('app.routes.transcription.transcription_service') as mock_service:
        mock_service.transcribe_audio_file = AsyncMock()

        response = client.post("/api/v1/transcribe/file")

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422
        mock_service.transcribe_audio_file.assert_not_called()


def test_transcribe_file_invalid_extension(client):
    fake = io.BytesIO(b"not audio")
    response = client.post(
        "/api/v1/transcribe/file",
        files={"file": ("file.txt", fake, "text/plain")}
    )
    assert response.status_code == 400


def test_transcribe_file_too_large(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.MAX_AUDIO_SIZE_MB", 1)
    big_file = io.BytesIO(b"X" * (2 * 1024 * 1024))  # 2MB
    response = client.post(
        "/api/v1/transcribe/file",
        files={"file": ("audio.wav", big_file, "audio/wav")}
    )
    assert response.status_code == 413


def test_transcribe_file_service_error(client, monkeypatch):
    async def fake_transcribe_audio_chunk(*args, **kwargs):
        raise RuntimeError("Simulated failure")

    monkeypatch.setattr(transcription_service, "transcribe_audio_chunk", fake_transcribe_audio_chunk)

    f = io.BytesIO(b"RIFF" + b"00" * 50)
    response = client.post(
        "/api/v1/transcribe/file",
        files={"file": ("audio.wav", f, "audio/wav")}
    )
    assert response.status_code == 500

# ---------------------- WEBSOCKET ----------------------

def test_websocket_transcription(monkeypatch):
    async def fake_transcribe_audio_chunk(audio_chunk, task="transcribe", language=None, sample_rate=16000, channels=1):
        return "mocked live text"

    monkeypatch.setattr(transcription_service, "transcribe_audio_chunk", fake_transcribe_audio_chunk)

    client = TestClient(app)
    with client.websocket_connect("/ws/transcribe") as websocket:
        audio_data = base64.b64encode(b"RIFF" + b"00" * 10).decode()
        websocket.send_text(json.dumps({
            "type": "audio_chunk",
            "data": audio_data,
            "sample_rate": 16000,
            "channels": 1
        }))
        response = websocket.receive_text()
        data = json.loads(response)
        assert data["type"] == "transcription"
        assert data["text"] == "mocked live text"


