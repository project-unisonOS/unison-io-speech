# unison-io-speech

Multimodal I/O service for speech: local Speech-to-Text (ASR) + Text-to-Speech (TTS) plus a WebSocket streaming façade (VAD + barge-in).

Phase 4: streams partial transcripts to the renderer and forwards final transcripts to the orchestrator as `InputEventEnvelope` (`POST /input`).

## Status
Phase 1.1: local-first speech is supported.

- Default: `UNISON_SPEECH_ENGINE_MODE=local` (real engines)
- Unit tests: `UNISON_SPEECH_ENGINE_MODE=stub` (lightweight)

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
- `POST /speech/stt` — Speech-to-Text
  - Request: `{ "audio": "<base64 wav or pcm16>", "profile": "fast|accurate" }`
  - Returns a transcript string + metadata (`engine`, `profile`)
- `POST /speech/tts` — Text-to-Speech
  - Request: `{ "text": "hello", "profile": "lightweight|natural" }`
  - Returns an audio data URL + metadata (`engine`, `profile`)
- `WS /stream` — WebSocket audio streaming (see `WEBSOCKET_API.md`), default port `8084`

## Notes

- Local ASR engine: faster-whisper (CTranslate2)
- Local TTS engine: Piper
- Model assets are expected to be installed via Model Packs into `UNISON_MODEL_DIR` (default `/var/lib/unison/models`).
- WebSocket sessions derive a `trace_id` from incoming headers (`x-trace-id`/`x-request-id`/`traceparent`) or generate one; forwarded downstream for correlation.
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
