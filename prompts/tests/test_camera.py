from pathlib import Path

import pytest

from camera import LaptopCameraProvider, PiCameraProvider, SampleImageProvider, get_camera_provider


def test_sample_image_provider_missing_file_returns_none(tmp_path):
    provider = SampleImageProvider(sample_path=tmp_path / "does_not_exist.jpg")
    assert provider.capture() is None


def test_sample_image_provider_returns_existing_readable_image():
    provider = SampleImageProvider(sample_path=Path("prompts/samples/images/sample.jpg"))
    result = provider.capture()
    assert result == Path("prompts/samples/images/sample.jpg")


def test_pi_camera_provider_raises_not_implemented():
    provider = PiCameraProvider()
    with pytest.raises(NotImplementedError):
        provider.capture()


def test_unknown_camera_mode_raises_value_error():
    with pytest.raises(ValueError):
        get_camera_provider("bluetooth-camera")


def test_get_camera_provider_returns_matching_types():
    assert isinstance(get_camera_provider("laptop"), LaptopCameraProvider)
    assert isinstance(get_camera_provider("sample"), SampleImageProvider)
    assert isinstance(get_camera_provider("pi"), PiCameraProvider)


def test_laptop_camera_provider_capture_failure_returns_none_without_raising(monkeypatch):
    class _FakeCap:
        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr("camera.cv2.VideoCapture", lambda index: _FakeCap())

    provider = LaptopCameraProvider(camera_index=0)
    assert provider.capture() is None
