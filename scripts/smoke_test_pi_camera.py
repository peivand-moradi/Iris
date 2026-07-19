"""Task 13 smoke test: capture one frame from the Pi Camera via Picamera2
and verify the JPEG exists and can be decoded. Always releases the camera.

Only runs on Raspberry Pi OS with the python3-picamera2 system package
installed (see requirements-pi.txt) — will FAIL cleanly everywhere else.

Usage:
    python scripts/smoke_test_pi_camera.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import PiCameraProvider  # noqa: E402

OUTPUT_PATH = Path("scripts/_smoke_pi_camera_output.jpg")


def main() -> None:
    provider = PiCameraProvider()

    path = provider.capture()
    if path is None:
        print(
            "FAIL: could not capture from the Pi Camera. Check that picamera2 is "
            "installed (sudo apt install python3-picamera2), the venv was created "
            "with --system-site-packages, the camera ribbon cable is seated, and "
            "no other process (e.g. another Iris instance) is holding the camera."
        )
        raise SystemExit(1)

    import shutil

    shutil.copy(path, OUTPUT_PATH)

    import cv2

    if cv2.imread(str(OUTPUT_PATH)) is None:
        print("FAIL: captured JPEG could not be decoded.")
        raise SystemExit(1)

    print(f"OK: captured and decoded a frame, saved to {OUTPUT_PATH}")
    print("Open it and confirm it looks like a reasonable Pi Camera frame.")


if __name__ == "__main__":
    main()
