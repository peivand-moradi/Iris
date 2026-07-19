"""Task 13 smoke test: wire up the physical button via GPIOButtonTrigger
(the same class app.py uses) and confirm a real press is detected.

Only runs on Raspberry Pi OS with gpiozero installed (see requirements-pi.txt)
and a button wired between the configured GPIO pin and GND.

Usage:
    python scripts/smoke_test_gpio_button.py [pin] [timeout_seconds]
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config  # noqa: E402
from trigger import GPIOButtonTrigger  # noqa: E402


def main() -> None:
    config = load_config()
    pin = int(sys.argv[1]) if len(sys.argv) > 1 else config.gpio_button_pin
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0

    pressed = threading.Event()

    try:
        gpio_trigger = GPIOButtonTrigger(pin=pin, on_press=pressed.set)
        gpio_trigger.start()
    except Exception as exc:
        print(
            f"FAIL: could not start the GPIO trigger on pin {pin} ({exc}). "
            "Check that gpiozero is installed and this is running on the Pi."
        )
        raise SystemExit(1)

    print(f"Listening on GPIO pin {pin} (BCM numbering). Press the button now...")
    print(f"Waiting up to {timeout:.0f}s.")

    detected = pressed.wait(timeout=timeout)
    gpio_trigger.stop()

    if not detected:
        print(
            "FAIL: no press detected in time. Check the wiring (button between "
            f"pin {pin} and GND) and that you're using the correct BCM pin number."
        )
        raise SystemExit(1)

    print("OK: button press detected.")


if __name__ == "__main__":
    main()
