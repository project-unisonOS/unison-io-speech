# WebSocket Streaming API - io-speech

**Version**: 1.0  
**Endpoint**: `ws://localhost:8083/stream`  
**Protocol**: WebSocket with JSON messages  
**Audio Format**: PCM16, 16kHz, mono

---

## 📋 Overview

The io-speech WebSocket API provides real-time bidirectional audio streaming for speech-to-text (STT) with Voice Activity Detection (VAD) and barge-in support.

### Key Features

- ✅ **Real-time Streaming**: Low-latency audio streaming
- ✅ **Voice Activity Detection**: Automatic speech start/end detection
- ✅ **Partial Transcripts**: Interim results during speech
- ✅ **Final Transcripts**: Complete transcription on speech end
- ✅ **Barge-in Support**: Cancel TTS playback on user speech
- ✅ **Session Management**: Multiple concurrent sessions

---

## 🔌 Connection

### Establishing Connection

```javascript
const ws = new WebSocket('ws://localhost:8083/stream');

ws.onopen = () => {
    console.log('Connected to io-speech');
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    handleServerMessage(message);
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('Disconnected from io-speech');
};
```

### Connection Parameters

- **URL**: `ws://localhost:8083/stream`
- **Protocol**: WebSocket (RFC 6455)
- **Subprotocol**: None
- **Headers**: Standard WebSocket headers

---

## 📤 Client → Server Messages

### 1. Audio Input Message

Send audio data for transcription.

**Type**: `audio`

```json
{
    "type": "audio",
    "data": "base64_encoded_pcm16_audio",
    "timestamp": 1699372800000,
    "sequence": 1
}
```

**Fields**:
- `type` (string): Always `"audio"`
- `data` (string): Base64-encoded PCM16 audio data
- `timestamp` (integer): Client timestamp in milliseconds
- `sequence` (integer): Sequence number for ordering (starts at 1)

**Audio Format**:
- **Encoding**: PCM16 (16-bit signed integer)
- **Sample Rate**: 16000 Hz
- **Channels**: 1 (mono)
- **Byte Order**: Little-endian

**Example**:
```javascript
// Capture audio from microphone
const audioData = captureAudio(); // Returns ArrayBuffer
const base64Audio = btoa(String.fromCharCode(...new Uint8Array(audioData)));

ws.send(JSON.stringify({
    type: 'audio',
    data: base64Audio,
    timestamp: Date.now(),
    sequence: sequenceNumber++
}));
```

---

### 2. Control Message

Send control commands to manage the session.

**Type**: `control`

```json
{
    "type": "control",
    "action": "start_listening",
    "timestamp": 1699372800000
}
```

**Fields**:
- `type` (string): Always `"control"`
- `action` (string): One of:
  - `"start_listening"` - Start listening for speech
  - `"stop_listening"` - Stop listening
  - `"cancel_tts"` - Cancel TTS playback (barge-in)
- `timestamp` (integer, optional): Client timestamp in milliseconds

**Actions**:

#### start_listening
Begin listening for speech input.

```json
{
    "type": "control",
    "action": "start_listening"
}
```

#### stop_listening
Stop listening and finalize any pending transcription.

```json
{
    "type": "control",
    "action": "stop_listening"
}
```

#### cancel_tts
Cancel ongoing TTS playback (barge-in).

```json
{
    "type": "control",
    "action": "cancel_tts"
}
```

---

## 📥 Server → Client Messages

### 1. Transcript Message

Transcription result (partial or final).

**Type**: `transcript`

```json
{
    "type": "transcript",
    "text": "hello world",
    "is_final": true,
    "confidence": 0.95,
    "timestamp": 1699372800000
}
```

**Fields**:
- `type` (string): Always `"transcript"`
- `text` (string): Transcribed text
- `is_final` (boolean): 
  - `true` - Final transcript (speech ended)
  - `false` - Partial transcript (speech ongoing)
- `confidence` (float): Confidence score (0.0 to 1.0)
- `timestamp` (integer): Server timestamp in milliseconds

**Example Flow**:
```
Client sends audio → Server sends partial transcripts → Speech ends → Server sends final transcript
```

---

### 2. VAD Event Message

Voice Activity Detection events.

**Type**: `vad_event`

```json
{
    "type": "vad_event",
    "event": "speech_start",
    "energy": 0.45,
    "timestamp": 1699372800000
}
```

**Fields**:
- `type` (string): Always `"vad_event"`
- `event` (string): One of:
  - `"speech_start"` - Speech detected
  - `"speech_end"` - Speech ended (silence detected)
- `energy` (float, optional): Audio energy level (0.0 to 1.0)
- `timestamp` (integer): Server timestamp in milliseconds

**Events**:

#### speech_start
Triggered when speech is detected.

```json
{
    "type": "vad_event",
    "event": "speech_start",
    "energy": 0.45,
    "timestamp": 1699372800000
}
```

