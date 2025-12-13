from src.websocket_handler import WebSocketManager


class _WS:
    def __init__(self):
        self.headers = {"x-trace-id": "trace-123"}
        self.query_params = {"person_id": "p1"}


def test_websocket_manager_extracts_trace_and_person_id():
    mgr = WebSocketManager()
    session = mgr.create_session(_WS())  # type: ignore[arg-type]
    assert session.trace_id == "trace-123"
    assert session.person_id == "p1"

