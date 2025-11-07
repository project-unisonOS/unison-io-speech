"""
Tests for WebSocket message schema
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from message_schema import (
    ClientMessage,
    parse_client_message,
    create_transcript_message,
    create_error_message,
    create_vad_event,
    create_status_message,
    validate_audio_data
)


class TestClientMessages:
    """Tests for client message parsing"""
    
    def test_parse_audio_chunk(self):
        """Test parsing audio chunk message"""
        msg = {
            "type": "audio_chunk",
            "audio": "dGVzdA==",
            "sequence": 1
        }
        parsed = parse_client_message(msg)
        assert parsed.type == MessageType.AUDIO_CHUNK
        assert parsed.audio == "dGVzdA=="
        assert parsed.sequence == 1
    
    def test_parse_start_stream(self):
        """Test parsing start stream message"""
        msg = {
            "type": "start_stream",
            "config": {
                "sample_rate": 16000,
                "encoding": "pcm"
            }
        }
        parsed = parse_client_message(msg)
        assert parsed.type == MessageType.START_STREAM
        assert parsed.config["sample_rate"] == 16000
    
    def test_parse_end_stream(self):
        """Test parsing end stream message"""
        msg = {"type": "end_stream"}
        parsed = parse_client_message(msg)
        assert parsed.type == MessageType.END_STREAM
    
    def test_parse_cancel(self):
        """Test parsing cancel message"""
        msg = {"type": "cancel"}
        parsed = parse_client_message(msg)
        assert parsed.type == MessageType.CANCEL
    
    def test_parse_invalid_type(self):
        """Test parsing message with invalid type"""
        msg = {"type": "invalid_type"}
        with pytest.raises(ValueError, match="Invalid message type"):
            parse_client_message(msg)
    
    def test_parse_missing_type(self):
        """Test parsing message without type"""
        msg = {"audio": "test"}
        with pytest.raises(ValueError, match="Missing 'type'"):
            parse_client_message(msg)
    
    def test_parse_audio_chunk_missing_audio(self):
        """Test audio chunk without audio data"""
        msg = {"type": "audio_chunk", "sequence": 1}
        with pytest.raises(ValueError, match="Missing 'audio'"):
            parse_client_message(msg)


class TestServerMessages:
    """Tests for server message creation"""
    
    def test_create_partial_transcript(self):
        """Test creating partial transcript message"""
        msg = create_transcript_message(
            text="hello",
            is_final=False,
            confidence=0.8
        )
        assert msg.text == "hello"
        assert msg.is_final is False
        assert msg.confidence == 0.8
        assert msg.timestamp_ms > 0
    
    def test_create_final_transcript(self):
        """Test creating final transcript message"""
        msg = create_transcript_message(
            text="hello world",
            is_final=True,
            confidence=0.95
        )
        assert msg.text == "hello world"
        assert msg.is_final is True
        assert msg.confidence == 0.95
    
    def test_create_speech_start(self):
        """Test creating speech start message"""
        msg = create_vad_event("speech_start", energy=0.5)
        assert msg.event == "speech_start"
        assert msg.energy == 0.5
        assert msg.timestamp_ms > 0
    
    def test_create_speech_end(self):
        """Test creating speech end message"""
        msg = create_vad_event("speech_end", energy=0.1)
        assert msg.event == "speech_end"
        assert msg.energy == 0.1
    
    def test_create_error_message(self):
        """Test creating error message"""
        msg = create_error_message(
            code="invalid_audio",
            message="Invalid audio format"
        )
        assert msg.code == "invalid_audio"
        assert msg.message == "Invalid audio format"
    
    def test_create_status_message(self):
        """Test creating status message"""
        msg = create_status_message("listening")
        assert msg.status == "listening"
        assert msg.timestamp_ms > 0


class TestMessageValidation:
    """Tests for message validation"""
    
    def test_validate_audio_chunk_sequence(self):
        """Test audio chunk sequence validation"""
        msg = {
            "type": "audio_chunk",
            "audio": "dGVzdA==",
            "sequence": 1
        }
        parsed = parse_client_message(msg)
        assert parsed.sequence == 1
    
    def test_validate_config_structure(self):
        """Test config structure validation"""
        msg = {
            "type": "start_stream",
            "config": {
                "sample_rate": 16000,
                "encoding": "pcm",
                "channels": 1
            }
        }
        parsed = parse_client_message(msg)
        assert "sample_rate" in parsed.config
        assert "encoding" in parsed.config
    
    def test_validate_audio_data(self):
        """Test audio data validation"""
        # Valid base64
        assert validate_audio_data("dGVzdA==") is True
        
        # Invalid base64
        assert validate_audio_data("not_base64!!!") is False
    
    def test_validate_empty_audio(self):
        """Test validation of empty audio"""
        assert validate_audio_data("") is False
