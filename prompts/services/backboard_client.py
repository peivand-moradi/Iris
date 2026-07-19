"""Raw Backboard.io API calls. All model-specific request construction stays in this file.

Built directly against Backboard's documented REST API (docs.backboard.io):
  - Auth:          header "X-API-Key: <BACKBOARD_API_KEY>"
  - Create thread: POST {base_url}/assistants/{assistant_id}/threads
  - Send message:  POST {base_url}/threads/messages (multipart/form-data when
                    an image is attached, since the documented "files" field
                    on this endpoint requires multipart encoding)

There is no documented JSON-schema-enforced structured output on this API —
only a coarse `json_output` boolean. The exact required keys are therefore
restated in the per-message content (in addition to living in the assistant's
system prompt) and the response is parsed/validated locally in
services/output_validator.py, which is designed to catch exactly this kind
of soft guarantee.
"""

import json
import logging
from pathlib import Path

import requests

from config import load_config

logger = logging.getLogger("iris.backboard")


class BackboardError(Exception):
    """Raised for any recoverable Backboard API failure (auth, network, timeout, bad response)."""


def _headers(config) -> dict[str, str]:
    return {"X-API-Key": config.backboard_api_key}


def create_thread() -> str:
    config = load_config()
    if not config.backboard_assistant_id:
        raise BackboardError("BACKBOARD_ASSISTANT_ID is not configured")

    url = f"{config.backboard_base_url}/assistants/{config.backboard_assistant_id}/threads"
    try:
        response = requests.post(
            url, json={}, headers=_headers(config), timeout=config.request_timeout_seconds
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise BackboardError(f"Could not create a Backboard thread: {exc}") from exc

    thread_id = response.json().get("thread_id")
    if not thread_id:
        raise BackboardError("Backboard did not return a thread_id")
    return thread_id


def _build_message_content(transcript: str, audio_events: list[str]) -> str:
    lines = [f'Heard: "{transcript}"']
    if audio_events:
        lines.append(f"Audio events detected: {', '.join(audio_events)}")
    lines.append(
        "Respond with a single JSON object only, no surrounding prose, using exactly these keys: "
        '"heard", "possible_meaning", "why", "certainty" (one of "low", "medium", "high"), '
        '"alternative" (string or null), "visual_context_used" (true/false), "spoken_summary" '
        "(one short sentence)."
    )
    return "\n".join(lines)


def send_interpretation_request(
    transcript: str,
    audio_events: list[str],
    image_path: Path | None,
    thread_id: str,
) -> dict:
    """Send the transcript (and optional image) to Backboard and return the parsed JSON dict."""
    config = load_config()

    data = {
        "content": _build_message_content(transcript, audio_events),
        "thread_id": thread_id,
        "assistant_id": config.backboard_assistant_id,
        "json_output": "true",
        "memory": "off",
    }
    if config.backboard_provider:
        data["llm_provider"] = config.backboard_provider
    if config.backboard_model:
        data["model_name"] = config.backboard_model

    files = None
    image_file = None
    if image_path is not None:
        image_file = open(image_path, "rb")
        files = {"files": (image_path.name, image_file, "image/jpeg")}
        print(files)

    try:
        response = requests.post(
            f"{config.backboard_base_url}/threads/messages",
            data=data,
            files=files,
            headers=_headers(config),
            timeout=config.request_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise BackboardError(f"Backboard request failed: {exc}") from exc
    finally:
        if image_file is not None:
            image_file.close()

    payload = response.json()
    content = payload.get("content")
    if not content:
        raise BackboardError("Backboard response had no content")

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise BackboardError(f"Backboard content was not valid JSON: {exc}") from exc
