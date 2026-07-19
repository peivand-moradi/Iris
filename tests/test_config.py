from config import load_config


def test_defaults_when_env_absent(monkeypatch):
    for key in (
        "BACKBOARD_API_KEY", "BACKBOARD_ASSISTANT_ID", "ELEVENLABS_API_KEY",
        "CAMERA_MODE", "TTS_ENABLED", "DEMO_MODE", "MIC_DEVICE_INDEX",
    ):
        monkeypatch.delenv(key, raising=False)

    config = load_config()

    assert config.camera_mode == "laptop"
    assert config.tts_enabled is False
    assert config.demo_mode is False
    assert config.audio_buffer_seconds == 10
    assert config.elevenlabs_stt_model == "scribe_v2"
    assert config.trigger_mode == "software"
    assert config.gpio_button_pin == 17
    assert config.mic_device_index is None


def test_env_overrides_are_read(monkeypatch):
    monkeypatch.setenv("CAMERA_MODE", "sample")
    monkeypatch.setenv("TTS_ENABLED", "true")
    monkeypatch.setenv("DEMO_MODE", "TRUE")
    monkeypatch.setenv("AUDIO_BUFFER_SECONDS", "5")
    monkeypatch.setenv("TRIGGER_MODE", "gpio")
    monkeypatch.setenv("GPIO_BUTTON_PIN", "27")
    monkeypatch.setenv("MIC_DEVICE_INDEX", "2")

    config = load_config()

    assert config.camera_mode == "sample"
    assert config.tts_enabled is True
    assert config.demo_mode is True
    assert config.audio_buffer_seconds == 5
    assert config.trigger_mode == "gpio"
    assert config.gpio_button_pin == 27
    assert config.mic_device_index == 2


def test_bool_parsing_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("TTS_ENABLED", "False")
    assert load_config().tts_enabled is False

    monkeypatch.setenv("TTS_ENABLED", "yes")
    assert load_config().tts_enabled is True
