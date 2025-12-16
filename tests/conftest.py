import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))

# Keep unit tests lightweight; Phase 1.1 smoketests exercise the real local engines.
os.environ.setdefault("UNISON_SPEECH_ENGINE_MODE", "stub")
