import os
from pathlib import Path

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

    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    TEMP_UPLOAD_DIR: str = os.getenv("TEMP_UPLOAD_DIR", str(BASE_DIR / "tmp"))
    MODEL_CACHE_DIR: str = os.getenv("MODEL_CACHE_DIR", str(BASE_DIR / "models"))
    LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "app.log"))

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

os.makedirs(settings.TEMP_UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.MODEL_CACHE_DIR, exist_ok=True)
os.makedirs(Path(settings.LOG_FILE).parent, exist_ok=True)
