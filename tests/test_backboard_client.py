from services.backboard_client import (
    _build_conversation_reply_content,
    _build_conversation_start_content,
    _build_message_content,
    _guess_image_mime_type,
    _open_image_for_upload,
    _post_thread_message,
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
    assert '"visual_context_used"' in content
    assert '"visual_description"' in content
    assert '"spoken_summary"' in content


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


def test_guess_image_mime_type_uses_actual_extension(tmp_path):
    assert _guess_image_mime_type(tmp_path / "capture.jpg") == "image/jpeg"
    assert _guess_image_mime_type(tmp_path / "capture.png") == "image/png"


def test_guess_image_mime_type_falls_back_to_jpeg_for_unrecognized_extension(tmp_path):
    assert _guess_image_mime_type(tmp_path / "capture.notarealext") == "image/jpeg"


def test_open_image_for_upload_attaches_real_bytes_with_correct_mime_type(tmp_path):
    image_path = tmp_path / "capture.png"
    image_path.write_bytes(b"\x89PNG fake bytes")

    files, handle = _open_image_for_upload(image_path)

    try:
        assert files is not None
        filename, file_obj, mime_type = files["files"]
        assert filename == "capture.png"
        assert mime_type == "image/png"
        assert file_obj.read() == b"\x89PNG fake bytes"
    finally:
        handle.close()


def test_open_image_for_upload_degrades_to_text_only_when_file_missing(tmp_path):
    missing_path = tmp_path / "does_not_exist.jpg"

    files, handle = _open_image_for_upload(missing_path)

    assert files is None
    assert handle is None


def test_post_thread_message_sends_image_as_multipart_file_not_a_path_string(monkeypatch, tmp_path):
    image_path = tmp_path / "capture.jpg"
    image_path.write_bytes(b"jpeg-bytes")

    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"content": '{"ok": true}'}

    def _fake_post(url, data, files, headers, timeout):
        # Read the attached bytes here, before _post_thread_message's `finally`
        # closes the file handle on the way out.
        filename, file_obj, mime_type = files["files"]
        captured["filename"] = filename
        captured["mime_type"] = mime_type
        captured["bytes"] = file_obj.read()
        return _FakeResponse()

    monkeypatch.setattr("services.backboard_client.requests.post", _fake_post)

    _post_thread_message({"content": "hi"}, image_path, _FakeConfig(assistant_id="a", base_url="https://example.test/api"))

    assert captured["filename"] == "capture.jpg"
    assert captured["mime_type"] == "image/jpeg"
    # The actual bytes were attached — not the path re-encoded as text.
    assert captured["bytes"] == b"jpeg-bytes"


def test_post_thread_message_falls_back_to_text_only_when_image_missing(monkeypatch, tmp_path):
    missing_path = tmp_path / "gone.jpg"
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"content": '{"ok": true}'}

    def _fake_post(url, data, files, headers, timeout):
        captured["files"] = files
        return _FakeResponse()

    monkeypatch.setattr("services.backboard_client.requests.post", _fake_post)

    result = _post_thread_message(
        {"content": "hi"}, missing_path, _FakeConfig(assistant_id="a", base_url="https://example.test/api")
    )

    assert captured["files"] is None
    assert result == {"ok": True}


class _FakeConfig:
    def __init__(self, assistant_id: str, base_url: str):
        self.backboard_assistant_id = assistant_id
        self.backboard_base_url = base_url
        self.backboard_api_key = "key"
        self.request_timeout_seconds = 30
