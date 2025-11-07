from fastapi import FastAPI, Request, Body, WebSocket
import uvicorn
import logging
import json
import time
import base64
from typing import Any, Dict
from unison_common.logging import configure_logging, log_json
from collections import defaultdict

# Import WebSocket handler
from websocket_handler import handle_websocket_stream, get_active_sessions, get_session_count

app = FastAPI(title="unison-io-speech")

logger = configure_logging("unison-io-speech")

# Simple in-memory metrics
_metrics = defaultdict(int)
_start_time = time.time()

@app.get("/healthz")
@app.get("/health")
def health(request: Request):
    _metrics["/health"] += 1
    event_id = request.headers.get("X-Event-ID")
    log_json(logging.INFO, "health", service="unison-io-speech", event_id=event_id)
    return {"status": "ok", "service": "unison-io-speech"}

@app.get("/metrics")
def metrics():
    """Prometheus text-format metrics."""
    uptime = time.time() - _start_time
    lines = [
        "# HELP unison_io_speech_requests_total Total number of requests by endpoint",
        "# TYPE unison_io_speech_requests_total counter",
    ]
    for k, v in _metrics.items():
        lines.append(f'unison_io_speech_requests_total{{endpoint="{k}"}} {v}')
    lines.extend([
        "",
        "# HELP unison_io_speech_uptime_seconds Service uptime in seconds",
        "# TYPE unison_io_speech_uptime_seconds gauge",
        f"unison_io_speech_uptime_seconds {uptime}",
    ])
    return "\n".join(lines)

@app.get("/readyz")
@app.get("/ready")
def ready(request: Request):
    event_id = request.headers.get("X-Event-ID")
    log_json(logging.INFO, "ready", service="unison-io-speech", event_id=event_id, ready=True)
    return {"ready": True}

@app.post("/speech/stt")
def speech_to_text(request: Request, body: Dict[str, Any] = Body(...)):
    """
    Speech-to-Text stub.
    Accepts base64 audio data or a placeholder and returns a transcript.
    """
    _metrics["/speech/stt"] += 1
    event_id = request.headers.get("X-Event-ID")
    audio_b64 = body.get("audio")
    if not isinstance(audio_b64, str):
        return {"ok": False, "error": "missing or invalid 'audio' field (base64 string)", "event_id": event_id}
    # MVP: ignore audio, return a placeholder transcript
    transcript = "This is a placeholder transcript from speech-to-text."
    log_json(logging.INFO, "stt", service="unison-io-speech", event_id=event_id, transcript_len=len(transcript))
    return {"ok": True, "transcript": transcript, "event_id": event_id}

@app.post("/speech/tts")
def text_to_speech(request: Request, body: Dict[str, Any] = Body(...)):
    """
    Text-to-Speech stub.
    Accepts text and returns a placeholder audio URL or base64 stub.
    """
    _metrics["/speech/tts"] += 1
    event_id = request.headers.get("X-Event-ID")
    text = body.get("text")
    if not isinstance(text, str) or not text:
        return {"ok": False, "error": "missing or invalid 'text' field", "event_id": event_id}
    # MVP: return a placeholder base64-encoded WAV (tiny silence)
    silence_wav = "UklGRigAAABXQVZFZm10IBAAAAAAQAEAAEAfAAAQAQABAAgAZGF0YQQAAAA="
    audio_url = f"data:audio/wav;base64,{silence_wav}"
    log_json(logging.INFO, "tts", service="unison-io-speech", event_id=event_id, text_len=len(text))
    return {"ok": True, "audio_url": audio_url, "event_id": event_id}

@app.websocket("/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time audio streaming.
    
    Supports:
    - Bidirectional audio streaming
    - Voice Activity Detection (VAD)
    - Streaming transcription
    - Barge-in support
    """
    _metrics["/stream"] += 1
    await handle_websocket_stream(websocket)

@app.get("/sessions")
def get_sessions(request: Request):
    """Get information about active WebSocket sessions"""
    _metrics["/sessions"] += 1
    event_id = request.headers.get("X-Event-ID")
    sessions = get_active_sessions()
    log_json(logging.INFO, "sessions", service="unison-io-speech", event_id=event_id, count=len(sessions))
    return {
        "ok": True,
        "count": get_session_count(),
        "sessions": sessions,
        "event_id": event_id
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8084)
