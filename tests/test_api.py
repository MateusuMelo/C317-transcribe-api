
import base64
import json

import pytest
from unittest.mock import Mock, patch, AsyncMock
import io
from pydub import AudioSegment
from pydub.generators import Sine


def test_root_serves_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "audio-translation-api"


def test_api_health_with_model_loaded_flag(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert isinstance(data["model_loaded"], bool)


def test_transcribe_file_success(client, monkeypatch):
    # Mock the transcription service to return a specific transcription
    mock_response = {
        "text": "Test de Transcrição",
        "language": "pt",
        "confidence": 0.95,
        "duration": 3.0,
        "processed_at": "2024-01-01T00:00:00"
    }

    mock_transcribe = AsyncMock(return_value=Mock(**mock_response))
    monkeypatch.setattr(
        "app.services.transcription_service.transcription_service.transcribe_audio_file",
        mock_transcribe
    )

    # Create a real OGG audio file for testing
    audio_bytes = create_test_audio_bytes()
    files = {
        "file": ("sample.ogg", audio_bytes, "audio/ogg"),
    }

    resp = client.post("/api/v1/transcribe/file", files=files)
    assert resp.status_code == 200
    data = resp.json()

    # Verify the mocked transcription
    assert data["text"] == "Test de Transcrição"
    assert data["language"] == "pt"
    assert data["confidence"] == 0.95
    assert data["duration"] == 3.0
    assert "processed_at" in data

    # Verify the service was called with correct parameters
    mock_transcribe.assert_called_once()


def test_transcribe_file_with_language_parameter(client, monkeypatch):
    """Test transcription with specific language parameter"""
    mock_response = {
        "text": "Transcription Test",
        "language": "en",
        "confidence": 0.92,
        "duration": 2.5,
        "processed_at": "2024-01-01T00:00:00"
    }

    mock_transcribe = AsyncMock(return_value=Mock(**mock_response))
    monkeypatch.setattr(
        "app.services.transcription_service.transcription_service.transcribe_audio_file",
        mock_transcribe
    )

    audio_bytes = create_test_audio_bytes()
    files = {
        "file": ("sample.ogg", audio_bytes, "audio/ogg"),
    }
    data = {
        "language": "en",
        "task": "transcribe"
    }

    resp = client.post("/api/v1/transcribe/file", files=files, data=data)
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "en"


def test_transcribe_file_translation_task(client, monkeypatch):
    """Test translation task instead of transcription"""
    mock_response = {
        "text": "Translation Test",
        "language": "en",
        "confidence": 0.88,
        "duration": 2.0,
        "processed_at": "2024-01-01T00:00:00"
    }

    mock_transcribe = AsyncMock(return_value=Mock(**mock_response))
    monkeypatch.setattr(
        "app.services.transcription_service.transcription_service.transcribe_audio_file",
        mock_transcribe
    )

    audio_bytes = create_test_audio_bytes()
    files = {
        "file": ("sample.ogg", audio_bytes, "audio/ogg"),
    }
    data = {
        "task": "translate"
    }

    resp = client.post("/api/v1/transcribe/file", files=files, data=data)
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Translation Test"


def test_transcribe_file_invalid_extension(client):
    audio_bytes = b"not_audio"
    files = {
        "file": ("document.txt", audio_bytes, "text/plain"),
    }
    resp = client.post("/api/v1/transcribe/file", files=files)
    assert resp.status_code == 400
    assert "File must be an audio file" in resp.json()["detail"]


def test_transcribe_file_no_file_uploaded(client):
    resp = client.post("/api/v1/transcribe/file")
    assert resp.status_code == 422  # Validation error


def test_transcribe_file_too_large(client, monkeypatch):
    from app.core import config as cfg
    old = cfg.settings.MAX_AUDIO_SIZE_MB
    cfg.settings.MAX_AUDIO_SIZE_MB = 0
    try:
        audio_bytes = b"A" * 10
        files = {
            "file": ("big.ogg", audio_bytes, "audio/ogg"),
        }
        resp = client.post("/api/v1/transcribe/file", files=files)
        assert resp.status_code == 413
        assert "File too large" in resp.json()["detail"]
    finally:
        cfg.settings.MAX_AUDIO_SIZE_MB = old


def test_transcribe_file_service_error(client, monkeypatch):
    """Test when transcription service raises an exception"""
    mock_transcribe = AsyncMock(side_effect=Exception("Transcription failed"))
    monkeypatch.setattr(
        "app.services.transcription_service.transcription_service.transcribe_audio_file",
        mock_transcribe
    )

    audio_bytes = create_test_audio_bytes()
    files = {
        "file": ("sample.ogg", audio_bytes, "audio/ogg"),
    }

    resp = client.post("/api/v1/transcribe/file", files=files)
    assert resp.status_code == 500
    assert "Transcription error" in resp.json()["detail"]


def test_transcribe_stream_endpoint(client, monkeypatch):
    """Test the streaming transcription endpoint"""
    mock_transcriptions = ["First part", "Second part", "Final part"]

    async def mock_stream(*args, **kwargs):
        for text in mock_transcriptions:
            yield text

    monkeypatch.setattr(
        "app.services.transcription_service.transcription_service.transcribe_audio_stream",
        mock_stream
    )

    audio_bytes = create_test_audio_bytes()
    files = {
        "file": ("stream.ogg", audio_bytes, "audio/ogg"),
    }

    resp = client.post("/api/v1/transcribe/stream", files=files)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/plain; charset=utf-8"
    assert "cache-control" in resp.headers


def test_transcribe_stream_invalid_file(client):
    files = {
        "file": ("invalid.txt", b"not audio", "text/plain"),
    }
    resp = client.post("/api/v1/transcribe/stream", files=files)
    assert resp.status_code == 400


def test_websocket_connection(client):
    """Test WebSocket connection and basic ping-pong"""
    with client.websocket_connect("/ws/transcribe") as ws:
        # Test ping-pong
        ws.send_text('{"type": "ping"}')
        response = ws.receive_text()
        assert response == '{"type": "pong"}'


def test_websocket_audio_transcription(client, monkeypatch):
    """Test WebSocket audio transcription with mocked service"""
    # Mock the transcription service
    mock_transcribe = AsyncMock(return_value="Test de Transcrição")
    monkeypatch.setattr(
        "app.services.transcription_service.transcription_service.transcribe_audio_chunk",
        mock_transcribe
    )

    with client.websocket_connect("/ws/transcribe") as ws:
        # Send audio chunk
        audio_bytes = create_test_audio_bytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        message = {
            "type": "audio_chunk",
            "data": audio_b64,
            "is_final": True,
            "task": "transcribe"
        }

        ws.send_text(json.dumps(message))

        # Receive transcription
        response = ws.receive_text()
        response_data = json.loads(response)

        assert response_data["type"] == "transcription"
        assert response_data["text"] == "Test de Transcrição"
        assert response_data["is_final"] == True

        # Verify service was called
        mock_transcribe.assert_called_once()



def test_multiple_websocket_connections(client, monkeypatch):
    """Test multiple simultaneous WebSocket connections"""
    mock_transcribe = AsyncMock(return_value="Test Transcription")
    monkeypatch.setattr(
        "app.services.transcription_service.transcription_service.transcribe_audio_chunk",
        mock_transcribe
    )

    # Create multiple connections
    with client.websocket_connect("/ws/transcribe") as ws1, \
            client.websocket_connect("/ws/transcribe") as ws2:
        # Test both connections work independently
        ws1.send_text('{"type": "ping"}')
        response1 = ws1.receive_text()
        assert response1 == '{"type": "pong"}'

        ws2.send_text('{"type": "ping"}')
        response2 = ws2.receive_text()
        assert response2 == '{"type": "pong"}'


def create_test_audio_bytes() -> bytes:
    """Create test audio bytes in OGG format"""
    try:
        # Generate a simple sine wave audio
        tone = Sine(440).to_audio_segment(duration=2000)  # 2 seconds
        tone = tone.set_frame_rate(16000).set_channels(1)

        # Export to bytes in OGG format
        audio_io = io.BytesIO()
        tone.export(audio_io, format="ogg", codec="libvorbis")
        return audio_io.getvalue()
    except ImportError:
        # Fallback: return dummy audio data if pydub is not available
        return b"fake_ogg_audio_data_for_testing"


# Additional utility tests
def test_file_handler_utilities():
    """Test FileHandler utility methods"""
    from app.utils.file_handlers import FileHandler

    # Test file extension extraction
    assert FileHandler.get_file_extension("audio.ogg") == "ogg"
    assert FileHandler.get_file_extension("audio.wav") == "wav"
    assert FileHandler.get_file_extension("audio.mp3") == "mp3"
    assert FileHandler.get_file_extension("no_extension") == ""

    # Test audio file validation
    assert FileHandler.is_audio_file("audio.ogg") == True
    assert FileHandler.is_audio_file("audio.wav") == True
    assert FileHandler.is_audio_file("audio.mp3") == True
    assert FileHandler.is_audio_file("document.txt") == False
    assert FileHandler.is_audio_file("image.jpg") == False


def test_audio_converter_utilities():
    """Test AudioConverter utility methods"""
    from app.utils.audio_converters import AudioConverter

    # Test that the class can be instantiated and methods exist
    converter = AudioConverter()
    assert hasattr(converter, 'convert_to_wav')
    assert hasattr(converter, 'ensure_compatible_audio')
    assert hasattr(converter, 'convert_audio_chunk')


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])