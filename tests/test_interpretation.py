from models import TranscriptResult
from services import interpretation


def test_mock_mode_used_when_credentials_missing(monkeypatch):
    monkeypatch.setattr("services.interpretation.load_config", lambda: _FakeConfig(api_key="", assistant_id=""))

    transcript = TranscriptResult(text="Nice weather we're having.", audio_events=[], success=True)
    result = interpretation.interpret_context(transcript, image_path=None, thread_id="t1")

    assert result.success
    assert "mock" in result.possible_meaning.lower()


def test_real_path_used_when_credentials_present(monkeypatch):
    monkeypatch.setattr(
        "services.interpretation.load_config", lambda: _FakeConfig(api_key="key", assistant_id="asst-1")
    )
    monkeypatch.setattr(
        "services.interpretation.backboard_client.send_interpretation_request",
        lambda **kwargs: {
            "heard": "hi",
            "possible_meaning": "real meaning",
            "why": "real reason",
            "certainty": "high",
            "alternative": None,
            "visual_context_used": False,
            "image_relevance": "unavailable",
            "spoken_summary": "real summary",
        },
    )

    transcript = TranscriptResult(text="hi", audio_events=[], success=True)
    result = interpretation.interpret_context(transcript, image_path=None, thread_id="t1")

    assert result.success
    assert result.possible_meaning == "real meaning"


def test_backboard_error_produces_fallback_not_crash(monkeypatch):
    from services.backboard_client import BackboardError

    monkeypatch.setattr(
        "services.interpretation.load_config", lambda: _FakeConfig(api_key="key", assistant_id="asst-1")
    )

    def _boom(**kwargs):
        raise BackboardError("network down")

    monkeypatch.setattr("services.interpretation.backboard_client.send_interpretation_request", _boom)

    transcript = TranscriptResult(text="hi", audio_events=[], success=True)
    result = interpretation.interpret_context(transcript, image_path=None, thread_id="t1")

    assert not result.success
    assert result.certainty == "low"


class _FakeConfig:
    def __init__(self, api_key: str, assistant_id: str):
        self.backboard_api_key = api_key
        self.backboard_assistant_id = assistant_id
