"""Task 2/3 smoke test: run the real controller.run_interpretation() pipeline
once, headlessly (no Tkinter window). Uses whatever mix of real/mock services
is currently configured via .env — this is the same code path the UI calls.

Usage:
    python scripts/smoke_test_end_to_end.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config  # noqa: E402
from logging_setup import configure_logging  # noqa: E402


def main() -> None:
    configure_logging(load_config().log_level)

    import controller

    states = []
    result = controller.run_interpretation(on_state_change=states.append)

    print(f"States observed: {states}")
    if not result.success:
        print(f"Result was unsuccessful (this can be expected without real audio/camera): {result.error}")
        return

    print("OK: full pipeline produced a result:")
    print(f"  heard             = {result.heard!r}")
    print(f"  possible_meaning  = {result.possible_meaning!r}")
    print(f"  certainty         = {result.certainty}")
    print(f"  visual_context_used = {result.visual_context_used}")
    print(f"  spoken_summary    = {result.spoken_summary!r}")


if __name__ == "__main__":
    main()
