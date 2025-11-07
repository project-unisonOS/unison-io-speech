# P1.2: io-speech WebSocket Streaming - Implementation Plan

**Date**: November 7, 2025  
**Status**: In Progress  
**Target**: < 250ms latency, VAD, barge-in support

---

## 🎯 Objectives

Transform io-speech from HTTP-only to real-time WebSocket streaming with:
1. **WebSocket endpoint** for bidirectional audio streaming
2. **Voice Activity Detection (VAD)** for speech start/end detection
3. **Barge-in support** to interrupt TTS playback
4. **Low latency** (< 250ms mic → partial transcript)
5. **Backpressure handling** without audio drops

---

## 📋 Requirements

### Functional Requirements

1. **WebSocket Streaming**
   - `/stream` WebSocket endpoint
   - Bidirectional audio streaming
   - Message-based protocol (JSON)
   - Connection lifecycle management

2. **Voice Activity Detection**
   - Detect speech start (voice activity begins)
   - Detect speech end (silence after speech)
   - Configurable sensitivity
   - Energy-based detection

3. **Barge-in Support**
   - Detect user speech during TTS playback
   - Cancel ongoing TTS
   - Signal orchestrator to stop output
   - Resume listening immediately

4. **Audio Processing**
   - Support PCM16, 16kHz, mono
   - Chunk-based processing (100-200ms chunks)
   - Streaming transcription (partial results)
   - Final transcript on speech end

5. **Performance**
   - < 250ms latency (mic → partial transcript)
   - Handle backpressure gracefully
   - No audio drops under normal load
   - Efficient memory usage

### Non-Functional Requirements

1. **Reliability**
   - Graceful connection handling
   - Error recovery
   - Connection timeout handling

2. **Testability**
   - 20+ unit tests
   - WebSocket test client
   - VAD test cases
   - Barge-in scenarios

3. **Documentation**
   - WebSocket API specification
   - Message schema documentation
   - Integration examples
   - Troubleshooting guide

---

## 🏗️ Architecture

### Message Protocol

```json
// Client → Server (Audio Input)
{
  "type": "audio",
  "data": "base64_encoded_pcm16",
  "timestamp": 1699392000000,
  "sequence": 1
}

// Client → Server (Control)
{
  "type": "control",
  "action": "start_listening" | "stop_listening" | "cancel_tts"
}

// Server → Client (Partial Transcript)
{
  "type": "transcript",
  "text": "hello wor",
  "is_final": false,
  "confidence": 0.85,
  "timestamp": 1699392000100
}

// Server → Client (Final Transcript)
{
  "type": "transcript",
  "text": "hello world",
  "is_final": true,
  "confidence": 0.95,
  "timestamp": 1699392000500
}

// Server → Client (VAD Event)
{
  "type": "vad",
  "event": "speech_start" | "speech_end",
  "timestamp": 1699392000000
}

// Server → Client (TTS Audio)
{
  "type": "audio_output",
  "data": "base64_encoded_audio",
  "format": "pcm16",
  "sample_rate": 16000,
  "sequence": 1
}

// Server → Client (Barge-in)
{
  "type": "barge_in",
  "cancelled_sequence": 5,
  "timestamp": 1699392000000
}

// Server → Client (Error)
{
  "type": "error",
  "code": "invalid_audio_format",
  "message": "Audio must be PCM16, 16kHz, mono",
  "timestamp": 1699392000000
}
```

### Component Structure

```
unison-io-speech/
├── src/
│   ├── server.py              # Main FastAPI app (existing)
│   ├── websocket_handler.py   # NEW: WebSocket endpoint
│   ├── vad.py                 # NEW: Voice Activity Detection
│   ├── audio_processor.py     # NEW: Audio chunk processing
│   ├── barge_in.py            # NEW: Barge-in detection
│   ├── message_schema.py      # NEW: Message types
│   └── streaming_stt.py       # NEW: Streaming STT (stub)
├── tests/
│   ├── test_websocket.py      # NEW: WebSocket tests
│   ├── test_vad.py            # NEW: VAD tests
│   ├── test_barge_in.py       # NEW: Barge-in tests
│   └── test_integration.py    # NEW: E2E tests
└── docs/
    └── WEBSOCKET_API.md       # NEW: API documentation
```

---

## 🔧 Implementation Steps

### Phase 1: WebSocket Foundation (Day 1-2)

**Tasks**:
1. Add WebSocket dependencies (`websockets`, `python-multipart`)
2. Create message schema module
3. Implement `/stream` WebSocket endpoint
4. Add connection lifecycle management
5. Implement basic echo test
6. Write WebSocket connection tests

**Deliverables**:
- `message_schema.py` - Message types and validation
- `websocket_handler.py` - WebSocket endpoint
- `test_websocket.py` - Connection tests
- Basic WebSocket working

---

### Phase 2: Voice Activity Detection (Day 2-3)

**Tasks**:
1. Implement energy-based VAD
2. Add speech start/end detection
3. Configure sensitivity thresholds
4. Add VAD state machine
5. Emit VAD events via WebSocket
6. Write VAD unit tests

