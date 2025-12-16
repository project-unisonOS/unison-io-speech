from __future__ import annotations

import base64
import os
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from unison_common.models import ModelPackResolver


def _pcm16_bytes_to_float32(audio_bytes: bytes) -> np.ndarray:
    pcm = np.frombuffer(audio_bytes, dtype=np.int16)
    return (pcm.astype(np.float32) / 32768.0).copy()


def _decode_wav_bytes(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    # Minimal WAV PCM decoder (PCM16 only).
    import io

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if sampwidth != 2:
        raise ValueError(f"unsupported wav sample width: {sampwidth}")
    audio = _pcm16_bytes_to_float32(frames)
    if channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1).astype(np.float32)
    return audio, rate


def _resolve_model_path(*, profile: str) -> str:
    # Explicit overrides first.
    if profile == "accurate":
        explicit = os.getenv("UNISON_ASR_MODEL_PATH_ACCURATE")
        if explicit:
            return explicit
        model_id = os.getenv("UNISON_ASR_MODEL_ID_ACCURATE", "asr:faster-whisper:medium.en")
    else:
        explicit = os.getenv("UNISON_ASR_MODEL_PATH_FAST")
        if explicit:
            return explicit
        model_id = os.getenv("UNISON_ASR_MODEL_ID_FAST", "asr:faster-whisper:tiny.en")

    resolver = ModelPackResolver.from_env()
    return str(resolver.get_model_path(model_id=model_id))


@dataclass
class FasterWhisperAsrEngine:
    """
    Local ASR engine backed by faster-whisper (CTranslate2).
    """

    _models: dict[str, object]

    def __init__(self) -> None:
        self._models = {}

    def _get_model(self, profile: str):
        profile_key = "accurate" if profile == "accurate" else "fast"
        model = self._models.get(profile_key)
        if model is not None:
            return model

        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("faster-whisper is not installed") from exc

        model_path = _resolve_model_path(profile=profile_key)
        device = os.getenv("UNISON_ASR_DEVICE", "cpu")
        compute_type = os.getenv("UNISON_ASR_COMPUTE_TYPE_ACCURATE" if profile_key == "accurate" else "UNISON_ASR_COMPUTE_TYPE_FAST", "int8")
        model = WhisperModel(model_path, device=device, compute_type=compute_type)
        self._models[profile_key] = model
        return model

    def transcribe_pcm16(
        self,
        *,
        audio_pcm16: bytes,
        sample_rate_hz: int = 16000,
        profile: str = "fast",
        language: str = "en",
    ) -> Tuple[str, float]:
        audio = _pcm16_bytes_to_float32(audio_pcm16)
        return self.transcribe_audio_array(audio=audio, sample_rate_hz=sample_rate_hz, profile=profile, language=language)

    def transcribe_audio_b64(self, *, audio_b64: str, profile: str = "fast") -> Tuple[str, float]:
        raw = base64.b64decode(audio_b64)
        if raw[:4] == b"RIFF":
            audio, rate = _decode_wav_bytes(raw)
            return self.transcribe_audio_array(audio=audio, sample_rate_hz=rate, profile=profile, language="en")
        return self.transcribe_pcm16(audio_pcm16=raw, sample_rate_hz=16000, profile=profile, language="en")

    def transcribe_audio_array(
        self,
        *,
        audio: np.ndarray,
        sample_rate_hz: int,
        profile: str,
        language: str,
    ) -> Tuple[str, float]:
        model = self._get_model(profile)

        # Best-effort resampling: assume 16k if not; keep minimal deps.
        if sample_rate_hz != 16000:
            # naive resample (linear interpolation)
            x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
            new_len = int(len(audio) * (16000 / float(sample_rate_hz)))
            x_new = np.linspace(0.0, 1.0, num=max(1, new_len), endpoint=False)
            audio = np.interp(x_new, x_old, audio).astype(np.float32)

        beam_size = int(os.getenv("UNISON_ASR_BEAM_SIZE_ACCURATE" if profile == "accurate" else "UNISON_ASR_BEAM_SIZE_FAST", "1"))
        vad_filter = os.getenv("UNISON_ASR_VAD_FILTER", "false").lower() in {"1", "true", "yes", "on"}

        segments, info = model.transcribe(audio, language=language, beam_size=beam_size, vad_filter=vad_filter)  # type: ignore[attr-defined]
        text_parts = [seg.text.strip() for seg in segments if getattr(seg, "text", "").strip()]
        text = " ".join(text_parts).strip()

        # faster-whisper returns an info object; expose a conservative confidence.
        confidence = 0.0
        try:
            confidence = float(getattr(info, "language_probability", 0.0))  # type: ignore[arg-type]
        except Exception:
            confidence = 0.0
        return text, max(0.0, min(1.0, confidence if confidence > 0 else 0.9))


_ENGINE: Optional[FasterWhisperAsrEngine] = None


def get_asr_engine() -> FasterWhisperAsrEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = FasterWhisperAsrEngine()
    return _ENGINE

