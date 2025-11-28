# WebSocket Message Schema vs EventEnvelope Schema

**Understanding the relationship between io-speech WebSocket messages and Unison EventEnvelope**

---

## 🎯 TL;DR

**WebSocket Messages** (io-speech) and **EventEnvelope** (platform-wide) serve **different purposes** at **different layers**:

- **WebSocket Messages**: Real-time, low-latency, client ↔ io-speech communication
- **EventEnvelope**: Service-to-service, asynchronous, platform-wide event bus

They are **complementary**, not competing schemas.

---

## 📊 Schema Comparison

### WebSocket Message Schema (io-speech)

**Purpose**: Real-time bidirectional streaming between client and io-speech service

**Location**: `unison-io-speech/src/message_schema.py`

**Message Types**:
```python
# Client → Server
- AudioInputMessage      # Raw audio chunks
- ControlMessage         # start_listening, stop_listening, cancel_tts

# Server → Client
- TranscriptMessage      # Partial/final transcripts
- VADEventMessage        # speech_start, speech_end
- AudioOutputMessage     # TTS audio chunks
- BargeInMessage         # TTS cancellation
- ErrorMessage           # Error notifications
- StatusMessage          # Connection status
```

**Characteristics**:
- ✅ Lightweight (minimal overhead)
- ✅ Real-time (< 250ms latency target)
- ✅ Streaming-focused (audio chunks)
- ✅ Client-facing (WebSocket protocol)
- ✅ Stateful (session-based)

---

### EventEnvelope Schema (Platform-wide)

**Purpose**: Service-to-service communication across the entire Unison platform

**Location**: `unison-docs/dev/specs/schemas/event-envelope.md` (schema) and `unison-common` envelope helpers

**Event Types**:
```python
# Intent Events
- INTENT_RECEIVED, INTENT_PROCESSED, INTENT_DECOMPOSED, INTENT_FAILED

# Context Events
- CONTEXT_UPDATED, CONTEXT_QUERY, CONTEXT_RESPONSE

# I/O Events
- SPEECH_PROCESSED, VISION_PROCESSED, IO_REQUEST, IO_RESPONSE

# System Events
- SERVICE_HEALTH, SERVICE_METRICS, SYSTEM_ALERT
```

**Characteristics**:
- ✅ Comprehensive (full metadata)
- ✅ Traceable (correlation_id, causation_id)
- ✅ Routable (NATS topics)
- ✅ Service-facing (internal platform)
- ✅ Stateless (event-driven)

---

## 🔄 How They Work Together

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Application                       │
│                  (Web, Mobile, Desktop)                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ WebSocket Messages
                            │ (message_schema.py)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   io-speech Service                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  WebSocket Handler                                  │   │
│  │  - Receives audio chunks (AudioInputMessage)        │   │
│  │  - Sends transcripts (TranscriptMessage)            │   │
│  │  - Emits VAD events (VADEventMessage)               │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            │ Converts to EventEnvelope      │
│                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Event Publisher                                    │   │
│  │  - Creates SPEECH_PROCESSED events                  │   │
│  │  - Publishes to NATS (EventEnvelope)                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ EventEnvelope
                            │ (events.py)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    NATS Event Bus                           │
│              (unison.speech.processed)                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator Service                      │
│  - Receives SPEECH_PROCESSED events                         │
│  - Routes to intent processing                              │
│  - Coordinates with other services                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔀 Conversion Flow

### Example: User speaks "hello world"

#### Step 1: Client → io-speech (WebSocket Message)

```json
{
  "type": "audio",
  "data": "base64_encoded_audio...",
  "timestamp": 1699392000000,
  "sequence": 1
}
```

#### Step 2: io-speech processes audio

- VAD detects speech
- STT generates transcript
- WebSocket sends back:

```json
{
  "type": "transcript",
  "text": "hello world",
  "is_final": true,
  "confidence": 0.95,
  "timestamp": 1699392000500
}
```

#### Step 3: io-speech → Platform (EventEnvelope)

```python
event = EventEnvelope(
    event_type=EventType.SPEECH_PROCESSED,
    source_service="unison-io-speech",
    topic="unison.speech.processed",
    correlation_id="<from-websocket-session>",
    data={
        "transcript": "hello world",
        "confidence": 0.95,
        "audio_duration_ms": 1200,
        "language": "en-US"
    },
    metadata={
        "session_id": "<websocket-session-id>",
        "vad_events": ["speech_start", "speech_end"],
        "processing_time_ms": 150
    }
)
```

#### Step 4: Orchestrator receives EventEnvelope

```python
# Orchestrator subscribes to "unison.speech.processed"
async def handle_speech_processed(event: EventEnvelope):
    transcript = event.data["transcript"]
    correlation_id = event.correlation_id
    
    # Process intent
    intent_event = EventEnvelope(
        event_type=EventType.INTENT_RECEIVED,
        source_service="unison-orchestrator",
        topic="unison.intent.received",
        correlation_id=correlation_id,
        causation_id=event.event_id,  # Link back to speech event
        data={
            "expression": transcript,
            "person_id": "<user-id>"
        }
    )
    
    await publish_event(intent_event)
```

