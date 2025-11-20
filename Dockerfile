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

# Copy requirements first for better caching
COPY pyproject.toml .

# Install Python dependencies
RUN pip install  .

# Copy application code
COPY . .

# Create directory for models
RUN mkdir -p /app/models

# Copy pre-downloaded Whisper model
COPY data/models /app/models

# Set environment variable to use local model
ENV MODEL_CACHE_DIR=/app/models
ENV WHISPER_MODEL_CACHE=/app/models

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]