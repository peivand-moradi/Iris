"""Task 2 smoke test: create a Backboard thread and send a text-only request
through the configured assistant, then normalize the response through the
application's own service layer. Requires BACKBOARD_API_KEY and
BACKBOARD_ASSISTANT_ID.

Usage:
    python scripts/smoke_test_backboard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config  # noqa: E402
from models import TranscriptResult  # noqa: E402
from services import interpretation  # noqa: E402


def main() -> None:
    config = load_config()
    if not (config.backboard_api_key and config.backboard_assistant_id):
        print(
            "FAIL: BACKBOARD_API_KEY and/or BACKBOARD_ASSISTANT_ID are not set in .env.\n"
            "Get an API key at https://app.backboard.io (Settings -> API Keys), then run\n"
            "scripts/setup_backboard_assistant.py to create the assistant and obtain an assistant_id."
        )
        raise SystemExit(1)

    thread_id = interpretation.create_interpretation_session()
    print(f"Created thread: {thread_id}")

    transcript = TranscriptResult(text="Nice weather we're having.", audio_events=[], success=True)
    result = interpretation.interpret_context(transcript, image_path=None, thread_id=thread_id)

    if not result.success:
        print(f"FAIL: interpretation was unsuccessful ({result.error}).")
        raise SystemExit(1)

    print("OK: normalized InterpretationResult:")
    print(f"  possible_meaning = {result.possible_meaning!r}")
    print(f"  certainty        = {result.certainty}")
    print(f"  spoken_summary   = {result.spoken_summary!r}")


if __name__ == "__main__":
    main()
