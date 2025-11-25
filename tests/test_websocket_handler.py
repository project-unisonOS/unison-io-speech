import asyncio
from unittest.mock import AsyncMock

from src.websocket_handler import WebSocketHandler


def test_create_and_get_session():
    handler = WebSocketHandler()
    session_id = handler.create_session()
    session = handler.get_session(session_id)
    assert session is not None
    assert session.session_id == session_id


def test_close_session():
    handler = WebSocketHandler()
    session_id = handler.create_session()
    handler.close_session(session_id)
    assert handler.get_session(session_id) is None


def test_handle_start_stream_sends_ready():
    handler = WebSocketHandler()
    websocket = AsyncMock()
    session_id = handler.create_session()
    asyncio.get_event_loop().run_until_complete(
        handler.handle_message(websocket, {"type": "start_stream"}, session_id)
    )
    websocket.send_json.assert_called()