#### speech_end
Triggered when speech ends (silence detected).

```json
{
    "type": "vad_event",
    "event": "speech_end",
    "energy": 0.05,
    "timestamp": 1699372800000
}
```

---

### 3. Barge-in Message

Notification that TTS was cancelled due to user speech.

**Type**: `barge_in`

```json
{
    "type": "barge_in",
    "cancelled_sequence": 42,
    "timestamp": 1699372800000
}
```

**Fields**:
- `type` (string): Always `"barge_in"`
- `cancelled_sequence` (integer): Sequence number of cancelled TTS
- `timestamp` (integer): Server timestamp in milliseconds

---

### 4. Error Message

Error notification.

**Type**: `error`

```json
{
    "type": "error",
    "code": "invalid_audio",
    "message": "Invalid audio format",
    "timestamp": 1699372800000
}
```

**Fields**:
- `type` (string): Always `"error"`
- `code` (string): Error code
- `message` (string): Human-readable error message
- `timestamp` (integer): Server timestamp in milliseconds

**Error Codes**:
- `invalid_audio` - Invalid audio format or encoding
- `rate_limit` - Too many requests
- `internal_error` - Server error
- `session_expired` - Session timed out
- `invalid_message` - Malformed message

---

### 5. Status Message

Session status updates.

**Type**: `status`

```json
{
    "type": "status",
    "status": "listening",
    "timestamp": 1699372800000
}
```

**Fields**:
- `type` (string): Always `"status"`
- `status` (string): One of:
  - `"connected"` - Connection established
  - `"listening"` - Listening for speech
  - `"processing"` - Processing audio
  - `"speaking"` - TTS playing
- `timestamp` (integer): Server timestamp in milliseconds

---

## 🔄 Message Flow Examples

### Example 1: Basic Speech Recognition

```
Client                          Server
  |                               |
  |--- connect ------------------>|
  |<-- status: connected ---------|
  |                               |
  |--- control: start_listening ->|
  |<-- status: listening ---------|
  |                               |
  |--- audio chunk 1 ------------>|
  |--- audio chunk 2 ------------>|
  |<-- vad_event: speech_start ---|
  |--- audio chunk 3 ------------>|
  |<-- transcript: "hello" -------|  (partial, is_final: false)
  |--- audio chunk 4 ------------>|
  |<-- transcript: "hello wo..." -|  (partial, is_final: false)
  |--- audio chunk 5 ------------>|
  |<-- vad_event: speech_end -----|
  |<-- transcript: "hello world" -|  (final, is_final: true)
  |                               |
```

### Example 2: Barge-in Scenario

```
Client                          Server
  |                               |
  |<-- status: speaking ----------|  (TTS playing)
  |                               |
  |--- audio chunk 1 ------------>|  (User starts speaking)
  |<-- vad_event: speech_start ---|
  |<-- barge_in: seq=42 ----------|  (TTS cancelled)
  |<-- status: listening ---------|
  |--- audio chunk 2 ------------>|
  |<-- transcript: "stop" --------|  (partial)
  |--- audio chunk 3 ------------>|
  |<-- vad_event: speech_end -----|
  |<-- transcript: "stop" --------|  (final)
  |                               |
```

### Example 3: Error Handling

```
Client                          Server
  |                               |
  |--- audio chunk (invalid) ---->|
  |<-- error: invalid_audio ------|
  |                               |
  |--- audio chunk (valid) ------>|
  |<-- transcript: "hello" -------|
  |                               |
```

---

## 💻 Client Implementation Examples

### JavaScript/TypeScript

```typescript
class SpeechClient {
    private ws: WebSocket;
    private sequence: number = 1;
    
    constructor(url: string) {
        this.ws = new WebSocket(url);
        this.setupHandlers();
    }
    
    private setupHandlers() {
        this.ws.onopen = () => {
            console.log('Connected');
            this.startListening();
        };
        
        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            this.handleMessage(msg);
        };
    }
    
    startListening() {
        this.send({
            type: 'control',
            action: 'start_listening'
        });
    }
    
    sendAudio(audioData: ArrayBuffer) {
        const base64 = this.arrayBufferToBase64(audioData);
        this.send({
            type: 'audio',
            data: base64,
            timestamp: Date.now(),
            sequence: this.sequence++
        });
    }
    
    bargeIn() {
        this.send({
            type: 'control',
            action: 'cancel_tts'
        });
    }
    
    private handleMessage(msg: any) {
        switch (msg.type) {
            case 'transcript':
                if (msg.is_final) {
                    console.log('Final:', msg.text);
                } else {
                    console.log('Partial:', msg.text);
                }
                break;
            case 'vad_event':
                console.log('VAD:', msg.event);
                break;
            case 'error':
                console.error('Error:', msg.message);
                break;
        }
    }
    
    private send(data: any) {
        this.ws.send(JSON.stringify(data));
    }
    
    private arrayBufferToBase64(buffer: ArrayBuffer): string {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }
}

// Usage
const client = new SpeechClient('ws://localhost:8083/stream');
```

