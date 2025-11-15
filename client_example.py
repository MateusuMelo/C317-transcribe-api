# audio_streaming_client/main.py
import asyncio
import websockets
import json
import base64
import pyaudio
import numpy as np
from collections import deque
import time


class RealTimeAudioStreamer:
    def __init__(self, websocket_url: str = "ws://localhost:8000/ws/transcribe"):
        self.websocket_url = websocket_url
        self.websocket = None
        self.is_recording = False
        self.is_connected = False
        
        # Audio configuration for real-time streaming
        self.chunk_size = 1024
        self.sample_rate = 16000
        self.channels = 1
        self.format = pyaudio.paInt16
        
        # Buffer for 5-second chunks
        self.audio_buffer = deque()
        self.buffer_duration = 5  # seconds
        self.samples_per_chunk = self.sample_rate * self.buffer_duration
        
        self.audio = pyaudio.PyAudio()
        
    async def connect(self):
        """Connect to WebSocket server"""
        try:
            self.websocket = await websockets.connect(self.websocket_url)
            self.is_connected = True
            print("Connected to WebSocket server")
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio input - collects 5-second chunks"""
        if self.is_recording:
            self.audio_buffer.append(in_data)
            
            # Keep only last 5 seconds of audio
            max_chunks = self.samples_per_chunk // self.chunk_size
            while len(self.audio_buffer) > max_chunks:
                self.audio_buffer.popleft()
                
        return (in_data, pyaudio.paContinue)
    
    def start_recording(self):
        """Start recording audio from microphone"""
        if self.is_recording:
            print("Already recording")
            return
            
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self.audio_callback
            )
            
            self.is_recording = True
            print("Started recording... Speak now!")
            
        except Exception as e:
            print(f"Failed to start recording: {e}")
    
    def stop_recording(self):
        """Stop recording audio"""
        if self.is_recording:
            self.is_recording = False
            if hasattr(self, 'stream'):
                self.stream.stop_stream()
                self.stream.close()
            print("Stopped recording")
    
    def get_audio_chunk(self) -> bytes:
        """Get 5-second audio chunk from buffer"""
        if len(self.audio_buffer) > 0:
            return b''.join(self.audio_buffer)
        return b""
    
    async def send_audio_chunks(self):
        """Continuously send 5-second audio chunks"""
        last_send_time = 0
        chunk_interval = 5  # seconds
        
        while self.is_connected and self.is_recording:
            current_time = time.time()
            
            # Send chunk every 5 seconds
            if current_time - last_send_time >= chunk_interval:
                audio_chunk = self.get_audio_chunk()
                
                if len(audio_chunk) > 0:
                    try:
                        audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
                        
                        message = {
                            "type": "audio_chunk",
                            "data": audio_b64,
                            "is_final": False,
                            "task": "transcribe"
                        }
                        
                        await self.websocket.send(json.dumps(message))
                        print(f"Sent audio chunk: {len(audio_chunk)} bytes")
                        
                    except Exception as e:
                        print(f"Error sending audio: {e}")
                        self.is_connected = False
                
                last_send_time = current_time
            
            await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
    
    async def receive_transcriptions(self):
        """Receive transcriptions from server"""
        while self.is_connected:
            try:
                response = await self.websocket.recv()
                data = json.loads(response)
                
                if data["type"] == "transcription" and data["text"].strip():
                    print(f"\n🎯 TRANSCRIPTION: {data['text']}\n")
                    
                elif data["type"] == "error":
                    print(f"Server error: {data['message']}")
                    
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed by server")
                self.is_connected = False
                break
            except Exception as e:
                print(f"Error receiving message: {e}")
                break
    
    async def run(self, duration: int = 30):
        """Main method to run the audio streaming"""
        if not await self.connect():
            return
        
        # Start receiving transcriptions
        receive_task = asyncio.create_task(self.receive_transcriptions())
        
        # Start recording
        self.start_recording()
        
        # Start sending audio chunks
        send_task = asyncio.create_task(self.send_audio_chunks())
        
        try:
            print(f"Recording for {duration} seconds...")
            await asyncio.sleep(duration)
            
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        
        finally:
            # Cleanup
            self.stop_recording()
            send_task.cancel()
            receive_task.cancel()
            
            if self.websocket:
                await self.websocket.close()
            
            self.audio.terminate()
            print("Client stopped")


async def main():
    """Run the real-time audio streaming client"""
    streamer = RealTimeAudioStreamer()
    await streamer.run(duration=60)  # Record for 60 seconds


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
