# app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import base64
import asyncio
import logging
from app.services.transcription_service import transcription_service

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total: {len(self.active_connections)}")
        else:
            logger.warning("Attempted to disconnect WebSocket that wasn't in active connections")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)


manager = ConnectionManager()


@router.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        await transcription_service.initialize()
        logger.info("Model ready for real-time transcription")

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
                    logger.warning("No audio data received for 60 seconds")
                    break
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected during audio reception")
                    break
                except Exception as e:
                    logger.error(f"Error receiving audio: {e}")
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
                await manager.send_personal_message(json.dumps(response), websocket)
                logger.debug(f"📤 Sent transcription: {transcription}")

    except WebSocketDisconnect:
        logger.info("Client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Always ensure connection is cleaned up
        manager.disconnect(websocket)