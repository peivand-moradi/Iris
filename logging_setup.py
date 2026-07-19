import logging

_EVENTS_LOGGER_NAME = "iris.events"

# Fields that must never reach the logs even if a caller passes them by mistake.
_FORBIDDEN_KEYS = {"audio", "image", "transcript", "transcript_text", "raw", "text", "api_key", "secret"}


def configure_logging(level: int | str = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def log_event(event: str, **fields) -> None:
    """Log a sanitized pipeline milestone (see Task 11's required timestamp events).

    Only short, non-sensitive fields (booleans, enums, ids, short error strings)
    should be passed in. Raw audio, images, and transcript content are stripped
    defensively even if accidentally supplied.
    """
    safe_fields = {k: v for k, v in fields.items() if k not in _FORBIDDEN_KEYS}
    logging.getLogger(_EVENTS_LOGGER_NAME).info("event=%s %s", event, safe_fields)
