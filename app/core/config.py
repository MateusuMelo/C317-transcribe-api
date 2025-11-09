import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1
    API_RELOAD: bool = True

    # Whisper
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # Audio
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHUNK_SIZE: int = 1024
    MAX_AUDIO_SIZE_MB: int = 50

    # Paths
    TEMP_UPLOAD_DIR: str = "/tmp"
    MODEL_CACHE_DIR: str = "/app/models"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

os.makedirs(settings.TEMP_UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.MODEL_CACHE_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)
