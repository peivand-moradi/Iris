"""Conversation-mode follow-up on an interpretation. Mirrors
services/interpretation.py's shape (session-start + per-turn functions, mock
fallback when Backboard's conversation assistant isn't configured), but keeps
ONE thread alive for the life of a single conversation instead of one thread
per request — a scoped, deliberate exception to the "new thread + memory off
per press" design used for interpretation. The thread is discarded (never
revisited) once the conversation ends.
"""

import uuid

from config import load_config
from models import ConversationTurnResult, InterpretationResult
from services import backboard_client
from services.conversation_validator import validate_conversation_turn


def _configured(config) -> bool:
    return bool(config.backboard_api_key and config.backboard_conversation_assistant_id)


def _build_recap(interpretation: InterpretationResult) -> str:
    lines = [
        f'Heard: "{interpretation.heard}"',
        f"Possible meaning: {interpretation.possible_meaning}",
    ]
    if interpretation.why:
        lines.append(f"Why: {interpretation.why}")
    if interpretation.alternative:
        lines.append(f"Alternative: {interpretation.alternative}")
    return "\n".join(lines)


def start_conversation(interpretation: InterpretationResult) -> ConversationTurnResult:
    config = load_config()

    if not _configured(config):
        return _mock_turn(thread_id=str(uuid.uuid4()), history=[], opening=True)

    try:
        thread_id = backboard_client.create_thread(assistant_id=config.backboard_conversation_assistant_id)
    except backboard_client.BackboardError as exc:
        return validate_conversation_turn(None, thread_id="", history=[], error=str(exc))

    try:
        raw = backboard_client.send_conversation_start(
            recap=_build_recap(interpretation),
            thread_id=thread_id,
            assistant_id=config.backboard_conversation_assistant_id,
        )
    except backboard_client.BackboardError as exc:
        return validate_conversation_turn(None, thread_id=thread_id, history=[], error=str(exc))

    return validate_conversation_turn(raw, thread_id=thread_id, history=[])


def continue_conversation(
    user_reply: str,
    thread_id: str,
    history: list[tuple[str, str]],
) -> ConversationTurnResult:
    config = load_config()
    updated_history = history + [("user", user_reply)]

    if not _configured(config):
        return _mock_turn(thread_id=thread_id, history=updated_history, opening=False)

    try:
        raw = backboard_client.send_conversation_reply(
            history=updated_history,
            thread_id=thread_id,
            assistant_id=config.backboard_conversation_assistant_id,
        )
    except backboard_client.BackboardError as exc:
        return validate_conversation_turn(None, thread_id=thread_id, history=updated_history, error=str(exc))

    return validate_conversation_turn(raw, thread_id=thread_id, history=updated_history)


def _mock_turn(thread_id: str, history: list[tuple[str, str]], opening: bool) -> ConversationTurnResult:
    message = (
        "[mock] Who were you talking to — a coworker, a friend, or family?"
        if opening
        else "[mock] Thanks — that's all I needed to know."
    )
    return ConversationTurnResult(
        message=message,
        conversation_over=not opening,
        thread_id=thread_id,
        history=history + [("iris", message)],
        success=True,
    )
