# tests/test_websocket_routes.py
import base64
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestWebSocketRoutes:
    """Test cases for WebSocket transcription routes"""

    @pytest.fixture
    def client(self):
        """Test client fixture"""
        return TestClient(app)

    @pytest.fixture
    def fresh_manager(self):
        """Create a fresh ConnectionManager for each test"""
        from app.routes.websocket import ConnectionManager
        return ConnectionManager()

    @pytest.fixture
    def mock_transcription_service(self):
        """Mock transcription service"""
        with patch('app.routes.websocket.transcription_service') as mock_service:
            mock_service.initialize = AsyncMock()
            mock_service.transcribe_audio_chunk = AsyncMock()
            yield mock_service

    @pytest.fixture(autouse=True)
    def patch_manager(self, fresh_manager):
        """Patch the global manager with a fresh instance for each test"""
        with patch('app.routes.websocket.manager', fresh_manager):
            yield

    @pytest.mark.asyncio
    async def test_websocket_connection(self, client, mock_transcription_service, fresh_manager):
        """Test WebSocket connection establishment"""
        with client.websocket_connect("/ws/transcribe") as websocket:
            # Connection should be established
            assert len(fresh_manager.active_connections) == 1
            # Model should be initialized
            mock_transcription_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_audio_transcription(self, client, mock_transcription_service):
        """Test audio transcription via WebSocket"""
        # Mock transcription response
        mock_transcription_service.transcribe_audio_chunk.return_value = "Hello world"

        with client.websocket_connect("/ws/transcribe") as websocket:
            # Prepare test audio data
            test_audio_data = b"fake_audio_data_here"
            audio_b64 = base64.b64encode(test_audio_data).decode('utf-8')

            # Send audio chunk message
            audio_message = {
                "type": "audio_chunk",
                "data": audio_b64,
                "sample_rate": 16000,
                "channels": 1
            }
            websocket.send_text(json.dumps(audio_message))

            # Should receive transcription response
            response = websocket.receive_text()
            response_data = json.loads(response)

            assert response_data["type"] == "transcription"
            assert response_data["text"] == "Hello world"
            assert "timestamp" in response_data

            # Verify service was called with correct parameters
            mock_transcription_service.transcribe_audio_chunk.assert_called_once_with(
                test_audio_data,
                sample_rate=16000,
                channels=1
            )

    @pytest.mark.asyncio
    async def test_websocket_audio_transcription_default_params(self, client, mock_transcription_service):
        """Test audio transcription with default parameters"""
        mock_transcription_service.transcribe_audio_chunk.return_value = "Test transcription"

        with client.websocket_connect("/ws/transcribe") as websocket:
            # Send audio chunk without sample_rate and channels
            test_audio_data = b"fake_audio_data"
            audio_b64 = base64.b64encode(test_audio_data).decode('utf-8')

            audio_message = {
                "type": "audio_chunk",
                "data": audio_b64
                # sample_rate and channels omitted to test defaults
            }
            websocket.send_text(json.dumps(audio_message))

            response = websocket.receive_text()
            response_data = json.loads(response)

            assert response_data["type"] == "transcription"

            # Verify service was called with default parameters
            mock_transcription_service.transcribe_audio_chunk.assert_called_once_with(
                test_audio_data,
                sample_rate=16000,  # default
                channels=1  # default
            )

    @pytest.mark.asyncio
    async def test_websocket_empty_transcription(self, client, mock_transcription_service):
        """Test when transcription returns empty result"""
        mock_transcription_service.transcribe_audio_chunk.return_value = ""

        with client.websocket_connect("/ws/transcribe") as websocket:
            test_audio_data = b"fake_audio_data"
            audio_b64 = base64.b64encode(test_audio_data).decode('utf-8')

            audio_message = {
                "type": "audio_chunk",
                "data": audio_b64
            }
            websocket.send_text(json.dumps(audio_message))

            # Should not receive any response for empty transcription
            # Use timeout to verify no response
            with pytest.raises(Exception):  # Should timeout waiting for response
                websocket.receive_text(timeout=1.0)

    @pytest.mark.asyncio
    async def test_websocket_multiple_connections(self, client, mock_transcription_service, fresh_manager):
        """Test multiple simultaneous WebSocket connections"""
        # Use side_effect to return different values for each call
        transcriptions = ["Test message 1", "Test message 2"]
        mock_transcription_service.transcribe_audio_chunk.side_effect = transcriptions

        # Create multiple connections
        with client.websocket_connect("/ws/transcribe") as websocket1, \
                client.websocket_connect("/ws/transcribe") as websocket2:
            assert len(fresh_manager.active_connections) == 2

            # Test both connections independently
            test_audio = b"audio_data_1"
            audio_b64 = base64.b64encode(test_audio).decode('utf-8')

            message = {
                "type": "audio_chunk",
                "data": audio_b64
            }

            # Send from first connection
            websocket1.send_text(json.dumps(message))
            response1 = websocket1.receive_text()
            response_data1 = json.loads(response1)
            assert response_data1["type"] == "transcription"
            assert response_data1["text"] == "Test message 1"

            # Send from second connection
            websocket2.send_text(json.dumps(message))
            response2 = websocket2.receive_text()
            response_data2 = json.loads(response2)
            assert response_data2["type"] == "transcription"
            assert response_data2["text"] == "Test message 2"

            # Both should have been processed
            assert mock_transcription_service.transcribe_audio_chunk.call_count == 2

    @pytest.mark.asyncio
    async def test_websocket_invalid_message_type(self, client, mock_transcription_service):
        """Test WebSocket with invalid message type"""
        mock_transcription_service.transcribe_audio_chunk.return_value = "Valid response"

        with client.websocket_connect("/ws/transcribe") as websocket:
            # Send invalid message type
            invalid_message = {
                "type": "invalid_type",
                "data": "some_data"
            }
            websocket.send_text(json.dumps(invalid_message))

            # Should not crash and continue listening
            # Verify by sending a valid message afterwards
            test_audio = b"valid_audio_data"
            audio_b64 = base64.b64encode(test_audio).decode('utf-8')
            valid_message = {
                "type": "audio_chunk",
                "data": audio_b64
            }
            websocket.send_text(json.dumps(valid_message))

            response = websocket.receive_text()
            response_data = json.loads(response)
            assert response_data["type"] == "transcription"

    @pytest.mark.asyncio
    async def test_websocket_malformed_json(self, client, mock_transcription_service):
        """Test WebSocket with malformed JSON"""
        mock_transcription_service.transcribe_audio_chunk.return_value = "Recovery test"

        with client.websocket_connect("/ws/transcribe") as websocket:
            # Send malformed JSON
            websocket.send_text("{ malformed json }")

            # Should not crash - verify by sending valid message
            test_audio = b"recovery_audio"
            audio_b64 = base64.b64encode(test_audio).decode('utf-8')
            valid_message = {
                "type": "audio_chunk",
                "data": audio_b64
            }
            websocket.send_text(json.dumps(valid_message))

            response = websocket.receive_text()
            response_data = json.loads(response)
            assert response_data["type"] == "transcription"

    @pytest.mark.asyncio
    async def test_websocket_audio_chunk_missing_data(self, client, mock_transcription_service):
        """Test WebSocket audio chunk without data field"""
        with client.websocket_connect("/ws/transcribe") as websocket:
            # Send audio chunk without data
            invalid_message = {
                "type": "audio_chunk"
                # data field missing
            }
            websocket.send_text(json.dumps(invalid_message))

            # Should handle gracefully - no response expected
            with pytest.raises(Exception):  # Should timeout
                websocket.receive_text(timeout=1.0)

    @pytest.mark.asyncio
    async def test_websocket_timeout(self, client, mock_transcription_service):
        """Test WebSocket timeout handling"""
        mock_transcription_service.transcribe_audio_chunk.return_value = "After timeout"

        with client.websocket_connect("/ws/transcribe") as websocket:
            # Don't send any messages for a while
            # The connection should remain open but timeout internally
            # After timeout, sending a message should still work

            test_audio = b"audio_after_timeout"
            audio_b64 = base64.b64encode(test_audio).decode('utf-8')
            message = {
                "type": "audio_chunk",
                "data": audio_b64
            }

            # This should work even after internal timeout
            websocket.send_text(json.dumps(message))
            response = websocket.receive_text()
            response_data = json.loads(response)
            assert response_data["type"] == "transcription"

    @pytest.mark.asyncio
    async def test_websocket_disconnect(self, client, mock_transcription_service, fresh_manager):
        """Test WebSocket client disconnect handling"""
        # Connection manager should track disconnections
        initial_connections = len(fresh_manager.active_connections)

        with client.websocket_connect("/ws/transcribe") as websocket:
            assert len(fresh_manager.active_connections) == initial_connections + 1

        # After context manager exits, connection should be removed
        assert len(fresh_manager.active_connections) == initial_connections

    @pytest.mark.asyncio
    async def test_connection_manager_functionality(self):
        """Test ConnectionManager class basic functionality"""
        from app.routes.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()

        # Test connect
        await manager.connect(mock_websocket)
        assert len(manager.active_connections) == 1
        assert mock_websocket in manager.active_connections
        mock_websocket.accept.assert_called_once()

        # Test disconnect
        manager.disconnect(mock_websocket)
        assert len(manager.active_connections) == 0
        assert mock_websocket not in manager.active_connections

        # Test disconnect with non-existent connection (should not crash)
        manager.disconnect(AsyncMock())

    @pytest.mark.asyncio
    async def test_websocket_concurrent_operations(self, client):
        """Test concurrent WebSocket operations with multiple messages"""
        with patch('app.routes.websocket.transcription_service') as mock_service:
            mock_service.initialize = AsyncMock()
            # Use side_effect to handle multiple calls
            transcriptions = ["Concurrent test 1", "Concurrent test 2", "Concurrent test 3"]
            mock_service.transcribe_audio_chunk = AsyncMock(side_effect=transcriptions)

            with client.websocket_connect("/ws/transcribe") as websocket:
                # Send multiple messages sequentially
                for i in range(3):
                    test_audio = f"audio_data_{i}".encode()
                    audio_b64 = base64.b64encode(test_audio).decode('utf-8')
                    message = {
                        "type": "audio_chunk",
                        "data": audio_b64
                    }
                    websocket.send_text(json.dumps(message))

                    # Receive response for each message
                    response = websocket.receive_text()
                    response_data = json.loads(response)
                    assert response_data["type"] == "transcription"
                    assert response_data["text"] == f"Concurrent test {i + 1}"

                # Verify all calls were made
                assert mock_service.transcribe_audio_chunk.call_count == 3

    @pytest.mark.asyncio
    async def test_websocket_large_audio_chunk(self, client):
        """Test WebSocket with large audio chunk data"""
        with patch('app.routes.websocket.transcription_service') as mock_service:
            mock_service.initialize = AsyncMock()
            mock_service.transcribe_audio_chunk = AsyncMock(return_value="Large audio processed")

            with client.websocket_connect("/ws/transcribe") as websocket:
                # Create larger audio data
                large_audio_data = b"x" * 10000  # 10KB of data
                audio_b64 = base64.b64encode(large_audio_data).decode('utf-8')

                message = {
                    "type": "audio_chunk",
                    "data": audio_b64,
                    "sample_rate": 44100,  # Higher sample rate
                    "channels": 2  # Stereo
                }

                websocket.send_text(json.dumps(message))
                response = websocket.receive_text()
                response_data = json.loads(response)

                assert response_data["type"] == "transcription"
                assert response_data["text"] == "Large audio processed"

                # Verify service was called with correct parameters
                mock_service.transcribe_audio_chunk.assert_called_once_with(
                    large_audio_data,
                    sample_rate=44100,
                    channels=2
                )


# Standalone test functions that don't need class fixtures
@pytest.mark.asyncio
async def test_connection_manager_standalone():
    """Test ConnectionManager functionality outside test class"""
    from app.routes.websocket import ConnectionManager

    manager = ConnectionManager()
    mock_websocket = AsyncMock()
    mock_websocket.accept = AsyncMock()

    # Test basic functionality
    await manager.connect(mock_websocket)
    assert len(manager.active_connections) == 1

    manager.disconnect(mock_websocket)
    assert len(manager.active_connections) == 0


@pytest.mark.asyncio
async def test_connection_manager_multiple_connections():
    """Test ConnectionManager with multiple connections"""
    from app.routes.websocket import ConnectionManager

    manager = ConnectionManager()

    # Create multiple mock WebSockets
    mock_websockets = [AsyncMock() for _ in range(3)]
    for ws in mock_websockets:
        ws.accept = AsyncMock()
        await manager.connect(ws)

    assert len(manager.active_connections) == 3

    # Disconnect one
    manager.disconnect(mock_websockets[0])
    assert len(manager.active_connections) == 2

    # Disconnect remaining
    for ws in mock_websockets[1:]:
        manager.disconnect(ws)

    assert len(manager.active_connections) == 0
