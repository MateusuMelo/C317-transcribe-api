let mediaRecorder;
let audioChunks = [];
let ws;

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusDiv = document.getElementById('status');
const statusText = document.getElementById('statusText');
const transcriptionDiv = document.getElementById('transcription');

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            }
        });

        // Conectar WebSocket
        connectWebSocket();

        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                // Enviar chunk via WebSocket
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(event.data);
                }
            }
        };

        mediaRecorder.start(1000); // Enviar a cada 1 segundo

        startBtn.disabled = true;
        stopBtn.disabled = false;
        updateStatus('Conectado e Gravando', 'connected');

    } catch (error) {
        console.error('Erro ao acessar microfone:', error);
        updateStatus('Erro: ' + error.message, 'disconnected');
    }
}

function stopRecording() {
    if (mediaRecorder) {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    if (ws) {
        ws.close();
    }
    startBtn.disabled = false;
    stopBtn.disabled = true;
    updateStatus('Desconectado', 'disconnected');
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/realtime`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        updateStatus('Conectado', 'connected');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'transcription' && data.data.text) {
            transcriptionDiv.innerHTML += `<p>${data.data.text}</p>`;
            transcriptionDiv.scrollTop = transcriptionDiv.scrollHeight;
        } else if (data.type === 'error') {
            console.error('Erro do servidor:', data.data.error);
        }
    };

    ws.onclose = () => {
        updateStatus('Desconectado', 'disconnected');
    };

    ws.onerror = (error) => {
        console.error('Erro WebSocket:', error);
        updateStatus('Erro de conexão', 'disconnected');
    };
}

async function uploadFile() {
    const fileInput = document.getElementById('audioFile');
    const file = fileInput.files[0];

    if (!file) {
        alert('Selecione um arquivo de áudio');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/v1/transcribe/file', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        document.getElementById('fileResult').innerHTML = `
            <div style="background: #f0f0f0; padding: 15px; margin: 10px 0;">
                <strong>Texto:</strong> ${result.text}<br>
                <strong>Idioma:</strong> ${result.language}<br>
                <strong>Duração:</strong> ${result.duration.toFixed(2)}s
            </div>
        `;
    } catch (error) {
        console.error('Erro no upload:', error);
        alert('Erro ao processar arquivo');
    }
}

function updateStatus(message, className) {
    statusText.textContent = message;
    statusDiv.className = `status ${className}`;
}