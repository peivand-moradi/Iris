import logging
from typing import Callable

logger = logging.getLogger("iris.trigger")


class GPIOButtonTrigger:
    """Task 13: physical push-button trigger for Raspberry Pi.

    Wraps gpiozero.Button so a physical button press calls exactly the same
    callback the software button already uses (App.trigger_interpretation,
    which calls controller.run_interpretation()) — no separate code path.
    Only importable/usable on Raspberry Pi OS with gpiozero installed.
    """

    def __init__(self, pin: int, on_press: Callable[[], None], bounce_time: float = 0.3) -> None:
        self.pin = pin
        self.on_press = on_press
        self.bounce_time = bounce_time
        self._button = None

    def start(self) -> None:
        from gpiozero import Button

        self._button = Button(self.pin, bounce_time=self.bounce_time)
        self._button.when_pressed = self.on_press
        logger.info("GPIO button trigger started on pin %d", self.pin)

    def stop(self) -> None:
        if self._button is not None:
            self._button.close()
            self._button = None
            logger.info("GPIO button trigger stopped")
