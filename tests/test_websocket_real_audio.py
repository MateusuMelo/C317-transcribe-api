# tests/test_websocket_real_audio.py
import base64
import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def real_audio_data():
    """Load real audio file for testing"""
    audio_path = os.path.join(os.path.dirname(__file__), "data", "teste.ogg")
    if not os.path.exists(audio_path):
        pytest.skip(f"Audio file not found: {audio_path}")

    with open(audio_path, "rb") as audio_file:
        return audio_file.read()


@pytest.fixture(autouse=True)
def patch_manager():
    """Patch the global manager with a fresh instance for each test"""
    from src.routes.websocket import ConnectionManager
    fresh_manager = ConnectionManager()
    with patch('src.routes.websocket.manager', fresh_manager):
        yield


@pytest.mark.asyncio
async def test_websocket_real_audio_transcription(client, real_audio_data):
    """Test WebSocket with real audio file containing 'Teste de transcrição'"""
    with patch('src.routes.websocket.transcription_service') as mock_service:
        mock_service.initialize = AsyncMock()
        mock_service.transcribe_audio_chunk = AsyncMock(return_value="Teste de transcrição")

        with client.websocket_connect("/ws/transcribe") as websocket:
            # Encode real audio data to base64
            audio_b64 = base64.b64encode(real_audio_data).decode('utf-8')

            # Send audio chunk message
            audio_message = {
                "type": "audio_chunk",
                "data": audio_b64,
                "sample_rate": 16000,
                "channels": 1
            }
            websocket.send_text(json.dumps(audio_message))

            # Receive and verify transcription response
            response = websocket.receive_text()
            response_data = json.loads(response)

            assert response_data["type"] == "transcription"
            assert response_data["text"] == "Teste de transcrição"
            assert "timestamp" in response_data

            # Verify service was called with the real audio data
            mock_service.transcribe_audio_chunk.assert_called_once_with(
                real_audio_data,
                sample_rate=16000,
                channels=1
            )


@pytest.mark.asyncio
async def test_websocket_real_audio_multiple_chunks(client, real_audio_data):
    """Test WebSocket with multiple chunks of real audio data"""
    with patch('src.routes.websocket.transcription_service') as mock_service:
        mock_service.initialize = AsyncMock()
        # Simulate different transcriptions for different chunks
        mock_service.transcribe_audio_chunk = AsyncMock(
            side_effect=["Teste de", "transcrição", "completo"]
        )

        with client.websocket_connect("/ws/transcribe") as websocket:
            # Split audio data into chunks (simulating real-time streaming)
            chunk_size = len(real_audio_data) // 3
            chunks = [
                real_audio_data[i:i + chunk_size]
                for i in range(0, len(real_audio_data), chunk_size)
            ][:3]  # Take first 3 chunks

            expected_transcriptions = ["Teste de", "transcrição", "completo"]

            for i, chunk in enumerate(chunks):
                audio_b64 = base64.b64encode(chunk).decode('utf-8')

                audio_message = {
                    "type": "audio_chunk",
                    "data": audio_b64,
                    "sample_rate": 16000,
                    "channels": 1
                }
                websocket.send_text(json.dumps(audio_message))

                # Receive response for each chunk
                response = websocket.receive_text()
                response_data = json.loads(response)

                assert response_data["type"] == "transcription"
                assert response_data["text"] == expected_transcriptions[i]
                assert "timestamp" in response_data

            # Verify all chunks were processed
            assert mock_service.transcribe_audio_chunk.call_count == 3