"""
core/voice.py — Cross-platform voice capture and transcription for OnTrack.

Audio capture backend selection (automatic, in priority order):
  Linux    → sounddevice via PipeWire-ALSA or PipeWire-pulse (managed by
              WirePlumber). If ONTRACK_PIPEWIRE_NODE is set, that node is used
              as the capture source; otherwise the system default is used.
  Windows  → sounddevice via WASAPI
  macOS    → sounddevice via CoreAudio
  Android  → android.media.AudioRecord via plyer (Kivy apps)
  iOS      → AVAudioEngine via objc bridge (future; currently uses CoreAudio)

Transcription engine:
  faster-whisper (CTranslate2 backend) — fully offline, no API key.
  Model is downloaded once to ~/.cache/ontrack/whisper/ on first use.

  Model size tradeoffs:
    tiny    —  39M params,  ~1s/min audio,  WER ~12%   (fast, low RAM)
    base    —  74M params,  ~1s/min audio,  WER ~9%    (good default)
    small   — 244M params,  ~2s/min audio,  WER ~6%    (recommended)
    medium  — 769M params,  ~5s/min audio,  WER ~5%
    large-v3— 1550M params, ~10s/min audio, WER ~4%    (best quality)

Usage:
    from core.voice import VoiceRecognizer, RecordingState

    vr = VoiceRecognizer()          # loads model lazily on first use
    vr.start_recording()            # begin capturing mic audio
    # ... user speaks ...
    text = vr.stop_and_transcribe() # stop capture, return transcript string

    # Async usage (recommended for GUI):
    vr.start_recording()
    vr.stop_and_transcribe_async(callback=lambda text, err: ...)
"""

from __future__ import annotations

import os
import sys
import time
import queue
import threading
import platform
import pathlib
import tempfile
import wave
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

import numpy as np

# ── Constants ──────────────────────────────────────────────────────────────

SAMPLE_RATE    = 16_000   # Whisper expects 16 kHz mono
CHANNELS       = 1
SAMPLE_WIDTH   = 2        # int16 = 2 bytes
CHUNK_FRAMES   = 1024     # frames per sounddevice callback (~64ms at 16kHz)
SILENCE_THRESH = 0.01     # RMS below this → silence
SILENCE_PAD_S  = 0.6      # seconds of silence to keep after speech ends
MAX_RECORD_S   = 60       # hard cap on recording length

WHISPER_CACHE  = pathlib.Path.home() / ".cache" / "ontrack" / "whisper"
DEFAULT_MODEL  = os.getenv("ONTRACK_WHISPER_MODEL", "base")

# ── Platform detection ─────────────────────────────────────────────────────

_PLATFORM = platform.system()  # "Linux", "Windows", "Darwin"
try:
    import android  # type: ignore
    _PLATFORM = "Android"
except ImportError:
    pass

# ── State ──────────────────────────────────────────────────────────────────

class RecordingState(Enum):
    IDLE        = auto()
    RECORDING   = auto()
    PROCESSING  = auto()
    ERROR       = auto()

@dataclass
class VoiceResult:
    text:     str
    language: str
    duration: float   # seconds of audio transcribed
    elapsed:  float   # wall-clock seconds for transcription
    error:    Optional[str] = None

    def __bool__(self):
        return self.error is None and bool(self.text.strip())

# ── Model management ───────────────────────────────────────────────────────

_model_lock   = threading.Lock()
_model_cache: dict[str, object] = {}

def _load_model(model_size: str = DEFAULT_MODEL):
    """
    Load (or return cached) a faster-whisper model.
    Downloads automatically on first use (~150MB for 'base').
    """
    with _model_lock:
        if model_size in _model_cache:
            return _model_cache[model_size]

        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as e:
            raise ImportError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            ) from e

        WHISPER_CACHE.mkdir(parents=True, exist_ok=True)

        # Device selection: GPU if available, else CPU
        try:
            import torch  # type: ignore
            device    = "cuda" if torch.cuda.is_available() else "cpu"
            compute   = "float16" if device == "cuda" else "int8"
        except ImportError:
            device, compute = "cpu", "int8"

        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute,
            download_root=str(WHISPER_CACHE),
        )
        _model_cache[model_size] = model
        return model

# ── Audio capture — desktop (sounddevice) ─────────────────────────────────

def _get_sounddevice_device() -> Optional[int]:
    """
    Return the sounddevice device index to use for capture.

    On Linux with PipeWire:
      - If ONTRACK_PIPEWIRE_NODE is set, find the device matching that name.
        This lets WirePlumber route through its echo-cancel virtual source.
      - Otherwise use the system default (PipeWire's default source).
    """
    node_name = os.getenv("ONTRACK_PIPEWIRE_NODE", "")
    if not node_name:
        return None  # use default

    try:
        import sounddevice as sd  # type: ignore
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if node_name.lower() in dev["name"].lower() and dev["max_input_channels"] > 0:
                return i
    except Exception:
        pass
    return None


