import re

from models import ConversationTurnResult

_FALLBACK_MESSAGE = "I'm not able to continue this conversation right now."
_MAX_MESSAGE_LENGTH = 400
_PERCENTAGE_PATTERN = re.compile(r"\d{1,3}\s*%")


def validate_conversation_turn(
    raw: dict | None,
    thread_id: str,
    history: list[tuple[str, str]],
    error: str | None = None,
) -> ConversationTurnResult:
    if raw is None:
        return _fallback(thread_id, history, error)

    if not isinstance(raw, dict):
        return _fallback(thread_id, history, "Model output was not a JSON object")

    missing = [field for field in ("message", "conversation_over") if field not in raw]
    if missing:
        return _fallback(thread_id, history, f"Missing required field(s): {', '.join(missing)}")

    if not isinstance(raw["message"], str) or not raw["message"].strip():
        return _fallback(thread_id, history, "Field 'message' was not a non-empty string")

    if len(raw["message"]) > _MAX_MESSAGE_LENGTH:
        return _fallback(thread_id, history, "Field 'message' was excessively long")

    if not isinstance(raw["conversation_over"], bool):
        return _fallback(thread_id, history, "conversation_over was not a boolean")

    if _PERCENTAGE_PATTERN.search(raw["message"]):
        return _fallback(thread_id, history, "Unsupported confidence percentage found in 'message'")

    return ConversationTurnResult(
        message=raw["message"],
        conversation_over=raw["conversation_over"],
        thread_id=thread_id,
        history=history + [("iris", raw["message"])],
        success=True,
    )


def _fallback(
    thread_id: str,
    history: list[tuple[str, str]],
    error: str | None,
) -> ConversationTurnResult:
    return ConversationTurnResult(
        message=_FALLBACK_MESSAGE,
        conversation_over=True,
        thread_id=thread_id,
        history=history,
        success=False,
        error=error,
    )
