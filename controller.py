import threading
from pathlib import Path
from typing import Callable

import audio
from camera import get_camera_provider
from config import load_config
from logging_setup import log_event
from models import ConversationTurnResult, InterpretationResult
from services import conversation, interpretation
from services.elevenlabs_client import transcribe_audio
from tempfiles import cleanup as cleanup_temp_file

STARTING = "STARTING"
LISTENING = "LISTENING"
CAPTURING = "CAPTURING"
PROCESSING = "PROCESSING"
RESULT = "RESULT"
CONVERSATION = "CONVERSATION"
ERROR = "ERROR"


def select_camera_mode(camera_mode: str, demo_mode: bool) -> str:
    """Demo mode always uses the sample image for a reliable, repeatable demo,
    regardless of CAMERA_MODE (see README "Demo mode" section)."""
    return "sample" if demo_mode else camera_mode


_config = load_config()
_camera = get_camera_provider(
    select_camera_mode(_config.camera_mode, _config.demo_mode)
)
_lock = threading.Lock()


def _error_result(
    message: str,
    thread_id: str = "",
) -> InterpretationResult:
    return InterpretationResult(
        heard="",
        possible_meaning="",
        why="",
        certainty="low",
        alternative=None,
        visual_context_used=False,
        image_relevance="unavailable",
        spoken_summary="",
        thread_id=thread_id,
        success=False,
        error=message,
        image_captured=False,
    )


def run_interpretation(
    on_state_change: Callable[[str], None] | None = None,
) -> InterpretationResult:
    """The single entry point every trigger (software button, and later GPIO) must call."""

    def set_state(state: str) -> None:
        if on_state_change:
            on_state_change(state)

    log_event("button_pressed")

    if not _lock.acquire(blocking=False):
        return _error_result(
            "A request is already being processed. "
            "Please wait for the current result."
        )

    audio_path: Path | None = None
    image_path: Path | None = None
    image_captured = False

    try:
        set_state(CAPTURING)

        audio_path = audio.get_recent_audio()
        log_event("audio_saved", success=audio_path is not None)

        if audio_path is None:
            return _error_result(
                "No recent speech was captured. "
                "Please try speaking again and press the button."
            )

        try:
            image_path = _camera.capture()

            image_captured = (
                image_path is not None
                and image_path.exists()
                and image_path.is_file()
                and image_path.stat().st_size > 0
            )

            log_event(
                "image_captured",
                success=image_captured,
                path=str(image_path) if image_path else None,
                size_bytes=(
                    image_path.stat().st_size
                    if image_captured
                    else None
                ),
            )

        except Exception as exc:
            image_path = None
            image_captured = False

            log_event(
                "image_captured",
                success=False,
                error=str(exc),
            )

        set_state(PROCESSING)

        try:
            transcript = transcribe_audio(audio_path)
        except Exception as exc:
            log_event(
                "transcript_received",
                success=False,
                error=str(exc),
            )
            return _error_result(
                "Speech could not be transcribed right now. "
                "Please try again."
            )

        log_event(
            "transcript_received",
            success=transcript.success,
        )

        if not transcript.success or not transcript.text.strip():
            return _error_result(
                transcript.error
                or "No understandable speech was detected. Please try again."
            )

        try:
            thread_id = interpretation.create_interpretation_session()

            result = interpretation.interpret_context(
                transcript,
                image_path if image_captured else None,
                thread_id,
            )

            result.image_captured = image_captured

        except Exception as exc:
            log_event(
                "interpretation_received",
                success=False,
                error=str(exc),
            )
            return _error_result(
                "The interpretation service is unavailable right now. "
                "Please try again."
            )

        log_event(
            "interpretation_received",
            success=result.success,
            image_captured=result.image_captured,
            visual_context_used=result.visual_context_used,
        )

        log_event(
            "validation_finished",
            success=result.success,
            certainty=result.certainty,
        )

        return result

    finally:
        cleanup_temp_file(audio_path)
        cleanup_temp_file(image_path)
        _lock.release()


def _conversation_error_result(
    message: str,
    thread_id: str = "",
    history: list[tuple[str, str]] | None = None,
) -> ConversationTurnResult:
    return ConversationTurnResult(
        message=message,
        conversation_over=True,
        thread_id=thread_id,
        history=history or [],
        success=False,
        error=message,
    )


