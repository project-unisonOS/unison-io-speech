import asyncio
from unittest.mock import AsyncMock

from src.message_schema import ControlMessage
from src.websocket_handler import StreamingSession

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)

def run(coroutine):
    return LOOP.run_until_complete(coroutine)


def test_control_barge_in_cancels_tts_and_resumes_listening():
    websocket = AsyncMock()
    session = StreamingSession("phase8", websocket)
    run(session.start_tts_playback(7))
    run(session.handle_control(ControlMessage(action="cancel_tts")))
    assert session.is_speaking is False
    assert session.is_listening is True
    payloads = [call.args[0] for call in websocket.send_json.call_args_list]
    assert {"barge_in", "status"}.issubset({payload["type"] for payload in payloads})
    assert next(payload for payload in payloads if payload["type"] == "barge_in")["reason"] == "control"


def test_caption_only_mode_is_a_first_class_fallback():
    websocket = AsyncMock()
    session = StreamingSession("phase8-caption", websocket)
    run(
        session.handle_control(
            ControlMessage(action="set_output_modes", output_modes=["captions"])
        )
    )
    assert session.output_modes == ["captions"]
    payload = websocket.send_json.call_args.args[0]
    assert payload["fallback"] == "captions"
    assert payload["semantic_actions_preserved"] is True
