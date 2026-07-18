"""Generate the sample audio/image assets used by demo mode and Task 3's vertical
slice (samples/audio/sample.wav, samples/images/sample.jpg).

Without ELEVENLABS_API_KEY, this produces structurally-valid PLACEHOLDER audio
(a short tone, not real speech) and a synthetic "rainy window" image. Re-run
this script after ELEVENLABS_API_KEY is configured to regenerate the audio as
a real spoken line ("Nice weather we're having.") via ElevenLabs TTS.

Usage:
    python scripts/generate_sample_assets.py
"""

import sys
import wave
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config  # noqa: E402

SAMPLE_TEXT = "Nice weather we're having."


def _generate_placeholder_tone_wav(path: Path, sample_rate: int = 16000, seconds: float = 3.0) -> None:
    t = np.linspace(0, seconds, int(sample_rate * seconds), endpoint=False)
    tone = (0.2 * np.sin(2 * np.pi * 220 * t) * 32767).astype("int16")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(tone.tobytes())
    print(f"Wrote placeholder tone WAV (not real speech) to {path}")


def _generate_real_speech_via_tts(path: Path, config) -> bool:
    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs.play import save
    except ImportError:
        return False

    if not config.elevenlabs_voice_id:
        print("ELEVENLABS_API_KEY is set but ELEVENLABS_VOICE_ID is not; skipping real speech synthesis.")
        return False

    client = ElevenLabs(api_key=config.elevenlabs_api_key)
    audio = client.text_to_speech.convert(
        text=SAMPLE_TEXT,
        voice_id=config.elevenlabs_voice_id,
        model_id=config.elevenlabs_tts_model,
        output_format="mp3_44100_128",
    )
    mp3_path = path.with_suffix(".mp3")
    path.parent.mkdir(parents=True, exist_ok=True)
    save(audio, str(mp3_path))
    print(f"Wrote real spoken sample via ElevenLabs TTS to {mp3_path}")
    print("Set SAMPLE_AUDIO_PATH to this .mp3 file (Scribe accepts mp3) or convert it to WAV.")
    return True


def _generate_sample_image(path: Path, width: int = 1280, height: int = 720) -> None:
    rng = np.random.default_rng(seed=42)
    image = np.full((height, width, 3), (90, 70, 60), dtype="uint8")  # overcast gray-blue
    for _ in range(220):
        x = int(rng.integers(0, width))
        y = int(rng.integers(0, height))
        length = int(rng.integers(15, 40))
        cv2.line(image, (x, y), (x - 4, y + length), (200, 200, 200), 1, lineType=cv2.LINE_AA)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    print(f"Wrote synthetic rainy-window placeholder image to {path}")


def main() -> None:
    config = load_config()
    audio_path = Path(config.sample_audio_path)
    image_path = Path(config.sample_image_path)

    if not (config.elevenlabs_api_key and _generate_real_speech_via_tts(audio_path, config)):
        _generate_placeholder_tone_wav(audio_path)

    _generate_sample_image(image_path)


if __name__ == "__main__":
    main()
