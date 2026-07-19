from services.conversation_validator import validate_conversation_turn

VALID = {
    "message": "Was that a coworker, a friend, or family?",
    "conversation_over": False,
}


def test_valid_output_passes_through_and_appends_to_history():
    result = validate_conversation_turn(VALID, thread_id="t1", history=[("user", "hi")])
    assert result.success
    assert result.message == VALID["message"]
    assert result.conversation_over is False
    assert result.thread_id == "t1"
    assert result.history == [("user", "hi"), ("iris", VALID["message"])]


def test_none_raw_produces_fallback_and_keeps_history_unchanged():
    history = [("user", "hi")]
    result = validate_conversation_turn(None, thread_id="t1", history=history, error="boom")
    assert not result.success
    assert result.conversation_over is True
    assert result.error == "boom"
    assert result.history == history


def test_missing_message_produces_fallback():
    raw = {"conversation_over": False}
    result = validate_conversation_turn(raw, thread_id="t1", history=[])
    assert not result.success
    assert "message" in result.error


def test_missing_conversation_over_produces_fallback():
    raw = {"message": "hi"}
    result = validate_conversation_turn(raw, thread_id="t1", history=[])
    assert not result.success
    assert "conversation_over" in result.error


def test_non_string_message_produces_fallback():
    raw = {**VALID, "message": 42}
    result = validate_conversation_turn(raw, thread_id="t1", history=[])
    assert not result.success


def test_empty_message_produces_fallback():
    raw = {**VALID, "message": "   "}
    result = validate_conversation_turn(raw, thread_id="t1", history=[])
    assert not result.success


def test_overlong_message_produces_fallback():
    raw = {**VALID, "message": "x" * 500}
    result = validate_conversation_turn(raw, thread_id="t1", history=[])
    assert not result.success


def test_non_bool_conversation_over_produces_fallback():
    raw = {**VALID, "conversation_over": "false"}
    result = validate_conversation_turn(raw, thread_id="t1", history=[])
    assert not result.success


def test_percentage_confidence_produces_fallback():
    raw = {**VALID, "message": "I am 90% sure that was a coworker."}
    result = validate_conversation_turn(raw, thread_id="t1", history=[])
    assert not result.success


def test_non_dict_raw_produces_fallback():
    result = validate_conversation_turn("not a dict", thread_id="t1", history=[])
    assert not result.success
