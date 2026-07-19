import threading
from pathlib import Path
from typing import Callable

import audio
from camera import get_camera_provider
from config import load_config
from logging_setup import log_event
from models import InterpretationResult
from prompts.services import interpretation
from prompts.services.elevenlabs_client import transcribe_audio
from tempfiles import cleanup as cleanup_temp_file

STARTING = "STARTING"
LISTENING = "LISTENING"
CAPTURING = "CAPTURING"
PROCESSING = "PROCESSING"
RESULT = "RESULT"
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