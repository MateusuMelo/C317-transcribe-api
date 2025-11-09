from datetime import datetime
from typing import List, Dict

from fastapi import WebSocket

from app.models.schemas import WebSocketMessage
from app.services.transcription_service import transcription_service


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_data: Dict[WebSocket, Dict] = {}

    async def initialize(self):
        """Initialize necessary services"""
        await transcription_service.initialize()

    async def cleanup(self):
        """Clean up connections"""
        for connection in self.active_connections:
            await connection.close()
        self.active_connections.clear()
        self.connection_data.clear()

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_data[websocket] = {
            "client_id": client_id,
            "connected_at": datetime.now()
        }
        print(f"Client {client_id} connected")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            client_data = self.connection_data.get(websocket, {})
            client_id = client_data.get("client_id", "Unknown")
            self.active_connections.remove(websocket)
            self.connection_data.pop(websocket, None)
            print(f"Client {client_id} disconnected")

    async def send_message(self, websocket: WebSocket, message: WebSocketMessage):
        try:
            await websocket.send_json(message.dict())
        except Exception as e:
            print(f"Error sending message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: WebSocketMessage):
        disconnected = []
        for connection in self.active_connections:
            try:
                await self.send_message(connection, message)
            except:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)

    async def handle_audio_chunk(self, websocket: WebSocket, audio_data: bytes):
        """Process received audio chunk"""
        try:
            # Transcribe audio
            transcription = await transcription_service.transcribe_audio_chunk(audio_data)

            if transcription:
                # Send transcription back
                message = WebSocketMessage(
                    type="transcription",
                    data={"text": transcription},
                    timestamp=datetime.now()
                )
                await self.send_message(websocket, message)

        except Exception as e:
            error_message = WebSocketMessage(
                type="error",
                data={"error": str(e)},
                timestamp=datetime.now()
            )
            await self.send_message(websocket, error_message)


# Global connection manager instance
websocket_manager = ConnectionManager()