### Python

```python
import asyncio
import websockets
import json
import base64

async def speech_client():
    uri = "ws://localhost:8083/stream"
    sequence = 1
    
    async with websockets.connect(uri) as websocket:
        # Start listening
        await websocket.send(json.dumps({
            "type": "control",
            "action": "start_listening"
        }))
        
        # Send audio
        audio_data = capture_audio()  # Your audio capture function
        await websocket.send(json.dumps({
            "type": "audio",
            "data": base64.b64encode(audio_data).decode('utf-8'),
            "timestamp": int(time.time() * 1000),
            "sequence": sequence
        }))
        sequence += 1
        
        # Receive messages
        async for message in websocket:
            msg = json.loads(message)
            
            if msg['type'] == 'transcript':
                if msg['is_final']:
                    print(f"Final: {msg['text']}")
                else:
                    print(f"Partial: {msg['text']}")
            
            elif msg['type'] == 'vad_event':
                print(f"VAD: {msg['event']}")
            
            elif msg['type'] == 'error':
                print(f"Error: {msg['message']}")

# Run
asyncio.run(speech_client())
```

---

## ⚙️ Configuration

### Audio Settings

```javascript
const audioConfig = {
    sampleRate: 16000,      // Hz
    channels: 1,            // Mono
    bitsPerSample: 16,      // PCM16
    encoding: 'pcm',        // PCM format
    chunkSize: 1600         // Samples per chunk (100ms at 16kHz)
};
```

### VAD Settings

Default VAD configuration (server-side):
- **Energy Threshold**: 0.01
- **Speech Pad**: 300ms
- **Silence Duration**: 500ms
- **Sample Rate**: 16000 Hz

---

## 🔒 Best Practices

### 1. Audio Chunking

Send audio in small chunks (100-200ms) for low latency:

```javascript
const CHUNK_SIZE = 1600; // 100ms at 16kHz
const CHUNK_INTERVAL = 100; // ms

setInterval(() => {
    const chunk = captureAudioChunk(CHUNK_SIZE);
    client.sendAudio(chunk);
}, CHUNK_INTERVAL);
```

### 2. Sequence Numbers

Always increment sequence numbers:

```javascript
let sequence = 1;
function sendAudio(data) {
    ws.send(JSON.stringify({
        type: 'audio',
        data: data,
        timestamp: Date.now(),
        sequence: sequence++
    }));
}
```

### 3. Error Handling

Handle all error cases:

```javascript
ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    reconnect();
};

ws.onclose = (event) => {
    if (!event.wasClean) {
        console.error('Connection lost');
        reconnect();
    }
};
```

### 4. Barge-in

Detect speech start and cancel TTS immediately:

```javascript
function handleMessage(msg) {
    if (msg.type === 'vad_event' && msg.event === 'speech_start') {
        if (isTTSPlaying) {
            ws.send(JSON.stringify({
                type: 'control',
                action: 'cancel_tts'
            }));
        }
    }
}
```

---

## 📊 Performance Characteristics

### Latency

- **Target**: < 250ms mic → partial transcript
- **Typical**: 150-200ms
- **Network**: Depends on connection quality

### Throughput

- **Audio Rate**: 32 KB/s (16kHz PCM16 mono)
- **Message Rate**: ~10 messages/second
- **Bandwidth**: ~40 KB/s with overhead

### Limits

- **Max Connections**: 100 concurrent
- **Max Audio Length**: 60 seconds per utterance
- **Max Message Size**: 64 KB
- **Session Timeout**: 5 minutes idle

---

## 🐛 Troubleshooting

### Connection Issues

**Problem**: Cannot connect to WebSocket

**Solutions**:
- Check server is running: `curl http://localhost:8083/health`
- Verify URL: `ws://localhost:8083/stream`
- Check firewall settings

### Audio Issues

**Problem**: No transcription received

**Solutions**:
- Verify audio format (PCM16, 16kHz, mono)
- Check base64 encoding
- Ensure audio has sufficient energy
- Send control: start_listening

### VAD Issues

**Problem**: Speech not detected

**Solutions**:
- Increase microphone volume
- Check audio energy levels
- Reduce background noise
- Adjust VAD threshold (server-side)

---

## 📚 Additional Resources

- **API Reference**: `/docs` (FastAPI auto-generated)
- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics`
- **Sessions**: `GET /sessions` (monitoring)

---

## 🔄 Version History

### v1.0 (Current)
- Initial WebSocket streaming API
- VAD support
- Barge-in support
- Session management

---

**Last Updated**: November 7, 2025  
**Maintained By**: Unison Platform Team
