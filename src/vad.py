"""
Voice Activity Detection (VAD) for io-speech

Simple energy-based VAD for detecting speech start/end.
Can be upgraded to WebRTC VAD or ML-based VAD in the future.
"""

import numpy as np
from typing import Literal, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class VADConfig:
    """VAD configuration parameters"""
    energy_threshold: float = 0.01  # Energy threshold for speech detection
    speech_pad_ms: int = 300  # Padding before/after speech (ms)
    silence_duration_ms: int = 700  # Silence duration to end speech (ms)
    sample_rate: int = 16000  # Audio sample rate
    frame_duration_ms: int = 30  # Frame duration for processing (ms)
    
    @property
    def frame_size(self) -> int:
        """Calculate frame size in samples"""
        return int(self.sample_rate * self.frame_duration_ms / 1000)
    
    @property
    def speech_pad_frames(self) -> int:
        """Calculate speech padding in frames"""
        return int(self.speech_pad_ms / self.frame_duration_ms)
    
    @property
    def silence_frames(self) -> int:
        """Calculate silence duration in frames"""
        return int(self.silence_duration_ms / self.frame_duration_ms)


class VoiceActivityDetector:
    """
    Energy-based Voice Activity Detector
    
    Detects speech start and end based on audio energy levels.
    Uses a simple state machine with hysteresis to avoid false triggers.
    """
    
    def __init__(self, config: Optional[VADConfig] = None):
        self.config = config or VADConfig()
        self.state: Literal["silence", "speech"] = "silence"
        self.speech_frames = 0
        self.silence_frames = 0
        self.energy_history = []
        self.max_history_size = 100
        
        logger.info(
            f"VAD initialized: threshold={self.config.energy_threshold}, "
            f"speech_pad={self.config.speech_pad_ms}ms, "
            f"silence={self.config.silence_duration_ms}ms"
        )
    
    def calculate_energy(self, audio_data: np.ndarray) -> float:
        """
        Calculate RMS energy of audio frame
        
        Args:
            audio_data: Audio samples (PCM16 or float32)
        
        Returns:
            RMS energy value
        """
        if len(audio_data) == 0:
            return 0.0
        
        # Convert to float if needed
        if audio_data.dtype == np.int16:
            audio_float = audio_data.astype(np.float32) / 32768.0
        else:
            audio_float = audio_data.astype(np.float32)
        
        # Calculate RMS energy
        energy = np.sqrt(np.mean(audio_float ** 2))
        return float(energy)
    
    def process_frame(self, audio_data: np.ndarray) -> Optional[Literal["speech_start", "speech_end"]]:
        """
        Process audio frame and detect VAD events
        
        Args:
            audio_data: Audio samples for one frame
        
        Returns:
            VAD event if state changed, None otherwise
        """
        energy = self.calculate_energy(audio_data)
        
        # Store energy history for adaptive thresholding
        self.energy_history.append(energy)
        if len(self.energy_history) > self.max_history_size:
            self.energy_history.pop(0)
        
        # Determine if frame contains speech
        is_speech = energy > self.config.energy_threshold
        
        event = None
        
        if self.state == "silence":
            if is_speech:
                self.speech_frames += 1
                if self.speech_frames >= self.config.speech_pad_frames:
                    # Transition to speech
                    self.state = "speech"
                    self.silence_frames = 0
                    event = "speech_start"
                    logger.debug(f"Speech started (energy={energy:.4f})")
            else:
                self.speech_frames = 0
        
        elif self.state == "speech":
            if not is_speech:
                self.silence_frames += 1
                if self.silence_frames >= self.config.silence_frames:
                    # Transition to silence
                    self.state = "silence"
                    self.speech_frames = 0
                    event = "speech_end"
                    logger.debug(f"Speech ended (silence={self.silence_frames} frames)")
            else:
                self.silence_frames = 0
        
        return event
    
    def process_chunk(self, audio_chunk: bytes, format: str = "pcm16") -> list[Literal["speech_start", "speech_end"]]:
        """
        Process audio chunk and return all VAD events
        
        Args:
            audio_chunk: Raw audio bytes
            format: Audio format ("pcm16", "pcm8", "float32")
        
        Returns:
            List of VAD events detected in this chunk
        """
        # Convert bytes to numpy array
        if format == "pcm16":
            audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
        elif format == "pcm8":
            audio_data = np.frombuffer(audio_chunk, dtype=np.int8)
        elif format == "float32":
            audio_data = np.frombuffer(audio_chunk, dtype=np.float32)
        else:
            raise ValueError(f"Unsupported audio format: {format}")
        
        # Process chunk in frames
        events = []
        frame_size = self.config.frame_size
        
        for i in range(0, len(audio_data), frame_size):
            frame = audio_data[i:i + frame_size]
            if len(frame) < frame_size:
                # Pad last frame if needed
                frame = np.pad(frame, (0, frame_size - len(frame)), mode='constant')
            
            event = self.process_frame(frame)
            if event:
                events.append(event)
        
        return events
    
    def reset(self):
        """Reset VAD state"""
        self.state = "silence"
        self.speech_frames = 0
        self.silence_frames = 0
        self.energy_history = []
        logger.debug("VAD state reset")
    
    def get_state(self) -> Literal["silence", "speech"]:
        """Get current VAD state"""
        return self.state
    
    def is_speaking(self) -> bool:
        """Check if currently in speech state"""
        return self.state == "speech"
    
    def get_average_energy(self) -> float:
        """Get average energy from history"""
        if not self.energy_history:
            return 0.0
        return float(np.mean(self.energy_history))
    
    def adapt_threshold(self, percentile: float = 75):
        """
        Adapt energy threshold based on energy history
        
        Args:
            percentile: Percentile of energy history to use as threshold
        """
        if len(self.energy_history) < 10:
            return  # Need more history
        
        new_threshold = float(np.percentile(self.energy_history, percentile))
        
        # Only adapt if significantly different
        if abs(new_threshold - self.config.energy_threshold) > 0.005:
            old_threshold = self.config.energy_threshold
            self.config.energy_threshold = new_threshold
            logger.info(f"VAD threshold adapted: {old_threshold:.4f} → {new_threshold:.4f}")


