"""
WebSocket Handler for io-speech streaming

Handles bidirectional audio streaming, VAD events, and barge-in support.
"""

import asyncio
import base64
import json
import logging
import os
import time
from typing import Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import uuid

import httpx

from .message_schema import (
    parse_client_message,
    create_transcript_message,
    create_vad_event,
    create_barge_in_message,
    create_error_message,
    create_status_message,
    AudioInputMessage,
    ControlMessage,
)
from .vad import VoiceActivityDetector, VADConfig

logger = logging.getLogger(__name__)

_ORCH_HOST = os.getenv("UNISON_ORCH_HOST", "orchestrator")
_ORCH_PORT = os.getenv("UNISON_ORCH_PORT", "8080")
_ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", f"http://{_ORCH_HOST}:{_ORCH_PORT}")
_ORCHESTRATOR_INPUT_PATH = os.getenv("UNISON_ORCHESTRATOR_INPUT_PATH", "/input")

_RENDERER_URL = os.getenv("EXPERIENCE_RENDERER_URL", os.getenv("UNISON_RENDERER_URL", "http://experience-renderer:8082"))

_FORWARD_FINAL = os.getenv("UNISON_SPEECH_FORWARD_FINAL_TO_ORCHESTRATOR", "true").lower() in {"1", "true", "yes", "on"}
_STREAM_PARTIAL = os.getenv("UNISON_SPEECH_STREAM_PARTIAL_TO_RENDERER", "true").lower() in {"1", "true", "yes", "on"}


def _extract_trace_id(headers: Any) -> str:
    try:
        x_trace = headers.get("x-trace-id") or headers.get("X-Trace-Id")
        if isinstance(x_trace, str) and x_trace.strip():
            return x_trace.strip()
        x_req = headers.get("x-request-id") or headers.get("X-Request-Id")
        if isinstance(x_req, str) and x_req.strip():
            return x_req.strip()
        tp = headers.get("traceparent") or headers.get("Traceparent")
        if isinstance(tp, str):
            parts = tp.split("-")
            if len(parts) >= 3 and parts[1]:
                return parts[1]
    except Exception:
        pass
    return uuid.uuid4().hex


def _format_traceparent(trace_id_hex: str, span_id_hex16: str = "0000000000000001") -> str:
    trace_id = (trace_id_hex or uuid.uuid4().hex).replace("-", "")[:32].ljust(32, "0")
    span_id = (span_id_hex16 or uuid.uuid4().hex[:16])[:16].ljust(16, "0")
    return f"00-{trace_id}-{span_id}-01"


def _service_auth_header() -> dict[str, str]:
    try:
        from jose import jwt

        secret = os.getenv("UNISON_SERVICE_SECRET", "default-service-secret")
        now = int(time.time())
        payload = {
            "sub": "service-io-speech",
            "type": "service",
            "roles": ["service"],
            "iat": now,
            "exp": now + 3600,
            "jti": f"io_speech_{now}",
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}
    except Exception:
        return {}


