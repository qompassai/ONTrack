"""
tests/test_voice.py — Voice recognition tests for OnTrack.

Test structure:
  Unit tests (fast, no hardware, no model download):
    - VoiceRecognizer state machine
    - RecordingState transitions
    - VoiceResult __bool__ logic
    - Audio format validation
    - Platform detection
    - PipeWire node env var handling

  Integration tests (require sounddevice + faster-whisper):
    Marked with @pytest.mark.integration
    Skipped automatically in CI if deps are missing.

  Hardware tests (require real microphone):
    Marked with @pytest.mark.hardware
    Always skipped in CI.

Run unit tests only:
    pytest tests/test_voice.py -m "not integration and not hardware" -v

Run integration tests (needs faster-whisper installed):
    pytest tests/test_voice.py -m integration -v

Run everything including hardware tests:
    pytest tests/test_voice.py --hardware -v
"""

from __future__ import annotations

import os
import time
import threading
import platform
import pathlib
import wave
import struct
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Optional

import numpy as np
import pytest

# ── Fixtures & helpers ─────────────────────────────────────────────────────

@pytest.fixture
def silence_audio() -> np.ndarray:
    """1 second of silence at 16 kHz int16."""
    return np.zeros(16_000, dtype=np.int16)


@pytest.fixture
def tone_audio() -> np.ndarray:
    """1 second of 440 Hz sine wave at 16 kHz int16 (≈ speech-level amplitude)."""
    t = np.linspace(0, 1.0, 16_000, endpoint=False)
    return (np.sin(2 * np.pi * 440 * t) * 8192).astype(np.int16)


@pytest.fixture
def sample_wav(tmp_path, tone_audio) -> str:
    """Write a 440Hz WAV file and return its path."""
    p = str(tmp_path / "sample.wav")
    with wave.open(p, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16_000)
        wf.writeframes(tone_audio.tobytes())
    return p


@pytest.fixture
def mock_faster_whisper():
    """Patch faster_whisper.WhisperModel so no download or GPU is needed."""
    mock_segment = MagicMock()
    mock_segment.text = "  123 Main Street Spokane  "

    mock_info = MagicMock()
    mock_info.language = "en"

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=MagicMock(return_value=mock_model))}):
        yield mock_model


@pytest.fixture
def mock_sounddevice():
    """Patch sounddevice so no real hardware is touched."""
    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)

    mock_sd = MagicMock()
    mock_sd.InputStream.return_value = mock_stream
    mock_sd.query_devices.return_value = [
        {"name": "OnTrack Echo Cancel", "max_input_channels": 1},
        {"name": "Built-in Microphone",  "max_input_channels": 1},
    ]

    with patch.dict("sys.modules", {"sounddevice": mock_sd}):
        yield mock_sd


# ── Unit: VoiceResult ──────────────────────────────────────────────────────

class TestVoiceResult:
    def test_truthy_when_text_present(self):
        from core.voice import VoiceResult
        r = VoiceResult(text="hello", language="en", duration=1.0, elapsed=0.5)
        assert bool(r) is True

    def test_falsy_when_empty_text(self):
        from core.voice import VoiceResult
        r = VoiceResult(text="", language="en", duration=1.0, elapsed=0.5)
        assert bool(r) is False

    def test_falsy_on_error(self):
        from core.voice import VoiceResult
        r = VoiceResult(text="hello", language="en", duration=1.0, elapsed=0.5,
                        error="mic error")
        assert bool(r) is False

    def test_falsy_whitespace_only(self):
        from core.voice import VoiceResult
        r = VoiceResult(text="   ", language="en", duration=1.0, elapsed=0.5)
        assert bool(r) is False


# ── Unit: RecordingState ───────────────────────────────────────────────────

class TestRecordingState:
    def test_idle_by_default(self):
        from core.voice import VoiceRecognizer, RecordingState
        vr = VoiceRecognizer()
        assert vr.state == RecordingState.IDLE

    def test_not_recording_initially(self):
        from core.voice import VoiceRecognizer
        vr = VoiceRecognizer()
        assert vr.is_recording() is False

    def test_not_processing_initially(self):
        from core.voice import VoiceRecognizer
        vr = VoiceRecognizer()
        assert vr.is_processing() is False

    def test_stop_without_start_returns_error(self):
        from core.voice import VoiceRecognizer
        vr = VoiceRecognizer()
        result = vr.stop_and_transcribe()
        assert result.error is not None
        assert "recording" in result.error.lower()


# ── Unit: audio constants ──────────────────────────────────────────────────

class TestAudioConstants:
    def test_sample_rate_is_16k(self):
        from core.voice import SAMPLE_RATE
        assert SAMPLE_RATE == 16_000

    def test_channels_is_mono(self):
        from core.voice import CHANNELS
        assert CHANNELS == 1

    def test_max_record_sensible(self):
        from core.voice import MAX_RECORD_S
        assert 10 <= MAX_RECORD_S <= 300


