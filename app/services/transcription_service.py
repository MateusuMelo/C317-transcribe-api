import asyncio
import io
import os
import tempfile
from datetime import datetime
from typing import AsyncGenerator, Optional
import numpy as np
import wave

from faster_whisper import WhisperModel
from pydub import AudioSegment
from pydub.generators import Sine

from app.core.config import settings
from app.models.schemas import TranscriptionResponse
from app.utils.audio_converters import AudioConverter


class TranscriptionService:
    def __init__(self):
        self.model: Optional[WhisperModel] = None
        self.audio_converter = AudioConverter()
        self._initialized = False

    async def initialize(self):
        """Initialize Whisper model"""
        if self._initialized and self.model is not None:
            return

        try:
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: WhisperModel(
                    settings.WHISPER_MODEL_SIZE,
                    device=settings.WHISPER_DEVICE,
                    compute_type=settings.WHISPER_COMPUTE_TYPE,
                    download_root=settings.MODEL_CACHE_DIR
                )
            )
            self._initialized = True
            print(f"Whisper model '{settings.WHISPER_MODEL_SIZE}' loaded successfully!")
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
            raise

    async def transcribe_audio_file(
            self,
            audio_data: bytes,
            file_extension: str = "wav",
            task: str = "translate",
            language: Optional[str] = None
    ) -> TranscriptionResponse:
        """Transcribe complete audio file"""
        await self.initialize()

        # Ensure model is properly initialized
        if self.model is None:
            raise Exception("Whisper model not initialized")

        with tempfile.NamedTemporaryFile(
                suffix=f".{file_extension}",
                delete=False,
                dir=settings.TEMP_UPLOAD_DIR
        ) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name

        converted_path = None
        try:
            # Convert audio if necessary
            converted_path = await self.audio_converter.ensure_compatible_audio(temp_path)

            # Execute transcription in thread pool
            loop = asyncio.get_event_loop()
            segments, info = await loop.run_in_executor(
                None,
                lambda: self.model.transcribe(
                    converted_path,
                    task=task,
                    language=language,
                    beam_size=5,
                    best_of=5,
                    vad_filter=True
                )
            )

            # Combine all segments into full text
            full_text = " ".join(segment.text for segment in segments)

            return TranscriptionResponse(
                text=full_text.strip(),
                language=info.language,
                confidence=getattr(info, 'language_probability', None),
                duration=sum(segment.duration for segment in segments),
                processed_at=datetime.now()
            )

        except Exception as e:
            print(f"Error in transcribe_audio_file: {e}")
            raise Exception(f"Transcription error: {str(e)}")

        finally:
            # Cleanup temporary files
            try:
                if converted_path and os.path.exists(converted_path) and converted_path != temp_path:
                    os.unlink(converted_path)
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                print(f"Warning: Error cleaning up temp files: {e}")

    def _raw_audio_to_wav_bytes(self, raw_audio: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
        """Convert raw PCM audio to WAV format bytes"""
        try:
            # Create WAV file in memory
            wav_io = io.BytesIO()

            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(raw_audio)

            return wav_io.getvalue()

        except Exception as e:
            print(f"Error converting raw audio to WAV: {e}")
            # Fallback: create synthetic audio for testing
            return self._create_synthetic_audio()

    def _create_synthetic_audio(self, duration_ms: int = 5000) -> bytes:
        """Create synthetic audio for testing when real audio fails"""
        try:
            # Generate a simple sine wave
            tone = Sine(440).to_audio_segment(duration=duration_ms)
            tone = tone.set_frame_rate(16000).set_channels(1)

            wav_io = io.BytesIO()
            tone.export(wav_io, format="wav")
            return wav_io.getvalue()
        except:
            # Ultimate fallback
            return b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00"

    async def transcribe_audio_chunk(
            self,
            audio_chunk: bytes,
            task: str = "transcribe",
            language: Optional[str] = 'pt',
            sample_rate: int = 16000,
            channels: int = 1
    ) -> str:
        """Transcribe a single audio chunk in real-time"""
        await self.initialize()

        # Ensure model is properly initialized
        if self.model is None:
            print("❌ Whisper model not initialized")
            return ""

        try:
            # Check if it's raw PCM data or formatted audio
            is_raw_audio = True

            # Try to detect common audio formats
            if audio_chunk.startswith(b'RIFF') or audio_chunk.startswith(b'OggS') or audio_chunk.startswith(b'ID3'):
                is_raw_audio = False

            if is_raw_audio:
                print(f"Processing raw PCM audio: {len(audio_chunk)} bytes")
                # Convert raw PCM to WAV
                wav_data = self._raw_audio_to_wav_bytes(audio_chunk, sample_rate, channels)
            else:
                print(f"Processing formatted audio: {len(audio_chunk)} bytes")
                # It's already in a format that can be processed
                wav_data = audio_chunk

            if not wav_data or len(wav_data) < 100:  # Too small to process
                return ""

            # Use temporary file for transcription
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(wav_data)
                temp_path = temp_file.name

            try:
                # Optimized for real-time transcription
                loop = asyncio.get_event_loop()
                segments, info = await loop.run_in_executor(
                    None,
                    lambda: self.model.transcribe(
                        temp_path,
                        task=task,
                        language=language,
                        beam_size=2,
                        best_of=2,
                        vad_filter=True,
                        vad_parameters=dict(
                            threshold=0.3,  # Lower threshold for better detection
                            min_speech_duration_ms=500,
                            max_speech_duration_s=10,
                            min_silence_duration_ms=400
                        ),
                        without_timestamps=True,
                        no_speech_threshold=0.5  # Lower threshold to detect more speech
                    )
                )

                transcription = " ".join(segment.text for segment in segments).strip()

                if transcription:
                    print(f"🎯 Transcription: {transcription}")
                else:
                    print("🔇 No speech detected")

                return transcription

            finally:
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass

        except Exception as e:
            print(f"❌ Error transcribing audio chunk: {e}")
            return ""

    async def process_realtime_stream(
            self,
            audio_chunks: AsyncGenerator[bytes, None],
            chunk_duration: int = 5000,
            language: Optional[str] = None,
            task: str = "transcribe",
            sample_rate: int = 16000,
            channels: int = 1
    ) -> AsyncGenerator[str, None]:
        """Process real-time audio stream in chunks"""
        await self.initialize()

        buffer = b""
        chunk_counter = 0

        async for chunk in audio_chunks:
            if not chunk:
                continue

            buffer += chunk

            # Calculate approximate duration of buffer
            buffer_duration = (len(buffer) / (sample_rate * 2)) * 1000  # ms

            # Process if we have enough audio (approximately 5 seconds)
            if buffer_duration >= chunk_duration:
                print(f"🔄 Processing chunk {chunk_counter} ({len(buffer)} bytes, ~{buffer_duration:.0f}ms)")

                transcription = await self.transcribe_audio_chunk(
                    buffer, task, language, sample_rate, channels
                )

                if transcription and transcription.strip():
                    yield transcription
                    chunk_counter += 1

                # Reset buffer
                buffer = b""

        # Process any remaining audio
        if buffer:
            final_duration = (len(buffer) / (sample_rate * 2)) * 1000
            if final_duration >= 1000:  # At least 1 second
                print(f"🔄 Processing final chunk ({len(buffer)} bytes, ~{final_duration:.0f}ms)")
                transcription = await self.transcribe_audio_chunk(buffer, task, language, sample_rate, channels)
                if transcription and transcription.strip():
                    yield transcription

    async def _process_audio_chunk(
            self,
            audio_segment: AudioSegment,
            language: Optional[str],
            task: str,
            segment_id: int
    ) -> str:
        """Process an individual audio chunk (legacy method)"""
        try:
            # Convert to WAV in memory
            wav_io = io.BytesIO()
            audio_segment.export(wav_io, format="wav")
            wav_data = wav_io.getvalue()

            return await self.transcribe_audio_chunk(wav_data, task, language)

        except Exception as e:
            print(f"Error processing chunk {segment_id}: {e}")
            return ""


# Global service instance
transcription_service = TranscriptionService()