import logging
import platform
import subprocess
from pathlib import Path

from tempfiles import cleanup

logger = logging.getLogger("iris.playback")


def play_mp3(path: Path) -> bool:
    """Play a local MP3 file synchronously.

    Uses the platform's built-in playback command so no extra audio-decoding
    dependency is required. Returns True if a player was found and ran
    without error; False if playback is unsupported or failed.
    """
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["afplay", str(path)], check=True, capture_output=True)
            return True
        if system == "Linux":
            subprocess.run(["aplay", str(path)], check=True, capture_output=True)
            return True
        if system == "Windows":
            import winsound

            winsound.PlaySound(str(path), winsound.SND_FILENAME)
            return True
        logger.warning("MP3 playback is not supported on platform: %s", system)
        return False
    except FileNotFoundError:
        logger.warning("No system audio player found for platform: %s", system)
        return False
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("MP3 playback failed: %s", exc)
        return False


def play_and_cleanup(path: Path) -> bool:
    """Play a temporary MP3 and always delete it afterward."""
    try:
        return play_mp3(path)
    finally:
        cleanup(path)
