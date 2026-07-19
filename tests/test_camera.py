import subprocess
import sys
import types
from pathlib import Path

import cv2
import numpy as np
import pytest

from camera import (
    LaptopCameraProvider,
    PiCameraProvider,
    PiRemoteCameraProvider,
    SampleImageProvider,
    get_camera_provider,
)


def test_sample_image_provider_missing_file_returns_none(tmp_path):
    provider = SampleImageProvider(sample_path=tmp_path / "does_not_exist.jpg")
    assert provider.capture() is None


def test_sample_image_provider_returns_existing_readable_image():
    provider = SampleImageProvider(sample_path=Path("samples/images/sample.jpg"))
    result = provider.capture()
    assert result == Path("samples/images/sample.jpg")


def test_pi_camera_provider_returns_none_when_picamera2_unavailable():
    # picamera2 is a Raspberry Pi OS system package and is genuinely not
    # installed in this environment, so this exercises the real ImportError
    # fallback rather than a mock.
    provider = PiCameraProvider()
    assert provider.capture() is None


def _install_fake_picamera2(monkeypatch, picamera2_class):
    fake_module = types.ModuleType("picamera2")
    fake_module.Picamera2 = picamera2_class
    monkeypatch.setitem(sys.modules, "picamera2", fake_module)
    monkeypatch.setattr("camera.time.sleep", lambda seconds: None)


def test_pi_camera_provider_capture_success_with_mocked_picamera2(monkeypatch):
    calls = []

    class _FakePicamera2:
        def create_still_configuration(self, main=None):
            return {"main": main}

        def configure(self, config):
            calls.append(("configure", config))

        def start(self):
            calls.append(("start",))

        def capture_file(self, path):
            calls.append(("capture_file", path))
            cv2.imwrite(path, np.zeros((10, 10, 3), dtype="uint8"))

        def close(self):
            calls.append(("close",))

    _install_fake_picamera2(monkeypatch, _FakePicamera2)

    provider = PiCameraProvider()
    result = provider.capture()

    assert result is not None
    assert result.exists()
    assert [c[0] for c in calls] == ["configure", "start", "capture_file", "close"]


def test_pi_camera_provider_closes_camera_even_on_capture_failure(monkeypatch):
    calls = []

    class _FakePicamera2:
        def create_still_configuration(self, main=None):
            return {}

        def configure(self, config):
            pass

        def start(self):
            raise RuntimeError("camera exploded")

        def capture_file(self, path):
            pass

        def close(self):
            calls.append("closed")

    _install_fake_picamera2(monkeypatch, _FakePicamera2)

    provider = PiCameraProvider()
    result = provider.capture()

    assert result is None
    assert calls == ["closed"]


def test_unknown_camera_mode_raises_value_error():
    with pytest.raises(ValueError):
        get_camera_provider("bluetooth-camera")


def test_get_camera_provider_returns_matching_types():
    assert isinstance(get_camera_provider("laptop"), LaptopCameraProvider)
    assert isinstance(get_camera_provider("sample"), SampleImageProvider)
    assert isinstance(get_camera_provider("pi"), PiCameraProvider)
    assert isinstance(get_camera_provider("pi-remote"), PiRemoteCameraProvider)


def test_laptop_camera_provider_capture_failure_returns_none_without_raising(monkeypatch):
    class _FakeCap:
        def isOpened(self):
            return False

        def release(self):
            pass

    # accepts the optional backend flag (e.g. cv2.CAP_DSHOW on Windows) too
    monkeypatch.setattr("camera.cv2.VideoCapture", lambda index, *args: _FakeCap())

    provider = LaptopCameraProvider(camera_index=0)
    assert provider.capture() is None


def test_laptop_camera_provider_uses_dshow_backend_on_windows(monkeypatch):
    calls = []

    class _FakeCap:
        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr("camera.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "camera.cv2.VideoCapture",
        lambda index, *args: calls.append((index, args)) or _FakeCap(),
    )

    LaptopCameraProvider(camera_index=0).capture()

    assert calls == [(0, (cv2.CAP_DSHOW,))]


