"""
mobile/screens/voice.py — Voice input screen for the Kivy Android app.

Reached from the home screen via a mic button.
Records audio, transcribes with Whisper (faster-whisper on device),
then passes the text back to the home screen's address entry.
"""

from __future__ import annotations
import threading

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.utils import get_color_from_hex
from kivy.metrics import dp

C_BG      = get_color_from_hex("#111827ff")
C_SURFACE = get_color_from_hex("#1A2535ff")
C_CARD    = get_color_from_hex("#243044ff")
C_BLUE    = get_color_from_hex("#0057A8ff")
C_NAVY    = get_color_from_hex("#002855ff")
C_ORANGE  = get_color_from_hex("#F26522ff")
C_WHITE   = get_color_from_hex("#FFFFFFff")
C_GRAY    = get_color_from_hex("#6B7280ff")
C_RED     = get_color_from_hex("#EF4444ff")
C_GREEN   = get_color_from_hex("#22C55Eff")


class VoiceScreen(Screen):
    """
    Full-screen voice input:
      - Large mic button (tap to start, tap to stop)
      - Animated waveform indicator while recording
      - Transcription result display
      - Confirm / Re-try / Cancel buttons
    """

    def __init__(self, on_result=None, **kw):
        super().__init__(**kw)
        self._on_result = on_result   # callback(text: str)
        self._recognizer = None
        self._build()

    def on_enter(self):
        # Lazy-import to avoid loading whisper at app start
        from core.voice import VoiceRecognizer, RecordingState
        if self._recognizer is None:
            self._recognizer = VoiceRecognizer(model_size="base")
            VoiceRecognizer.preload_model("base")

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=dp(12),
                         padding=[dp(16), dp(12)])

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        back = Button(text="← Back",
                      background_color=C_NAVY, color=C_WHITE,
                      size_hint_x=None, width=dp(80),
                      size_hint_y=None, height=dp(42))
        back.bind(on_release=lambda *_: self._cancel())
        header.add_widget(back)
        header.add_widget(Label(
            text="[b]Voice Input[/b]", markup=True,
            color=C_WHITE, font_size=dp(18)
        ))
        root.add_widget(header)

        # Instruction
        self.instruction_lbl = Label(
            text="Tap the mic and say an address",
            color=C_GRAY, font_size=dp(14),
            size_hint_y=None, height=dp(30),
        )
        root.add_widget(self.instruction_lbl)

        # Big mic button
        self.mic_btn = Button(
            text="🎤",
            font_size=dp(64),
            background_color=C_SURFACE,
            color=C_WHITE,
            size_hint=(None, None),
            size=(dp(160), dp(160)),
        )
        self.mic_btn.pos_hint = {"center_x": 0.5}
        self.mic_btn.bind(on_release=lambda *_: self._toggle_recording())

        mic_wrapper = BoxLayout(size_hint=(1, None), height=dp(180))
        mic_wrapper.add_widget(self.mic_btn)
        root.add_widget(mic_wrapper)

        # Status / waveform label
        self.status_lbl = Label(
            text="",
            color=C_GRAY, font_size=dp(14),
            size_hint_y=None, height=dp(32),
        )
        root.add_widget(self.status_lbl)

        # Progress bar (shown during transcription)
        self.progress = ProgressBar(
            max=100, value=0,
            size_hint_y=None, height=dp(6),
        )
        root.add_widget(self.progress)

        # Result box
        self.result_lbl = Label(
            text="",
            color=C_WHITE, font_size=dp(16),
            text_size=(dp(320), None),
            halign="center",
            size_hint_y=None, height=dp(80),
        )
        root.add_widget(self.result_lbl)

        # Action buttons (hidden until result ready)
        self.action_row = BoxLayout(
            size_hint_y=None, height=dp(48), spacing=dp(10),
            opacity=0,
        )
        confirm_btn = Button(text="✓ Use This Address",
                             background_color=C_GREEN, color=C_WHITE)
        confirm_btn.bind(on_release=lambda *_: self._confirm())
        retry_btn = Button(text="↩ Retry",
                           background_color=C_NAVY, color=C_WHITE,
                           size_hint_x=None, width=dp(90))
        retry_btn.bind(on_release=lambda *_: self._retry())
        self.action_row.add_widget(confirm_btn)
        self.action_row.add_widget(retry_btn)
        root.add_widget(self.action_row)

        self.add_widget(root)

    # ── Recording control ──────────────────────────────────────────────────

    def _toggle_recording(self):
        from core.voice import RecordingState
        state = self._recognizer.state
        if state == RecordingState.IDLE:
            self._start()
        elif state == RecordingState.RECORDING:
            self._stop()

    def _start(self):
        self.result_lbl.text = ""
        self.action_row.opacity = 0
        self.status_lbl.text = "● Listening…"
        self.mic_btn.background_color = C_RED
        self._recognizer.start_recording()
        self._blink_event = Clock.schedule_interval(self._blink, 0.5)

    def _stop(self):
        if hasattr(self, "_blink_event"):
            self._blink_event.cancel()
        self.mic_btn.background_color = C_SURFACE
        self.status_lbl.text = "Transcribing…"
        self.progress.value = 10

        self._recognizer.stop_and_transcribe_async(
            callback=lambda r: Clock.schedule_once(lambda dt: self._on_done(r))
        )

    def _on_done(self, result):
        self.progress.value = 100
        if result.error:
            self.status_lbl.text = f"Error: {result.error[:60]}"
            self.progress.value = 0
        elif result.text.strip():
            self.result_lbl.text = result.text.strip()
            self.status_lbl.text = f"Language: {result.language}  ·  {result.duration:.1f}s audio"
            self.action_row.opacity = 1
        else:
            self.status_lbl.text = "No speech detected — try again."
            self.progress.value = 0

    def _blink(self, dt):
        if "●" in self.status_lbl.text:
            self.status_lbl.text = "○ Listening…"
        else:
            self.status_lbl.text = "● Listening…"

    # ── Action buttons ─────────────────────────────────────────────────────

    def _confirm(self):
        text = self.result_lbl.text.strip()
        if text and self._on_result:
            self._on_result(text)
        App.get_running_app().navigate("home", "right")

    def _retry(self):
        self.result_lbl.text = ""
        self.action_row.opacity = 0
        self.status_lbl.text = "Tap the mic to try again."
        self.progress.value = 0
        self.mic_btn.background_color = C_SURFACE

    def _cancel(self):
        App.get_running_app().navigate("home", "right")
