"""
Tests for WebSocket handler
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from websocket_handler import WebSocketHandler, StreamingSession


class TestStreamingSession:
    """Tests for StreamingSession"""
    
    def test_session_initialization(self):
        """Test session initializes correctly"""
        session = StreamingSession("test-123")
        assert session.session_id == "test-123"
        assert session.is_active is True
        assert session.audio_buffer == b""
        assert session.transcript_buffer == ""
    
    def test_session_add_audio(self):
        """Test adding audio to session"""
        session = StreamingSession("test-123")
        session.add_audio(b"audio_data")
        assert session.audio_buffer == b"audio_data"
    
    def test_session_clear_buffer(self):
        """Test clearing audio buffer"""
        session = StreamingSession("test-123")
        session.add_audio(b"audio_data")
        session.clear_buffer()
        assert session.audio_buffer == b""
    
    def test_session_deactivate(self):
        """Test deactivating session"""
        session = StreamingSession("test-123")
        session.deactivate()
        assert session.is_active is False


class TestWebSocketHandler:
    """Tests for WebSocketHandler"""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance"""
        return WebSocketHandler()
    
    def test_handler_initialization(self, handler):
        """Test handler initializes correctly"""
        assert handler.active_sessions == {}
        assert hasattr(handler, 'vad')
    
    def test_create_session(self, handler):
        """Test creating a new session"""
        session_id = handler.create_session()
        assert session_id in handler.active_sessions
        assert handler.active_sessions[session_id].is_active
    
    def test_get_session(self, handler):
        """Test getting existing session"""
        session_id = handler.create_session()
        session = handler.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id
    
    def test_get_nonexistent_session(self, handler):
        """Test getting non-existent session"""
        session = handler.get_session("nonexistent")
        assert session is None
    
    def test_close_session(self, handler):
        """Test closing a session"""
        session_id = handler.create_session()
        handler.close_session(session_id)
        assert session_id not in handler.active_sessions
    
    def test_multiple_sessions(self, handler):
        """Test handling multiple sessions"""
        session1 = handler.create_session()
        session2 = handler.create_session()
        
        assert session1 != session2
        assert len(handler.active_sessions) == 2
    
    @pytest.mark.asyncio
    async def test_handle_audio_chunk(self, handler):
        """Test handling audio chunk"""
        session_id = handler.create_session()
        
        # Mock WebSocket
        websocket = AsyncMock()
        
        message = {
            "type": "audio_chunk",
            "audio": "dGVzdA==",  # base64 "test"
            "sequence": 1
        }
        
        await handler.handle_message(websocket, message, session_id)
        
        # Session should have audio data
        session = handler.get_session(session_id)
        assert len(session.audio_buffer) > 0
    
    @pytest.mark.asyncio
    async def test_handle_start_stream(self, handler):
        """Test handling start stream"""
        session_id = handler.create_session()
        websocket = AsyncMock()
        
        message = {
            "type": "start_stream",
            "config": {
                "sample_rate": 16000,
                "encoding": "pcm"
            }
        }
        
        await handler.handle_message(websocket, message, session_id)
        
        # Should send ready message
        websocket.send_json.assert_called_once()
        call_args = websocket.send_json.call_args[0][0]
        assert call_args["type"] == "ready"
    
    @pytest.mark.asyncio
    async def test_handle_end_stream(self, handler):
        """Test handling end stream"""
        session_id = handler.create_session()
        websocket = AsyncMock()
        
        message = {"type": "end_stream"}
        
        await handler.handle_message(websocket, message, session_id)
        
        # Session should be deactivated
        session = handler.get_session(session_id)
        if session:
            assert session.is_active is False
    
    @pytest.mark.asyncio
    async def test_handle_cancel(self, handler):
        """Test handling cancel"""
        session_id = handler.create_session()
        websocket = AsyncMock()
        
        message = {"type": "cancel"}
        
        await handler.handle_message(websocket, message, session_id)
        
        # Session should be cleaned up
        session = handler.get_session(session_id)
        assert session is None or not session.is_active


