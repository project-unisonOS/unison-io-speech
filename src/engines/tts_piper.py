from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from unison_common.models import ModelPackResolver


def _resolve_voice_model_path(*, profile: str) -> Path:
    # Explicit overrides first.
    if profile == "natural":
        explicit = os.getenv("UNISON_TTS_MODEL_PATH_NATURAL")
        if explicit:
            return Path(explicit).expanduser().resolve()
        model_id = os.getenv("UNISON_TTS_MODEL_ID_NATURAL", "tts:piper:en_US-lessac")
    else:
        explicit = os.getenv("UNISON_TTS_MODEL_PATH_LIGHTWEIGHT")
        if explicit:
            return Path(explicit).expanduser().resolve()
        model_id = os.getenv("UNISON_TTS_MODEL_ID_LIGHTWEIGHT", "tts:piper:en_US-lessac")

    resolver = ModelPackResolver.from_env()
    return resolver.get_model_path(model_id=model_id)


def _find_onnx(model_path: Path) -> Path:
    if model_path.is_file() and model_path.suffix == ".onnx":
        return model_path
    if model_path.is_dir():
        for cand in sorted(model_path.glob("*.onnx")):
            return cand
    raise FileNotFoundError(f"piper voice model not found at: {model_path}")


@dataclass
class PiperTtsEngine:
    """
    Local TTS engine backed by Piper.

    Implementation uses the `piper` CLI (installed by piper-tts) for maximum compatibility.
    """

    def synthesize_wav(self, *, text: str, profile: str = "lightweight") -> bytes:
        if not text.strip():
            raise ValueError("empty text")

        model_root = _resolve_voice_model_path(profile=profile)
        onnx = _find_onnx(model_root)

        piper_bin = os.getenv("UNISON_PIPER_BIN") or "piper"
        with tempfile.TemporaryDirectory(prefix="unison-piper-") as td:
            out_wav = Path(td) / "out.wav"
            cmd = [
                piper_bin,
                "--model",
                str(onnx),
                "--output_file",
                str(out_wav),
            ]
            proc = subprocess.run(cmd, input=text.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            if proc.returncode != 0:
                raise RuntimeError(f"piper failed: {proc.stderr.decode('utf-8', 'ignore')[:200]}")
            return out_wav.read_bytes()

    def synthesize_data_url(self, *, text: str, profile: str = "lightweight") -> str:
        wav = self.synthesize_wav(text=text, profile=profile)
        b64 = base64.b64encode(wav).decode("ascii")
        return f"data:audio/wav;base64,{b64}"


_ENGINE: Optional[PiperTtsEngine] = None


def get_tts_engine() -> PiperTtsEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = PiperTtsEngine()
    return _ENGINE

