"""Task 2 smoke test: send the sample (or a given) WAV to ElevenLabs Scribe v2
and verify usable text comes back. Requires ELEVENLABS_API_KEY.

Usage:
    python scripts/smoke_test_elevenlabs_stt.py [path/to/audio.wav]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config  # noqa: E402
from services.elevenlabs_client import transcribe_audio  # noqa: E402


def main() -> None:
    config = load_config()
    if not config.elevenlabs_api_key:
        print("FAIL: ELEVENLABS_API_KEY is not set in .env. Get one at https://elevenlabs.io "
              "(Profile -> API Keys) and set it first.")
        raise SystemExit(1)

    audio_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(config.sample_audio_path)
    if not audio_path.exists():
        print(f"FAIL: audio file not found: {audio_path}")
        raise SystemExit(1)

    result = transcribe_audio(audio_path)
    if not result.success:
        print(f"FAIL: transcription was unsuccessful ({result.error}).")
        raise SystemExit(1)

    print(f"OK: transcript = {result.text!r}")
    print(f"audio_events = {result.audio_events}")


if __name__ == "__main__":
    main()
