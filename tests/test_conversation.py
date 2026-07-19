from models import InterpretationResult
from services import conversation


def _interpretation(thread_id="t0"):
    return InterpretationResult(
        heard="Nice weather we're having.",
        possible_meaning="They may be joking.",
        why="Context suggests irony.",
        certainty="medium",
        alternative=None,
        visual_context_used=False,
        spoken_summary="They may be joking.",
        thread_id=thread_id,
        success=True,
    )


def test_mock_mode_start_conversation_used_when_conversation_assistant_missing(monkeypatch):
    monkeypatch.setattr(
        "services.conversation.load_config",
        lambda: _FakeConfig(api_key="", conversation_assistant_id=""),
    )

    result = conversation.start_conversation(_interpretation())

    assert result.success
    assert "mock" in result.message.lower()
    assert result.conversation_over is False
    assert result.history == [("iris", result.message)]


def test_mock_mode_continue_conversation_terminates_on_second_turn(monkeypatch):
    monkeypatch.setattr(
        "services.conversation.load_config",
        lambda: _FakeConfig(api_key="", conversation_assistant_id=""),
    )

    opening = conversation.start_conversation(_interpretation())
    result = conversation.continue_conversation("a coworker", opening.thread_id, opening.history)

    assert result.success
    assert result.conversation_over is True
    assert result.history[-2] == ("user", "a coworker")
    assert result.history[-1] == ("iris", result.message)


def test_real_start_path_used_when_configured(monkeypatch):
    monkeypatch.setattr(
        "services.conversation.load_config",
        lambda: _FakeConfig(api_key="key", conversation_assistant_id="conv-asst-1"),
    )
    monkeypatch.setattr(
        "services.conversation.backboard_client.create_thread", lambda assistant_id: "thread-1"
    )
    monkeypatch.setattr(
        "services.conversation.backboard_client.send_conversation_start",
        lambda recap, thread_id, assistant_id: {
            "message": "Who were you talking to?",
            "conversation_over": False,
        },
    )

    result = conversation.start_conversation(_interpretation())

    assert result.success
    assert result.message == "Who were you talking to?"
    assert result.thread_id == "thread-1"


def test_real_continue_path_used_when_configured(monkeypatch):
    monkeypatch.setattr(
        "services.conversation.load_config",
        lambda: _FakeConfig(api_key="key", conversation_assistant_id="conv-asst-1"),
    )
    monkeypatch.setattr(
        "services.conversation.backboard_client.send_conversation_reply",
        lambda history, thread_id, assistant_id: {
            "message": "Thanks, that helps.",
            "conversation_over": True,
        },
    )

    result = conversation.continue_conversation("a coworker", "thread-1", [("iris", "Who?")])

    assert result.success
    assert result.conversation_over is True
    assert result.history == [("iris", "Who?"), ("user", "a coworker"), ("iris", "Thanks, that helps.")]


def test_backboard_error_on_create_thread_produces_fallback_not_crash(monkeypatch):
    from services.backboard_client import BackboardError

    monkeypatch.setattr(
        "services.conversation.load_config",
        lambda: _FakeConfig(api_key="key", conversation_assistant_id="conv-asst-1"),
    )

    def _boom(assistant_id):
        raise BackboardError("network down")

    monkeypatch.setattr("services.conversation.backboard_client.create_thread", _boom)

    result = conversation.start_conversation(_interpretation())

    assert not result.success
    assert result.conversation_over is True


def test_backboard_error_on_send_produces_fallback_not_crash(monkeypatch):
    from services.backboard_client import BackboardError

    monkeypatch.setattr(
        "services.conversation.load_config",
        lambda: _FakeConfig(api_key="key", conversation_assistant_id="conv-asst-1"),
    )

    def _boom(history, thread_id, assistant_id):
        raise BackboardError("network down")

    monkeypatch.setattr("services.conversation.backboard_client.send_conversation_reply", _boom)

    result = conversation.continue_conversation("a coworker", "thread-1", [])

    assert not result.success
    assert result.conversation_over is True


class _FakeConfig:
    def __init__(self, api_key: str, conversation_assistant_id: str):
        self.backboard_api_key = api_key
        self.backboard_conversation_assistant_id = conversation_assistant_id