**Deliverables**:
- `vad.py` - VAD implementation
- `test_vad.py` - VAD tests
- VAD events working in WebSocket

---

### Phase 3: Audio Processing (Day 3-4)

**Tasks**:
1. Implement audio chunk processing
2. Add PCM16 format validation
3. Create streaming STT stub
4. Implement partial transcript generation
5. Add final transcript on speech end
6. Write audio processing tests

**Deliverables**:
- `audio_processor.py` - Audio processing
- `streaming_stt.py` - Streaming STT stub
- `test_audio_processor.py` - Audio tests
- Streaming transcription working

---

### Phase 4: Barge-in Support (Day 4-5)

**Tasks**:
1. Implement barge-in detection
2. Add TTS cancellation logic
3. Signal orchestrator on barge-in
4. Resume listening after barge-in
5. Write barge-in tests

**Deliverables**:
- `barge_in.py` - Barge-in logic
- `test_barge_in.py` - Barge-in tests
- Barge-in working end-to-end

---

### Phase 5: Latency Optimization (Day 5)

**Tasks**:
1. Profile WebSocket latency
2. Optimize audio chunk size
3. Reduce processing overhead
4. Add latency metrics
5. Verify < 250ms target

**Deliverables**:
- Latency < 250ms verified
- Performance metrics added
- Optimization documentation

---

### Phase 6: Testing & Documentation (Day 6)

**Tasks**:
1. Write integration tests (20+ total)
2. Create WebSocket API documentation
3. Add usage examples
4. Write troubleshooting guide
5. Update README

**Deliverables**:
- `WEBSOCKET_API.md` - Complete API docs
- 20+ tests passing
- Integration examples
- Updated README

---

## 📊 Acceptance Criteria

### Performance
- [ ] < 250ms mic → partial transcript locally
- [ ] Backpressure handled without drops
- [ ] Efficient memory usage (< 100MB per connection)

### Functionality
- [ ] VAD detects speech start/end accurately
- [ ] Barge-in cancels TTS immediately
- [ ] Partial transcripts stream in real-time
- [ ] Final transcript on speech end

### Quality
- [ ] 20+ unit tests passing
- [ ] Integration tests passing
- [ ] Message schema documented
- [ ] API documentation complete

### Reliability
- [ ] Graceful connection handling
- [ ] Error recovery working
- [ ] Connection timeout handling
- [ ] No memory leaks

---

## 🧪 Testing Strategy

### Unit Tests (15 tests)
1. Message schema validation
2. WebSocket connection lifecycle
3. VAD speech detection
4. VAD silence detection
5. Audio chunk processing
6. Barge-in detection
7. Error handling
8. Message serialization

### Integration Tests (5 tests)
1. Full streaming STT flow
2. VAD → transcript → speech end
3. Barge-in during TTS
4. Multiple concurrent connections
5. Backpressure handling

### Performance Tests (2 tests)
1. Latency measurement
2. Memory usage under load

---

## 📚 Dependencies

### New Python Packages
```
websockets==12.0
webrtcvad==2.0.10  # For production VAD (optional)
numpy==1.26.0      # For audio processing
```

### Existing Packages
- fastapi (WebSocket support built-in)
- uvicorn (WebSocket support)
- unison_common (logging, tracing)

---

## 🚀 Deployment

### Docker
- Update Dockerfile to include new dependencies
- No port changes (still 8084)
- WebSocket uses same port as HTTP

### Configuration
```env
# WebSocket settings
WS_MAX_CONNECTIONS=100
WS_PING_INTERVAL=30
WS_PING_TIMEOUT=10

# VAD settings
VAD_ENERGY_THRESHOLD=0.01
VAD_SPEECH_PAD_MS=300
VAD_SILENCE_DURATION_MS=700

# Audio settings
AUDIO_CHUNK_MS=100
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
```

---

## 📈 Success Metrics

1. **Latency**: < 250ms (mic → partial transcript)
2. **Accuracy**: VAD 95%+ speech detection
3. **Reliability**: 99%+ uptime
4. **Test Coverage**: 90%+ code coverage
5. **Documentation**: Complete API docs

---

## 🔄 Integration Points

### Orchestrator
- Receives WebSocket connection requests
- Routes audio to io-speech
- Handles barge-in signals
- Manages conversation state

### io-core
- Coordinates I/O streams
- Manages audio routing
- Handles device selection

### Frontend (Future)
- WebSocket client implementation
- Audio capture and streaming
- Transcript display
- Barge-in UI feedback

---

## 📝 Notes

- Start with stub STT implementation (placeholder transcripts)
- Real STT integration (Whisper, etc.) in future phase
- VAD can use simple energy-based detection initially
- WebRTC VAD can be added later for production
- Focus on protocol and architecture first
- Performance optimization can be iterative

---

**Status**: Ready to implement  
**Next**: Start Phase 1 - WebSocket Foundation
