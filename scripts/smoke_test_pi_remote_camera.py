"""Task 13 (laptop-mic variant) smoke test: capture one frame from a Pi
Camera over SSH while this process stays on the laptop, and verify the JPEG
exists and can be decoded.

Runs ON THE LAPTOP. Requires key-based SSH auth to PI_SSH_HOST (see README)
and rpicam-still available on the Pi.

Usage:
    python scripts/smoke_test_pi_remote_camera.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import PiRemoteCameraProvider  # noqa: E402
from config import load_config  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent / "_smoke_pi_remote_camera_output.jpg"


def main() -> None:
    config = load_config()
    provider = PiRemoteCameraProvider(host=config.pi_ssh_host)

    path = provider.capture()
    if path is None:
        print(
            f"FAIL: could not capture from {config.pi_ssh_host}. Check that "
            "key-based SSH login works (ssh " + config.pi_ssh_host + " echo ok), "
            "that rpicam-still is installed on the Pi, and that the camera "
            "ribbon cable is seated."
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
