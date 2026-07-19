import sys
import types

from trigger import GPIOButtonTrigger


def _install_fake_gpiozero(monkeypatch):
    created = []

    class _FakeButton:
        def __init__(self, pin, bounce_time=None):
            self.pin = pin
            self.bounce_time = bounce_time
            self.when_pressed = None
            self.closed = False
            created.append(self)

        def close(self):
            self.closed = True

    fake_module = types.ModuleType("gpiozero")
    fake_module.Button = _FakeButton
    monkeypatch.setitem(sys.modules, "gpiozero", fake_module)
    return created


def test_start_wires_when_pressed_to_callback(monkeypatch):
    created = _install_fake_gpiozero(monkeypatch)
    presses = []

    gpio_trigger = GPIOButtonTrigger(pin=17, on_press=lambda: presses.append(1), bounce_time=0.3)
    gpio_trigger.start()

    assert len(created) == 1
    assert created[0].pin == 17
    assert created[0].bounce_time == 0.3

    created[0].when_pressed()
    assert presses == [1]


def test_stop_closes_button(monkeypatch):
    created = _install_fake_gpiozero(monkeypatch)

    gpio_trigger = GPIOButtonTrigger(pin=17, on_press=lambda: None)
    gpio_trigger.start()
    gpio_trigger.stop()

    assert created[0].closed is True


def test_stop_is_safe_when_never_started():
    gpio_trigger = GPIOButtonTrigger(pin=17, on_press=lambda: None)
    gpio_trigger.stop()  # must not raise
