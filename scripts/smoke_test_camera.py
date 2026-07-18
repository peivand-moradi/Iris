"""Task 2 smoke test: capture one frame from the laptop webcam via OpenCV
and verify the JPEG exists and can be decoded. Always releases the camera.

Usage:
    python scripts/smoke_test_camera.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import LaptopCameraProvider  # noqa: E402
from config import load_config  # noqa: E402

OUTPUT_PATH = Path("scripts/_smoke_camera_output.jpg")


def main() -> None:
    config = load_config()
    provider = LaptopCameraProvider(camera_index=config.camera_index)

    path = provider.capture()
    if path is None:
        print(
            f"FAIL: could not capture from camera index {config.camera_index}. "
            "Check that no other app is using the camera and that camera "
            "permission is granted to this terminal/Python."
        )
        raise SystemExit(1)

    import shutil

    shutil.copy(path, OUTPUT_PATH)

    import cv2

    if cv2.imread(str(OUTPUT_PATH)) is None:
        print("FAIL: captured JPEG could not be decoded.")
        raise SystemExit(1)

    print(f"OK: captured and decoded a frame, saved to {OUTPUT_PATH}")
    print("Open it and confirm it looks like a reasonable webcam frame.")


if __name__ == "__main__":
    main()
