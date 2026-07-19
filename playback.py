import logging
import platform
import subprocess
from pathlib import Path

from tempfiles import cleanup

logger = logging.getLogger("iris.playback")


def play_mp3(path: Path) -> bool:
    """Play a local MP3 file synchronously."""

    if not path.exists():
        logger.warning("Audio file does not exist: %s", path)
        return False

    system = platform.system()

    try:
        if system == "Darwin":
            subprocess.run(
                ["afplay", str(path)],
                check=True,
                capture_output=True,
            )
            return True

        if system == "Linux":
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", str(path)],
                check=True,
                capture_output=True,
            )
            return True

        if system == "Windows":
            import pygame

            pygame.mixer.init()
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()

            clock = pygame.time.Clock()

            while pygame.mixer.music.get_busy():
                clock.tick(10)

            pygame.mixer.music.unload()
            pygame.mixer.quit()
            return True

        logger.warning(
            "MP3 playback is not supported on platform: %s",
            system,
        )
        return False

    except Exception as exc:
        logger.warning("MP3 playback failed: %s", exc)

        if system == "Windows":
            try:
                pygame.mixer.quit()
            except Exception:
                pass

        return False


def play_and_cleanup(path: Path) -> bool:
    """Play a temporary MP3 and always delete it afterward."""

    try:
        return play_mp3(path)
    finally:
        cleanup(path)