import os

import aiofiles
from fastapi import UploadFile


class FileHandler:
    @staticmethod
    async def save_upload_file(upload_file: UploadFile, destination: str) -> str:
        """Save uploaded file"""
        file_path = os.path.join(destination, upload_file.filename)

        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await upload_file.read()
            await out_file.write(content)

        return file_path

    @staticmethod
    async def read_file_chunks(file_path: str, chunk_size: int = 8192):
        """Read file in chunks"""
        async with aiofiles.open(file_path, 'rb') as file:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Extract file extension"""
        return filename.split('.')[-1].lower() if '.' in filename else ''

    @staticmethod
    def is_audio_file(filename: str) -> bool:
        """Check if file is an audio file"""
        audio_extensions = {'wav', 'mp3', 'm4a', 'ogg', 'flac', 'aac'}
        extension = FileHandler.get_file_extension(filename)
        return extension in audio_extensions