def start_conversation(interpretation_result: InterpretationResult) -> ConversationTurnResult:
    """Acquire the shared lock for the whole conversation — released only by
    end_conversation(), which MUST be called exactly once for every
    start_conversation() call, regardless of outcome. Holding the lock for the
    conversation's duration (not per turn) keeps a stray GPIO/software
    interpretation press from racing the shared mic buffer/camera while a
    conversation is live — it fails cleanly via the same "already being
    processed" path a concurrent interpretation press already gets."""
    log_event("conversation_started")

    if not _lock.acquire(blocking=False):
        return _conversation_error_result(
            "A request is already being processed. Please wait for the current result."
        )

    try:
        result = conversation.start_conversation(interpretation_result)
        log_event("conversation_turn_received", success=result.success, opening=True)
        return result
    except Exception as exc:
        log_event("conversation_turn_received", success=False, error=str(exc))
        return _conversation_error_result("The conversation service is unavailable right now.")


def continue_conversation(thread_id: str, history: list[tuple[str, str]]) -> ConversationTurnResult:
    """Caller must already hold the lock via start_conversation(). Reuses
    audio.get_recent_audio() + transcribe_audio() exactly as run_interpretation()
    does — no new capture primitive."""
    audio_path = audio.get_recent_audio()
    log_event("conversation_audio_saved", success=audio_path is not None)

    if audio_path is None:
        return _conversation_error_result(
            "No recent speech was captured. Please try answering again.",
            thread_id=thread_id,
            history=history,
        )

    try:
        transcript = transcribe_audio(audio_path)
    except Exception as exc:
        log_event("conversation_transcript_received", success=False, error=str(exc))
        return _conversation_error_result(
            "Speech could not be transcribed right now.", thread_id=thread_id, history=history
        )
    finally:
        cleanup_temp_file(audio_path)

    if not transcript.success or not transcript.text.strip():
        return _conversation_error_result(
            transcript.error or "No understandable speech was detected.",
            thread_id=thread_id,
            history=history,
        )

    try:
        result = conversation.continue_conversation(transcript.text, thread_id, history)
    except Exception as exc:
        log_event("conversation_turn_received", success=False, error=str(exc))
        return _conversation_error_result(
            "The conversation service is unavailable right now.", thread_id=thread_id, history=history
        )

    log_event(
        "conversation_turn_received",
        success=result.success,
        conversation_over=result.conversation_over,
    )
    return result


def end_conversation() -> None:
    """Release the lock acquired by start_conversation(). Must be called
    exactly once per start_conversation() call."""
    log_event("conversation_ended")
    _lock.release()


_CONVERSATION_TRIGGER_PHRASES = ("let's talk", "lets talk", "let us talk")


def _mentions_conversation_trigger(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _CONVERSATION_TRIGGER_PHRASES)


def try_start_conversation_by_voice(
    interpretation_result: InterpretationResult,
) -> ConversationTurnResult | None:
    """Listens once for the user saying a conversation-start phrase (e.g.
    "let's talk") right after a result was spoken aloud. Reuses the same
    capture/transcribe primitives as everywhere else in this app.

    Returns None (lock already released) if nothing usable was captured or
    the phrase wasn't said — the caller does nothing further in that case.
    Returns a ConversationTurnResult (lock held for the conversation's
    duration, exactly like start_conversation()) if the phrase was said —
    the caller MUST then run the normal turn loop and eventually call
    end_conversation() exactly once.
    """
    if not _lock.acquire(blocking=False):
        return None

    audio_path = audio.get_recent_audio()
    if audio_path is None:
        _lock.release()
        return None

    try:
        transcript = transcribe_audio(audio_path)
    except Exception:
        _lock.release()
        return None
    finally:
        cleanup_temp_file(audio_path)

    if not transcript.success or not transcript.text.strip():
        _lock.release()
        return None

    if not _mentions_conversation_trigger(transcript.text):
        _lock.release()
        return None

    log_event("conversation_started", trigger="voice")
    try:
        result = conversation.start_conversation(interpretation_result)
        log_event("conversation_turn_received", success=result.success, opening=True)
        return result
    except Exception as exc:
        log_event("conversation_turn_received", success=False, error=str(exc))
        return _conversation_error_result("The conversation service is unavailable right now.")