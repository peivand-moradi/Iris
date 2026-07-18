"""Task 2 smoke test: play a local MP3 through the platform's audio player.
If no MP3 path is given, synthesizes a one-word MP3 via ElevenLabs TTS first
(requires ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID); otherwise just reports
that playback is unsupported/unavailable rather than crashing.

Usage:
    python scripts/smoke_test_playback.py [path/to/audio.mp3]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import playback  # noqa: E402
from config import load_config  # noqa: E402


def main() -> None:
    if len(sys.argv) > 1:
        mp3_path = Path(sys.argv[1])
        cleanup_after = False
    else:
        from services.elevenlabs_client import synthesize_result

        config = load_config()
        if not (config.elevenlabs_api_key and config.elevenlabs_voice_id):
            print(
                "No MP3 path given and TTS is not configured (need ELEVENLABS_API_KEY and "
                "ELEVENLABS_VOICE_ID). Pass an existing .mp3 path instead."
            )
            raise SystemExit(1)
        path = synthesize_result("This is a playback test.")
        if path is None:
            print("FAIL: could not synthesize a test MP3.")
            raise SystemExit(1)
        mp3_path = path
        cleanup_after = True

    if not mp3_path.exists():
        print(f"FAIL: {mp3_path} does not exist.")
        raise SystemExit(1)

    ok = playback.play_mp3(mp3_path) if not cleanup_after else playback.play_and_cleanup(mp3_path)
    if ok:
        print("OK: playback command completed without error.")
    else:
        print("Playback unsupported or failed on this platform (reported cleanly, not a crash).")


if __name__ == "__main__":
    main()
