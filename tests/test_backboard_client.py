from services.backboard_client import _build_message_content


def test_message_content_includes_transcript():
    content = _build_message_content("Nice weather we're having.", [])
    assert '"Nice weather we\'re having."' in content


def test_message_content_includes_audio_events_when_present():
    content = _build_message_content("Ha!", ["laughter"])
    assert "laughter" in content


def test_message_content_omits_audio_events_line_when_absent():
    content = _build_message_content("hello", [])
    assert "Audio events" not in content


def test_message_content_instructs_json_only_response():
    content = _build_message_content("hello", [])
    assert "JSON object" in content
    assert '"possible_meaning"' in content
    assert '"certainty"' in content
    assert '"image_relevance"' in content
