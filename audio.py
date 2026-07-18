import logging
import threading
import wave
from collections import deque
from pathlib import Path

import numpy as np
import sounddevice as sd

from config import load_config
from tempfiles import new_temp_path

logger = logging.getLogger("iris.audio")

_SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM
_BLOCK_FRAMES = 1024
_MIN_USABLE_FRAMES = 4000  # ~0.25s at 16kHz; guards against near-empty buffers


class RollingAudioBuffer:
    """Keeps roughly `buffer_seconds` of recent mono 16-bit audio in RAM.

    The sounddevice callback runs on its own thread, so all access to the
    underlying deque is protected by a lock. Nothing is written to disk
    until save_recent_window() is called.
    """

    def __init__(self, sample_rate: int, buffer_seconds: int) -> None:
        self.sample_rate = sample_rate
        self.buffer_seconds = buffer_seconds
        max_blocks = max(1, int(buffer_seconds * sample_rate / _BLOCK_FRAMES) + 1)
        self._blocks: deque[np.ndarray] = deque(maxlen=max_blocks)
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    @property
    def is_running(self) -> bool:
        return self._stream is not None

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            logger.debug("Audio stream status: %s", status)
        with self._lock:
            self._blocks.append(indata[:, 0].copy())

    def start(self) -> None:
        if self._stream is not None:
            return
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=_BLOCK_FRAMES,
            callback=self._callback,
        )
        self._stream.start()
        logger.info("Microphone stream started at %d Hz", self.sample_rate)

    def stop(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            with self._lock:
                self._blocks.clear()
        logger.info("Microphone stream stopped")

    def snapshot(self) -> np.ndarray:
        with self._lock:
            if not self._blocks:
                return np.array([], dtype="int16")
            return np.concatenate(list(self._blocks))

    def save_recent_window(self) -> Path | None:
        samples = self.snapshot()
        if samples.size < _MIN_USABLE_FRAMES:
            logger.warning("Rolling audio buffer too short to be usable (%d frames)", samples.size)
            return None

        path = new_temp_path(".wav")
        try:
            with wave.open(str(path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(_SAMPLE_WIDTH_BYTES)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(samples.tobytes())
        except OSError as exc:
            logger.error("Failed to write WAV file: %s", exc)
            return None
        return path


_config = load_config()
_buffer = RollingAudioBuffer(sample_rate=_config.mic_sample_rate, buffer_seconds=_config.audio_buffer_seconds)


def start_audio_stream() -> None:
    """Start the rolling microphone buffer. Raises if no input device is available."""
    _buffer.start()


def stop_audio_stream() -> None:
    _buffer.stop()


def get_recent_audio() -> Path | None:
    """Return a WAV file covering the most recent audio window, or None if unavailable.

    In demo mode this returns the checked-in sample WAV instead of the live
    buffer, per Task 12's requirement that demo mode uses prerecorded audio.
    """
    if _config.demo_mode:
        sample_path = Path(_config.sample_audio_path)
        if not sample_path.exists():
            logger.error("Demo mode sample audio missing: %s", sample_path)
            return None
        return sample_path

    if not _buffer.is_running:
        logger.warning("get_recent_audio() called before the microphone stream was started")
        return None

    return _buffer.save_recent_window()
