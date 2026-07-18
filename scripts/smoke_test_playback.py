"""Task 2 smoke test: play a local audio file through the platform's audio
player. If no path is given, synthesizes a one-word WAV via ElevenLabs TTS
first (requires ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID); otherwise just
reports that playback is unsupported/unavailable rather than crashing.

Usage:
    python scripts/smoke_test_playback.py [path/to/audio.wav]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import playback  # noqa: E402
from config import load_config  # noqa: E402


def main() -> None:
    if len(sys.argv) > 1:
        audio_path = Path(sys.argv[1])
        cleanup_after = False
    else:
        from services.elevenlabs_client import synthesize_result

        config = load_config()
        if not (config.elevenlabs_api_key and config.elevenlabs_voice_id):
            print(
                "No audio path given and TTS is not configured (need ELEVENLABS_API_KEY and "
                "ELEVENLABS_VOICE_ID). Pass an existing audio file path instead."
            )
            raise SystemExit(1)
        path = synthesize_result("This is a playback test.")
        if path is None:
            print("FAIL: could not synthesize a test WAV.")
            raise SystemExit(1)
        audio_path = path
        cleanup_after = True

    if not audio_path.exists():
        print(f"FAIL: {audio_path} does not exist.")
        raise SystemExit(1)

    ok = playback.play_mp3(audio_path) if not cleanup_after else playback.play_and_cleanup(audio_path)
    if ok:
        print("OK: playback command completed without error.")
    else:
        print("Playback unsupported or failed on this platform (reported cleanly, not a crash).")


if __name__ == "__main__":
    main()