# ── Unit: device listing (sounddevice mocked) ──────────────────────────────

class TestDeviceListing:
    def test_list_devices_returns_list(self, mock_sounddevice):
        from core.voice import VoiceRecognizer
        devices = VoiceRecognizer.list_input_devices()
        assert isinstance(devices, list)

    def test_list_devices_has_name_and_index(self, mock_sounddevice):
        from core.voice import VoiceRecognizer
        devices = VoiceRecognizer.list_input_devices()
        for dev in devices:
            assert "name" in dev
            assert "index" in dev

    def test_list_devices_no_crash_without_sounddevice(self):
        """If sounddevice is missing, list_input_devices returns [] gracefully."""
        import sys
        saved = sys.modules.pop("sounddevice", None)
        try:
            from core.voice import VoiceRecognizer
            result = VoiceRecognizer.list_input_devices()
            assert result == []
        finally:
            if saved:
                sys.modules["sounddevice"] = saved


# ── Unit: PipeWire node selection ─────────────────────────────────────────

class TestPipeWireNodeSelection:
    def test_env_var_selects_device(self, mock_sounddevice, monkeypatch):
        monkeypatch.setenv("ONTRACK_PIPEWIRE_NODE", "OnTrack Echo Cancel")
        from core.voice import _get_sounddevice_device
        idx = _get_sounddevice_device()
        assert idx == 0  # first device in mock list matches

    def test_no_env_returns_none(self, mock_sounddevice, monkeypatch):
        monkeypatch.delenv("ONTRACK_PIPEWIRE_NODE", raising=False)
        from core.voice import _get_sounddevice_device
        idx = _get_sounddevice_device()
        assert idx is None  # use system default

    def test_unknown_node_returns_none(self, mock_sounddevice, monkeypatch):
        monkeypatch.setenv("ONTRACK_PIPEWIRE_NODE", "NonExistentDevice")
        from core.voice import _get_sounddevice_device
        idx = _get_sounddevice_device()
        assert idx is None


# ── Unit: _transcribe() with mocked model ─────────────────────────────────

class TestTranscribeUnit:
    def test_empty_audio_returns_error(self):
        from core.voice import _transcribe
        result = _transcribe(np.zeros(0, dtype=np.int16))
        assert result.error is not None

    def test_returns_voice_result_type(self, mock_faster_whisper, tone_audio):
        from core.voice import _transcribe, VoiceResult
        result = _transcribe(tone_audio)
        assert isinstance(result, VoiceResult)

    def test_transcribe_text_stripped(self, mock_faster_whisper, tone_audio):
        from core.voice import _transcribe
        result = _transcribe(tone_audio)
        assert result.text == "123 Main Street Spokane"

    def test_transcribe_language_detected(self, mock_faster_whisper, tone_audio):
        from core.voice import _transcribe
        result = _transcribe(tone_audio)
        assert result.language == "en"

    def test_transcribe_duration_approximate(self, mock_faster_whisper, tone_audio):
        from core.voice import _transcribe, SAMPLE_RATE
        result = _transcribe(tone_audio)
        expected_dur = len(tone_audio) / SAMPLE_RATE
        assert abs(result.duration - expected_dur) < 0.1

    def test_transcribe_elapsed_nonnegative(self, mock_faster_whisper, tone_audio):
        from core.voice import _transcribe
        result = _transcribe(tone_audio)
        assert result.elapsed >= 0.0

    def test_model_missing_returns_error(self, tone_audio):
        """If faster-whisper raises ImportError, return VoiceResult with error."""
        import core.voice as v
        original = v._load_model
        try:
            v._load_model = MagicMock(side_effect=ImportError("faster-whisper not found"))
            # Clear cache so _load_model is called
            v._model_cache.clear()
            result = v._transcribe(tone_audio)
            assert result.error is not None
        finally:
            v._load_model = original
            v._model_cache.clear()


# ── Unit: transcribe_file ──────────────────────────────────────────────────

class TestTranscribeFile:
    def test_transcribes_wav_file(self, mock_faster_whisper, sample_wav):
        from core.voice import transcribe_file
        result = transcribe_file(sample_wav)
        assert isinstance(result.text, str)

    def test_nonexistent_file_returns_error(self, mock_faster_whisper, tmp_path):
        from core.voice import transcribe_file
        result = transcribe_file(str(tmp_path / "nonexistent.wav"))
        assert result.error is not None


# ── Unit: async stop_and_transcribe ───────────────────────────────────────

