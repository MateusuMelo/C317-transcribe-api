FROM python:3.12-slim

# Install system dependencies including build tools for pyaudio
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    gcc \
    g++ \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy project metadata
COPY pyproject.toml .

# Install Python dependencies
RUN pip install .

# Copy application code
COPY . .

# Create directory for models
RUN mkdir -p /app/models

# ----------------------------------------
# 👉 Baixar Whisper BASE durante o build
# ----------------------------------------
ENV WHISPER_MODEL_SIZE="base"
ENV MODEL_CACHE_DIR="/app/models"

RUN python3 - <<EOF
from faster_whisper import WhisperModel
import os

model_size = os.getenv("WHISPER_MODEL_SIZE")
cache_dir  = os.getenv("MODEL_CACHE_DIR")

print(f"📥 Baixando Whisper '{model_size}' em '{cache_dir}'...")
WhisperModel(model_size, download_root=cache_dir)
print("✅ Modelo Whisper baixado com sucesso!")
EOF

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
