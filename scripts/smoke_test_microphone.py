"""Task 2 smoke test: record a short WAV from the laptop microphone and verify
it is structurally readable. Run manually and confirm you can hear your own
voice back — this script only checks structure, not content.

Usage:
    python scripts/smoke_test_microphone.py [seconds]
"""

import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import sounddevice as sd  # noqa: E402

from config import load_config  # noqa: E402

SAMPLE_RATE = 16000
OUTPUT_PATH = Path("scripts/_smoke_mic_output.wav")


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    device = load_config().mic_device_index  # None = system default; see MIC_DEVICE_INDEX in .env

    print(f"Recording {seconds:.1f}s of mono 16-bit audio at {SAMPLE_RATE} Hz (device={device}). Speak now...")
    try:
        recording = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16", device=device)
        sd.wait()
    except sd.PortAudioError as exc:
        print(f"FAIL: could not access the microphone ({exc}). Check system audio permissions.")
        raise SystemExit(1)

    if recording.size == 0 or not np.any(recording):
        print(
            "FAIL: recording buffer is empty or entirely silent. Check system audio "
            "permissions for this terminal, or that the right input device is selected — "
            "run `python -c \"import sounddevice as sd; print(sd.query_devices())\"` to "
            "list devices, then set MIC_DEVICE_INDEX in .env to the correct index."
        )
        raise SystemExit(1)

    with wave.open(str(OUTPUT_PATH), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(recording.tobytes())

    if not OUTPUT_PATH.exists() or OUTPUT_PATH.stat().st_size == 0:
        print("FAIL: WAV file was not written or is empty.")
        raise SystemExit(1)

    with wave.open(str(OUTPUT_PATH), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == SAMPLE_RATE

    print(f"OK: wrote structurally valid WAV to {OUTPUT_PATH}")
    print("Play it back and confirm it contains understandable speech, e.g.:")
    print(f"  afplay {OUTPUT_PATH}   # macOS")


if __name__ == "__main__":
    main()
