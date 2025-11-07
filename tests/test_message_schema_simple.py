"""
Simple tests for WebSocket message schema
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from message_schema import (
    parse_client_message,
    create_transcript_message,
    create_error_message,
    create_vad_event,
    create_status_message,
    validate_audio_data
)


class TestClientMessageParsing:
    """Tests for client message parsing"""
    
    def test_parse_audio_message(self):
        """Test parsing audio message"""
        msg = {
            "type": "audio",
            "data": "dGVzdA==",
            "timestamp": 1234567890,
            "sequence": 1
        }
        parsed = parse_client_message(msg)
        assert parsed.type == "audio"
        assert parsed.data == "dGVzdA=="
        assert parsed.sequence == 1
    
    def test_parse_control_message(self):
        """Test parsing control message"""
        msg = {
            "type": "control",
            "action": "start_listening"
        }
        parsed = parse_client_message(msg)
        assert parsed.type == "control"
        assert parsed.action == "start_listening"
    
    def test_parse_unknown_type_raises_error(self):
        """Test that unknown type raises error"""
        msg = {"type": "unknown"}
        with pytest.raises(ValueError, match="Unknown message type"):
            parse_client_message(msg)


class TestServerMessageCreation:
    """Tests for server message creation"""
    
    def test_create_transcript_final(self):
        """Test creating final transcript"""
        msg = create_transcript_message(
            text="hello world",
            is_final=True,
            confidence=0.95
        )
        assert msg.text == "hello world"
        assert msg.is_final is True
        assert msg.confidence == 0.95
    
    def test_create_transcript_partial(self):
        """Test creating partial transcript"""
        msg = create_transcript_message(
            text="hello",
            is_final=False,
            confidence=0.8
        )
        assert msg.text == "hello"
        assert msg.is_final is False
    
    def test_create_vad_speech_start(self):
        """Test creating speech start event"""
        msg = create_vad_event("speech_start", energy=0.5)
        assert msg.event == "speech_start"
        assert msg.energy == 0.5
    
    def test_create_vad_speech_end(self):
        """Test creating speech end event"""
        msg = create_vad_event("speech_end", energy=0.1)
        assert msg.event == "speech_end"
    
    def test_create_error(self):
        """Test creating error message"""
        msg = create_error_message(
            code="invalid_audio",
            message="Invalid format"
        )
        assert msg.code == "invalid_audio"
        assert msg.message == "Invalid format"
    
    def test_create_status(self):
        """Test creating status message"""
        msg = create_status_message("listening")
        assert msg.status == "listening"


class TestAudioValidation:
    """Tests for audio validation"""
    
    def test_validate_valid_base64(self):
        """Test validating valid base64"""
        assert validate_audio_data("dGVzdA==") is True
    
    def test_validate_invalid_base64(self):
        """Test validating invalid base64"""
        assert validate_audio_data("not_base64!!!") is False
    
    def test_validate_empty_audio(self):
        """Test validating empty audio"""
        assert validate_audio_data("") is False