class _DesktopRecorder:
    """
    Captures microphone audio using sounddevice.
    Works on Linux (PipeWire-ALSA/PipeWire-pulse), Windows (WASAPI),
    macOS (CoreAudio).
    """

    def __init__(self):
        self._q: queue.Queue[np.ndarray] = queue.Queue()
        self._stream  = None
        self._chunks:  list[np.ndarray] = []
        self._running = False

    def start(self):
        import sounddevice as sd  # type: ignore

        device_idx = _get_sounddevice_device()
        self._chunks.clear()
        self._running = True

        def _cb(indata, frames, time_info, status):
            if self._running:
                self._q.put(indata.copy())

        self._stream = sd.InputStream(
            samplerate  = SAMPLE_RATE,
            channels    = CHANNELS,
            dtype       = "int16",
            blocksize   = CHUNK_FRAMES,
            device      = device_idx,
            callback    = _cb,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Drain the queue
        while not self._q.empty():
            try:
                self._chunks.append(self._q.get_nowait())
            except queue.Empty:
                break

        if not self._chunks:
            return np.zeros(0, dtype=np.int16)

        audio = np.concatenate(self._chunks, axis=0).flatten()
        return audio

    @staticmethod
    def list_devices() -> list[dict]:
        try:
            import sounddevice as sd  # type: ignore
            devs = sd.query_devices()
            return [
                {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
                for i, d in enumerate(devs)
                if d["max_input_channels"] > 0
            ]
        except Exception:
            return []


# ── Audio capture — Android ────────────────────────────────────────────────

class _AndroidRecorder:
    """
    Captures microphone audio on Android using AudioRecord via Pyjnius.
    Requires RECORD_AUDIO permission (declared in buildozer.spec).
    """

    def __init__(self):
        self._chunks: list[bytes] = []
        self._running = False
        self._thread:  Optional[threading.Thread] = None

    def start(self):
        from jnius import autoclass  # type: ignore
        from android.permissions import request_permissions, Permission  # type: ignore

        request_permissions([Permission.RECORD_AUDIO])

        AudioRecord    = autoclass("android.media.AudioRecord")
        AudioFormat    = autoclass("android.media.AudioFormat")
        AudioSource    = autoclass("android.media.MediaRecorder$AudioSource")

        buf_size = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        ) * 4

        self._ar = AudioRecord(
            AudioSource.MIC,
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            buf_size,
        )
        self._buf_size = buf_size
        self._chunks.clear()
        self._running = True
        self._ar.startRecording()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self):
        from jnius import autoclass  # type: ignore
        import jarray  # type: ignore
        buf = jarray.array("b", [0] * self._buf_size)
        while self._running:
            n = self._ar.read(buf, 0, self._buf_size)
            if n > 0:
                self._chunks.append(bytes(buf[:n]))

    def stop(self) -> np.ndarray:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._ar.stop()
        self._ar.release()

        if not self._chunks:
            return np.zeros(0, dtype=np.int16)
        raw = b"".join(self._chunks)
        return np.frombuffer(raw, dtype=np.int16)

    @staticmethod
    def list_devices() -> list[dict]:
        return [{"index": 0, "name": "Android Microphone", "channels": 1}]


# ── Transcription ──────────────────────────────────────────────────────────

