"""ElevenLabs integration. Kept isolated per the plan: Scribe v2 for transcription,
TTS for reading only the already-validated spoken_summary aloud — never for
interpretation or summarization.
"""

import logging
from pathlib import Path

from config import load_config
from models import TranscriptResult
from tempfiles import new_temp_path

logger = logging.getLogger("iris.elevenlabs")


def _client():
    from elevenlabs.client import ElevenLabs

    config = load_config()
    return ElevenLabs(api_key=config.elevenlabs_api_key)


def transcribe_audio(audio_path: Path) -> TranscriptResult:
    config = load_config()

    if not config.elevenlabs_api_key:
        return TranscriptResult(
            text="[mock transcript] Nice weather we're having.",
            audio_events=[],
            success=True,
        )

    try:
        with open(audio_path, "rb") as audio_file:
            result = _client().speech_to_text.convert(
                file=audio_file,
                model_id=config.elevenlabs_stt_model,
                tag_audio_events=True,
            )
    except FileNotFoundError:
        return TranscriptResult(text="", audio_events=[], success=False, error="Audio file was not found.")
    except Exception as exc:  # ElevenLabs SDK raises provider-specific exceptions here
        logger.warning("ElevenLabs transcription failed: %s", exc)
        return TranscriptResult(
            text="", audio_events=[], success=False, error="Transcription is unavailable right now."
        )

    text = (result.text or "").strip()
    audio_events = [w.text for w in (result.words or []) if getattr(w, "type", None) == "audio_event"]

    if not text:
        return TranscriptResult(
            text="", audio_events=audio_events, success=False, error="No understandable speech was detected."
        )

    return TranscriptResult(text=text, audio_events=audio_events, success=True)


def synthesize_result(text: str) -> Path | None:
    config = load_config()

    if not config.tts_enabled or not config.elevenlabs_api_key:
        return None

    if not config.elevenlabs_voice_id:
        logger.warning("TTS_ENABLED is true but ELEVENLABS_VOICE_ID is not configured; skipping speech output.")
        return None

    try:
        import wave

        pcm_sample_rate = 24000
        chunks = _client().text_to_speech.convert(
            text=text,
            voice_id=config.elevenlabs_voice_id,
            model_id=config.elevenlabs_tts_model,
            output_format=f"pcm_{pcm_sample_rate}",
        )
        pcm_bytes = b"".join(chunks)

        # Written as a real WAV (not the raw headerless PCM ElevenLabs returns) so
        # playback.py's afplay/aplay/winsound all get a file format they can open —
        # winsound in particular cannot play MP3 on Windows, only WAV.
        path = new_temp_path(".wav")
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(pcm_sample_rate)
            wav_file.writeframes(pcm_bytes)
        return path
    except Exception as exc:
        logger.warning("ElevenLabs TTS failed: %s", exc)
        return None
