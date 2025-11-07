import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"
    assert j.get("service") == "unison-io-speech"


def test_ready():
    r = client.get("/ready")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ready") is True


def test_stt_missing_audio():
    r = client.post("/speech/stt", json={})
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is False
    assert "audio" in j.get("error", "")


def test_stt_placeholder():
    r = client.post("/speech/stt", json={"audio": "dGVzdA=="})  # base64 "test"
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert isinstance(j.get("transcript"), str)
    assert "placeholder" in j.get("transcript", "").lower()


def test_tts_missing_text():
    r = client.post("/speech/tts", json={})
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is False
    assert "text" in j.get("error", "")


def test_tts_placeholder():
    r = client.post("/speech/tts", json={"text": "hello world"})
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    audio_url = j.get("audio_url", "")
    assert audio_url.startswith("data:audio/wav;base64,")