def test_laptop_camera_provider_does_not_use_dshow_backend_off_windows(monkeypatch):
    calls = []

    class _FakeCap:
        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr("camera.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "camera.cv2.VideoCapture",
        lambda index, *args: calls.append((index, args)) or _FakeCap(),
    )

    LaptopCameraProvider(camera_index=0).capture()

    assert calls == [(0, ())]


def test_laptop_camera_provider_retries_until_a_usable_frame_arrives(monkeypatch):
    good_frame = np.zeros((10, 10, 3), dtype="uint8")

    class _FakeCap:
        def __init__(self):
            self.reads = 0

        def isOpened(self):
            return True

        def set(self, prop, value):
            pass

        def read(self):
            self.reads += 1
            # first two reads fail (as commonly happens right after opening a
            # webcam), then succeed — the old code gave up on the very first
            # failed read, the retry loop should not.
            if self.reads <= 2:
                return False, None
            return True, good_frame

        def release(self):
            pass

    monkeypatch.setattr("camera.cv2.VideoCapture", lambda index, *args: _FakeCap())
    monkeypatch.setattr("camera.time.sleep", lambda seconds: None)

    provider = LaptopCameraProvider(camera_index=0)
    result = provider.capture()

    assert result is not None
    assert result.exists()


def test_laptop_camera_provider_gives_up_after_max_attempts(monkeypatch):
    class _FakeCap:
        def isOpened(self):
            return True

        def set(self, prop, value):
            pass

        def read(self):
            return False, None

        def release(self):
            pass

    monkeypatch.setattr("camera.cv2.VideoCapture", lambda index, *args: _FakeCap())
    monkeypatch.setattr("camera.time.sleep", lambda seconds: None)

    provider = LaptopCameraProvider(camera_index=0)
    assert provider.capture() is None


def _completed(returncode=0, stderr=b""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stderr=stderr)


def test_pi_remote_camera_provider_capture_success(monkeypatch):
    calls = []

    def fake_run(args, capture_output, timeout):
        calls.append(args)
        if args[0] == "scp":
            local_path = args[2]
            cv2.imwrite(local_path, np.zeros((10, 10, 3), dtype="uint8"))
        return _completed(returncode=0)

    monkeypatch.setattr("camera.subprocess.run", fake_run)

    provider = PiRemoteCameraProvider(host="iris@iris.local")
    result = provider.capture()

    assert result is not None
    assert result.exists()
    assert calls[0][0] == "ssh"
    assert calls[1][0] == "scp"
    assert calls[2][0] == "ssh"
    assert calls[2][1] == "iris@iris.local"
    assert calls[2][2].startswith("rm -f ")


def test_pi_remote_camera_provider_returns_none_when_ssh_capture_fails(monkeypatch):
    def fake_run(args, capture_output, timeout):
        if args[0] == "ssh" and args[2].startswith("rpicam-still"):
            return _completed(returncode=1, stderr=b"no cameras available")
        return _completed(returncode=0)

    monkeypatch.setattr("camera.subprocess.run", fake_run)

    provider = PiRemoteCameraProvider(host="iris@iris.local")
    assert provider.capture() is None


def test_pi_remote_camera_provider_returns_none_when_scp_transfer_fails(monkeypatch):
    def fake_run(args, capture_output, timeout):
        if args[0] == "scp":
            return _completed(returncode=1, stderr=b"lost connection")
        return _completed(returncode=0)

    monkeypatch.setattr("camera.subprocess.run", fake_run)

    provider = PiRemoteCameraProvider(host="iris@iris.local")
    assert provider.capture() is None


def test_pi_remote_camera_provider_returns_none_on_timeout(monkeypatch):
    def fake_run(args, capture_output, timeout):
        raise subprocess.TimeoutExpired(cmd=args, timeout=timeout)

    monkeypatch.setattr("camera.subprocess.run", fake_run)

    provider = PiRemoteCameraProvider(host="iris@iris.local")
    assert provider.capture() is None


def test_pi_remote_camera_provider_returns_none_when_ssh_binary_missing(monkeypatch):
    def fake_run(args, capture_output, timeout):
        raise FileNotFoundError("ssh not found")

    monkeypatch.setattr("camera.subprocess.run", fake_run)

    provider = PiRemoteCameraProvider(host="iris@iris.local")
    assert provider.capture() is None
