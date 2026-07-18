import audio


def test_get_recent_audio_returns_none_when_stream_not_started(monkeypatch):
    monkeypatch.setattr(audio._config, "demo_mode", False)
    assert audio._buffer.is_running is False
    assert audio.get_recent_audio() is None


def test_demo_mode_returns_sample_audio_path(monkeypatch, tmp_path):
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFF....WAVEfmt ")

    monkeypatch.setattr(audio._config, "demo_mode", True)
    monkeypatch.setattr(audio._config, "sample_audio_path", str(sample))

    result = audio.get_recent_audio()

    assert result == sample


def test_demo_mode_missing_sample_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(audio._config, "demo_mode", True)
    monkeypatch.setattr(audio._config, "sample_audio_path", str(tmp_path / "missing.wav"))

    assert audio.get_recent_audio() is None
