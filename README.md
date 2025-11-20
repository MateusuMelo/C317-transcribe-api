[![Tests](https://github.com/MateusuMelo/C317-transcribe-api/actions/workflows/ci.yml/badge.svg)](https://github.com/MateusuMelo/C317-transcribe-api/actions/workflows/ci.yml)
![Python Version](https://img.shields.io/badge/python-3.12-blue)

# 🎙️ Audio Transcription API

Uma API completa para transcrição de áudio em tempo real usando Whisper, com cliente interativo para testes.

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Funcionalidades](#-funcionalidades)
- [Tecnologias](#-tecnologias)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [API Endpoints](#-api-endpoints)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Docker](#-docker)
- [Testes](#-testes)
---

## 🎯 Visão Geral

Esta API fornece serviços de transcrição de áudio em tempo real usando o modelo Whisper da OpenAI. Suporta tanto upload de arquivos de áudio quanto streaming em tempo real via WebSocket.

## ✨ Funcionalidades

- **🎙️ Transcrição em Tempo Real**: Streaming de áudio via WebSocket
- **📁 Upload de Arquivos**: Suporte a múltiplos formatos de áudio (WAV, MP3, OGG, M4A, FLAC, AAC)
- **🌐 Suporte a Múltiplos Idiomas**: Detecção automática de idioma
- **⚡ Alta Performance**: Usa faster-whisper para otimização
- **🐳 Containerizada**: Pronta para Docker e Docker Compose
- **🎮 Cliente Interativo**: Jogo de transcrição para testes
- **🔍 Health Checks**: Monitoramento da saúde da API

## 🛠 Tecnologias

- **FastAPI** - Framework web moderno
- **Faster-Whisper** - Modelo de transcrição otimizado
- **WebSocket** - Comunicação em tempo real
- **PyAudio** - Captura de áudio do microfone
- **Docker** - Containerização
- **Pydub** - Processamento de áudio
- **UV** - Gerenciador de pacotes Python

## 📦 Instalação

### Pré-requisitos

- Python 3.11+
- Docker e Docker Compose (opcional)
- FFmpeg

### Instalação Local

```bash
git clone <repository-url>
cd audio-transcription-api
uv sync
```

#### Instale o FFmpeg

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Baixe do site oficial: https://ffmpeg.org/download.html
```
#### Instale o PyAudio (para o cliente)
```bash
sudo apt-get install portaudio19-dev
uv add pyaudio
#or pip
pip install pyaudio
```
---

## 🚀 Uso

### Iniciar a API

```bash
# Modo desenvolvimento
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Ou usando Docker
docker-compose up --build
```

A API estará disponível em: [http://localhost:8000](http://localhost:8000)




---

## 🔌 Exemplo de Cliente Simples (Python)

Este é o cliente mais básico possível, sem classes, apenas o essencial para integração:

```python
import asyncio
import websockets
import pyaudio
import base64
import json

WS_URL = "ws://localhost:8000/ws/transcribe"

CHUNK = 1024
RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16

async def main():
    async with websockets.connect(WS_URL) as ws:
        print("Conectado ao servidor WebSocket.")

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )

        async def send_audio():
            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_b64 = base64.b64encode(data).decode("utf-8")

                message = {
                    "type": "audio_chunk",
                    "data": audio_b64,
                    "is_final": False,
                    "task": "transcribe"
                }

                await ws.send(json.dumps(message))

        async def receive_text():
            while True:
                response = await ws.recv()
                data = json.loads(response)

                if data.get("type") == "transcription":
                    print("Transcrição:", data["text"])

        await asyncio.gather(send_audio(), receive_text())

if __name__ == "__main__":
    asyncio.run(main())
```


---
## 📡 API Endpoints

### Health Check

```http
GET /health
```

```json
{
  "status": "healthy",
  "service": "audio-translation-api",
  "model_loaded": true
}
```

### Transcrição de Arquivo

```http
POST /api/v1/transcribe/file
```

**Body:** FormData com arquivo de áudio

**Parâmetros:**
- `task` – "transcribe" ou "translate"
- `language` – código do idioma (opcional)

**Exemplo de resposta:**
```json
{
  "text": "Esta é uma transcrição de exemplo",
  "language": "pt",
  "confidence": 0.95,
  "duration": 3.2
}
```

### WebSocket em Tempo Real

```http
WS /ws/transcribe
```

**Mensagens enviadas:**
```json
{
  "type": "audio_chunk",
  "data": "base64_audio_data",
  "sample_rate": 16000,
  "channels": 1
}
```

**Mensagens recebidas:**
```json
{
  "type": "transcription",
  "text": "transcrição do áudio",
  "timestamp": 1234567890.123
}
```

---

## 📁 Estrutura do Projeto

```
audio-transcription-api/
├── app/
│   ├── core/config.py
│   ├── models/schemas.py
│   ├── routes/
│   │   ├── transcription.py
│   │   └── websocket.py
│   ├── services/
│   │   ├── transcription_service.py
│   │   └── websocket_manager.py
│   ├── utils/
│   │   ├── audio_converters.py
│   │   └── file_handlers.py
│   ├── static/
│   │   ├── index.html
│   │   └── js/recorder.js
│   └── main.py
├── tests/
│   ├── client_test.py
│   ├── test_api.py
│   └── conftest.py
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 🐳 Docker

```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
docker-compose down -v
```

### Variáveis de Ambiente

```env
API_HOST=0.0.0.0
API_PORT=8000
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_AUDIO_SIZE_MB=25
MODEL_CACHE_DIR=/app/models
TEMP_UPLOAD_DIR=/tmp
```

---

## 🧪 Testes

```bash
pytest tests/
pytest --cov=app tests/
pytest tests/test_api.py -v
```

---
