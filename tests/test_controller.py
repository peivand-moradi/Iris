import threading

import controller
from models import InterpretationResult, TranscriptResult


def _valid_result(thread_id="t1"):
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


def _patch_happy_path(monkeypatch, tmp_path):
    fake_audio = tmp_path / "audio.wav"
    fake_audio.write_bytes(b"fake")

    monkeypatch.setattr(controller.audio, "get_recent_audio", lambda: fake_audio)
    monkeypatch.setattr(controller._camera, "capture", lambda: None)
    monkeypatch.setattr(
        controller, "transcribe_audio",
        lambda path: TranscriptResult(text="Nice weather we're having.", audio_events=[], success=True),
    )
    monkeypatch.setattr(controller.interpretation, "create_interpretation_session", lambda: "t1")
    monkeypatch.setattr(controller.interpretation, "interpret_context", lambda *a, **k: _valid_result())
    return fake_audio


def test_happy_path_produces_result(monkeypatch, tmp_path):
    _patch_happy_path(monkeypatch, tmp_path)
    states = []

    result = controller.run_interpretation(on_state_change=states.append)

    assert result.success
    assert result.possible_meaning == "They may be joking."
    assert states == [controller.CAPTURING, controller.PROCESSING]


def test_no_audio_short_circuits_before_transcription(monkeypatch):
    monkeypatch.setattr(controller.audio, "get_recent_audio", lambda: None)
    called = []
    monkeypatch.setattr(controller, "transcribe_audio", lambda path: called.append(path))

    result = controller.run_interpretation()

    assert not result.success
    assert called == []


def test_empty_transcript_short_circuits_before_interpretation(monkeypatch, tmp_path):
    fake_audio = tmp_path / "audio.wav"
    fake_audio.write_bytes(b"fake")
    monkeypatch.setattr(controller.audio, "get_recent_audio", lambda: fake_audio)
    monkeypatch.setattr(controller._camera, "capture", lambda: None)
    monkeypatch.setattr(
        controller, "transcribe_audio",
        lambda path: TranscriptResult(text="", audio_events=[], success=False, error="No speech"),
    )
    called = []
    monkeypatch.setattr(
        controller.interpretation, "create_interpretation_session",
        lambda: called.append(1) or "t1",
    )

    result = controller.run_interpretation()

    assert not result.success
    assert called == []


def test_camera_failure_does_not_crash_pipeline(monkeypatch, tmp_path):
    _patch_happy_path(monkeypatch, tmp_path)

    def _boom():
        raise RuntimeError("camera exploded")

    monkeypatch.setattr(controller._camera, "capture", _boom)

    result = controller.run_interpretation()

    assert result.success


def test_repeated_press_while_busy_is_rejected(monkeypatch, tmp_path):
    release_event = threading.Event()
    entered_event = threading.Event()

    fake_audio = tmp_path / "audio.wav"
    fake_audio.write_bytes(b"fake")
    monkeypatch.setattr(controller.audio, "get_recent_audio", lambda: fake_audio)
    monkeypatch.setattr(controller._camera, "capture", lambda: None)

    def _slow_transcribe(path):
        entered_event.set()
        release_event.wait(timeout=2)
        return TranscriptResult(text="hello", audio_events=[], success=True)

    monkeypatch.setattr(controller, "transcribe_audio", _slow_transcribe)
    monkeypatch.setattr(controller.interpretation, "create_interpretation_session", lambda: "t1")
    monkeypatch.setattr(controller.interpretation, "interpret_context", lambda *a, **k: _valid_result())

    results = []
    thread = threading.Thread(target=lambda: results.append(controller.run_interpretation()))
    thread.start()
    entered_event.wait(timeout=2)

    second_result = controller.run_interpretation()

    release_event.set()
    thread.join(timeout=2)

    assert not second_result.success
    assert "already being processed" in second_result.error
    assert results[0].success


def test_temp_files_are_cleaned_up_after_run(monkeypatch, tmp_path):
    fake_audio = tmp_path / "audio.wav"
    fake_audio.write_bytes(b"fake")

    cleaned = []
    monkeypatch.setattr(controller, "cleanup_temp_file", cleaned.append)
    _patch_happy_path(monkeypatch, tmp_path)
    monkeypatch.setattr(controller.audio, "get_recent_audio", lambda: fake_audio)

    controller.run_interpretation()

    assert fake_audio in cleaned


