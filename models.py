from dataclasses import dataclass

ALLOWED_CERTAINTY = ("low", "medium", "high")


@dataclass
class TranscriptResult:
    text: str
    audio_events: list[str]
    success: bool
    error: str | None = None


@dataclass
class InterpretationResult:
    heard: str
    possible_meaning: str
    why: str
    certainty: str
    alternative: str | None
    visual_context_used: bool
    spoken_summary: str
    thread_id: str
    success: bool
    visual_description: str = ""
    error: str | None = None
    image_captured: bool = False


@dataclass
class ConversationTurnResult:
    message: str
    conversation_over: bool
    thread_id: str
    history: list[tuple[str, str]]  # ("iris" | "user", text) pairs, oldest first
    success: bool
    error: str | None = None