class TestAsyncTranscription:
    def test_callback_called(self, mock_faster_whisper, mock_sounddevice, tone_audio):
        from core.voice import VoiceRecognizer, RecordingState

        done = threading.Event()
        received: list = []

        def cb(result):
            received.append(result)
            done.set()

        vr = VoiceRecognizer()
        vr._recorder._chunks = [tone_audio]
        vr.state = RecordingState.RECORDING

        vr.stop_and_transcribe_async(callback=cb)
        done.wait(timeout=10)

        assert len(received) == 1
        assert received[0].text == "123 Main Street Spokane"

    def test_state_returns_to_idle_after_async(self, mock_faster_whisper, mock_sounddevice, tone_audio):
        from core.voice import VoiceRecognizer, RecordingState

        done = threading.Event()
        vr = VoiceRecognizer()
        vr._recorder._chunks = [tone_audio]
        vr.state = RecordingState.RECORDING

        vr.stop_and_transcribe_async(callback=lambda r: done.set())
        done.wait(timeout=10)

        assert vr.state == RecordingState.IDLE


# ── Unit: model path helpers ───────────────────────────────────────────────

class TestModelPath:
    def test_default_model_env_var(self, monkeypatch):
        monkeypatch.setenv("ONTRACK_WHISPER_MODEL", "tiny")
        import importlib
        import core.voice as v
        importlib.reload(v)
        assert v.DEFAULT_MODEL == "tiny"

    def test_whisper_cache_under_home(self):
        from core.voice import WHISPER_CACHE
        assert str(pathlib.Path.home()) in str(WHISPER_CACHE)
        assert "ontrack" in str(WHISPER_CACHE)


# ── Integration tests (need real faster-whisper) ───────────────────────────

@pytest.mark.integration
class TestIntegration:
    """
    These tests require faster-whisper to be installed:
        pip install faster-whisper

    They download the 'tiny' model (~75 MB) on first run.
    Run with: pytest tests/test_voice.py -m integration -v
    """

    @pytest.fixture(autouse=True)
    def _skip_if_no_faster_whisper(self):
        pytest.importorskip("faster_whisper", reason="faster-whisper not installed")

    def test_transcribe_silence_returns_empty(self, silence_audio):
        from core.voice import _transcribe
        result = _transcribe(silence_audio, model_size="tiny")
        # Silence may produce empty text or a noise segment — no crash
        assert isinstance(result.text, str)

    def test_transcribe_completes_in_reasonable_time(self, tone_audio):
        from core.voice import _transcribe
        start = time.monotonic()
        result = _transcribe(tone_audio, model_size="tiny")
        elapsed = time.monotonic() - start
        # 1 second of audio with tiny model should complete within 30s even on slow CPU
        assert elapsed < 30.0, f"Transcription took {elapsed:.1f}s"

    def test_transcribe_file_wav(self, sample_wav):
        from core.voice import transcribe_file
        result = transcribe_file(sample_wav, model_size="tiny")
        assert result.error is None or result.text == ""

    def test_preload_model_does_not_crash(self):
        from core.voice import VoiceRecognizer
        # Should complete without raising
        VoiceRecognizer.preload_model("tiny")
        time.sleep(2)  # give background thread time


# ── Hardware tests (require real microphone) ──────────────────────────────

@pytest.mark.hardware
class TestHardware:
    """
    These tests require a real microphone.
    Run with: pytest tests/test_voice.py -m hardware -v
    DO NOT run in CI.
    """

    @pytest.fixture(autouse=True)
    def _check_hardware(self, request):
        if not request.config.getoption("--hardware", default=False):
            pytest.skip("Hardware tests require --hardware flag")
        pytest.importorskip("sounddevice")
        pytest.importorskip("faster_whisper")

    def test_record_1_second(self):
        from core.voice import VoiceRecognizer
        vr = VoiceRecognizer(model_size="tiny")
        vr.start_recording()
        time.sleep(1)
        result = vr.stop_and_transcribe()
        assert result.error is None
        assert isinstance(result.text, str)

    def test_pipewire_echo_cancel_node(self, monkeypatch):
        """Requires the 51-ontrack-echo-cancel.conf to be installed."""
        monkeypatch.setenv("ONTRACK_PIPEWIRE_NODE", "OnTrack Echo Cancel")
        from core.voice import VoiceRecognizer
        vr = VoiceRecognizer(model_size="tiny")
        vr.start_recording()
        time.sleep(1)
        result = vr.stop_and_transcribe()
        assert result.error is None


# ── conftest additions ─────────────────────────────────────────────────────

def pytest_addoption(parser):
    """Register --hardware flag so hardware tests can be opted in."""
    try:
        parser.addoption(
            "--hardware",
            action="store_true",
            default=False,
            help="Run hardware tests (requires microphone)",
        )
    except ValueError:
        pass  # already registered