class TestWebSocketIntegration:
    """Integration tests for WebSocket flow"""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance"""
        return WebSocketHandler()
    
    @pytest.mark.asyncio
    async def test_complete_streaming_flow(self, handler):
        """Test complete streaming flow"""
        websocket = AsyncMock()
        session_id = handler.create_session()
        
        # 1. Start stream
        await handler.handle_message(
            websocket,
            {
                "type": "start_stream",
                "config": {"sample_rate": 16000}
            },
            session_id
        )
        
        # 2. Send audio chunks
        for i in range(5):
            await handler.handle_message(
                websocket,
                {
                    "type": "audio_chunk",
                    "audio": "dGVzdA==",
                    "sequence": i
                },
                session_id
            )
        
        # 3. End stream
        await handler.handle_message(
            websocket,
            {"type": "end_stream"},
            session_id
        )
        
        # Should have sent multiple messages
        assert websocket.send_json.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_barge_in_scenario(self, handler):
        """Test barge-in (cancel during speech)"""
        websocket = AsyncMock()
        session_id = handler.create_session()
        
        # Start stream
        await handler.handle_message(
            websocket,
            {"type": "start_stream", "config": {}},
            session_id
        )
        
        # Send some audio
        await handler.handle_message(
            websocket,
            {"type": "audio_chunk", "audio": "dGVzdA==", "sequence": 1},
            session_id
        )
        
        # Cancel (barge-in)
        await handler.handle_message(
            websocket,
            {"type": "cancel"},
            session_id
        )
        
        # Session should be cleaned up
        session = handler.get_session(session_id)
        assert session is None or not session.is_active


class TestErrorHandling:
    """Tests for error handling"""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance"""
        return WebSocketHandler()
    
    @pytest.mark.asyncio
    async def test_invalid_message_type(self, handler):
        """Test handling invalid message type"""
        websocket = AsyncMock()
        session_id = handler.create_session()
        
        message = {"type": "invalid_type"}
        
        await handler.handle_message(websocket, message, session_id)
        
        # Should send error message
        websocket.send_json.assert_called()
        call_args = websocket.send_json.call_args[0][0]
        assert call_args["type"] == "error"
    
    @pytest.mark.asyncio
    async def test_missing_session(self, handler):
        """Test handling message with missing session"""
        websocket = AsyncMock()
        
        message = {"type": "audio_chunk", "audio": "dGVzdA==", "sequence": 1}
        
        await handler.handle_message(websocket, message, "nonexistent")
        
        # Should handle gracefully
        websocket.send_json.assert_called()
    
    @pytest.mark.asyncio
    async def test_malformed_audio(self, handler):
        """Test handling malformed audio data"""
        websocket = AsyncMock()
        session_id = handler.create_session()
        
        message = {
            "type": "audio_chunk",
            "audio": "not_base64!!!",
            "sequence": 1
        }
        
        await handler.handle_message(websocket, message, session_id)
        
        # Should handle error
        websocket.send_json.assert_called()


class TestSessionManagement:
    """Tests for session management"""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance"""
        return WebSocketHandler()
    
    def test_session_cleanup(self, handler):
        """Test cleaning up old sessions"""
        # Create multiple sessions
        sessions = [handler.create_session() for _ in range(5)]
        
        # Close some sessions
        for session_id in sessions[:3]:
            handler.close_session(session_id)
        
        # Should have 2 active sessions
        assert len(handler.active_sessions) == 2
    
    def test_session_isolation(self, handler):
        """Test that sessions are isolated"""
        session1 = handler.create_session()
        session2 = handler.create_session()
        
        # Add audio to session1
        s1 = handler.get_session(session1)
        s1.add_audio(b"audio1")
        
        # Session2 should not have this audio
        s2 = handler.get_session(session2)
        assert s2.audio_buffer != b"audio1"
