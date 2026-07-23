from message_schema import (
    AudioInputMessage,
    ControlMessage,
    create_transcript_message,
    create_barge_in_message,
    create_modality_status,
    parse_client_message,
)


def test_parse_audio_message():
    msg = {"type": "audio", "data": "dGVzdA==", "timestamp": 1, "sequence": 0}
    parsed = parse_client_message(msg)
    assert isinstance(parsed, AudioInputMessage)
    assert parsed.data == "dGVzdA=="


def test_parse_control_message():
    msg = {"type": "control", "action": "start_listening"}
    parsed = parse_client_message(msg)
    assert isinstance(parsed, ControlMessage)
    assert parsed.action == "start_listening"


def test_parse_invalid_type():
    try:
        parse_client_message({"type": "bad"})
    except ValueError as e:
        assert "Unknown message type" in str(e)
    else:
        raise AssertionError("Expected ValueError for invalid type")


def test_transcript_message_timestamp():
    msg = create_transcript_message("hello", is_final=True, confidence=0.9)
    assert msg.text == "hello"
    assert msg.timestamp > 0


def test_non_voice_output_negotiation_preserves_semantic_actions():
    parsed = parse_client_message(
        {"type": "control", "action": "set_output_modes", "output_modes": ["captions", "visual"]}
    )
    assert parsed.output_modes == ["captions", "visual"]
    status = create_modality_status(parsed.output_modes)
    assert status.active == ["captions", "visual"]
    assert status.fallback == "captions"
    assert status.semantic_actions_preserved is True


def test_barge_in_records_voice_or_explicit_control_reason():
    assert create_barge_in_message(4).reason == "voice"
    assert create_barge_in_message(4, reason="control").reason == "control"
