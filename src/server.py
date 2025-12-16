from fastapi import FastAPI, Request, Body, WebSocket
import uvicorn
import logging
import json
import os
import time
from typing import Any, Dict
from unison_common.logging import configure_logging, log_json
from unison_common.tracing_middleware import TracingMiddleware
from unison_common.tracing import initialize_tracing, instrument_fastapi, instrument_httpx
try:
    from unison_common import BatonMiddleware
except Exception:
    BatonMiddleware = None
from collections import defaultdict

# Import WebSocket handler
from .websocket_handler import handle_websocket_stream, get_active_sessions, get_session_count
from .engines import get_asr_engine, get_tts_engine

app = FastAPI(title="unison-io-speech")
app.add_middleware(TracingMiddleware, service_name="unison-io-speech")
if BatonMiddleware:
    app.add_middleware(BatonMiddleware)

logger = configure_logging("unison-io-speech")
_ENGINE_MODE = os.getenv("UNISON_SPEECH_ENGINE_MODE", "local").strip().lower()

# P0.3: Initialize tracing and instrument FastAPI/httpx
initialize_tracing()
instrument_fastapi(app)
instrument_httpx()

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
    ready_ok = True
    detail = "ok"
    if os.getenv("UNISON_SPEECH_READY_CHECK", "true").lower() in {"1", "true", "yes", "on"}:
        try:
            # Force model resolution (without loading weights) for a product-grade failure mode.
            _ = get_asr_engine()
            _ = get_tts_engine()
        except Exception as exc:
            ready_ok = False
            detail = str(exc)
    log_json(logging.INFO, "ready", service="unison-io-speech", event_id=event_id, ready=ready_ok, detail=detail)
    return {"ready": ready_ok, "detail": detail}

@app.post("/speech/stt")
def speech_to_text(request: Request, body: Dict[str, Any] = Body(...)):
    """
    Speech-to-Text stub.
    Accepts base64 audio data or a placeholder and returns a transcript.
    """
    _metrics["/speech/stt"] += 1
    event_id = request.headers.get("X-Event-ID")
    baton = request.headers.get("X-Context-Baton")
    audio_b64 = body.get("audio")
    person_id = body.get("person_id")
    session_id = body.get("session_id")
    if not isinstance(audio_b64, str):
        return {"ok": False, "error": "missing or invalid 'audio' field (base64 string)", "event_id": event_id}
    profile = body.get("profile") or os.getenv("UNISON_SPEECH_DEFAULT_ASR_PROFILE", "fast")
    if profile not in {"fast", "accurate"}:
        profile = "fast"
    if _ENGINE_MODE == "stub":
        transcript, confidence = "stub transcript", 0.5
    else:
        try:
            engine = get_asr_engine()
            transcript, confidence = engine.transcribe_audio_b64(audio_b64=audio_b64, profile=profile)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "event_id": event_id}
    log_json(
        logging.INFO,
        "stt",
        service="unison-io-speech",
        event_id=event_id,
        transcript_len=len(transcript),
        person_id=person_id,
        session_id=session_id,
    )
    return {
        "ok": True,
        "transcript": transcript,
        "confidence": confidence,
        "engine": "faster-whisper",
        "profile": profile,
        "event_id": event_id,
        "person_id": person_id,
        "session_id": session_id,
        "baton": baton,
        "received_at": time.time(),
    }

@app.post("/speech/tts")
def text_to_speech(request: Request, body: Dict[str, Any] = Body(...)):
    """
    Text-to-Speech stub.
    Accepts text and returns a placeholder audio URL or base64 stub.
    """
    _metrics["/speech/tts"] += 1
    event_id = request.headers.get("X-Event-ID")
    baton = request.headers.get("X-Context-Baton")
    text = body.get("text")
    person_id = body.get("person_id")
    session_id = body.get("session_id")
    if not isinstance(text, str) or not text:
        return {"ok": False, "error": "missing or invalid 'text' field", "event_id": event_id}
    profile = body.get("profile") or os.getenv("UNISON_SPEECH_DEFAULT_TTS_PROFILE", "lightweight")
    if profile not in {"lightweight", "natural"}:
        profile = "lightweight"
    if _ENGINE_MODE == "stub":
        silence_wav = "UklGRigAAABXQVZFZm10IBAAAAAAQAEAAEAfAAAQAQABAAgAZGF0YQQAAAA="
        audio_url = f"data:audio/wav;base64,{silence_wav}"
    else:
        try:
            tts = get_tts_engine()
            audio_url = tts.synthesize_data_url(text=text, profile=profile)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "event_id": event_id}
    log_json(
        logging.INFO,
        "tts",
        service="unison-io-speech",
        event_id=event_id,
        text_len=len(text),
        person_id=person_id,
        session_id=session_id,
    )
    return {
        "ok": True,
        "audio_url": audio_url,
        "engine": "piper",
        "profile": profile,
        "event_id": event_id,
        "person_id": person_id,
        "session_id": session_id,
        "baton": baton,
        "received_at": time.time(),
    }

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