def test_select_camera_mode_forces_sample_in_demo_mode():
    assert controller.select_camera_mode("laptop", demo_mode=True) == "sample"
    assert controller.select_camera_mode("laptop", demo_mode=False) == "laptop"
    assert controller.select_camera_mode("sample", demo_mode=False) == "sample"


def _valid_turn(thread_id="t1", history=None, conversation_over=False):
    from models import ConversationTurnResult

    return ConversationTurnResult(
        message="Who were you talking to?",
        conversation_over=conversation_over,
        thread_id=thread_id,
        history=history or [("iris", "Who were you talking to?")],
        success=True,
    )


def test_start_conversation_rejects_concurrent_interpretation_press(monkeypatch, tmp_path):
    release_event = threading.Event()
    entered_event = threading.Event()

    def _slow_start(interpretation):
        entered_event.set()
        release_event.wait(timeout=2)
        return _valid_turn()

    monkeypatch.setattr(controller.conversation, "start_conversation", _slow_start)

    results = []
    thread = threading.Thread(
        target=lambda: results.append(controller.start_conversation(_valid_result()))
    )
    thread.start()
    entered_event.wait(timeout=2)

    interpretation_result = controller.run_interpretation()

    release_event.set()
    thread.join(timeout=2)

    assert not interpretation_result.success
    assert "already being processed" in interpretation_result.error
    assert results[0].success
    controller.end_conversation()


def test_run_interpretation_rejects_concurrent_conversation_start(monkeypatch, tmp_path):
    release_event = threading.Event()
    entered_event = threading.Event()

    fake_audio = tmp_path / "audio.wav"
    fake_audio.write_bytes(b"fake")
    monkeypatch.setattr(controller.audio, "get_recent_audio", lambda: fake_audio)
    monkeypatch.setattr(controller._camera, "capture", lambda: None)

    def _slow_transcribe(path):
        entered_event.set()
        release_event.wait(timeout=2)
        return TranscriptResult(text="hello", audio_events=[], success=True)

    monkeypatch.setattr(controller, "transcribe_audio", _slow_transcribe)
    monkeypatch.setattr(controller.interpretation, "create_interpretation_session", lambda: "t1")
    monkeypatch.setattr(controller.interpretation, "interpret_context", lambda *a, **k: _valid_result())

    results = []
    thread = threading.Thread(target=lambda: results.append(controller.run_interpretation()))
    thread.start()
    entered_event.wait(timeout=2)

    conversation_result = controller.start_conversation(_valid_result())

    release_event.set()
    thread.join(timeout=2)

    assert not conversation_result.success
    assert "already being processed" in conversation_result.error
    assert results[0].success


def test_continue_conversation_no_audio_short_circuits(monkeypatch):
    monkeypatch.setattr(controller.audio, "get_recent_audio", lambda: None)
    called = []
    monkeypatch.setattr(controller, "transcribe_audio", lambda path: called.append(path))

    result = controller.continue_conversation("t1", [("iris", "hi")])

    assert not result.success
    assert called == []
    assert result.history == [("iris", "hi")]


def test_continue_conversation_empty_transcript_short_circuits(monkeypatch, tmp_path):
    fake_audio = tmp_path / "audio.wav"
    fake_audio.write_bytes(b"fake")
    monkeypatch.setattr(controller.audio, "get_recent_audio", lambda: fake_audio)
    monkeypatch.setattr(
        controller, "transcribe_audio",
        lambda path: TranscriptResult(text="", audio_events=[], success=False, error="No speech"),
    )
    called = []
    monkeypatch.setattr(
        controller.conversation, "continue_conversation",
        lambda *a, **k: called.append(1),
    )

    result = controller.continue_conversation("t1", [])

    assert not result.success
    assert called == []


def test_end_conversation_releases_lock_for_subsequent_interpretation(monkeypatch):
    monkeypatch.setattr(controller.conversation, "start_conversation", lambda interpretation: _valid_turn())

    start_result = controller.start_conversation(_valid_result())
    assert start_result.success

    blocked = controller.run_interpretation()
    assert not blocked.success

    controller.end_conversation()

    monkeypatch.setattr(controller.audio, "get_recent_audio", lambda: None)
    after_release = controller.run_interpretation()
    assert not after_release.success
    assert "No recent speech" in after_release.error