def _transcribe(
    audio: np.ndarray,
    model_size: str = DEFAULT_MODEL,
    language: Optional[str] = None,
) -> VoiceResult:
    """
    Transcribe a numpy int16 PCM array using faster-whisper.
    Returns a VoiceResult.
    """
    if audio.size == 0:
        return VoiceResult(text="", language="", duration=0.0, elapsed=0.0,
                           error="No audio recorded.")

    duration = len(audio) / SAMPLE_RATE
    t0 = time.monotonic()

    try:
        model = _load_model(model_size)
        # faster-whisper expects float32 in [-1, 1]
        audio_f32 = audio.astype(np.float32) / 32768.0

        segments, info = model.transcribe(
            audio_f32,
            language    = language,
            beam_size   = 5,
            vad_filter  = True,              # skip silence automatically
            vad_parameters = {
                "min_silence_duration_ms": 300,
                "speech_pad_ms": 200,
            },
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()
        elapsed = time.monotonic() - t0

        return VoiceResult(
            text     = text,
            language = info.language,
            duration = duration,
            elapsed  = elapsed,
        )

    except Exception as e:
        return VoiceResult(
            text="", language="", duration=duration,
            elapsed=time.monotonic() - t0,
            error=str(e),
        )


# ── Public API ─────────────────────────────────────────────────────────────

class VoiceRecognizer:
    """
    High-level voice recognition interface for OnTrack.

    Thread-safe. The recording happens on the calling thread's sounddevice
    stream; transcription runs on a background thread to keep UI responsive.

    Example (blocking):
        vr = VoiceRecognizer()
        vr.start_recording()
        time.sleep(3)
        result = vr.stop_and_transcribe()
        print(result.text)

    Example (non-blocking callback):
        def on_done(result: VoiceResult):
            print(result.text)
        vr.start_recording()
        time.sleep(3)
        vr.stop_and_transcribe_async(on_done)
    """

    def __init__(
        self,
        model_size:  str = DEFAULT_MODEL,
        language:    Optional[str] = None,
        max_seconds: float = MAX_RECORD_S,
    ):
        self.model_size  = model_size
        self.language    = language
        self.max_seconds = max_seconds
        self.state       = RecordingState.IDLE

        # Choose recorder based on platform
        if _PLATFORM == "Android":
            self._recorder = _AndroidRecorder()
        else:
            self._recorder = _DesktopRecorder()

        self._audio: Optional[np.ndarray] = None
        self._auto_stop_timer: Optional[threading.Timer] = None

    def start_recording(self):
        """Begin capturing microphone audio."""
        if self.state == RecordingState.RECORDING:
            return

        self.state  = RecordingState.RECORDING
        self._audio = None
        self._recorder.start()

        # Auto-stop after max_seconds
        self._auto_stop_timer = threading.Timer(
            self.max_seconds, self._auto_stop
        )
        self._auto_stop_timer.daemon = True
        self._auto_stop_timer.start()

    def stop_and_transcribe(self) -> VoiceResult:
        """
        Stop recording and block until transcription completes.
        Returns a VoiceResult.
        """
        if self.state != RecordingState.RECORDING:
            return VoiceResult(text="", language="", duration=0.0, elapsed=0.0,
                               error="Not currently recording.")

        self._cancel_auto_stop()
        audio = self._recorder.stop()
        self.state  = RecordingState.PROCESSING
        result = _transcribe(audio, self.model_size, self.language)
        self.state  = RecordingState.IDLE
        return result

    def stop_and_transcribe_async(
        self,
        callback: Callable[[VoiceResult], None],
    ):
        """
        Stop recording; run transcription on a background thread.
        `callback(result)` is called when transcription completes.
        """
        if self.state != RecordingState.RECORDING:
            callback(VoiceResult(text="", language="", duration=0.0, elapsed=0.0,
                                 error="Not currently recording."))
            return

        self._cancel_auto_stop()
        audio = self._recorder.stop()
        self.state = RecordingState.PROCESSING

        def _worker():
            result = _transcribe(audio, self.model_size, self.language)
            self.state = RecordingState.IDLE
            callback(result)

        threading.Thread(target=_worker, daemon=True).start()

    def is_recording(self) -> bool:
        return self.state == RecordingState.RECORDING

    def is_processing(self) -> bool:
        return self.state == RecordingState.PROCESSING

    @staticmethod
    def list_input_devices() -> list[dict]:
        """List available audio input devices."""
        if _PLATFORM == "Android":
            return _AndroidRecorder.list_devices()
        return _DesktopRecorder.list_devices()

    @staticmethod
    def preload_model(model_size: str = DEFAULT_MODEL):
        """
        Download and cache the Whisper model in a background thread.
        Call this at app startup to avoid delay on first transcription.
        """
        def _load():
            try:
                _load_model(model_size)
            except Exception:
                pass
        threading.Thread(target=_load, daemon=True).start()

    def _auto_stop(self):
        if self.state == RecordingState.RECORDING:
            self._recorder.stop()
            self.state = RecordingState.IDLE

    def _cancel_auto_stop(self):
        if self._auto_stop_timer:
            self._auto_stop_timer.cancel()
            self._auto_stop_timer = None


# ── Convenience: one-shot transcribe from file ─────────────────────────────

def transcribe_file(
    path: str,
    model_size: str = DEFAULT_MODEL,
    language: Optional[str] = None,
) -> VoiceResult:
    """Transcribe a WAV/MP3/etc. audio file and return a VoiceResult."""
    try:
        try:
            import soundfile as sf  # type: ignore
            audio, sr = sf.read(path, dtype="int16", always_2d=False)
            if sr != SAMPLE_RATE:
                import scipy.signal as sps  # type: ignore
                num = int(len(audio) * SAMPLE_RATE / sr)
                audio = sps.resample(audio.astype(np.float32), num).astype(np.int16)
        except ImportError:
            # Fallback: read raw WAV with stdlib
            with wave.open(path, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16)
    except Exception as e:
        return VoiceResult(text="", language="", duration=0.0, elapsed=0.0,
                           error=str(e))

    return _transcribe(audio, model_size, language)
