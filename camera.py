import logging
import platform
import time
from pathlib import Path
from typing import Protocol

import cv2

from config import load_config
from tempfiles import new_temp_path

logger = logging.getLogger("iris.camera")

_CAPTURE_WIDTH = 1280
_CAPTURE_HEIGHT = 720
_WARMUP_FRAMES = 3  # discard a few frames so exposure/white-balance can settle
_MAX_CAPTURE_ATTEMPTS = 10
_CAPTURE_RETRY_DELAY_SECONDS = 0.1


class CameraProvider(Protocol):
    def capture(self) -> Path | None:
        ...


class LaptopCameraProvider:
    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index

    def capture(self) -> Path | None:
        if platform.system() == "Windows":
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self.camera_index)

        try:
            if not cap.isOpened():
                logger.warning(
                    "Laptop camera at index %d could not be opened",
                    self.camera_index,
                )
                return None

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, _CAPTURE_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, _CAPTURE_HEIGHT)

            frame = None

            for attempt in range(_MAX_CAPTURE_ATTEMPTS):
                ok, candidate = cap.read()

                if ok and candidate is not None and candidate.size > 0:
                    frame = candidate

                if frame is not None and attempt >= _WARMUP_FRAMES:
                    break

                time.sleep(_CAPTURE_RETRY_DELAY_SECONDS)

            if frame is None:
                logger.warning(
                    "Laptop camera at index %d opened but failed to deliver "
                    "a usable frame",
                    self.camera_index,
                )
                return None

            path = new_temp_path(".jpg")

            if not cv2.imwrite(str(path), frame):
                logger.warning("Failed to write captured frame to disk")
                return None

            if cv2.imread(str(path)) is None:
                logger.warning("Captured JPEG could not be decoded back")
                return None

            return path

        except cv2.error as exc:
            logger.warning("OpenCV error during capture: %s", exc)
            return None

        finally:
            cap.release()


class SampleImageProvider:
    def __init__(self, sample_path: Path | None = None):
        self.sample_path = sample_path or Path(load_config().sample_image_path)

    def capture(self) -> Path | None:
        if not self.sample_path.exists():
            logger.warning("Sample image not found: %s", self.sample_path)
            return None

        if cv2.imread(str(self.sample_path)) is None:
            logger.warning(
                "Sample image could not be decoded: %s",
                self.sample_path,
            )
            return None

        return self.sample_path


class PiCameraProvider:
    """Interface-compatible stub. Real Picamera2 integration is out of scope."""

    def capture(self) -> Path | None:
        raise NotImplementedError(
            "PiCameraProvider is not implemented in this MVP. "
            "Set CAMERA_MODE=laptop or CAMERA_MODE=sample."
        )


def get_camera_provider(mode: str) -> CameraProvider:
    config = load_config()

    providers = {
        "laptop": lambda: LaptopCameraProvider(config.camera_index),
        "sample": SampleImageProvider,
        "pi": PiCameraProvider,
    }

    if mode not in providers:
        raise ValueError(f"Unknown camera mode: {mode}")

    return providers[mode]()