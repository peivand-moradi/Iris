from services.backboard_client import (
    _build_conversation_reply_content,
    _build_conversation_start_content,
    _build_message_content,
    create_thread,
)


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
    assert '"visual_description"' in content


def test_conversation_start_content_includes_recap_and_schema():
    content = _build_conversation_start_content("Heard: \"hi\"\nPossible meaning: greeting")
    assert "Possible meaning: greeting" in content
    assert "JSON object" in content
    assert '"message"' in content
    assert '"conversation_over"' in content


def test_conversation_reply_content_includes_history_and_schema():
    content = _build_conversation_reply_content([("iris", "Who were you talking to?"), ("user", "a coworker")])
    assert "Iris: Who were you talking to?" in content
    assert "User: a coworker" in content
    assert '"message"' in content
    assert '"conversation_over"' in content


def test_create_thread_uses_explicit_assistant_id_when_given(monkeypatch):
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"thread_id": "t1"}

    def _fake_post(url, json, headers, timeout):
        captured["url"] = url
        return _FakeResponse()

    monkeypatch.setattr(
        "services.backboard_client.load_config",
        lambda: _FakeConfig(assistant_id="default-asst", base_url="https://example.test/api"),
    )
    monkeypatch.setattr("services.backboard_client.requests.post", _fake_post)

    thread_id = create_thread(assistant_id="explicit-asst")

    assert thread_id == "t1"
    assert captured["url"] == "https://example.test/api/assistants/explicit-asst/threads"


def test_create_thread_defaults_to_config_assistant_id(monkeypatch):
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"thread_id": "t1"}

    def _fake_post(url, json, headers, timeout):
        captured["url"] = url
        return _FakeResponse()

    monkeypatch.setattr(
        "services.backboard_client.load_config",
        lambda: _FakeConfig(assistant_id="default-asst", base_url="https://example.test/api"),
    )
    monkeypatch.setattr("services.backboard_client.requests.post", _fake_post)

    thread_id = create_thread()

    assert thread_id == "t1"
    assert captured["url"] == "https://example.test/api/assistants/default-asst/threads"


class _FakeConfig:
    def __init__(self, assistant_id: str, base_url: str):
        self.backboard_assistant_id = assistant_id
        self.backboard_base_url = base_url
        self.backboard_api_key = "key"
        self.request_timeout_seconds = 30