# ============================================================================
# Helper Functions
# ============================================================================

def create_vad(
    energy_threshold: float = 0.01,
    speech_pad_ms: int = 300,
    silence_duration_ms: int = 700,
    sample_rate: int = 16000
) -> VoiceActivityDetector:
    """
    Create a VAD instance with custom configuration
    
    Args:
        energy_threshold: Energy threshold for speech detection
        speech_pad_ms: Padding before/after speech (ms)
        silence_duration_ms: Silence duration to end speech (ms)
        sample_rate: Audio sample rate
    
    Returns:
        Configured VAD instance
    """
    config = VADConfig(
        energy_threshold=energy_threshold,
        speech_pad_ms=speech_pad_ms,
        silence_duration_ms=silence_duration_ms,
        sample_rate=sample_rate
    )
    return VoiceActivityDetector(config)


def test_vad_with_audio(audio_file: str):
    """
    Test VAD with an audio file (for development/debugging)
    
    Args:
        audio_file: Path to audio file (WAV format)
    """
    import wave
    
    with wave.open(audio_file, 'rb') as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        
        logger.info(f"Testing VAD with {audio_file}")
        logger.info(f"Sample rate: {sample_rate}, Channels: {n_channels}, Width: {sample_width}")
        
        vad = create_vad(sample_rate=sample_rate)
        
        # Read and process audio
        chunk_size = int(sample_rate * 0.1)  # 100ms chunks
        while True:
            audio_bytes = wf.readframes(chunk_size)
            if not audio_bytes:
                break
            
            events = vad.process_chunk(audio_bytes, format="pcm16")
            for event in events:
                logger.info(f"VAD Event: {event}")
        
        logger.info(f"Final state: {vad.get_state()}")
        logger.info(f"Average energy: {vad.get_average_energy():.4f}")
