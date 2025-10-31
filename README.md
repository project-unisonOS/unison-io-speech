# unison-io-speech

Multimodal I/O service for speech: speech-to-text and text-to-speech stubs. Emits EventEnvelopes to the Orchestrator.

## Run locally

- Python
  - pip install -r requirements.txt
  - python src/server.py
  - Open: http://localhost:8084/health

- Docker
  - docker build -t unison-io-speech:dev .
  - docker run --rm -p 8084:8085 unison-io-speech:dev

## Endpoints

- `GET /health` — liveness
- `GET /ready` — readiness
- `POST /speech/stt` — Speech-to-Text (stub)
  - Request: base64-encoded audio or placeholder
  - Returns a transcript string
- `POST /speech/tts` — Text-to-Speech (stub)
  - Request: `{ "text": "hello" }`
  - Returns a placeholder audio URL or base64 stub

## Notes

- Intended for Developer Mode; stub implementations.
- Real STT/TTS will be plugged in later.
