import asyncio
import os
import subprocess
import tempfile


class AudioConverter:
    @staticmethod
    async def convert_to_wav(audio_data: bytes, input_format: str) -> bytes:
        """Convert audio to WAV format compatible with Whisper"""
        # Create temporary input file
        with tempfile.NamedTemporaryFile(suffix=f".{input_format}", delete=False) as input_file:
            input_file.write(audio_data)
            input_path = input_file.name

        # Temporary output file
        output_path = input_path + ".wav"

        try:
            # Convert using ffmpeg
            cmd = [
                "ffmpeg", "-i", input_path,
                "-ac", "1",  # mono
                "-ar", "16000",  # 16kHz
                "-acodec", "pcm_s16le",  # 16-bit PCM
                "-y",  # overwrite file
                output_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            await process.communicate()

            # Read converted file
            with open(output_path, "rb") as f:
                converted_data = f.read()

            return converted_data

        finally:
            # Clean up temporary files
            for path in [input_path, output_path]:
                if os.path.exists(path):
                    os.unlink(path)

    @staticmethod
    async def ensure_compatible_audio(file_path: str) -> str:
        """Ensure audio is in compatible format"""
        # Check if already WAV with correct specs
        if file_path.endswith('.wav'):
            return file_path

        # Convert if necessary
        output_path = file_path + ".converted.wav"

        cmd = [
            "ffmpeg", "-i", file_path,
            "-ac", "1",
            "-ar", "16000",
            "-acodec", "pcm_s16le",
            "-y",
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        await process.communicate()
        return output_path

    @staticmethod
    async def convert_audio_chunk(audio_chunk: bytes) -> bytes:
        """Convert audio chunk to appropriate format"""
        # Implementation for real-time audio chunks
        # Here you can add specific processing for chunks
        return audio_chunk
