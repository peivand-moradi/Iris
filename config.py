import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    backboard_api_key: str
    backboard_assistant_id: str
    backboard_provider: str
    backboard_model: str
    elevenlabs_api_key: str
    elevenlabs_stt_model: str
    elevenlabs_tts_model: str
    elevenlabs_voice_id: str
    audio_buffer_seconds: int
    capture_seconds: int
    mic_device_index: int | None
    camera_mode: str
    camera_index: int
    pi_ssh_host: str
    trigger_mode: str
    gpio_button_pin: int
    tts_enabled: bool
    demo_mode: bool
    sample_audio_path: str
    sample_image_path: str
    mic_sample_rate: int
    backboard_base_url: str
    request_timeout_seconds: int


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes")


def _optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def load_config() -> Config:
    return Config(
        backboard_api_key=os.getenv("BACKBOARD_API_KEY", ""),
        backboard_assistant_id=os.getenv("BACKBOARD_ASSISTANT_ID", ""),
        backboard_provider=os.getenv("BACKBOARD_PROVIDER", ""),
        backboard_model=os.getenv("BACKBOARD_MODEL", ""),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        elevenlabs_stt_model=os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2"),
        elevenlabs_tts_model=os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5"),
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", ""),
        audio_buffer_seconds=int(os.getenv("AUDIO_BUFFER_SECONDS", "10")),
        capture_seconds=int(os.getenv("CAPTURE_SECONDS", "10")),
        mic_device_index=_optional_int(os.getenv("MIC_DEVICE_INDEX", "")),
        camera_mode=os.getenv("CAMERA_MODE", "laptop"),
        camera_index=int(os.getenv("CAMERA_INDEX", "0")),
        pi_ssh_host=os.getenv("PI_SSH_HOST", "iris@iris.local"),
        trigger_mode=os.getenv("TRIGGER_MODE", "software"),
        gpio_button_pin=int(os.getenv("GPIO_BUTTON_PIN", "17")),
        tts_enabled=_bool(os.getenv("TTS_ENABLED", "false")),
        demo_mode=_bool(os.getenv("DEMO_MODE", "false")),
        sample_audio_path=os.getenv("SAMPLE_AUDIO_PATH", "samples/audio/sample.wav"),
        sample_image_path=os.getenv("SAMPLE_IMAGE_PATH", "samples/images/sample.jpg"),
        mic_sample_rate=int(os.getenv("MIC_SAMPLE_RATE", "16000")),
        backboard_base_url=os.getenv("BACKBOARD_BASE_URL", "https://app.backboard.io/api"),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
    )
