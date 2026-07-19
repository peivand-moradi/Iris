from pathlib import Path

from config import load_config
from models import InterpretationResult, TranscriptResult
from services import backboard_client
from services.output_validator import validate_interpretation


def _configured(config) -> bool:
    return bool(config.backboard_api_key and config.backboard_assistant_id)


def create_interpretation_session() -> str:
    config = load_config()
    if not _configured(config):
        import uuid

        return str(uuid.uuid4())
    return backboard_client.create_thread()


def interpret_context(
    transcript: TranscriptResult,
    image_path: Path | None,
    thread_id: str,
) -> InterpretationResult:
    config = load_config()

    if not _configured(config):
        return _mock_interpretation(transcript, image_path, thread_id)

    try:
        raw = backboard_client.send_interpretation_request(
            transcript=transcript.text,
            audio_events=transcript.audio_events,
            image_path=image_path,
            thread_id=thread_id,
        )
    except backboard_client.BackboardError as exc:
        return validate_interpretation(None, thread_id=thread_id, error=str(exc))

    return validate_interpretation(raw, thread_id=thread_id)


def _mock_interpretation(
    transcript: TranscriptResult,
    image_path: Path | None,
    thread_id: str,
) -> InterpretationResult:
    return InterpretationResult(
        heard=transcript.text,
        possible_meaning="[mock] No vision-capable model is configured yet.",
        why="[mock] Placeholder response — set BACKBOARD_API_KEY and BACKBOARD_ASSISTANT_ID to connect a real model.",
        certainty="low",
        alternative=None,
        visual_context_used=False,
        spoken_summary="This is only a placeholder result.",
        visual_description=(
            "[mock] A placeholder scene description would appear here."
            if image_path is not None
            else "No image was available."
        ),
        thread_id=thread_id,
        success=True,
    )
