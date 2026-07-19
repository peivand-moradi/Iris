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


def create_thread(assistant_id: str | None = None) -> str:
    config = load_config()
    assistant_id = assistant_id or config.backboard_assistant_id
    if not assistant_id:
        raise BackboardError("assistant_id is not configured")

    url = f"{config.backboard_base_url}/assistants/{assistant_id}/threads"
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
        '"alternative" (string or null), "visual_context_used" (true/false), "image_relevance" '
        '(one of "relevant", "not_relevant", "unavailable"), "visual_description" (one short sentence '
        'describing what is observable in the image, or "No image was available."), "spoken_summary" '
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

    return _post_thread_message(data, image_path, config)


def _post_thread_message(data: dict, image_path: Path | None, config) -> dict:
    """Shared POST to {base_url}/threads/messages; parses and returns the
    'content' JSON dict. Used by both interpretation and conversation turns."""
    files = None
    image_file = None
    if image_path is not None:
        image_file = open(image_path, "rb")
        files = {"files": (image_path.name, image_file, "image/jpeg")}

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


def _build_conversation_start_content(recap: str) -> str:
    lines = [
        "Here is what was just interpreted for the user:",
        recap,
        "",
        "Begin the conversation now with your first short spoken question or remark.",
        "Respond with a single JSON object only, no surrounding prose, using exactly these keys: "
        '"message" (one short spoken sentence), "conversation_over" (true/false; false for this '
        "opening turn unless there is truly nothing to ask).",
    ]
    return "\n".join(lines)


def _build_conversation_reply_content(history: list[tuple[str, str]]) -> str:
    lines = ["Conversation so far:"]
    for speaker, text in history:
        label = "Iris" if speaker == "iris" else "User"
        lines.append(f"{label}: {text}")
    lines.append(
        "Respond with a single JSON object only, no surrounding prose, using exactly these keys: "
        '"message" (one short spoken sentence), "conversation_over" (true/false).'
    )
    return "\n".join(lines)


def send_conversation_start(recap: str, thread_id: str, assistant_id: str) -> dict:
    return _send_conversation_message(_build_conversation_start_content(recap), thread_id, assistant_id)


def send_conversation_reply(history: list[tuple[str, str]], thread_id: str, assistant_id: str) -> dict:
    return _send_conversation_message(_build_conversation_reply_content(history), thread_id, assistant_id)


def _send_conversation_message(content: str, thread_id: str, assistant_id: str) -> dict:
    config = load_config()

    data = {
        "content": content,
        "thread_id": thread_id,
        "assistant_id": assistant_id,
        "json_output": "true",
        "memory": "off",
    }
    if config.backboard_provider:
        data["llm_provider"] = config.backboard_provider
    if config.backboard_model:
        data["model_name"] = config.backboard_model

    return _post_thread_message(data, image_path=None, config=config)