---

## 🎯 Key Differences

| Aspect | WebSocket Messages | EventEnvelope |
|--------|-------------------|---------------|
| **Layer** | Client ↔ Service | Service ↔ Service |
| **Protocol** | WebSocket (ws://) | NATS/HTTP |
| **Latency** | Real-time (< 250ms) | Async (seconds) |
| **State** | Stateful (session) | Stateless (event) |
| **Size** | Small (streaming) | Large (complete) |
| **Tracing** | Session-based | correlation_id based |
| **Routing** | Direct connection | Topic-based |
| **Audience** | End users | Internal services |
| **Purpose** | Streaming I/O | Event coordination |

---

## 🔧 Implementation Guidelines

### When to use WebSocket Messages

✅ **Use for**:
- Real-time audio streaming
- Low-latency interactions
- Client-facing APIs
- Streaming data (audio, video)
- Bidirectional communication
- Session-based state

❌ **Don't use for**:
- Service-to-service communication
- Asynchronous processing
- Event sourcing
- Distributed tracing
- Platform-wide coordination

### When to use EventEnvelope

✅ **Use for**:
- Service-to-service events
- Asynchronous workflows
- Event sourcing
- Distributed tracing
- Platform coordination
- Audit trails

❌ **Don't use for**:
- Real-time streaming
- Client-facing APIs
- Low-latency requirements
- Large binary data

---

## 📝 Code Example: Bridging the Two

### io-speech WebSocket Handler (Enhanced)

```python
from message_schema import TranscriptMessage, create_transcript_message
from unison_spec.events import EventEnvelope, EventType

class StreamingSession:
    def __init__(self, websocket: WebSocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.correlation_id = str(uuid.uuid4())  # For EventEnvelope
    
    async def generate_final_transcript(self):
        """Generate final transcript and publish to platform"""
        
        # 1. Send WebSocket message to client
        transcript_text = "hello world"
        ws_message = create_transcript_message(
            text=transcript_text,
            is_final=True,
            confidence=0.95
        )
        await self.send_message(ws_message.dict())
        
        # 2. Publish EventEnvelope to platform
        platform_event = EventEnvelope(
            event_type=EventType.SPEECH_PROCESSED,
            source_service="unison-io-speech",
            source_instance=self.session_id,
            topic="unison.speech.processed",
            correlation_id=self.correlation_id,
            data={
                "transcript": transcript_text,
                "confidence": 0.95,
                "audio_duration_ms": 1200,
                "language": "en-US",
                "is_final": True
            },
            metadata={
                "session_id": self.session_id,
                "vad_state": "speech_end",
                "processing_time_ms": 150,
                "model": "whisper-base"
            }
        )
        
        # Publish to NATS
        await publish_to_nats(platform_event)
```

---

## 🎊 Benefits of This Design

### 1. **Separation of Concerns**
- WebSocket handles real-time streaming
- EventEnvelope handles service coordination

### 2. **Optimal Performance**
- WebSocket: Low latency for user experience
- EventEnvelope: Reliable for service communication

### 3. **Scalability**
- WebSocket: Horizontal scaling of io-speech
- EventEnvelope: Decoupled service architecture

### 4. **Flexibility**
- Can change WebSocket protocol without affecting platform
- Can add new services without changing WebSocket API

### 5. **Traceability**
- WebSocket session_id links to EventEnvelope correlation_id
- Full distributed tracing across both layers

---

## 🔮 Future Enhancements

### Potential Additions

1. **WebSocket → EventEnvelope Mapping**
   ```python
   class WebSocketEventBridge:
       """Bridge WebSocket messages to EventEnvelope"""
       
       def ws_to_event(self, ws_message: ClientMessage) -> EventEnvelope:
           """Convert WebSocket message to EventEnvelope"""
           pass
   ```

2. **EventEnvelope → WebSocket Mapping**
   ```python
   class EventWebSocketBridge:
       """Bridge EventEnvelope to WebSocket messages"""
       
       def event_to_ws(self, event: EventEnvelope) -> ServerMessage:
           """Convert EventEnvelope to WebSocket message"""
           pass
   ```

3. **Unified Tracing**
   ```python
   # Link WebSocket session to EventEnvelope correlation
   ws_session.correlation_id = event.correlation_id
   ```

---

## 📚 Summary

**WebSocket Messages** and **EventEnvelope** are **complementary schemas** that work together:

- **WebSocket**: Client-facing, real-time, streaming layer
- **EventEnvelope**: Service-facing, async, coordination layer

**io-speech** acts as a **bridge**:
1. Receives WebSocket messages from clients
2. Processes audio in real-time
3. Sends WebSocket responses to clients
4. Publishes EventEnvelope events to platform

This design provides:
- ✅ Low latency for users (WebSocket)
- ✅ Reliable coordination for services (EventEnvelope)
- ✅ Clear separation of concerns
- ✅ Optimal performance at each layer

**They don't compete—they collaborate!** 🤝
