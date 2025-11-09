# tests/test_websocket_client.py
import asyncio
import websockets
import json
import base64
import os


class AudioWebSocketClient:
    def __init__(self):
        self.websocket = None
        self.receive_task = None

    async def connect(self, uri="ws://localhost:8000/ws/transcribe"):
        """Connect to WebSocket"""
        self.websocket = await websockets.connect(uri)
        print("Connected to WebSocket server")

    async def send_audio_from_file(self, audio_file_path):
        """Send audio from .ogg or .wav file"""
        try:
            # Check if file exists
            if not os.path.exists(audio_file_path):
                print(f"File {audio_file_path} not found!")
                return

            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()

            print(f"File read: {len(audio_data)} bytes")

            # Encode to base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')

            # Send to server
            message = {
                "type": "audio_chunk",
                "data": audio_b64,
                "is_final": True,
                "task": "transcribe"
            }

            print("Sending audio for transcription...")
            await self.websocket.send(json.dumps(message))

            # Wait for response directly
            print("Waiting for response...")
            response = await self.websocket.recv()
            data = json.loads(response)

            if data["type"] == "transcription":
                print(f"Transcription: {data['text']}")
            elif data["type"] == "error":
                print(f"Server error: {data['message']}")
            else:
                print(f"Unexpected response: {data}")

        except Exception as e:
            print(f"Error: {e}")

    async def close(self):
        """Close connection"""
        if self.websocket:
            await self.websocket.close()
            print("Connection closed")


async def test_simple():
    """Simple test with audio file"""
    client = AudioWebSocketClient()

    try:
        await client.connect()

        # Send audio file
        audio_file = "tests/data/teste.ogg"  # Put your .ogg file here


        await client.send_audio_from_file(audio_file)

    except Exception as e:
        print(f"Test error: {e}")
    finally:
        await client.close()


async def test_multiple_messages():
    """Test sending multiple messages"""
    client = AudioWebSocketClient()

    try:
        await client.connect()

        # First: test ping
        print("Testing ping...")
        await client.websocket.send(json.dumps({"type": "ping"}))
        response = await client.websocket.recv()
        print(f"Ping response: {response}")

        # Second: send audio
        audio_file = "tests/data/teste.ogg"
        await client.send_audio_from_file(audio_file)

    except Exception as e:
        print(f"Multiple test error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    print("Simple Test - One audio at a time")
    print("=" * 50)
    asyncio.run(test_simple())

    print("\n" + "=" * 50)
    print("Multiple Test - Ping + Audio")
    print("=" * 50)
    asyncio.run(test_multiple_messages())