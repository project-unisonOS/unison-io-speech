# unison-io-speech

Multimodal I/O service for speech: speech-to-text and text-to-speech stubs. Emits EventEnvelopes to the Orchestrator.

## Status
Optional (dev-mode) — stubbed speech gateway; used in devstack but not required for headless tests.

## Run locally

- Python
  - pip install -r requirements.txt
  - cp .env.example .env
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
- `WS /stream` — WebSocket audio streaming (see `WEBSOCKET_API.md`), default port `8084`

## Notes

- Intended for Developer Mode; stub implementations.
- Real STT/TTS will be plugged in later.
- Use renderer for expressive speech outputs; if an action would change physical hardware state (relays, smart speakers, etc.), route it through `unison-actuation` using the Action Envelope (`unison-docs/dev/specs/action-envelope.md`).

## Testing
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -c ../constraints.txt -r requirements.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OTEL_SDK_DISABLED=true python -m pytest
```

## Docs

Full docs at https://project-unisonos.github.io
- Repo roles: `unison-docs/dev/unison-repo-roles.md`
- Compatibility: `unison-docs/dev/compatibility-matrix.md`