class StreamingSession:
    """
    Manages a single WebSocket streaming session
    
    Handles audio input, VAD, transcription, and barge-in.
    """
    
    def __init__(
        self,
        session_id: str,
        websocket: Optional[WebSocket] = None,
        *,
        trace_id: Optional[str] = None,
        person_id: Optional[str] = None,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.trace_id = trace_id or uuid.uuid4().hex
        self.person_id = person_id
        self.vad = VoiceActivityDetector(VADConfig())
        self.is_active = True
        self.is_listening = False
        self.is_speaking = False  # TTS playback state
        self.audio_buffer: bytes = b""
        self.transcript_buffer: str = ""
        self.sequence_counter = 0
        self.tts_sequence: Optional[int] = None
        self.start_time = datetime.now()
        
        logger.info(f"Session {session_id} created")
    
    async def send_message(self, message: dict):
        """Send message to client"""
        if not self.websocket:
            return
        # Provide correlation fields for clients; safe for older clients to ignore.
        message.setdefault("trace_id", self.trace_id)
        message.setdefault("session_id", self.session_id)
        if self.person_id:
            message.setdefault("person_id", self.person_id)
        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error sending message: {e}")
            raise

    def add_audio(self, data: bytes):
        """Test helper: append audio bytes to buffer."""
        self.audio_buffer += data

    def clear_buffer(self):
        """Test helper: clear audio buffer."""
        self.audio_buffer = b""

    def deactivate(self):
        """Mark session inactive."""
        self.is_active = False
    
    async def handle_audio_input(self, message: AudioInputMessage):
        """
        Handle incoming audio data from client
        
        Processes audio through VAD and generates transcripts.
        """
        try:
            # Decode audio data
            audio_bytes = base64.b64decode(message.data)
            
            # Add to buffer
            self.audio_buffer += audio_bytes
            
            # Process through VAD
            vad_events = self.vad.process_chunk(audio_bytes, format="pcm16")
            
            # Send VAD events
            for event in vad_events:
                vad_msg = create_vad_event(event, energy=self.vad.get_average_energy())
                await self.send_message(vad_msg.dict())
                
                if event == "speech_start":
                    self.is_listening = True
                    # Check for barge-in
                    if self.is_speaking and self.tts_sequence is not None:
                        await self.handle_barge_in()
                    
                    # Send status update
                    status_msg = create_status_message("listening")
                    await self.send_message(status_msg.dict())
                
                elif event == "speech_end":
                    self.is_listening = False
                    # Generate final transcript
                    await self.generate_final_transcript()
                    
                    # Send status update
                    status_msg = create_status_message("processing")
                    await self.send_message(status_msg.dict())
            
            # Generate partial transcripts during speech
            if self.vad.is_speaking() and len(self.audio_buffer) > 16000:  # ~1 second
                await self.generate_partial_transcript()
        
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error handling audio: {e}")
            error_msg = create_error_message(
                "audio_processing_error",
                f"Failed to process audio: {str(e)}"
            )
            await self.send_message(error_msg.dict())
    
    async def generate_partial_transcript(self):
        """Generate and send partial transcript"""
        # Stub implementation - returns placeholder text
        # In production, this would call a streaming STT service
        
        transcript_text = f"Partial transcript... (buffer size: {len(self.audio_buffer)} bytes)"
        
        transcript_msg = create_transcript_message(
            text=transcript_text,
            is_final=False,
            confidence=0.75
        )
        
        await self.send_message(transcript_msg.dict())
        logger.debug(f"Session {self.session_id}: Sent partial transcript")
        if _STREAM_PARTIAL:
            await self._emit_partial_to_renderer(transcript_text)
    
    async def generate_final_transcript(self):
        """Generate and send final transcript"""
        # Stub implementation - returns placeholder text
        # In production, this would call a final STT service
        
        if len(self.audio_buffer) == 0:
            return
        
        # Simulate transcription based on audio length
        duration_sec = len(self.audio_buffer) / (16000 * 2)  # 16kHz, 16-bit
        transcript_text = f"This is a placeholder final transcript for {duration_sec:.1f}s of audio."
        
        transcript_msg = create_transcript_message(
            text=transcript_text,
            is_final=True,
            confidence=0.95
        )
        
        await self.send_message(transcript_msg.dict())
        logger.info(f"Session {self.session_id}: Sent final transcript ({len(transcript_text)} chars)")
        if _FORWARD_FINAL:
            await self._forward_final_to_orchestrator(transcript_text, confidence=0.95)
        
        # Clear buffer
        self.audio_buffer.clear()

    async def _emit_partial_to_renderer(self, transcript_text: str) -> None:
        if not _RENDERER_URL:
            return
        envelope = {
            "type": "outcome.reflected",
            "payload": {"text": transcript_text, "person_id": self.person_id, "session_id": self.session_id},
            "urgency": "low",
            "ts": time.time(),
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "person_id": self.person_id,
        }
        headers = {
            "x-request-id": self.trace_id,
            "x-trace-id": self.trace_id,
            "traceparent": _format_traceparent(self.trace_id),
        }
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                await client.post(f"{_RENDERER_URL.rstrip('/')}/events", json=envelope, headers=headers)
        except Exception:
            pass

    async def _forward_final_to_orchestrator(self, transcript_text: str, *, confidence: float) -> None:
        if not _ORCHESTRATOR_URL:
            return
        body = {
            "schema_version": "input-event.v1",
            "event_id": str(uuid.uuid4()),
            "trace_id": self.trace_id,
            "ts_unix_ms": int(datetime.now().timestamp() * 1000),
            "source": "io-speech",
            "modality": "speech",
            "payload": {"transcript": transcript_text, "text": transcript_text, "confidence": confidence, "is_final": True},
            "person_id": self.person_id,
            "session_id": self.session_id,
            "auth": {},
        }
        headers = {
            "x-request-id": self.trace_id,
            "x-trace-id": self.trace_id,
            "traceparent": _format_traceparent(self.trace_id),
        }
        headers.update(_service_auth_header())
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(f"{_ORCHESTRATOR_URL.rstrip('/')}{_ORCHESTRATOR_INPUT_PATH}", json=body, headers=headers)
        except Exception:
            pass
    
    async def handle_control(self, message: ControlMessage):
        """Handle control commands from client"""
        action = message.action
        
        if action == "start_listening":
            self.is_listening = True
            self.vad.reset()
            status_msg = create_status_message("listening")
            await self.send_message(status_msg.dict())
            logger.debug(f"Session {self.session_id}: Started listening")
        
        elif action == "stop_listening":
            self.is_listening = False
            if self.vad.is_speaking():
                await self.generate_final_transcript()
            self.vad.reset()
            status_msg = create_status_message("connected")
            await self.send_message(status_msg.dict())
            logger.debug(f"Session {self.session_id}: Stopped listening")
        
        elif action == "cancel_tts":
            if self.is_speaking and self.tts_sequence is not None:
                await self.handle_barge_in()
            logger.debug(f"Session {self.session_id}: TTS cancelled by user")
    
    async def handle_barge_in(self):
        """Handle barge-in (user interrupts TTS)"""
        if self.tts_sequence is None:
            return
        
        # Send barge-in notification
        barge_in_msg = create_barge_in_message(self.tts_sequence)
        await self.send_message(barge_in_msg.dict())
        
        # Reset TTS state
        self.is_speaking = False
        self.tts_sequence = None
        
        # Resume listening
        self.is_listening = True
        status_msg = create_status_message("listening")
        await self.send_message(status_msg.dict())
        
        logger.info(f"Session {self.session_id}: Barge-in detected, TTS cancelled")
    
    async def start_tts_playback(self, sequence: int):
        """Start TTS playback (called by orchestrator)"""
        self.is_speaking = True
        self.tts_sequence = sequence
        status_msg = create_status_message("speaking")
        await self.send_message(status_msg.dict())
        logger.debug(f"Session {self.session_id}: TTS playback started (seq={sequence})")
    
    async def end_tts_playback(self):
        """End TTS playback"""
        self.is_speaking = False
        self.tts_sequence = None
        status_msg = create_status_message("listening")
        await self.send_message(status_msg.dict())
        logger.debug(f"Session {self.session_id}: TTS playback ended")
    
    def get_session_info(self) -> dict:
        """Get session information for monitoring"""
        return {
            "session_id": self.session_id,
            "is_listening": self.is_listening,
            "is_speaking": self.is_speaking,
            "vad_state": self.vad.get_state(),
            "buffer_size": len(self.audio_buffer),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
        }

# Lightweight handler used by unit tests to manage sessions without FastAPI.
class WebSocketHandler:
    def __init__(self):
        self.active_sessions: dict[str, StreamingSession] = {}
        self.session_counter = 0
        self.vad = VoiceActivityDetector(VADConfig())

    def create_session(self) -> str:
        self.session_counter += 1
        session_id = f"session-{self.session_counter}"
        self.active_sessions[session_id] = StreamingSession(session_id)
        return session_id

    def get_session(self, session_id: str) -> Optional[StreamingSession]:
        return self.active_sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        self.active_sessions.pop(session_id, None)

    async def handle_message(self, websocket: Any, message: dict, session_id: str) -> None:
        """Minimal message router used by tests."""
        session = self.active_sessions.get(session_id)
        if session is None:
            session = StreamingSession(session_id, websocket if isinstance(websocket, WebSocket) else None)
            self.active_sessions[session_id] = session
        if websocket and session.websocket is None:
            session.websocket = websocket

        msg_type = message.get("type")
        try:
            if msg_type == "audio_chunk":
                audio_b64 = message.get("audio") or ""
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    session.add_audio(audio_bytes)
                    if websocket:
                        await websocket.send_json({"type": "audio_ack", "sequence": message.get("sequence")})
                except Exception:
                    if websocket:
                        await websocket.send_json({"type": "error", "message": "invalid audio"})
            elif msg_type == "start_stream":
                if websocket:
                    await websocket.send_json({"type": "ready", "session_id": session_id})
            elif msg_type == "end_stream":
                session.deactivate()
                if websocket:
                    await websocket.send_json({"type": "end", "session_id": session_id})
            elif msg_type == "cancel":
                session.deactivate()
                self.close_session(session_id)
                if websocket:
                    await websocket.send_json({"type": "cancelled", "session_id": session_id})
            else:
                if websocket:
                    await websocket.send_json({"type": "error", "message": "invalid message type"})
        except Exception:
            if websocket:
                await websocket.send_json({"type": "error", "message": "processing error"})

class WebSocketManager:
    """
    Manages multiple WebSocket streaming sessions
    """
    
    def __init__(self):
        self.sessions: dict[str, StreamingSession] = {}
        self.session_counter = 0
        logger.info("WebSocket manager initialized")
    
    def create_session(self, websocket: WebSocket) -> StreamingSession:
        """Create a new streaming session"""
        self.session_counter += 1
        session_id = f"session-{self.session_counter}"
        trace_id = _extract_trace_id(websocket.headers)
        person_id = websocket.query_params.get("person_id") if hasattr(websocket, "query_params") else None
        session = StreamingSession(session_id, websocket, trace_id=trace_id, person_id=person_id)
        self.sessions[session_id] = session
        logger.info(f"Created session {session_id} (total: {len(self.sessions)})")
        return session
    
    def remove_session(self, session_id: str):
        """Remove a streaming session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Removed session {session_id} (total: {len(self.sessions)})")
    
    def get_session(self, session_id: str) -> Optional[StreamingSession]:
        """Get a session by ID"""
        return self.sessions.get(session_id)
    
    def get_all_sessions(self) -> list[StreamingSession]:
        """Get all active sessions"""
        return list(self.sessions.values())
    
    def get_session_count(self) -> int:
        """Get number of active sessions"""
        return len(self.sessions)


# Global WebSocket manager instance
ws_manager = WebSocketManager()


# ============================================================================
# WebSocket Endpoint Handler
# ============================================================================

async def handle_websocket_stream(websocket: WebSocket):
    """
    Main WebSocket endpoint handler
    
    Handles connection lifecycle, message routing, and error handling.
    """
    # Accept connection
    await websocket.accept()
    
    # Create session
    session = ws_manager.create_session(websocket)
    
    try:
        # Send connection confirmation
        status_msg = create_status_message("connected")
        await session.send_message(status_msg.dict())
        
        # Message loop
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            try:
                # Parse message
                message = parse_client_message(data)
                
                # Route message
                if isinstance(message, AudioInputMessage):
                    await session.handle_audio_input(message)
                elif isinstance(message, ControlMessage):
                    await session.handle_control(message)
                else:
                    logger.warning(f"Session {session.session_id}: Unknown message type")
            
            except ValueError as e:
                # Invalid message format
                error_msg = create_error_message(
                    "invalid_message",
                    f"Invalid message format: {str(e)}"
                )
                await session.send_message(error_msg.dict())
            
            except Exception as e:
                # Processing error
                logger.error(f"Session {session.session_id}: Error processing message: {e}")
                error_msg = create_error_message(
                    "processing_error",
                    f"Error processing message: {str(e)}"
                )
                await session.send_message(error_msg.dict())
    
    except WebSocketDisconnect:
        logger.info(f"Session {session.session_id}: Client disconnected")
    
    except Exception as e:
        logger.error(f"Session {session.session_id}: Unexpected error: {e}")
    
    finally:
        # Cleanup
        ws_manager.remove_session(session.session_id)
        logger.info(f"Session {session.session_id}: Cleaned up")


# ============================================================================
# Helper Functions
# ============================================================================

def get_active_sessions() -> list[dict]:
    """Get information about all active sessions"""
    return [session.get_session_info() for session in ws_manager.get_all_sessions()]


def get_session_count() -> int:
    """Get number of active WebSocket sessions"""
    return ws_manager.get_session_count()
