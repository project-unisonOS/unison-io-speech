from fastapi.testclient import TestClient

from src import server  # noqa: E402


def test_stt_includes_metadata_and_baton():
    client = TestClient(server.app)
    resp = client.post("/speech/stt", json={"audio": "ZmFrZQ==", "person_id": "p1", "session_id": "s1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "baton" in body
    assert body["person_id"] == "p1"
    assert body["session_id"] == "s1"


def test_tts_includes_metadata_and_baton():
    client = TestClient(server.app)
    resp = client.post("/speech/tts", json={"text": "hello", "person_id": "p1", "session_id": "s1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "baton" in body
    assert body["person_id"] == "p1"
    assert body["session_id"] == "s1"
