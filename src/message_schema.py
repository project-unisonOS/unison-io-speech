"""
WebSocket Message Schema for io-speech streaming

Defines message types for bidirectional audio streaming, VAD events,
transcription, and barge-in support.
"""

from typing import Literal, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Client → Server Messages
# ============================================================================

class AudioInputMessage(BaseModel):
    """Audio data from client (PCM16, 16kHz, mono)"""
    type: Literal["audio"] = "audio"
    data: str = Field(..., description="Base64-encoded PCM16 audio data")
    timestamp: int = Field(..., description="Client timestamp in milliseconds")
    sequence: int = Field(..., description="Sequence number for ordering")


class ControlMessage(BaseModel):
    """Control commands from client"""
    type: Literal["control"] = "control"
    action: Literal["start_listening", "stop_listening", "cancel_tts"] = Field(
        ..., description="Control action to perform"
    )
    timestamp: Optional[int] = Field(None, description="Client timestamp in milliseconds")


# Union type for all client messages
ClientMessage = Union[AudioInputMessage, ControlMessage]


# ============================================================================
# Server → Client Messages
# ============================================================================

class TranscriptMessage(BaseModel):
    """Transcription result (partial or final)"""
    type: Literal["transcript"] = "transcript"
    text: str = Field(..., description="Transcribed text")
    is_final: bool = Field(..., description="True if final transcript, False if partial")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    timestamp: int = Field(..., description="Server timestamp in milliseconds")


class VADEventMessage(BaseModel):
    """Voice Activity Detection event"""
    type: Literal["vad"] = "vad"
    event: Literal["speech_start", "speech_end"] = Field(
        ..., description="VAD event type"
    )
    timestamp: int = Field(..., description="Server timestamp in milliseconds")
    energy: Optional[float] = Field(None, description="Audio energy level")


class AudioOutputMessage(BaseModel):
    """TTS audio output"""
    type: Literal["audio_output"] = "audio_output"
    data: str = Field(..., description="Base64-encoded audio data")
    format: str = Field(default="pcm16", description="Audio format")
    sample_rate: int = Field(default=16000, description="Sample rate in Hz")
    sequence: int = Field(..., description="Sequence number for ordering")
    timestamp: int = Field(..., description="Server timestamp in milliseconds")


class BargeInMessage(BaseModel):
    """Barge-in notification (TTS cancelled)"""
    type: Literal["barge_in"] = "barge_in"
    cancelled_sequence: int = Field(..., description="Sequence number of cancelled TTS")
    timestamp: int = Field(..., description="Server timestamp in milliseconds")


class ErrorMessage(BaseModel):
    """Error notification"""
    type: Literal["error"] = "error"
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    timestamp: int = Field(..., description="Server timestamp in milliseconds")


class StatusMessage(BaseModel):
    """Connection status update"""
    type: Literal["status"] = "status"
    status: Literal["connected", "listening", "processing", "speaking"] = Field(
        ..., description="Current connection status"
    )
    timestamp: int = Field(..., description="Server timestamp in milliseconds")


# Union type for all server messages
ServerMessage = Union[
    TranscriptMessage,
    VADEventMessage,
    AudioOutputMessage,
    BargeInMessage,
    ErrorMessage,
    StatusMessage,
]


# ============================================================================
# Helper Functions
# ============================================================================

def get_timestamp_ms() -> int:
    """Get current timestamp in milliseconds"""
    return int(datetime.now().timestamp() * 1000)


def parse_client_message(data: dict) -> ClientMessage:
    """Parse incoming client message"""
    msg_type = data.get("type")
    
    if msg_type == "audio":
        return AudioInputMessage(**data)
    elif msg_type == "control":
        return ControlMessage(**data)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")


def create_transcript_message(
    text: str,
    is_final: bool,
    confidence: float = 0.95
) -> TranscriptMessage:
    """Create a transcript message"""
    return TranscriptMessage(
        text=text,
        is_final=is_final,
        confidence=confidence,
        timestamp=get_timestamp_ms()
    )


def create_vad_event(event: Literal["speech_start", "speech_end"], energy: Optional[float] = None) -> VADEventMessage:
    """Create a VAD event message"""
    return VADEventMessage(
        event=event,
        timestamp=get_timestamp_ms(),
        energy=energy
    )


def create_barge_in_message(cancelled_sequence: int) -> BargeInMessage:
    """Create a barge-in message"""
    return BargeInMessage(
        cancelled_sequence=cancelled_sequence,
        timestamp=get_timestamp_ms()
    )


def create_error_message(code: str, message: str) -> ErrorMessage:
    """Create an error message"""
    return ErrorMessage(
        code=code,
        message=message,
        timestamp=get_timestamp_ms()
    )


def create_status_message(status: Literal["connected", "listening", "processing", "speaking"]) -> StatusMessage:
    """Create a status message"""
    return StatusMessage(
        status=status,
        timestamp=get_timestamp_ms()
    )


# ============================================================================
# Message Validation
# ============================================================================

def validate_audio_data(data: str) -> bool:
    """Validate base64-encoded audio data"""
    import base64
    try:
        decoded = base64.b64decode(data)
        # Check if length is reasonable (not empty, not too large)
        if len(decoded) == 0:
            return False
        if len(decoded) > 1024 * 1024:  # Max 1MB per chunk
            return False
        return True
    except Exception:
        return False


def validate_audio_format(sample_rate: int, channels: int, format: str) -> bool:
    """Validate audio format parameters"""
    valid_sample_rates = [8000, 16000, 22050, 44100, 48000]
    valid_channels = [1, 2]
    valid_formats = ["pcm16", "pcm8", "float32"]
    
    return (
        sample_rate in valid_sample_rates
        and channels in valid_channels
        and format in valid_formats
    )
