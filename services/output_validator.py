import re

from models import ALLOWED_CERTAINTY, InterpretationResult

_FALLBACK_MESSAGE = (
    "The meaning is unclear from the available context. "
    "There may be more than one possible interpretation."
)

_MAX_FIELD_LENGTH = 1000
_MAX_SPOKEN_SUMMARY_LENGTH = 400
_PERCENTAGE_PATTERN = re.compile(r"\d{1,3}\s*%")

_REQUIRED_STRING_FIELDS = ("heard", "possible_meaning", "why", "spoken_summary", "visual_description")


def validate_interpretation(
    raw: dict | None,
    thread_id: str,
    error: str | None = None,
) -> InterpretationResult:
    if raw is None:
        return _fallback(thread_id, error)

    if not isinstance(raw, dict):
        return _fallback(thread_id, "Model output was not a JSON object")

    required = (*_REQUIRED_STRING_FIELDS, "certainty", "visual_context_used")
    missing = [field for field in required if field not in raw]
    if missing:
        return _fallback(thread_id, f"Missing required field(s): {', '.join(missing)}")

    for field in _REQUIRED_STRING_FIELDS:
        if not isinstance(raw[field], str):
            return _fallback(thread_id, f"Field '{field}' was not a string")
        if len(raw[field]) > _MAX_FIELD_LENGTH:
            return _fallback(thread_id, f"Field '{field}' was excessively long")

    if not raw["possible_meaning"].strip():
        return _fallback(thread_id, "Empty possible_meaning in model output")

    if raw["certainty"] not in ALLOWED_CERTAINTY:
        return _fallback(thread_id, "Invalid certainty value in model output")

    if not isinstance(raw["visual_context_used"], bool):
        return _fallback(thread_id, "visual_context_used was not a boolean")

    alternative = raw.get("alternative")
    if alternative is not None and not isinstance(alternative, str):
        return _fallback(thread_id, "alternative was neither a string nor null")

    if len(raw["spoken_summary"]) > _MAX_SPOKEN_SUMMARY_LENGTH:
        return _fallback(thread_id, "spoken_summary too long")

    for field in (*_REQUIRED_STRING_FIELDS, "alternative"):
        value = raw.get(field)
        if isinstance(value, str) and _PERCENTAGE_PATTERN.search(value):
            return _fallback(thread_id, f"Unsupported confidence percentage found in '{field}'")

    return InterpretationResult(
        heard=raw["heard"],
        possible_meaning=raw["possible_meaning"],
        why=raw["why"],
        certainty=raw["certainty"],
        alternative=alternative,
        visual_context_used=raw["visual_context_used"],
        spoken_summary=raw["spoken_summary"],
        visual_description=raw["visual_description"],
        thread_id=thread_id,
        success=True,
    )


def _fallback(thread_id: str, error: str | None) -> InterpretationResult:
    return InterpretationResult(
        heard="",
        possible_meaning=_FALLBACK_MESSAGE,
        why="",
        certainty="low",
        alternative=None,
        visual_context_used=False,
        spoken_summary=_FALLBACK_MESSAGE,
        thread_id=thread_id,
        success=False,
        error=error,
    )
