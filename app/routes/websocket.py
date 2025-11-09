# app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import base64
import asyncio
from app.services.transcription_service import transcription_service

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"Client disconnected. Total: {len(self.active_connections)}")


manager = ConnectionManager()


@router.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        await transcription_service.initialize()
        print("Model ready for real-time transcription")

        async def audio_chunk_generator():
            """Generator for audio chunks"""
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                    message = json.loads(data)

                    if message["type"] == "audio_chunk":
                        audio_data = base64.b64decode(message["data"])

                        # Get audio parameters with defaults
                        sample_rate = message.get("sample_rate", 16000)
                        channels = message.get("channels", 1)

                        yield audio_data, sample_rate, channels

                except asyncio.TimeoutError:
                    print("No audio data received for 60 seconds")
                    break
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    print(f"Error receiving audio: {e}")
                    continue

        # Process audio stream in real-time
        async for audio_data, sample_rate, channels in audio_chunk_generator():
            transcription = await transcription_service.transcribe_audio_chunk(
                audio_data,
                sample_rate=sample_rate,
                channels=channels
            )

            if transcription:
                response = {
                    "type": "transcription",
                    "text": transcription,
                    "timestamp": asyncio.get_event_loop().time()
                }
                await websocket.send_text(json.dumps(response))
                print(f"📤 Sent transcription: {transcription}")

    except WebSocketDisconnect:
        print("Client disconnected")
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)